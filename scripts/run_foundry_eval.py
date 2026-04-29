#!/usr/bin/env python3
"""CLI entry point for Foundry cloud evaluation.

Reads the original project's evaluation output (raw_results.jsonl + results.json)
and submits it to Microsoft Foundry for cloud-based grading.

Requires: pip install -e ".[foundry]"
Requires: az login (DefaultAzureCredential)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(
        description="Run Foundry cloud evaluation on Model Router results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_foundry_eval.py --input-dir results/full-eval
  python scripts/run_foundry_eval.py --dry-run
  python scripts/run_foundry_eval.py --config configs/foundry.yaml --input-dir results/full-eval
  python scripts/run_foundry_eval.py --skip-quality    # Only cost/latency evaluators
  python scripts/run_foundry_eval.py --skip-custom     # Only quality graders
        """,
    )
    parser.add_argument(
        "--config",
        default="configs/foundry.yaml",
        help="Path to Foundry YAML config file (default: configs/foundry.yaml)",
    )
    parser.add_argument(
        "--input-dir",
        default="results/full-eval",
        help="Directory containing raw_results.jsonl and results.json (default: results/full-eval)",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path to original dataset for prompt text enrichment (optional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Transform data and validate config without calling Foundry API",
    )
    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Skip quality (score_model) graders",
    )
    parser.add_argument(
        "--skip-custom",
        action="store_true",
        help="Skip cost/latency custom evaluators",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip automatic output verification after eval completes",
    )

    args = parser.parse_args()

    # Load .env file if present
    load_dotenv()

    # Add project root to path so 'src' package is importable
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from src import configure_console_encoding
    configure_console_encoding()

    from src.foundry.config import load_foundry_config
    from src.foundry.runner import run_foundry_eval

    # Load config (non-strict for dry-run so missing env vars don't block)
    try:
        config = load_foundry_config(args.config, strict=not args.dry_run)
    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    input_dir = Path(args.input_dir)
    dataset_path = Path(args.dataset) if args.dataset else None

    print("=" * 60)
    print("  Foundry Cloud Evaluation")
    print("=" * 60)
    print(f"  Config:     {args.config}")
    print(f"  Input dir:  {input_dir}")
    print(f"  Dry run:    {args.dry_run}")
    print(f"  Quality:    {'skip' if args.skip_quality else 'enabled'}")
    print(f"  Custom:     {'skip' if args.skip_custom else 'enabled'}")
    print("=" * 60)

    try:
        result = run_foundry_eval(
            config=config,
            input_dir=input_dir,
            dataset_path=dataset_path,
            dry_run=args.dry_run,
            skip_quality=args.skip_quality,
            skip_custom=args.skip_custom,
        )

        if result and result.status == "completed":
            print("\n" + "=" * 60)
            print("  ✓ Evaluation completed successfully")
            if result.report_url:
                print(f"  Portal: {result.report_url}")
            print("=" * 60)
        elif result:
            print(f"\n  ✗ Evaluation ended with status: {result.status}")
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"\nInput error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nEvaluation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Auto-verify output
    if not args.no_verify and not args.dry_run:
        from src.verify import verify_foundry_eval

        output_dir = Path(config.output_directory if hasattr(config, 'output_directory') else "results/foundry-eval")
        vr = verify_foundry_eval(output_dir)
        vr.print_summary()
        if not vr.passed:
            sys.exit(1)


if __name__ == "__main__":
    main()
