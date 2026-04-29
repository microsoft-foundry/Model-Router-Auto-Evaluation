"""Transform raw evaluation results into Foundry-compatible JSONL.

Reads the original project's raw_results.jsonl (one line per completion) and
results.json (aggregated metrics with cost data), pairs router + baseline
results by prompt_id, and produces a single JSONL where each line has both
sides for Foundry graders to evaluate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file into a dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_pricing(results: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Extract per-token pricing from results.json cost sections.

    Returns a dict mapping endpoint key ("model_router" | "baseline") to
    {"cost_per_prompt_token": float, "cost_per_completion_token": float}
    computed from aggregated totals.
    """
    pricing: Dict[str, Dict[str, float]] = {}
    for key in ("model_router", "baseline"):
        section = results.get(key, {})
        cost = section.get("cost", {})
        total_cost = cost.get("estimated_cost_usd", 0.0)
        prompt_tokens = cost.get("total_prompt_tokens", 0)
        completion_tokens = cost.get("total_completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens > 0 and total_cost > 0:
            # Distribute cost proportionally by token count
            cost_per_token = total_cost / total_tokens
            pricing[key] = {
                "cost_per_prompt_token": cost_per_token,
                "cost_per_completion_token": cost_per_token,
            }
        else:
            pricing[key] = {
                "cost_per_prompt_token": 0.0,
                "cost_per_completion_token": 0.0,
            }
    return pricing


def _estimate_cost(
    record: Dict[str, Any],
    pricing: Dict[str, float],
) -> float:
    """Estimate USD cost for a single completion record."""
    prompt_tokens = record.get("prompt_tokens", 0)
    completion_tokens = record.get("completion_tokens", 0)
    return (
        prompt_tokens * pricing["cost_per_prompt_token"]
        + completion_tokens * pricing["cost_per_completion_token"]
    )


def transform(
    raw_results_path: Path,
    results_json_path: Path,
    output_path: Path,
) -> int:
    """Transform raw results into Foundry-compatible JSONL.

    Args:
        raw_results_path: Path to raw_results.jsonl from the original eval.
        results_json_path: Path to results.json with aggregated metrics.
        output_path: Where to write the Foundry input JSONL.

    Returns:
        Number of paired records written.
    """
    records = _load_jsonl(raw_results_path)
    results = _load_json(results_json_path)
    pricing = _extract_pricing(results)

    # Group by prompt_id
    router_by_prompt: Dict[str, Dict[str, Any]] = {}
    baseline_by_prompt: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        pid = rec.get("prompt_id", "")
        endpoint = rec.get("endpoint", "")
        if endpoint == "model_router":
            router_by_prompt[pid] = rec
        elif endpoint.startswith("baseline"):
            baseline_by_prompt[pid] = rec

    # Pair and write
    prompt_ids = sorted(set(router_by_prompt.keys()) & set(baseline_by_prompt.keys()))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for pid in prompt_ids:
            router = router_by_prompt[pid]
            baseline = baseline_by_prompt[pid]

            paired = {
                "prompt_id": pid,
                "prompt": _extract_prompt_text(router),
                "router_response": router.get("response_text", ""),
                "baseline_response": baseline.get("response_text", ""),
                "router_model": router.get("model_name", ""),
                "baseline_model": baseline.get("model_name", ""),
                "router_latency_ms": router.get("latency_ms", 0.0),
                "baseline_latency_ms": baseline.get("latency_ms", 0.0),
                "router_tokens": router.get("total_tokens", 0),
                "baseline_tokens": baseline.get("total_tokens", 0),
                "router_cost_usd": _estimate_cost(router, pricing["model_router"]),
                "baseline_cost_usd": _estimate_cost(baseline, pricing["baseline"]),
                "category": _infer_category(pid),
            }
            f.write(json.dumps(paired, ensure_ascii=False) + "\n")
            count += 1

    return count


def _extract_prompt_text(record: Dict[str, Any]) -> str:
    """Best-effort extraction of the original prompt text.

    The raw_results.jsonl doesn't store the prompt text directly, so we
    return the prompt_id as a placeholder. If the caller has access to the
    dataset, they can enrich this later.
    """
    # The original dataset is the source of truth for prompt text.
    # We use prompt_id as a fallback identifier.
    return record.get("prompt_id", "")


def _infer_category(prompt_id: str) -> str:
    """Infer category from prompt_id if available.

    The sample dataset uses IDs like 'sample_001' with no category encoding,
    so this returns an empty string by default.
    """
    return ""


def transform_with_dataset(
    raw_results_path: Path,
    results_json_path: Path,
    dataset_path: Path,
    output_path: Path,
) -> int:
    """Transform with dataset enrichment for prompt text and category.

    Reads the original dataset to fill in prompt text and category fields
    that aren't present in raw_results.jsonl.

    Args:
        raw_results_path: Path to raw_results.jsonl.
        results_json_path: Path to results.json.
        dataset_path: Path to the original dataset (.jsonl or .csv).
        output_path: Where to write the Foundry input JSONL.

    Returns:
        Number of paired records written.
    """
    records = _load_jsonl(raw_results_path)
    results = _load_json(results_json_path)
    pricing = _extract_pricing(results)

    # Load dataset for prompt text + category
    prompt_text_map: Dict[str, str] = {}
    category_map: Dict[str, str] = {}

    if dataset_path.suffix == ".jsonl":
        dataset = _load_jsonl(dataset_path)
        for item in dataset:
            pid = item.get("id", "")
            prompt_text_map[pid] = item.get("prompt", "")
            category_map[pid] = item.get("category", "")
    elif dataset_path.suffix == ".csv":
        import csv
        with open(dataset_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get("id", "")
                prompt_text_map[pid] = row.get("prompt", "")
                category_map[pid] = row.get("category", "")

    # Group by prompt_id
    router_by_prompt: Dict[str, Dict[str, Any]] = {}
    baseline_by_prompt: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        pid = rec.get("prompt_id", "")
        endpoint = rec.get("endpoint", "")
        if endpoint == "model_router":
            router_by_prompt[pid] = rec
        elif endpoint.startswith("baseline"):
            baseline_by_prompt[pid] = rec

    prompt_ids = sorted(set(router_by_prompt.keys()) & set(baseline_by_prompt.keys()))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for pid in prompt_ids:
            router = router_by_prompt[pid]
            baseline = baseline_by_prompt[pid]

            paired = {
                "prompt_id": pid,
                "prompt": prompt_text_map.get(pid, pid),
                "router_response": router.get("response_text", ""),
                "baseline_response": baseline.get("response_text", ""),
                "router_model": router.get("model_name", ""),
                "baseline_model": baseline.get("model_name", ""),
                "router_latency_ms": router.get("latency_ms", 0.0),
                "baseline_latency_ms": baseline.get("latency_ms", 0.0),
                "router_tokens": router.get("total_tokens", 0),
                "baseline_tokens": baseline.get("total_tokens", 0),
                "router_cost_usd": _estimate_cost(router, pricing["model_router"]),
                "baseline_cost_usd": _estimate_cost(baseline, pricing["baseline"]),
                "category": category_map.get(pid, ""),
            }
            f.write(json.dumps(paired, ensure_ascii=False) + "\n")
            count += 1

    return count
