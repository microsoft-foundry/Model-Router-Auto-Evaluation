"""Foundry evaluation orchestrator.

End-to-end flow:
  1. Transform raw results → Foundry JSONL
  2. Connect to Foundry
  3. Register custom evaluators (cost, latency)
  4. Build testing criteria (quality graders + custom evaluators)
  5. Upload data → Create eval → Run → Poll → Get results
  6. Generate report
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import EvalRunResult, FoundryEvalClient
from .config import CloudEvalConfig
from .custom_evaluators import COST_EVALUATOR_CODE, LATENCY_EVALUATOR_CODE
from .graders import build_custom_evaluator_criteria, build_quality_criteria
from .report import generate_foundry_report
from .transformer import transform, transform_with_dataset


def run_foundry_eval(
    config: CloudEvalConfig,
    input_dir: Path,
    dataset_path: Optional[Path] = None,
    dry_run: bool = False,
    skip_quality: bool = False,
    skip_custom: bool = False,
) -> Optional[EvalRunResult]:
    """Run the full Foundry evaluation pipeline.

    Args:
        config: Loaded Foundry configuration.
        input_dir: Directory containing raw_results.jsonl and results.json.
        dataset_path: Optional path to original dataset for prompt enrichment.
        dry_run: If True, transform data and validate but don't call Foundry.
        skip_quality: If True, skip quality (score_model) graders.
        skip_custom: If True, skip cost/latency custom evaluators.

    Returns:
        EvalRunResult if evaluation ran, None if dry_run.
    """
    output_dir = Path(config.output.directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_results = input_dir / "raw_results.jsonl"
    results_json = input_dir / "results.json"

    if not raw_results.exists():
        raise FileNotFoundError(f"raw_results.jsonl not found in {input_dir}")
    if not results_json.exists():
        raise FileNotFoundError(f"results.json not found in {input_dir}")

    # ── Step 1: Transform ────────────────────────────────────────────────
    foundry_jsonl = output_dir / "foundry_input.jsonl"
    print("\n── Step 1: Transform raw results → Foundry JSONL ──")

    if dataset_path and dataset_path.exists():
        count = transform_with_dataset(raw_results, results_json, dataset_path, foundry_jsonl)
        print(f"  ✓ Transformed {count} paired records (enriched with dataset)")
    else:
        count = transform(raw_results, results_json, foundry_jsonl)
        print(f"  ✓ Transformed {count} paired records")

    if count == 0:
        print("  ✗ No paired records found — check raw_results.jsonl")
        return None

    if dry_run:
        print("\n── Dry run complete ──")
        print(f"  Foundry input JSONL: {foundry_jsonl}")
        print(f"  Records: {count}")
        print("  Skipping Foundry API calls (--dry-run)")
        return None

    # ── Step 2: Connect ──────────────────────────────────────────────────
    print("\n── Step 2: Connect to Microsoft Foundry ──")
    client = FoundryEvalClient(
        project_endpoint=config.foundry.project_endpoint,
        model_deployment_name=config.foundry.model_deployment_name,
    )
    client.connect()
    print("  ✓ Connected (DefaultAzureCredential)")

    # ── Step 3: Build testing criteria ─────────────────────────────────
    print("\n── Step 3: Build testing criteria ──")
    testing_criteria: List[Dict[str, Any]] = []

    if not skip_quality and config.quality.enabled:
        quality_criteria = build_quality_criteria(
            model_deployment=config.foundry.model_deployment_name,
            absolute_template_path=config.quality.absolute_template,
            pairwise_template_path=config.quality.pairwise_template,
            pass_threshold=config.quality.pass_threshold,
            score_range=config.quality.range,
        )
        testing_criteria.extend(quality_criteria)
        print(f"  ✓ Quality graders: {len(quality_criteria)}")

    if not skip_custom and config.cost.enabled:
        testing_criteria.append(
            build_custom_evaluator_criteria(
                config.cost.evaluator_name,
                COST_EVALUATOR_CODE,
                config.cost.pass_threshold,
            )
        )
        print(f"  ✓ Cost evaluator: {config.cost.evaluator_name}")

    if not skip_custom and config.latency.enabled:
        testing_criteria.append(
            build_custom_evaluator_criteria(
                config.latency.evaluator_name,
                LATENCY_EVALUATOR_CODE,
                config.latency.pass_threshold,
            )
        )
        print(f"  ✓ Latency evaluator: {config.latency.evaluator_name}")

    print(f"  Total criteria: {len(testing_criteria)}")

    if not testing_criteria:
        print("  ✗ No testing criteria — nothing to evaluate")
        return None

    # ── Step 4: Upload → Create eval → Run → Poll ────────────────────────
    print("\n── Step 4: Upload data and run evaluation ──")

    file_id = client.upload_file(foundry_jsonl)
    print(f"  ✓ Uploaded: {file_id}")

    eval_name = f"model-router-eval-{int(time.time())}"
    eval_id = client.create_eval(name=eval_name, testing_criteria=testing_criteria)
    print(f"  ✓ Created eval: {eval_id}")

    run_name = f"run-{int(time.time())}"
    run_id = client.create_run(eval_id=eval_id, run_name=run_name, file_id=file_id)
    print(f"  ✓ Started run: {run_id}")

    print("  ⏳ Polling for completion...")
    status = client.poll_run(eval_id=eval_id, run_id=run_id)
    print(f"  ✓ Run status: {status}")

    if status != "completed":
        print(f"  ✗ Run did not complete successfully: {status}")
        return EvalRunResult(eval_id=eval_id, run_id=run_id, status=status)

    # ── Step 5: Get results and generate report ──────────────────────────
    print("\n── Step 5: Retrieve results and generate report ──")
    result = client.get_results(eval_id=eval_id, run_id=run_id)
    print(f"  ✓ Retrieved {len(result.output_items)} output items")

    if result.report_url:
        print(f"  ✓ Foundry portal: {result.report_url}")

    generate_foundry_report(
        result=result,
        config=config,
        output_dir=output_dir,
    )

    return result
