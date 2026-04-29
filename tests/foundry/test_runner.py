"""Tests for src/foundry/runner.py — integration tests with mocked SDK."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.foundry.client import EvalRunResult
from src.foundry.runner import run_foundry_eval


class TestRunFoundryEvalDryRun:
    def test_dry_run_transforms_data(
        self, tmp_path, foundry_config, sample_raw_results, sample_results_json
    ):
        """Dry run should transform data without calling Foundry API."""
        # Update config output dir
        foundry_config.output.directory = str(tmp_path / "output")

        result = run_foundry_eval(
            config=foundry_config,
            input_dir=tmp_path,
            dry_run=True,
        )

        assert result is None
        # Check JSONL was created
        foundry_jsonl = Path(foundry_config.output.directory) / "foundry_input.jsonl"
        assert foundry_jsonl.exists()

    def test_dry_run_missing_raw_results(self, tmp_path, foundry_config):
        """Should raise when raw_results.jsonl is missing."""
        foundry_config.output.directory = str(tmp_path / "output")

        with pytest.raises(FileNotFoundError, match="raw_results.jsonl"):
            run_foundry_eval(
                config=foundry_config,
                input_dir=tmp_path,
                dry_run=True,
            )


class TestRunFoundryEvalLive:
    @patch("src.foundry.runner.FoundryEvalClient")
    def test_full_run_with_mocked_client(
        self,
        MockClient,
        tmp_path,
        foundry_config,
        sample_raw_results,
        sample_results_json,
        mock_openai_client,
        mock_project_client,
    ):
        """Full run with mocked SDK should complete successfully."""
        foundry_config.output.directory = str(tmp_path / "output")

        # Setup mock client
        client_instance = MagicMock()
        MockClient.return_value = client_instance
        client_instance._openai_client = mock_openai_client
        client_instance._project_client = mock_project_client

        # Wire through client methods to use our mock
        client_instance.upload_file.return_value = "file-123"
        client_instance.create_eval.return_value = "eval-123"
        client_instance.create_run.return_value = "run-123"
        client_instance.poll_run.return_value = "completed"

        mock_result = EvalRunResult(
            eval_id="eval-123",
            run_id="run-123",
            status="completed",
            report_url="https://portal.azure.com/eval/run-123",
            output_items=[{
                "results": {
                    "quality_pairwise": {"score": 4.0, "passed": True},
                }
            }],
        )
        client_instance.get_results.return_value = mock_result

        result = run_foundry_eval(
            config=foundry_config,
            input_dir=tmp_path,
        )

        assert result is not None
        assert result.status == "completed"
        client_instance.connect.assert_called_once()
        client_instance.upload_file.assert_called_once()
        client_instance.create_eval.assert_called_once()
        client_instance.create_run.assert_called_once()


class TestRunFoundryEvalFixtures:
    """Tests using the 5-prompt pre-built fixture files."""

    def test_dry_run_five_prompts(self, fixture_input_dir, foundry_config):
        """Dry run with 5-prompt fixtures creates JSONL with 5 records."""
        foundry_config.output.directory = str(fixture_input_dir / "output")

        result = run_foundry_eval(
            config=foundry_config,
            input_dir=fixture_input_dir,
            dry_run=True,
        )

        assert result is None
        foundry_jsonl = Path(foundry_config.output.directory) / "foundry_input.jsonl"
        assert foundry_jsonl.exists()
        with open(foundry_jsonl) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 5

    def test_dry_run_with_dataset_enrichment(self, fixture_input_dir, foundry_config):
        """Dry run with dataset path enriches prompt text."""
        import json

        foundry_config.output.directory = str(fixture_input_dir / "output")
        dataset_path = fixture_input_dir / "sample_dataset.jsonl"

        run_foundry_eval(
            config=foundry_config,
            input_dir=fixture_input_dir,
            dataset_path=dataset_path,
            dry_run=True,
        )

        foundry_jsonl = Path(foundry_config.output.directory) / "foundry_input.jsonl"
        with open(foundry_jsonl) as f:
            rec = json.loads(f.readline())
        # Should have real prompt text, not just the ID
        assert len(rec["prompt"]) > 10

    @patch("src.foundry.runner.FoundryEvalClient")
    def test_skip_quality_reduces_criteria(
        self, MockClient, fixture_input_dir, foundry_config
    ):
        """--skip-quality should produce only 2 criteria (cost + latency)."""
        foundry_config.output.directory = str(fixture_input_dir / "output")

        client_instance = MagicMock()
        MockClient.return_value = client_instance
        client_instance.upload_file.return_value = "file-123"
        client_instance.create_eval.return_value = "eval-123"
        client_instance.create_run.return_value = "run-123"
        client_instance.poll_run.return_value = "completed"
        client_instance.get_results.return_value = EvalRunResult(
            eval_id="eval-123", run_id="run-123", status="completed",
        )

        run_foundry_eval(
            config=foundry_config,
            input_dir=fixture_input_dir,
            skip_quality=True,
        )

        # create_eval should receive exactly 2 criteria (cost + latency)
        call_args = client_instance.create_eval.call_args
        criteria = call_args.kwargs.get("testing_criteria") or call_args[1].get("testing_criteria")
        assert len(criteria) == 2

    @patch("src.foundry.runner.FoundryEvalClient")
    def test_skip_custom_reduces_criteria(
        self, MockClient, fixture_input_dir, foundry_config
    ):
        """--skip-custom should produce only 3 criteria (quality graders)."""
        foundry_config.output.directory = str(fixture_input_dir / "output")

        client_instance = MagicMock()
        MockClient.return_value = client_instance
        client_instance.upload_file.return_value = "file-123"
        client_instance.create_eval.return_value = "eval-123"
        client_instance.create_run.return_value = "run-123"
        client_instance.poll_run.return_value = "completed"
        client_instance.get_results.return_value = EvalRunResult(
            eval_id="eval-123", run_id="run-123", status="completed",
        )

        run_foundry_eval(
            config=foundry_config,
            input_dir=fixture_input_dir,
            skip_custom=True,
        )

        # create_eval should receive exactly 3 criteria (quality only)
        call_args = client_instance.create_eval.call_args
        criteria = call_args.kwargs.get("testing_criteria") or call_args[1].get("testing_criteria")
        assert len(criteria) == 3

    @patch("src.foundry.runner.FoundryEvalClient")
    def test_full_run_call_sequence(
        self, MockClient, fixture_input_dir, foundry_config
    ):
        """Full run should call SDK methods in correct order with 5 criteria."""
        foundry_config.output.directory = str(fixture_input_dir / "output")

        client_instance = MagicMock()
        MockClient.return_value = client_instance
        client_instance.upload_file.return_value = "file-123"
        client_instance.create_eval.return_value = "eval-123"
        client_instance.create_run.return_value = "run-123"
        client_instance.poll_run.return_value = "completed"
        client_instance.get_results.return_value = EvalRunResult(
            eval_id="eval-123", run_id="run-123", status="completed",
            output_items=[{"results": {"quality_pairwise": {"score": 4.0, "passed": True}}}],
        )

        result = run_foundry_eval(
            config=foundry_config,
            input_dir=fixture_input_dir,
        )

        assert result.status == "completed"
        # Verify full call sequence
        client_instance.connect.assert_called_once()
        client_instance.upload_file.assert_called_once()
        client_instance.create_eval.assert_called_once()
        client_instance.create_run.assert_called_once()
        client_instance.poll_run.assert_called_once()
        client_instance.get_results.assert_called_once()

        # Should have 5 criteria total: 3 quality + 1 cost + 1 latency
        call_args = client_instance.create_eval.call_args
        criteria = call_args.kwargs.get("testing_criteria") or call_args[1].get("testing_criteria")
        assert len(criteria) == 5
