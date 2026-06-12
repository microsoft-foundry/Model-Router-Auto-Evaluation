#!/usr/bin/env python3
"""Compare two evaluation runs side-by-side.

Reads results.json from two output directories and prints a delta table
showing cost, latency, quality, and model distribution changes.

Supports both local eval results and Foundry cloud eval results.

Usage:
    python scripts/compare_results.py results/run-a results/run-b
    python scripts/compare_results.py results/run-a results/run-b --format csv
    python scripts/compare_results.py results/full-eval results/foundry-eval
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _load_results(path: Path) -> dict:
    """Load results.json from an output directory."""
    results_file = path / "results.json"
    if not results_file.exists():
        print(f"ERROR: {results_file} not found.", file=sys.stderr)
        sys.exit(1)
    with open(results_file, "r", encoding="utf-8") as f:
        return json.load(f)


_MISSING = object()


def _safe_get(data: dict, *keys, default=None):
    """Safely traverse nested dict keys."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def _quality_metric(data: dict, *keys, default=None):
    """Read a quality metric from nested results.json layouts."""
    value = _safe_get(data, "quality", *keys, default=_MISSING)
    if value is not _MISSING:
        return value

    quality = data.get("quality")
    if not isinstance(quality, dict):
        return default
    if len(keys) == 1:
        return quality.get(keys[0], default)
    if keys[0] == "pairwise" and len(keys) == 2:
        return quality.get(keys[1], default)

    legacy_map = {
        ("absolute_scores", "router_overall"): "router_mean_score",
        ("absolute_scores", "baseline_overall"): "baseline_mean_score",
    }
    legacy_key = legacy_map.get(keys)
    if legacy_key:
        return quality.get(legacy_key, default)

    return default


def _fmt_delta(a, b, unit="", lower_is_better=True):
    """Format a delta with direction indicator."""
    if a is None or b is None:
        return "N/A"
    delta = b - a
    pct = (delta / a * 100) if a != 0 else 0
    sign = "+" if delta > 0 else ""
    # Green = improvement, Red = regression
    improved = (delta < 0) if lower_is_better else (delta > 0)
    indicator = "improved" if improved else ("regression" if delta != 0 else "same")
    return f"{a:.4f}{unit} -> {b:.4f}{unit} ({sign}{pct:.1f}%) [{indicator}]"


def _fmt_delta_ms(a, b):
    """Format millisecond delta."""
    if a is None or b is None:
        return "N/A"
    delta = b - a
    pct = (delta / a * 100) if a != 0 else 0
    sign = "+" if delta > 0 else ""
    improved = delta < 0
    indicator = "improved" if improved else ("regression" if delta != 0 else "same")
    return f"{a:.1f}ms -> {b:.1f}ms ({sign}{pct:.1f}%) [{indicator}]"


