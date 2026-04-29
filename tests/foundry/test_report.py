"""Tests for src/foundry/report.py — report generation."""

from __future__ import annotations

import json

from src.foundry.client import EvalRunResult
from src.foundry.report import generate_foundry_report


def _make_result_list_format(
    report_url="https://portal.azure.com/eval/run-123",
    output_items=None,
    result_counts=None,
):
    """Helper to build an EvalRunResult with list-format results (live API)."""
    if output_items is None:
        output_items = [
            {
                "datasource_item": {"prompt_id": "p001"},
                "results": [
                    {"name": "quality_absolute_router", "score": 4.0, "passed": True},
                    {"name": "quality_absolute_baseline", "score": 3.0, "passed": True},
                    {"name": "quality_pairwise", "score": 4.0, "passed": True},
                    {"name": "mr_cost_comparison", "score": 0.7, "passed": True},
                    {"name": "mr_latency_comparison", "score": 0.6, "passed": True},
                ],
            },
            {
                "datasource_item": {"prompt_id": "p002"},
                "results": [
                    {"name": "quality_absolute_router", "score": 5.0, "passed": True},
                    {"name": "quality_absolute_baseline", "score": 2.0, "passed": False},
                    {"name": "quality_pairwise", "score": 5.0, "passed": True},
                    {"name": "mr_cost_comparison", "score": 0.3, "passed": False},
                    {"name": "mr_latency_comparison", "score": 0.8, "passed": True},
                ],
            },
        ]
    return EvalRunResult(
        eval_id="eval-abc",
        run_id="run-abc",
        status="completed",
        report_url=report_url,
        output_items=output_items,
        result_counts=result_counts or {},
    )


def _make_result_dict_format(
    report_url="https://portal.azure.com/eval/run-123",
    output_items=None,
    result_counts=None,
):
    """Helper to build an EvalRunResult with dict-format results (legacy/mock)."""
    if output_items is None:
        output_items = [
            {
                "results": {
                    "quality_absolute_router": {"score": 4.0, "passed": True},
                    "quality_absolute_baseline": {"score": 3.0, "passed": True},
                    "quality_pairwise": {"score": 4.0, "passed": True},
                    "mr_cost_comparison": {"score": 0.7, "passed": True},
                    "mr_latency_comparison": {"score": 0.6, "passed": True},
                }
            },
            {
                "results": {
                    "quality_absolute_router": {"score": 5.0, "passed": True},
                    "quality_absolute_baseline": {"score": 2.0, "passed": False},
                    "quality_pairwise": {"score": 5.0, "passed": True},
                    "mr_cost_comparison": {"score": 0.3, "passed": False},
                    "mr_latency_comparison": {"score": 0.8, "passed": True},
                }
            },
        ]
    return EvalRunResult(
        eval_id="eval-abc",
        run_id="run-abc",
        status="completed",
        report_url=report_url,
        output_items=output_items,
        result_counts=result_counts or {},
    )


class TestGenerateFoundryReport:
    def test_generates_markdown(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["markdown"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        md_path = tmp_path / "report.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "# Foundry Cloud Evaluation Report" in content
        assert "eval-abc" in content
        assert "run-abc" in content

    def test_markdown_contains_grader_table(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["markdown"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "quality_absolute_router" in content
        assert "quality_pairwise" in content
        assert "mr_cost_comparison" in content
        assert "mr_latency_comparison" in content

    def test_markdown_includes_portal_link(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["markdown"]
        result = _make_result_list_format(report_url="https://portal.azure.com/eval/run-123")

        generate_foundry_report(result, foundry_config, tmp_path)

        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "https://portal.azure.com/eval/run-123" in content

    def test_markdown_no_portal_link(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["markdown"]
        result = _make_result_list_format(report_url=None)

        generate_foundry_report(result, foundry_config, tmp_path)

        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "Portal" not in content

    def test_generates_json(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["json"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        json_path = tmp_path / "results.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["eval_id"] == "eval-abc"
        assert data["run_id"] == "run-abc"
        assert data["status"] == "completed"

    def test_json_grader_summary_list_format(self, tmp_path, foundry_config):
        """Grader summary works with live API list-format results."""
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["json"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        summary = data["grader_summary"]

        # quality_absolute_router: scores [4.0, 5.0] → mean 4.5
        assert summary["quality_absolute_router"]["mean"] == 4.5
        assert summary["quality_absolute_router"]["count"] == 2
        assert summary["quality_absolute_router"]["pass_rate"] == 100.0

        # quality_absolute_baseline: scores [3.0, 2.0] → mean 2.5, 1 pass / 2 = 50%
        assert summary["quality_absolute_baseline"]["mean"] == 2.5
        assert summary["quality_absolute_baseline"]["pass_rate"] == 50.0

        # mr_cost_comparison: scores [0.7, 0.3] → mean 0.5, 1 pass / 2 = 50%
        assert summary["mr_cost_comparison"]["mean"] == 0.5
        assert summary["mr_cost_comparison"]["pass_rate"] == 50.0

    def test_json_grader_summary_dict_format(self, tmp_path, foundry_config):
        """Grader summary works with legacy dict-format results."""
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["json"]
        result = _make_result_dict_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        summary = data["grader_summary"]

        assert summary["quality_absolute_router"]["mean"] == 4.5
        assert summary["mr_cost_comparison"]["mean"] == 0.5

    def test_json_per_item_scores(self, tmp_path, foundry_config):
        """JSON output includes per-item scores for cross-validation."""
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["json"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        per_item = data["per_item_scores"]

        assert len(per_item) == 2
        assert per_item[0]["prompt_id"] == "p001"
        assert per_item[1]["prompt_id"] == "p002"
        assert per_item[0]["scores"]["quality_absolute_router"]["score"] == 4.0
        assert per_item[1]["scores"]["mr_cost_comparison"]["passed"] is False

    def test_json_output_items_count(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["json"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        assert data["output_items_count"] == 2

    def test_both_formats(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["markdown", "json"]
        result = _make_result_list_format()

        generate_foundry_report(result, foundry_config, tmp_path)

        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "results.json").exists()

    def test_empty_output_items(self, tmp_path, foundry_config):
        foundry_config.output.directory = str(tmp_path)
        foundry_config.output.formats = ["markdown", "json"]
        result = _make_result_list_format(output_items=[])

        generate_foundry_report(result, foundry_config, tmp_path)

        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "No grader results available" in content

        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        assert data["grader_summary"] == {}
        assert data["output_items_count"] == 0
        assert data["per_item_scores"] == []
