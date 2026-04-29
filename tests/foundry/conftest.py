"""Shared test fixtures for Foundry tests — mocked SDK clients."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.foundry.config import CloudEvalConfig, CustomEvaluatorConfig, FoundryConfig, OutputConfig, QualityGraderConfig

# Path to the pre-built fixture files
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def foundry_config(tmp_path):
    """Create a minimal CloudEvalConfig for testing."""
    return CloudEvalConfig(
        foundry=FoundryConfig(
            project_endpoint="https://test-project.services.ai.azure.com",
            model_deployment_name="gpt-5",
        ),
        quality=QualityGraderConfig(
            enabled=True,
            absolute_template="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template="configs/grader_prompts/quality_pairwise.yaml",
            pass_threshold=3,
            range=[1, 5],
        ),
        cost=CustomEvaluatorConfig(
            enabled=True,
            evaluator_name="mr_cost_comparison",
            pass_threshold=0.5,
        ),
        latency=CustomEvaluatorConfig(
            enabled=True,
            evaluator_name="mr_latency_comparison",
            pass_threshold=0.5,
        ),
        output=OutputConfig(
            directory=str(tmp_path / "foundry-results"),
            formats=["markdown", "json"],
        ),
    )


@pytest.fixture
def sample_raw_results(tmp_path):
    """Create sample raw_results.jsonl with paired router+baseline records."""
    records = [
        {
            "request_id": "r1",
            "prompt_id": "p001",
            "endpoint": "model_router",
            "model_name": "gpt-4o-mini",
            "response_text": "Router response 1",
            "prompt_tokens": 10,
            "completion_tokens": 50,
            "total_tokens": 60,
            "latency_ms": 500.0,
            "status": "success",
            "error_message": None,
            "timestamp": "2026-04-23T00:00:00Z",
        },
        {
            "request_id": "r2",
            "prompt_id": "p001",
            "endpoint": "baseline:gpt-5",
            "model_name": "gpt-5",
            "response_text": "Baseline response 1",
            "prompt_tokens": 10,
            "completion_tokens": 80,
            "total_tokens": 90,
            "latency_ms": 1200.0,
            "status": "success",
            "error_message": None,
            "timestamp": "2026-04-23T00:00:01Z",
        },
        {
            "request_id": "r3",
            "prompt_id": "p002",
            "endpoint": "model_router",
            "model_name": "grok-4-fast",
            "response_text": "Router response 2",
            "prompt_tokens": 15,
            "completion_tokens": 100,
            "total_tokens": 115,
            "latency_ms": 800.0,
            "status": "success",
            "error_message": None,
            "timestamp": "2026-04-23T00:00:02Z",
        },
        {
            "request_id": "r4",
            "prompt_id": "p002",
            "endpoint": "baseline:gpt-5",
            "model_name": "gpt-5",
            "response_text": "Baseline response 2",
            "prompt_tokens": 15,
            "completion_tokens": 120,
            "total_tokens": 135,
            "latency_ms": 1500.0,
            "status": "success",
            "error_message": None,
            "timestamp": "2026-04-23T00:00:03Z",
        },
    ]

    path = tmp_path / "raw_results.jsonl"
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return path


@pytest.fixture
def sample_results_json(tmp_path):
    """Create sample results.json with aggregated metrics."""
    data = {
        "evaluation_name": "test-eval",
        "model_router": {
            "endpoint": "model_router",
            "total_requests": 2,
            "successful_requests": 2,
            "cost": {
                "total_prompt_tokens": 25,
                "total_completion_tokens": 150,
                "total_tokens": 175,
                "estimated_cost_usd": 0.001,
            },
        },
        "baseline": {
            "endpoint": "baseline:gpt-5",
            "total_requests": 2,
            "successful_requests": 2,
            "cost": {
                "total_prompt_tokens": 25,
                "total_completion_tokens": 200,
                "total_tokens": 225,
                "estimated_cost_usd": 0.005,
            },
        },
    }

    path = tmp_path / "results.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


@pytest.fixture
def mock_openai_client():
    """Create a mocked OpenAI client with evals API."""
    client = MagicMock()

    # Mock file upload
    uploaded_file = MagicMock()
    uploaded_file.id = "file-abc123"
    client.files.create.return_value = uploaded_file

    # Mock eval creation
    eval_obj = MagicMock()
    eval_obj.id = "eval-abc123"
    client.evals.create.return_value = eval_obj

    # Mock run creation
    run = MagicMock()
    run.id = "run-abc123"
    run.status = "completed"
    run.report_url = "https://portal.azure.com/eval/run-abc123"
    client.evals.runs.create.return_value = run
    client.evals.runs.retrieve.return_value = run

    # Mock output items
    output_item = MagicMock()
    output_item.model_dump.return_value = {
        "results": {
            "quality_pairwise": {"score": 4.0, "passed": True},
            "quality_absolute_router": {"score": 4.0, "passed": True},
            "quality_absolute_baseline": {"score": 3.0, "passed": True},
        }
    }
    client.evals.runs.output_items.list.return_value = [output_item]

    return client


@pytest.fixture
def mock_project_client():
    """Create a mocked AIProjectClient."""
    client = MagicMock()
    evaluator = MagicMock()
    evaluator.id = "evaluator-abc123"
    client.beta.evaluators.create_version.return_value = evaluator
    return client


# ── 5-prompt fixture-file based fixtures ─────────────────────────────────────

@pytest.fixture
def fixture_input_dir(tmp_path):
    """Copy the pre-built fixture files into a tmp_path directory.

    Returns the tmp_path directory containing raw_results.jsonl,
    results.json, and sample_dataset.jsonl — ready for the Foundry
    pipeline without running live benchmarking.
    """
    for name in ("raw_results.jsonl", "results.json", "sample_dataset.jsonl"):
        src = FIXTURES_DIR / name
        dst = tmp_path / name
        shutil.copy2(src, dst)
    return tmp_path