def compare(run_a: dict, run_b: dict, label_a: str, label_b: str) -> list[dict]:
    """Build comparison rows for local eval results."""
    rows = []

    def _add(category, metric, val_a, val_b, unit="", lower_is_better=True):
        rows.append({
            "category": category,
            "metric": metric,
            "run_a": val_a,
            "run_b": val_b,
            "delta": (val_b - val_a) if val_a is not None and val_b is not None else None,
            "delta_pct": ((val_b - val_a) / val_a * 100) if val_a and val_b else None,
            "unit": unit,
            "lower_is_better": lower_is_better,
        })

    # Cost
    for endpoint in ["model_router", "baseline"]:
        cost_a = _safe_get(run_a, endpoint, "cost", "estimated_cost_usd")
        cost_b = _safe_get(run_b, endpoint, "cost", "estimated_cost_usd")
        _add("Cost", f"{endpoint} total ($)", cost_a, cost_b, "$")

    # Latency
    for endpoint in ["model_router", "baseline"]:
        for stat in ["mean_ms", "p90_ms", "p99_ms"]:
            lat_a = _safe_get(run_a, endpoint, "latency", stat)
            lat_b = _safe_get(run_b, endpoint, "latency", stat)
            _add("Latency", f"{endpoint} {stat}", lat_a, lat_b, "ms")

    # Quality
    for metric_key in ["router_win_rate", "baseline_win_rate", "tie_rate"]:
        val_a = _quality_metric(run_a, "pairwise", metric_key)
        val_b = _quality_metric(run_b, "pairwise", metric_key)
        better = metric_key == "router_win_rate"  # higher router wins is better
        _add("Quality", metric_key, val_a, val_b, "", lower_is_better=not better)

    for metric_key in ["router_overall", "baseline_overall"]:
        val_a = _quality_metric(run_a, "absolute_scores", metric_key)
        val_b = _quality_metric(run_b, "absolute_scores", metric_key)
        _add("Quality", metric_key, val_a, val_b, "", lower_is_better=False)

    _cat_a = _safe_get(run_a, "quality", "win_rate_by_category")
    cat_a = _cat_a if isinstance(_cat_a, dict) else {}
    _cat_b = _safe_get(run_b, "quality", "win_rate_by_category")
    cat_b = _cat_b if isinstance(_cat_b, dict) else {}
    for category in sorted(set(cat_a) | set(cat_b)):
        for metric_key in ["router_win_rate", "baseline_win_rate", "tie_rate"]:
            val_a = _safe_get(cat_a.get(category, {}), metric_key)
            val_b = _safe_get(cat_b.get(category, {}), metric_key)
            better = metric_key == "router_win_rate"
            _add("Quality by Category", f"{category} {metric_key}", val_a, val_b, "",
                 lower_is_better=not better)

    # Requests
    for endpoint in ["model_router", "baseline"]:
        req_a = _safe_get(run_a, endpoint, "total_requests")
        req_b = _safe_get(run_b, endpoint, "total_requests")
        _add("Requests", f"{endpoint} total", req_a, req_b, "", lower_is_better=False)

    return rows


def _is_foundry_format(data: dict) -> bool:
    """Detect if a results.json is in Foundry cloud eval format."""
    return "grader_summary" in data


def compare_foundry(run_a: dict, run_b: dict, label_a: str, label_b: str) -> list[dict]:
    """Build comparison rows for two Foundry eval results."""
    rows = []

    def _add(category, metric, val_a, val_b, unit="", lower_is_better=True):
        rows.append({
            "category": category,
            "metric": metric,
            "run_a": val_a,
            "run_b": val_b,
            "delta": (val_b - val_a) if val_a is not None and val_b is not None else None,
            "delta_pct": ((val_b - val_a) / val_a * 100) if val_a and val_b else None,
            "unit": unit,
            "lower_is_better": lower_is_better,
        })

    # Get all graders from both runs
    graders_a = run_a.get("grader_summary", {})
    graders_b = run_b.get("grader_summary", {})
    all_graders = sorted(set(graders_a) | set(graders_b))

    for grader in all_graders:
        mean_a = _safe_get(graders_a, grader, "mean")
        mean_b = _safe_get(graders_b, grader, "mean")
        _add("Grader Mean", grader, mean_a, mean_b, "", lower_is_better=False)

        pass_a = _safe_get(graders_a, grader, "pass_rate")
        pass_b = _safe_get(graders_b, grader, "pass_rate")
        _add("Pass Rate", f"{grader} (%)", pass_a, pass_b, "%", lower_is_better=False)

    # Result counts
    counts_a = run_a.get("result_counts", {})
    counts_b = run_b.get("result_counts", {})
    for key in ["passed", "failed", "errored", "total"]:
        val_a = counts_a.get(key)
        val_b = counts_b.get(key)
        better = key in ("passed", "total")
        _add("Results", key, val_a, val_b, "", lower_is_better=not better)

    return rows


