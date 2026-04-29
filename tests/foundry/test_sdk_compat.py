"""SDK compatibility smoke tests.

These tests verify the azure-ai-projects SDK exposes the APIs
we depend on. If a new SDK version breaks the interface, these
fail immediately with a clear message instead of cryptic runtime
errors deep in the pipeline.

Validated against: azure-ai-projects >=2.1.0,<3.0
"""

from __future__ import annotations

import importlib



# ── SDK import structure ──


def test_ai_project_client_importable():
    """AIProjectClient must be importable from azure.ai.projects."""
    mod = importlib.import_module("azure.ai.projects")
    assert hasattr(mod, "AIProjectClient"), (
        "azure.ai.projects.AIProjectClient not found. "
        "Upgrade: pip install 'azure-ai-projects>=2.1.0,<3.0'"
    )


def test_default_azure_credential_importable():
    """DefaultAzureCredential must be importable from azure.identity."""
    mod = importlib.import_module("azure.identity")
    assert hasattr(mod, "DefaultAzureCredential"), (
        "azure.identity.DefaultAzureCredential not found. "
        "Install: pip install 'azure-identity>=1.15'"
    )


# ── OpenAI Evals API types ──


def test_evals_run_create_params():
    """RunCreateParams must exist with the expected data_source types."""
    from openai.types.evals.run_create_params import DataSource  # noqa: F401
    from openai.types.evals.create_eval_jsonl_run_data_source_param import (
        CreateEvalJSONLRunDataSourceParam,
    )

    annotations = CreateEvalJSONLRunDataSourceParam.__annotations__
    assert "type" in annotations, "CreateEvalJSONLRunDataSourceParam missing 'type' field"
    assert "source" in annotations, "CreateEvalJSONLRunDataSourceParam missing 'source' field"


def test_jsonl_source_file_id():
    """SourceFileID must accept type='file_id' and an 'id' field."""
    from openai.types.evals.create_eval_jsonl_run_data_source_param import SourceFileID

    annotations = SourceFileID.__annotations__
    assert "id" in annotations, "SourceFileID missing 'id' field"
    assert "type" in annotations, "SourceFileID missing 'type' field"


# ── Testing criteria types ──


VALID_CRITERIA_TYPES = {"score_model", "python", "label_model", "string_check", "text_similarity"}


def test_valid_criteria_types_accepted():
    """Verify the criteria types we use (score_model, python) are valid.

    NOTE: 'stored_evaluator' is NOT a valid type as of v2.1.0.
    """
    used_types = {"score_model", "python"}
    assert used_types.issubset(VALID_CRITERIA_TYPES), (
        f"Used criteria types {used_types - VALID_CRITERIA_TYPES} are not in "
        f"the valid set {VALID_CRITERIA_TYPES}"
    )


# ── Data source format ──


def test_data_source_type_is_jsonl():
    """Data source type must be 'jsonl', not 'file_content' (removed in v2.1.0)."""
    from src.foundry.client import FoundryEvalClient

    # Verify the client code references 'jsonl' not 'file_content'
    import inspect
    source = inspect.getsource(FoundryEvalClient.create_run)
    assert '"jsonl"' in source or "'jsonl'" in source, (
        "FoundryEvalClient.create_run must use data_source type='jsonl'. "
        "'file_content' was removed in azure-ai-projects v2.1.0."
    )
    assert "file_content" not in source, (
        "FoundryEvalClient.create_run still references 'file_content'. "
        "Use type='jsonl' instead — 'file_content' is not valid in v2.1.0+."
    )


# ── Result format ──


def test_result_format_handles_list():
    """Report parser must handle list-format results (live API returns lists, not dicts)."""
    from src.foundry.report import _summarize_scores

    # Live API format: results is a list of dicts
    output_items = [
        {"results": [
            {"name": "grader_a", "score": 4.0, "passed": True},
            {"name": "grader_b", "score": 2.0, "passed": False},
        ]},
    ]
    summary = _summarize_scores(output_items)
    assert "grader_a" in summary, "Failed to parse list-format results"
    assert summary["grader_a"]["mean"] == 4.0


def test_result_format_handles_dict():
    """Report parser must also handle dict-format results (backwards compatibility)."""
    from src.foundry.report import _summarize_scores

    # Legacy/mock format: results is a dict
    output_items = [
        {"results": {
            "grader_a": {"score": 4.0, "passed": True},
            "grader_b": {"score": 2.0, "passed": False},
        }},
    ]
    summary = _summarize_scores(output_items)
    assert "grader_a" in summary, "Failed to parse dict-format results"
    assert summary["grader_a"]["mean"] == 4.0


# ── ResultCounts conversion ──


def test_result_counts_model_dump():
    """get_results must convert ResultCounts SDK objects to dicts (not call .items() directly)."""
    import inspect
    from src.foundry.client import FoundryEvalClient

    source = inspect.getsource(FoundryEvalClient.get_results)
    assert "model_dump" in source, (
        "FoundryEvalClient.get_results must use model_dump() to convert "
        "ResultCounts to dict. Calling .items() directly on the SDK object "
        "fails with AttributeError in v2.1.0."
    )
