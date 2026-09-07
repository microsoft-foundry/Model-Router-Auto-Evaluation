"""Tests for Azure Retail Prices API integration."""

from __future__ import annotations

import json

from src.config import PricingConfig
from src.retail_pricing import resolve_azure_retail_prices


def _meter(name: str, price: float) -> dict:
    return {
        "meterName": name,
        "retailPrice": price,
        "unitOfMeasure": "1M",
        "type": "Consumption",
        "effectiveStartDate": "2025-01-01T00:00:00Z",
    }


def test_refreshes_unambiguous_global_standard_prices(tmp_path, monkeypatch):
    payload = {
        "Items": [
            _meter("GPT 5 Mini inp Gl 1M Tokens", 0.25),
            _meter("GPT 5 Mini outpt Glbl 1M Tokens", 2.0),
            _meter("GPT 5 Mini Batch Inpt Glbl 1M Tokens", 0.125),
        ],
        "NextPageLink": None,
    }
    monkeypatch.setattr(
        "src.retail_pricing._fetch_json",
        lambda url, timeout_seconds: payload,
    )
    fallback = {"gpt-5-mini": PricingConfig(input=9.0, output=9.0)}
    settings = {
        "enabled": True,
        "models": {"gpt-5-mini": "GPT 5 Mini"},
        "cache_file": ".cache/prices.json",
    }

    result = resolve_azure_retail_prices(fallback, settings, tmp_path)

    assert result["gpt-5-mini"] == PricingConfig(input=0.25, output=2.0)
    cache = json.loads((tmp_path / ".cache" / "prices.json").read_text())
    assert cache["prices"]["gpt-5-mini"]["input"] == 0.25


def test_uses_yaml_fallback_when_meter_is_ambiguous(tmp_path, monkeypatch):
    payload = {
        "Items": [_meter("GPT 5 Mini Batch Inpt Glbl 1M Tokens", 0.125)],
        "NextPageLink": None,
    }
    monkeypatch.setattr(
        "src.retail_pricing._fetch_json",
        lambda url, timeout_seconds: payload,
    )
    fallback = {"gpt-5-mini": PricingConfig(input=0.3, output=2.1)}
    settings = {
        "enabled": True,
        "models": {"gpt-5-mini": "GPT 5 Mini"},
        "cache_file": ".cache/prices.json",
    }

    result = resolve_azure_retail_prices(fallback, settings, tmp_path)

    assert result["gpt-5-mini"] == fallback["gpt-5-mini"]


def test_model_terms_disambiguate_variants(tmp_path, monkeypatch):
    payload = {
        "Items": [
            _meter("5.4 inp Gl 1M Tokens", 2.5),
            _meter("5.4 opt Gl 1M Tokens", 15.0),
            _meter("5.4 pro inp Gl 1M Tokens", 20.0),
            _meter("5.4 pro opt Gl 1M Tokens", 180.0),
        ],
        "NextPageLink": None,
    }
    monkeypatch.setattr(
        "src.retail_pricing._fetch_json",
        lambda url, timeout_seconds: payload,
    )
    settings = {
        "enabled": True,
        "models": {
            "gpt-5.4": {
                "search": "5.4",
                "excluded_terms": ["pro"],
            }
        },
        "cache_file": ".cache/prices.json",
    }

    result = resolve_azure_retail_prices({}, settings, tmp_path)

    assert result["gpt-5.4"] == PricingConfig(input=2.5, output=15.0)


def test_uses_fresh_cache_without_network(tmp_path, monkeypatch):
    cache_path = tmp_path / ".cache" / "prices.json"
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": "2099-01-01T00:00:00+00:00",
                "currency": "USD",
                "region": None,
                "models": {"gpt-5-mini": "GPT 5 Mini"},
                "prices": {
                    "gpt-5-mini": {
                        "input": 0.25,
                        "output": 2.0,
                        "search_term": "GPT 5 Mini",
                    }
                },
            }
        )
    )
    monkeypatch.setattr(
        "src.retail_pricing._fetch_json",
        lambda url, timeout_seconds: (_ for _ in ()).throw(AssertionError("network called")),
    )
    settings = {
        "enabled": True,
        "models": {"gpt-5-mini": "GPT 5 Mini"},
        "cache_file": ".cache/prices.json",
    }

    result = resolve_azure_retail_prices({}, settings, tmp_path)

    assert result["gpt-5-mini"] == PricingConfig(input=0.25, output=2.0)
