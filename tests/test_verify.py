"""Tests for src.verify — post-eval output verification."""

from __future__ import annotations

import json
from pathlib import Path


from src.verify import VerifyResult, verify_foundry_eval, verify_local_eval


# ── Helpers ──────────────────────────────────────────────────────────


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_local_results() -> dict:
    """Minimal valid local results.json."""
    return {
        "model_router": {
            "total_requests": 10,
            "successful_requests": 10,
            "error_count": 0,
            "cost": {"estimated_cost_usd": 0.005},
            "latency": {"mean_ms": 1200.0},
        },
        "baseline": {
            "total_requests": 10,
            "successful_requests": 10,
            "error_count": 0,
            "cost": {"estimated_cost_usd": 0.065},
            "latency": {"mean_ms": 2400.0},
        },
    }


def _make_foundry_results() -> dict:
    """Minimal valid Foundry results.json."""
    return {
        "eval_id": "eval_abc123",
        "run_id": "evalrun_xyz789",
        "status": "completed",
        "result_counts": {"total": 10, "passed": 8, "failed": 2, "errored": 0},
        "grader_summary": {
            "quality_absolute_router": {"mean": 4.2, "pass_rate": 90.0, "count": 10},
        },
        "per_item_scores": [{"prompt_id": f"p{i}", "scores": {}} for i in range(10)],
    }


# ── VerifyResult unit tests ─────────────────────────────────────────


class TestVerifyResult:
    def test_all_pass(self):
        vr = VerifyResult("test")
        vr.ok("check 1")
        vr.ok("check 2")
        assert vr.passed is True
        assert vr.passed_count == 2
        assert vr.failed_count == 0

    def test_one_failure(self):
        vr = VerifyResult("test")
        vr.ok("good")
        vr.fail("bad")
        assert vr.passed is False
        assert vr.passed_count == 1
        assert vr.failed_count == 1

    def test_empty_is_pass(self):
        vr = VerifyResult("test")
        assert vr.passed is True

    def test_print_summary(self):
        import io

        vr = VerifyResult("demo")
        vr.ok("a")
        vr.fail("b")
        buf = io.StringIO()
        vr.print_summary(file=buf)
        out = buf.getvalue()
        assert "demo" in out
        assert "a" in out
        assert "b" in out
        assert "1/2 checks FAILED" in out


# ── verify_local_eval ────────────────────────────────────────────────


class TestVerifyLocalEval:
    def test_full_pass(self, tmp_path):
        _write_json(tmp_path / "results.json", _make_local_results())
        _write_text(tmp_path / "report.md", "# Report")
        _write_text(tmp_path / "dashboard.html", "<html></html>")
        _write_text(tmp_path / "raw_results.jsonl", '{"a":1}\n{"b":2}\n')

        vr = verify_local_eval(tmp_path)
        assert vr.passed is True
        assert vr.failed_count == 0

    def test_missing_results_json(self, tmp_path):
        vr = verify_local_eval(tmp_path)
        assert vr.passed is False
        assert any("not found" in msg for _, msg in vr.checks)

    def test_invalid_json(self, tmp_path):
        (tmp_path / "results.json").write_text("{bad json", encoding="utf-8")
        vr = verify_local_eval(tmp_path)
        assert vr.passed is False

    def test_high_error_rate(self, tmp_path):
        data = _make_local_results()
        data["model_router"]["error_count"] = 8
        data["model_router"]["successful_requests"] = 2
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")
        _write_text(tmp_path / "dashboard.html", "<html></html>")
        _write_text(tmp_path / "raw_results.jsonl", '{"a":1}\n')

        vr = verify_local_eval(tmp_path)
        assert vr.passed is False
        assert any("error rate" in msg.lower() for _, msg in vr.checks)

    def test_missing_report_files(self, tmp_path):
        _write_json(tmp_path / "results.json", _make_local_results())
        _write_text(tmp_path / "raw_results.jsonl", '{"a":1}\n')
        # No report.md or dashboard.html

        vr = verify_local_eval(tmp_path)
        assert vr.passed is False
        assert vr.failed_count == 2  # report.md + dashboard.html

    def test_zero_requests(self, tmp_path):
        data = _make_local_results()
        data["model_router"]["total_requests"] = 0
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")
        _write_text(tmp_path / "dashboard.html", "<html></html>")
        _write_text(tmp_path / "raw_results.jsonl", '{"a":1}\n')

        vr = verify_local_eval(tmp_path)
        assert vr.passed is False
        assert any("no requests" in msg for _, msg in vr.checks)

    def test_some_errors_below_threshold(self, tmp_path):
        data = _make_local_results()
        data["baseline"]["error_count"] = 1
        data["baseline"]["successful_requests"] = 9
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")
        _write_text(tmp_path / "dashboard.html", "<html></html>")
        _write_text(tmp_path / "raw_results.jsonl", '{"a":1}\n')

        vr = verify_local_eval(tmp_path)
        assert vr.passed is True  # 10% error rate is below 20% threshold


# ── verify_foundry_eval ──────────────────────────────────────────────


class TestVerifyFoundryEval:
    def test_full_pass(self, tmp_path):
        _write_json(tmp_path / "results.json", _make_foundry_results())
        _write_text(tmp_path / "report.md", "# Foundry Report")

        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is True
        assert vr.failed_count == 0

    def test_missing_results_json(self, tmp_path):
        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is False

    def test_non_completed_status(self, tmp_path):
        data = _make_foundry_results()
        data["status"] = "failed"
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")

        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is False
        assert any("failed" in msg for _, msg in vr.checks)

    def test_high_error_rate(self, tmp_path):
        data = _make_foundry_results()
        data["result_counts"]["errored"] = 8
        data["result_counts"]["passed"] = 2
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")

        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is False
        assert any("error rate" in msg.lower() for _, msg in vr.checks)

    def test_empty_grader_summary(self, tmp_path):
        data = _make_foundry_results()
        data["grader_summary"] = {}
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")

        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is False

    def test_missing_per_item_scores(self, tmp_path):
        data = _make_foundry_results()
        del data["per_item_scores"]
        _write_json(tmp_path / "results.json", data)
        _write_text(tmp_path / "report.md", "# Report")

        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is False

    def test_missing_report(self, tmp_path):
        _write_json(tmp_path / "results.json", _make_foundry_results())
        # No report.md

        vr = verify_foundry_eval(tmp_path)
        assert vr.passed is False
        assert any("report.md" in msg for _, msg in vr.checks)
