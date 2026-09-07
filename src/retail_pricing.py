"""Azure Retail Prices API integration for model token pricing."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import PricingConfig


_API_URL = "https://prices.azure.com/api/retail/prices"
_EXCLUDED_METER_TERMS = (
    " batch ",
    " cchd ",
    " cached ",
    " prty ",
    " priority ",
    " dzone ",
    " dz ",
    " regional ",
    " fine tuning ",
    " ft ",
    " grader ",
    " cd ",
    " wr ",
    " audio ",
    " image ",
    " realtime ",
)
_INPUT_PATTERN = re.compile(r"\b(inp|inpt|input)\b", re.IGNORECASE)
_OUTPUT_PATTERN = re.compile(r"\b(out|outpt|output|opt)\b", re.IGNORECASE)


def _fetch_json(url: str, timeout_seconds: int) -> Dict[str, Any]:
    request = Request(url, headers={"User-Agent": "model-router-auto-evaluation/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.load(response)


def _query_meter_items(
    search_term: str,
    currency: str,
    timeout_seconds: int,
    region: Optional[str] = None,
) -> list[Dict[str, Any]]:
    escaped_search = search_term.replace("'", "''")
    filter_value = (
        f"contains(meterName, '{escaped_search}') "
        "and serviceName eq 'Foundry Models' "
        "and priceType eq 'Consumption'"
    )
    if region:
        escaped_region = region.replace("'", "''")
        filter_value += f" and armRegionName eq '{escaped_region}'"
    query = urlencode({"currencyCode": currency, "$filter": filter_value})
    next_url: Optional[str] = f"{_API_URL}?{query}"
    items: list[Dict[str, Any]] = []

    while next_url:
        payload = _fetch_json(next_url, timeout_seconds)
        items.extend(payload.get("Items", []))
        next_url = payload.get("NextPageLink")

    return items


def _is_global_standard_meter(item: Dict[str, Any]) -> bool:
    meter = f" {item.get('meterName', '').lower()} "
    if item.get("type") != "Consumption" or item.get("unitOfMeasure") != "1M":
        return False
    if any(term in meter for term in _EXCLUDED_METER_TERMS):
        return False
    return " gl " in meter or " glbl " in meter or " global " in meter


def _matches_model_spec(
    item: Dict[str, Any],
    required_terms: Iterable[str],
    excluded_terms: Iterable[str],
) -> bool:
    meter = item.get("meterName", "").lower()
    return (
        all(term.lower() in meter for term in required_terms)
        and not any(term.lower() in meter for term in excluded_terms)
    )


def _select_price(
    items: Iterable[Dict[str, Any]],
    direction: str,
    required_terms: Iterable[str] = (),
    excluded_terms: Iterable[str] = (),
) -> Optional[float]:
    pattern = _INPUT_PATTERN if direction == "input" else _OUTPUT_PATTERN
    now = datetime.now(timezone.utc)
    candidates: list[tuple[datetime, float]] = []

    for item in items:
        if not _is_global_standard_meter(item):
            continue
        if not _matches_model_spec(item, required_terms, excluded_terms):
            continue
        meter_name = item.get("meterName", "")
        if not pattern.search(meter_name):
            continue
        effective = item.get("effectiveStartDate")
        effective_date = (
            datetime.fromisoformat(effective.replace("Z", "+00:00"))
            if effective
            else datetime.min.replace(tzinfo=timezone.utc)
        )
        if effective_date > now:
            continue
        price = item.get("retailPrice")
        if price is not None:
            candidates.append((effective_date, float(price)))

    if not candidates:
        return None

    latest_effective = max(effective for effective, _ in candidates)
    unique_prices = {
        price for effective, price in candidates if effective == latest_effective
    }
    return unique_prices.pop() if len(unique_prices) == 1 else None


def _load_cache(cache_path: Path, ttl_hours: int) -> Dict[str, Any]:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, json.JSONDecodeError):
        return {}

    age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
    return payload if age_hours <= ttl_hours else {}


def resolve_azure_retail_prices(
    pricing: Dict[str, PricingConfig],
    settings: Dict[str, Any],
    project_root: Path,
) -> Dict[str, PricingConfig]:
    """Overlay configured prices with current Azure retail token prices.

    Unresolved or unavailable meters retain their YAML-configured fallback.
    """
    if not settings.get("enabled", False):
        return pricing

    model_searches = settings.get("models", {})
    if not isinstance(model_searches, dict) or not model_searches:
        raise ValueError("pricing_source.azure_retail.models must be a non-empty mapping")

    currency = str(settings.get("currency", "USD"))
    timeout_seconds = int(settings.get("timeout_seconds", 20))
    region = settings.get("region")
    ttl_hours = int(settings.get("cache_ttl_hours", 24))
    cache_path = project_root / settings.get(
        "cache_file", ".cache/azure-retail-prices.json"
    )
    cached = _load_cache(cache_path, ttl_hours)
    if cached and (
        cached.get("currency") != currency
        or cached.get("region") != region
        or cached.get("models") != model_searches
    ):
        cached = {}
    resolved_data = cached.get("prices", {}) if cached else {}
    refreshed = not bool(cached)

    if refreshed:
        resolved_data = {}
        for model_name, model_spec in model_searches.items():
            if isinstance(model_spec, str):
                search_term = model_spec
                required_terms: list[str] = []
                excluded_terms: list[str] = []
            elif isinstance(model_spec, dict):
                search_term = model_spec.get("search")
                required_terms = list(model_spec.get("required_terms", []))
                excluded_terms = list(model_spec.get("excluded_terms", []))
            else:
                raise ValueError(
                    f"Azure retail model mapping for '{model_name}' must be a string or mapping"
                )
            if not search_term:
                raise ValueError(
                    f"Azure retail model mapping for '{model_name}' requires a search term"
                )
            try:
                items = _query_meter_items(
                    str(search_term), currency, timeout_seconds, region
                )
                input_price = _select_price(
                    items, "input", required_terms, excluded_terms
                )
                output_price = _select_price(
                    items, "output", required_terms, excluded_terms
                )
                if input_price is not None and output_price is not None:
                    resolved_data[model_name] = {
                        "input": input_price,
                        "output": output_price,
                        "search_term": search_term,
                    }
                else:
                    print(
                        f"Warning: Azure Retail Prices API did not return an unambiguous "
                        f"global-standard input/output pair for '{model_name}'. "
                        "Using YAML fallback if available."
                    )
            except Exception as exc:
                print(
                    f"Warning: Azure Retail Prices API lookup failed for '{model_name}': "
                    f"{exc}. Using YAML fallback if available."
                )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "currency": currency,
                    "region": region,
                    "models": model_searches,
                    "prices": resolved_data,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    merged = dict(pricing)
    for model_name, values in resolved_data.items():
        merged[model_name] = PricingConfig(
            input=float(values["input"]),
            output=float(values["output"]),
        )

    source = "Azure Retail Prices API" if refreshed else f"cache {cache_path}"
    print(f"Pricing: resolved {len(resolved_data)} model(s) from {source}; YAML is fallback.")
    return merged