def compare_cross(local: dict, foundry: dict, label_local: str, label_foundry: str) -> list[dict]:
    """Build comparison rows between a local eval and a Foundry eval."""
    rows = []

    def _add(category, metric, val_a, val_b, unit="", lower_is_better=True):
        rows.append({
            "category": category,
            "metric": metric,
            "run_a": val_a,
            "run_b": val_b,
            "delta": (val_b - val_a) if val_a is not None and val_b is not None else None,
            "delta_pct": ((val_b - val_a) / val_a * 100) if val_a and val_b else None,
            "unit": unit,
            "lower_is_better": lower_is_better,
        })

    graders = foundry.get("grader_summary", {})

    # Quality: map local quality scores to Foundry graders
    local_router_score = _quality_metric(local, "absolute_scores", "router_overall")
    foundry_router_score = _safe_get(graders, "quality_absolute_router", "mean")
    _add("Quality", "router_absolute_score", local_router_score, foundry_router_score, "",
         lower_is_better=False)

    local_baseline_score = _quality_metric(local, "absolute_scores", "baseline_overall")
    foundry_baseline_score = _safe_get(graders, "quality_absolute_baseline", "mean")
    _add("Quality", "baseline_absolute_score", local_baseline_score, foundry_baseline_score, "",
         lower_is_better=False)

    # Cost: local total vs Foundry cost ratio
    local_router_cost = _safe_get(local, "model_router", "cost", "estimated_cost_usd")
    local_baseline_cost = _safe_get(local, "baseline", "cost", "estimated_cost_usd")
    if local_router_cost is not None and local_baseline_cost and local_baseline_cost > 0:
        local_cost_ratio = 1 - (local_router_cost / local_baseline_cost)
    else:
        local_cost_ratio = None
    foundry_cost_ratio = _safe_get(graders, "mr_cost_comparison", "mean")
    _add("Cost", "savings_ratio (1=free, 0=same)", local_cost_ratio, foundry_cost_ratio, "",
         lower_is_better=False)

    # Pass rates from Foundry
    for grader_name in sorted(graders):
        pass_rate = _safe_get(graders, grader_name, "pass_rate")
        _add("Foundry Pass Rate", grader_name, None, pass_rate, "%", lower_is_better=False)

    return rows


def print_markdown(rows: list[dict], label_a: str, label_b: str):
    """Print comparison as a Markdown table."""
    print(f"\n## Comparison: {label_a} vs {label_b}\n")
    print(f"| Category | Metric | {label_a} | {label_b} | Delta | Change |")
    print("|----------|--------|-----------|-----------|-------|--------|")
    for r in rows:
        va = f"{r['run_a']:.4f}" if r['run_a'] is not None else "N/A"
        vb = f"{r['run_b']:.4f}" if r['run_b'] is not None else "N/A"
        delta = f"{r['delta']:+.4f}" if r['delta'] is not None else "N/A"
        pct = f"{r['delta_pct']:+.1f}%" if r['delta_pct'] is not None else ""
        print(f"| {r['category']} | {r['metric']} | {va} | {vb} | {delta} | {pct} |")
    print()


def print_csv(rows: list[dict], label_a: str, label_b: str):
    """Print comparison as CSV."""
    writer = csv.DictWriter(sys.stdout, fieldnames=[
        "category", "metric", f"run_a ({label_a})", f"run_b ({label_b})", "delta", "delta_pct",
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "category": r["category"],
            "metric": r["metric"],
            f"run_a ({label_a})": r["run_a"],
            f"run_b ({label_b})": r["run_b"],
            "delta": r["delta"],
            "delta_pct": f"{r['delta_pct']:.1f}%" if r["delta_pct"] is not None else "",
        })


def main():
    parser = argparse.ArgumentParser(
        description="Compare two evaluation runs side-by-side.",
        epilog="""
Examples:
  python scripts/compare_results.py results/run-a results/run-b
  python scripts/compare_results.py results/v1 results/v2 --format csv > diff.csv
  python scripts/compare_results.py results/full-eval results/foundry-eval
        """,
    )
    parser.add_argument("run_a", help="Path to first run's output directory")
    parser.add_argument("run_b", help="Path to second run's output directory")
    parser.add_argument(
        "--format", choices=["markdown", "csv"], default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    path_a = Path(args.run_a)
    path_b = Path(args.run_b)
    data_a = _load_results(path_a)
    data_b = _load_results(path_b)

    label_a = path_a.name
    label_b = path_b.name

    is_a_foundry = _is_foundry_format(data_a)
    is_b_foundry = _is_foundry_format(data_b)

    if is_a_foundry and is_b_foundry:
        rows = compare_foundry(data_a, data_b, label_a, label_b)
    elif not is_a_foundry and is_b_foundry:
        rows = compare_cross(data_a, data_b, label_a, label_b)
    elif is_a_foundry and not is_b_foundry:
        rows = compare_cross(data_b, data_a, label_b, label_a)
        label_a, label_b = label_b, label_a
    else:
        rows = compare(data_a, data_b, label_a, label_b)

    if args.format == "csv":
        print_csv(rows, label_a, label_b)
    else:
        print_markdown(rows, label_a, label_b)


if __name__ == "__main__":
    main()
