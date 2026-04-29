#!/usr/bin/env python3
"""Utility to clean up registered Foundry custom evaluators.

Useful for development and testing when you need to remove evaluators
that were registered during previous runs.

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
        description="Clean up registered Foundry custom evaluators.",
    )
    parser.add_argument(
        "--config",
        default="configs/foundry.yaml",
        help="Path to Foundry YAML config file (default: configs/foundry.yaml)",
    )
    parser.add_argument(
        "--evaluators",
        nargs="+",
        default=["mr_cost_comparison", "mr_latency_comparison"],
        help="Names of evaluators to delete",
    )

    args = parser.parse_args()

    load_dotenv()

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from src.foundry.config import load_foundry_config
    from src.foundry.client import FoundryEvalClient

    try:
        config = load_foundry_config(args.config)
    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    client = FoundryEvalClient(
        project_endpoint=config.foundry.project_endpoint,
        model_deployment_name=config.foundry.model_deployment_name,
    )
    client.connect()

    for name in args.evaluators:
        try:
            client.project_client.evaluators.delete(evaluator_name=name)
            print(f"  ✓ Deleted evaluator: {name}")
        except Exception as e:
            print(f"  ✗ Failed to delete {name}: {e}")


if __name__ == "__main__":
    main()
