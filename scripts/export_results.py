#!/usr/bin/env python3
"""Export evaluation results to different formats.

Reads from an evaluation output directory and exports to JSONL, CSV,
or a flat JSON summary suitable for dashboards and external tools.

Usage:
    python scripts/export_results.py results/my-run --format jsonl
    python scripts/export_results.py results/my-run --format csv --output export.csv
    python scripts/export_results.py results/my-run --format summary
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _load_json(path: Path, filename: str) -> dict | list | None:
    """Load a JSON file from the output directory."""
    f = path / filename
    if not f.exists():
        return None
    with open(f, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_jsonl(path: Path, filename: str) -> list[dict]:
    """Load a JSONL file from the output directory."""
    f = path / filename
    if not f.exists():
        return []
    records = []
    with open(f, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def export_jsonl(output_dir: Path, out_file):
    """Export raw results as JSONL (one record per API call)."""
    records = _load_jsonl(output_dir, "raw_results.jsonl")
    if not records:
        print("WARNING: raw_results.jsonl not found or empty.", file=sys.stderr)
        return
    for r in records:
        out_file.write(json.dumps(r) + "\n")
    print(f"Exported {len(records)} records as JSONL.", file=sys.stderr)


def export_csv(output_dir: Path, out_file):
    """Export detailed_results.csv (pass-through if it exists, else build from raw)."""
    csv_path = output_dir / "detailed_results.csv"
    if csv_path.exists():
        out_file.write(csv_path.read_text(encoding="utf-8"))
        print("Exported detailed_results.csv.", file=sys.stderr)
        return

    # Fallback: build from raw_results.jsonl
    records = _load_jsonl(output_dir, "raw_results.jsonl")
    if not records:
        print("WARNING: No results found to export.", file=sys.stderr)
        return

    fields = [
        "prompt_id", "endpoint", "model_name", "status",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "latency_ms", "error_message", "timestamp",
    ]
    writer = csv.DictWriter(out_file, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in records:
        writer.writerow(r)
    print(f"Exported {len(records)} records as CSV.", file=sys.stderr)


def export_summary(output_dir: Path, out_file):
    """Export a flat JSON summary (metrics only, no response text)."""
    metrics = _load_json(output_dir, "results.json")
    if not metrics:
        print("WARNING: results.json not found.", file=sys.stderr)
        return

    summary = {
        "source": str(output_dir),
        "model_router": {
            "total_requests": metrics.get("model_router", {}).get("total_requests"),
            "successful_requests": metrics.get("model_router", {}).get("successful_requests"),
            "cost_usd": (metrics.get("model_router", {}).get("cost") or {}).get("estimated_cost_usd"),
            "latency_mean_ms": (metrics.get("model_router", {}).get("latency") or {}).get("mean_ms"),
            "latency_p90_ms": (metrics.get("model_router", {}).get("latency") or {}).get("p90_ms"),
            "model_distribution": metrics.get("model_router", {}).get("model_distribution"),
        },
        "baseline": {
            "total_requests": metrics.get("baseline", {}).get("total_requests"),
            "successful_requests": metrics.get("baseline", {}).get("successful_requests"),
            "cost_usd": (metrics.get("baseline", {}).get("cost") or {}).get("estimated_cost_usd"),
            "latency_mean_ms": (metrics.get("baseline", {}).get("latency") or {}).get("mean_ms"),
            "latency_p90_ms": (metrics.get("baseline", {}).get("latency") or {}).get("p90_ms"),
        },
        "comparison": metrics.get("comparison"),
        "quality": {
            k: v for k, v in (metrics.get("quality") or {}).items()
            if k in ("router_win_rate", "baseline_win_rate", "tie_rate",
                     "router_mean_overall", "baseline_mean_overall")
        } if metrics.get("quality") else None,
    }

    out_file.write(json.dumps(summary, indent=2) + "\n")
    print("Exported summary JSON.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Export evaluation results to JSONL, CSV, or summary JSON.",
        epilog="""
Examples:
  python scripts/export_results.py results/my-run --format jsonl > raw.jsonl
  python scripts/export_results.py results/my-run --format csv --output export.csv
  python scripts/export_results.py results/my-run --format summary
        """,
    )
    parser.add_argument("input_dir", help="Path to evaluation output directory")
    parser.add_argument(
        "--format", choices=["jsonl", "csv", "summary"], default="summary",
        help="Export format (default: summary)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"ERROR: {input_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out_file = open(args.output, "w", encoding="utf-8")
    else:
        out_file = sys.stdout

    try:
        if args.format == "jsonl":
            export_jsonl(input_dir, out_file)
        elif args.format == "csv":
            export_csv(input_dir, out_file)
        elif args.format == "summary":
            export_summary(input_dir, out_file)
    finally:
        if args.output:
            out_file.close()


if __name__ == "__main__":
    main()
