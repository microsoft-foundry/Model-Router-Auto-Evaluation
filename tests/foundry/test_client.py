"""Tests for src/foundry/client.py — polling, results, and error paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.foundry.client import EvalRunResult, FoundryEvalClient


class TestPollRun:
    """Test poll_run with mocked OpenAI evals API."""

    def _make_client_with_mock(self):
        """Create a FoundryEvalClient with a mocked openai_client."""
        client = FoundryEvalClient(
            project_endpoint="https://test.services.ai.azure.com",
            model_deployment_name="gpt-5",
        )
        mock_openai = MagicMock()
        client._openai_client = mock_openai
        return client, mock_openai

    @patch("src.foundry.client.time.sleep", return_value=None)
    def test_poll_run_completed(self, mock_sleep):
        """Poll returns 'completed' when run finishes."""
        client, mock_openai = self._make_client_with_mock()

        # Simulate: first call running, second call completed
        run_running = MagicMock()
        run_running.status = "running"
        run_completed = MagicMock()
        run_completed.status = "completed"
        mock_openai.evals.runs.retrieve.side_effect = [run_running, run_completed]

        status = client.poll_run("eval-1", "run-1", poll_interval=1.0)
        assert status == "completed"
        assert mock_openai.evals.runs.retrieve.call_count == 2

    @patch("src.foundry.client.time.sleep", return_value=None)
    def test_poll_run_failed(self, mock_sleep):
        """Poll returns 'failed' when run fails."""
        client, mock_openai = self._make_client_with_mock()

        run_failed = MagicMock()
        run_failed.status = "failed"
        mock_openai.evals.runs.retrieve.return_value = run_failed

        status = client.poll_run("eval-1", "run-1", poll_interval=1.0)
        assert status == "failed"
        assert mock_openai.evals.runs.retrieve.call_count == 1

    @patch("src.foundry.client.time.sleep", return_value=None)
    def test_poll_run_cancelled(self, mock_sleep):
        """Poll returns 'cancelled' when run is cancelled."""
        client, mock_openai = self._make_client_with_mock()

        run_cancelled = MagicMock()
        run_cancelled.status = "cancelled"
        mock_openai.evals.runs.retrieve.return_value = run_cancelled

        status = client.poll_run("eval-1", "run-1", poll_interval=1.0)
        assert status == "cancelled"

    @patch("src.foundry.client.time.sleep", return_value=None)
    def test_poll_run_timeout(self, mock_sleep):
        """Poll returns 'timeout' when max_wait is exceeded."""
        client, mock_openai = self._make_client_with_mock()

        run_running = MagicMock()
        run_running.status = "running"
        mock_openai.evals.runs.retrieve.return_value = run_running

        # max_wait=3, poll_interval=1 → 3 polls then timeout
        status = client.poll_run("eval-1", "run-1", poll_interval=1.0, max_wait=3.0)
        assert status == "timeout"
        assert mock_openai.evals.runs.retrieve.call_count == 3


class TestGetResults:
    def test_get_results_builds_eval_run_result(self):
        """get_results should return a properly populated EvalRunResult."""
        client = FoundryEvalClient(
            project_endpoint="https://test.services.ai.azure.com",
            model_deployment_name="gpt-5",
        )
        mock_openai = MagicMock()
        client._openai_client = mock_openai

        # Mock run retrieval
        run = MagicMock()
        run.status = "completed"
        run.report_url = "https://portal.azure.com/eval/run-1"
        run.result_counts = {"passed": 3, "failed": 1}
        mock_openai.evals.runs.retrieve.return_value = run

        # Mock output items
        item = MagicMock()
        item.model_dump.return_value = {
            "results": {"quality_pairwise": {"score": 4.0, "passed": True}}
        }
        mock_openai.evals.runs.output_items.list.return_value = [item]

        result = client.get_results("eval-1", "run-1")

        assert isinstance(result, EvalRunResult)
        assert result.eval_id == "eval-1"
        assert result.run_id == "run-1"
        assert result.status == "completed"
        assert result.report_url == "https://portal.azure.com/eval/run-1"
        assert len(result.output_items) == 1
        assert result.result_counts == {"passed": 3, "failed": 1}


class TestRegisterEvaluator:
    def test_register_evaluator_calls_sdk(self):
        """register_evaluator should call project_client.beta.evaluators.create_version."""
        client = FoundryEvalClient(
            project_endpoint="https://test.services.ai.azure.com",
            model_deployment_name="gpt-5",
        )
        mock_project = MagicMock()
        evaluator = MagicMock()
        evaluator.id = "custom-eval-123"
        mock_project.beta.evaluators.create_version.return_value = evaluator
        client._project_client = mock_project

        result = client.register_evaluator(
            evaluator_name="test_evaluator",
            code="def grade(sample, item): return 0.5",
            deployment_name="gpt-5",
            pass_threshold=0.5,
        )

        assert result == "custom-eval-123"
        mock_project.beta.evaluators.create_version.assert_called_once()


class TestNotConnected:
    def test_openai_client_raises_when_not_connected(self):
        """Accessing openai_client before connect() should raise RuntimeError."""
        client = FoundryEvalClient(
            project_endpoint="https://test.services.ai.azure.com",
            model_deployment_name="gpt-5",
        )
        import pytest
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = client.openai_client

    def test_project_client_raises_when_not_connected(self):
        """Accessing project_client before connect() should raise RuntimeError."""
        client = FoundryEvalClient(
            project_endpoint="https://test.services.ai.azure.com",
            model_deployment_name="gpt-5",
        )
        import pytest
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = client.project_client
