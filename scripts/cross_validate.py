#!/usr/bin/env python3
"""Cross-validate local evaluation results against Foundry cloud evaluation.

Compares quality, cost, and latency metrics from both pipelines to confirm
they agree. Both grade the same prompt/response pairs independently.

Usage:
    python scripts/cross_validate.py
    python scripts/cross_validate.py results/full-eval results/foundry-eval
    python scripts/cross_validate.py --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: Path, filename: str) -> dict:
    """Load a JSON file or exit with a clear error."""
    filepath = path / filename
    if not filepath.exists():
        print(f"ERROR: {filepath} not found.", file=sys.stderr)
        print("  Run the corresponding evaluation first.", file=sys.stderr)
        sys.exit(1)
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def cross_validate(local: dict, foundry: dict) -> dict:
    """Compare local and Foundry results, return a structured comparison."""
    gs = foundry.get("grader_summary", {})

    if not gs:
        return {"error": "Foundry results.json has empty grader_summary. Re-run the Foundry eval."}

    # Extract local metrics
    lr = local.get("quality", {}).get("absolute_scores", {}).get("router_overall", 0)
    lb = local.get("quality", {}).get("absolute_scores", {}).get("baseline_overall", 0)
    lc = local.get("comparison", {}).get("cost_savings_ratio", 0)
    ll = local.get("comparison", {}).get("latency_diff_mean_ms", 0)

    # Extract Foundry metrics
    fr = gs.get("quality_absolute_router", {}).get("mean", 0)
    fb = gs.get("quality_absolute_baseline", {}).get("mean", 0)
    fc = gs.get("mr_cost_comparison", {}).get("mean", 0)
    fl = gs.get("mr_latency_comparison", {}).get("mean", 0)
    flp = gs.get("mr_latency_comparison", {}).get("pass_rate", 0)

    # Agreement checks
    quality_direction = (lr > lb) == (fr > fb)
    quality_close = abs(fr - lr) < 1.0
    cost_close = abs(fc - lc) < 0.05
    overall = quality_direction and quality_close and cost_close

    return {
        "quality": {
            "local_router": lr,
            "local_baseline": lb,
            "foundry_router": fr,
            "foundry_baseline": fb,
            "direction_agrees": quality_direction,
            "within_1pt": quality_close,
        },
        "cost": {
            "local_savings": lc,
            "foundry_savings": fc,
            "within_5pct": cost_close,
        },
        "latency": {
            "local_diff_ms": ll,
            "foundry_ratio": fl,
            "foundry_pass_rate": flp,
        },
        "per_item_scores": foundry.get("per_item_scores", []),
        "verdict": "CORRELATE" if overall else "DIVERGENCE",
    }


def print_report(result: dict):
    """Print human-readable cross-validation report."""
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    q = result["quality"]
    c = result["cost"]
    lat = result["latency"]

    print("=" * 65)
    print("  CROSS-VALIDATION: Local Eval vs Foundry Cloud Eval")
    print("=" * 65)

    print(f"\n  {'Metric':<25} {'Local':<15} {'Foundry':<15} {'Agree?'}")
    print("  " + "-" * 60)

    qa = "YES" if q["within_1pt"] else "NO"
    print(f"  {'Router quality':<25} {q['local_router']:<15.2f} {q['foundry_router']:<15.2f} {qa}")
    print(f"  {'Baseline quality':<25} {q['local_baseline']:<15.2f} {q['foundry_baseline']:<15.2f} "
          f"{'YES' if abs(q['foundry_baseline'] - q['local_baseline']) < 1.0 else 'NO'}")
    da = "YES" if q["direction_agrees"] else "NO"
    print(f"  {'Router > Baseline?':<25} {'Yes':<15} "
          f"{'Yes' if q['foundry_router'] > q['foundry_baseline'] else 'No':<15} {da}")

    ca = "YES" if c["within_5pct"] else "NO"
    print(f"  {'Cost savings':<25} {c['local_savings']:<15.1%} {c['foundry_savings']:<15.1%} {ca}")

    print(f"  {'Latency':<25} {'+' + str(round(lat['local_diff_ms'])) + 'ms':<15} "
          f"{lat['foundry_pass_rate']:.0f}% pass")

    # Per-item table
    per_item = result.get("per_item_scores", [])
    if per_item:
        print(f"\n  {'Prompt':<12} {'RtrQ':>5} {'BaseQ':>6} {'Pair':>5} "
              f"{'Cost':>7} {'Latency':>8}")
        print("  " + "-" * 50)
        for item in per_item:
            pid = item.get("prompt_id", "?")[-3:]
            s = item.get("scores", {})
            rq = s.get("quality_absolute_router", {}).get("score", 0)
            bq = s.get("quality_absolute_baseline", {}).get("score", 0)
            pw = s.get("quality_pairwise", {}).get("score", 0)
            co = s.get("mr_cost_comparison", {}).get("score", 0)
            la = s.get("mr_latency_comparison", {}).get("score", 0)
            bm = " *" if not s.get("quality_absolute_baseline", {}).get("passed", True) else ""
            lm = " *" if not s.get("mr_latency_comparison", {}).get("passed", True) else ""
            print(f"  {pid:<12} {rq:>5.0f} {bq:>5.0f}{bm:2s} {pw:>5.0f} "
                  f"{co:>7.3f} {la:>7.3f}{lm}")
        print("  * = failed threshold")

    v = result["verdict"]
    if v == "CORRELATE":
        print("\n  VERDICT: Local and Foundry evaluations CORRELATE WELL.")
        print("  Both independently confirm the same quality, cost, and latency trends.")
    else:
        print("\n  VERDICT: DIVERGENCE DETECTED — investigate differences.")
        print("  Check grader prompts, data transformation, and empty responses.")


def main():
    parser = argparse.ArgumentParser(
        description="Cross-validate local evaluation vs Foundry cloud evaluation.",
        epilog="""
Examples:
  python scripts/cross_validate.py
  python scripts/cross_validate.py results/full-eval results/foundry-eval
  python scripts/cross_validate.py --format json > cross_validation.json
        """,
    )
    parser.add_argument(
        "local_dir", nargs="?", default="results/full-eval",
        help="Directory with local results.json (default: results/full-eval)",
    )
    parser.add_argument(
        "foundry_dir", nargs="?", default="results/foundry-eval",
        help="Directory with Foundry results.json (default: results/foundry-eval)",
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    local = _load(Path(args.local_dir), "results.json")
    foundry = _load(Path(args.foundry_dir), "results.json")

    result = cross_validate(local, foundry)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print_report(result)

    # Exit code: 0 = correlate, 1 = divergence
    sys.exit(0 if result.get("verdict") == "CORRELATE" else 1)


if __name__ == "__main__":
    main()
