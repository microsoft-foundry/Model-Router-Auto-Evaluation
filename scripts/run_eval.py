#!/usr/bin/env python3
"""One-click entry point for running model router evaluations."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Microsoft Foundry Model Router against a baseline model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_eval.py                                       # Default config (saves to results/run-<unix_timestamp>/)
  python scripts/run_eval.py --dataset my_data.jsonl               # JSONL dataset
  python scripts/run_eval.py --dataset my_data.csv                 # CSV dataset
  python scripts/run_eval.py --dataset "sqlite:///prompts.db?table=prompts"  # SQLite
  python scripts/run_eval.py --sample-size 100                     # Subset of prompts
  python scripts/run_eval.py --dry-run                             # Validate only
  python scripts/run_eval.py --resume                              # Resume most recent interrupted run

  # Compare two runs:
  python scripts/compare_results.py results/run-1745750400 results/run-1745754000
        """,
    )
    parser.add_argument(
        "--config",
        default="configs/default.yaml",
        help="Path to YAML config file (default: configs/default.yaml)",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Override dataset path from config (supports .jsonl, .csv, or a DB connection string)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Override sample size (number of prompts to evaluate)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and dataset without making API calls",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted evaluation from checkpoint files",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip automatic output verification after eval completes",
    )

    args = parser.parse_args()

    # Add project root to path so 'src' package is importable
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    sys.path.insert(0, str(project_root))

    from src import configure_console_encoding
    configure_console_encoding()

    from src.config import load_config
    from src.dataset import load_dataset
    from src.runner import run_evaluation

    # Load config
    try:
        config = load_config(args.config)
    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply CLI overrides
    if args.dataset:
        config.dataset = args.dataset
    if args.sample_size is not None:
        config.sample_size = args.sample_size

    # Always use a timestamped subdirectory under results/
    results_base = project_root / "results"
    if args.resume:
        # Pick the most recent existing timestamped run directory (largest epoch = most recent)
        existing_runs = sorted(
            [d for d in results_base.iterdir() if d.is_dir() and d.name.startswith("run-") and d.name[4:].isdigit()],
            key=lambda d: int(d.name[4:]),
            reverse=True,
        )
        if not existing_runs:
            print("No previous timestamped run found to resume.", file=sys.stderr)
            sys.exit(1)
        config.output_directory = str(existing_runs[0])
        print(f"Resuming run: {existing_runs[0].name}")
    else:
        timestamp = f"run-{int(time.time())}"
        config.output_directory = str(results_base / timestamp)

    # Dry-run: validate config and dataset, then exit
    if args.dry_run:
        print("Dry-run mode: validating configuration and dataset...\n")
        print(f"Config: {args.config}")
        print(f"  Name: {config.name}")
        print(f"  Dataset: {config.dataset}")
        print(f"  Sample size: {config.sample_size or 'all'}")
        print(f"  Output directory: {config.output_directory}")
        print(f"  Model Router: {config.model_router.deployment_name}")
        print(f"  Baseline: {config.baseline.deployment_name}")

        try:
            prompts = load_dataset(
                config.dataset,
                sample_size=config.sample_size,
                random_seed=config.random_seed,
            )
            print(f"\n  Dataset valid: {len(prompts)} prompts loaded")

            # Show category distribution
            categories = {}
            for p in prompts:
                cat = p.category or "uncategorized"
                categories[cat] = categories.get(cat, 0) + 1
            if categories:
                print("  Categories:")
                for cat, count in sorted(categories.items()):
                    print(f"    {cat}: {count}")

        except Exception as e:
            print(f"\n  Dataset error: {e}", file=sys.stderr)
            sys.exit(1)

        print("\n✓ Dry-run passed. Ready to run evaluation.")
        sys.exit(0)

    # Run evaluation
    try:
        asyncio.run(run_evaluation(config, resume=args.resume))
    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nEvaluation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Auto-verify output
    if not args.no_verify:
        from src.verify import verify_local_eval

        vr = verify_local_eval(config.output_directory)
        vr.print_summary()
        if not vr.passed:
            sys.exit(1)


if __name__ == "__main__":
    main()
