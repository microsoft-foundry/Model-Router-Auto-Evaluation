"""Tests for src/foundry/custom_evaluators.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.foundry.custom_evaluators import (
    COST_EVALUATOR_CODE,
    LATENCY_EVALUATOR_CODE,
    get_evaluator_code,
    register_custom_evaluators,
)


class TestEvaluatorCode:
    def test_cost_code_returns_float(self):
        """Verify cost evaluator code is valid and produces expected results."""
        namespace = {}
        exec(COST_EVALUATOR_CODE, namespace)
        grade = namespace["grade"]

        # Router cheaper than baseline
        score = grade(None, {"router_cost_usd": 0.003, "baseline_cost_usd": 0.005})
        assert 0.5 < score <= 1.0

        # Parity
        score = grade(None, {"router_cost_usd": 0.005, "baseline_cost_usd": 0.005})
        assert score == 0.5

        # Router more expensive
        score = grade(None, {"router_cost_usd": 0.008, "baseline_cost_usd": 0.005})
        assert 0.0 <= score < 0.5

        # Zero baseline
        score = grade(None, {"router_cost_usd": 0.003, "baseline_cost_usd": 0.0})
        assert score == 0.5

    def test_latency_code_returns_float(self):
        """Verify latency evaluator code is valid and produces expected results."""
        namespace = {}
        exec(LATENCY_EVALUATOR_CODE, namespace)
        grade = namespace["grade"]

        # Router faster
        score = grade(None, {"router_latency_ms": 500, "baseline_latency_ms": 1200})
        assert 0.5 < score <= 1.0

        # Parity
        score = grade(None, {"router_latency_ms": 1000, "baseline_latency_ms": 1000})
        assert score == 0.5

        # Router slower
        score = grade(None, {"router_latency_ms": 1500, "baseline_latency_ms": 1000})
        assert 0.0 <= score < 0.5

    def test_scores_clamped(self):
        """Verify scores are clamped to [0.0, 1.0]."""
        namespace = {}
        exec(COST_EVALUATOR_CODE, namespace)
        grade = namespace["grade"]

        # Extreme: router cost is 10x baseline — would produce negative without clamping
        score = grade(None, {"router_cost_usd": 0.05, "baseline_cost_usd": 0.005})
        assert score >= 0.0
        assert score <= 1.0

    def test_latency_scores_clamped(self):
        """Verify latency scores are clamped for extreme ratios."""
        namespace = {}
        exec(LATENCY_EVALUATOR_CODE, namespace)
        grade = namespace["grade"]

        # Extreme: router 100x slower than baseline
        score = grade(None, {"router_latency_ms": 100000, "baseline_latency_ms": 1000})
        assert score == 0.0

        # Extreme: router near-instant, baseline very slow
        score = grade(None, {"router_latency_ms": 1, "baseline_latency_ms": 100000})
        assert score <= 1.0
        assert score > 0.9

    def test_cost_evaluator_against_fixture_data(self):
        """Run cost evaluator against realistic fixture data rows."""
        namespace = {}
        exec(COST_EVALUATOR_CODE, namespace)
        grade = namespace["grade"]

        # tp001: router cheaper (65 tokens cheap model vs 95 tokens expensive model)
        score = grade(None, {"router_cost_usd": 0.00006, "baseline_cost_usd": 0.00095})
        assert score > 0.5  # router wins on cost

        # tp004: router more expensive scenario
        score = grade(None, {"router_cost_usd": 0.0010, "baseline_cost_usd": 0.0005})
        assert score < 0.5  # baseline wins on cost

    def test_latency_evaluator_against_fixture_data(self):
        """Run latency evaluator against realistic fixture data rows."""
        namespace = {}
        exec(LATENCY_EVALUATOR_CODE, namespace)
        grade = namespace["grade"]

        # tp001: router faster (450ms vs 1200ms)
        score = grade(None, {"router_latency_ms": 450.0, "baseline_latency_ms": 1200.0})
        assert score > 0.5  # router wins

        # tp004: router slower (8000ms vs 900ms)
        score = grade(None, {"router_latency_ms": 8000.0, "baseline_latency_ms": 900.0})
        assert score < 0.5  # baseline wins

    def test_get_evaluator_code(self):
        assert get_evaluator_code("cost") == COST_EVALUATOR_CODE
        assert get_evaluator_code("latency") == LATENCY_EVALUATOR_CODE

    def test_get_evaluator_code_invalid(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown evaluator type"):
            get_evaluator_code("invalid")


class TestRegisterCustomEvaluators:
    def test_registers_both_evaluators(self, mock_project_client):
        client = MagicMock()
        client.register_evaluator.return_value = "eval-id"

        result = register_custom_evaluators(
            client=client,
            model_deployment="gpt-5",
        )

        assert "cost" in result
        assert "latency" in result
        assert client.register_evaluator.call_count == 2
