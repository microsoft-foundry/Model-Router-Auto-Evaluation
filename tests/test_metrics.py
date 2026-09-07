"""Tests for src/metrics.py — cost and latency aggregation."""


from src.config import PricingConfig
from src.metrics import compute_metrics, _compute_latency_stats, _compute_cost_stats
from tests.conftest import make_completion_result


class TestLatencyStats:
    def test_basic_stats(self):
        results = [
            make_completion_result(prompt_id=f"p{i}", latency_ms=float(i * 100))
            for i in range(1, 11)  # 100ms to 1000ms
        ]
        stats = _compute_latency_stats(results)
        assert stats is not None
        assert stats.count == 10
        assert stats.mean_ms == 550.0
        assert stats.min_ms == 100.0
        assert stats.max_ms == 1000.0

    def test_empty_results(self):
        stats = _compute_latency_stats([])
        assert stats is None

    def test_skips_errors(self):
        results = [
            make_completion_result(prompt_id="p1", latency_ms=100.0, status="success"),
            make_completion_result(prompt_id="p2", latency_ms=9999.0, status="error"),
        ]
        stats = _compute_latency_stats(results)
        assert stats is not None
        assert stats.count == 1
        assert stats.mean_ms == 100.0


class TestCostStats:
    def test_cost_calculation(self):
        results = [
            make_completion_result(
                prompt_id="p1",
                prompt_tokens=1000,
                completion_tokens=500,
            ),
        ]
        pricing = PricingConfig(input=2.50, output=10.00)
        stats = _compute_cost_stats(results, pricing)
        assert stats is not None
        assert stats.total_prompt_tokens == 1000
        assert stats.total_completion_tokens == 500
        assert stats.total_tokens == 1500
        # (1000/1M * 2.50) + (500/1M * 10.00) = 0.0025 + 0.005 = 0.0075
        assert abs(stats.estimated_cost_usd - 0.0075) < 0.0001

    def test_no_pricing(self):
        results = [make_completion_result(prompt_id="p1")]
        stats = _compute_cost_stats(results, None)
        assert stats is not None
        assert stats.estimated_cost_usd == 0.0

    def test_empty_results(self):
        pricing = PricingConfig(input=2.50, output=10.00)
        stats = _compute_cost_stats([], pricing)
        assert stats is None

    def test_includes_billable_tokens_from_error_results(self):
        results = [
            make_completion_result(
                prompt_id="p1",
                prompt_tokens=100,
                completion_tokens=200,
                status="error",
            ),
        ]
        pricing = PricingConfig(input=2.50, output=10.00)

        stats = _compute_cost_stats(results, pricing)

        assert stats is not None
        assert stats.total_tokens == 300
        assert stats.estimated_cost_usd > 0


class TestComputeMetrics:
    def test_full_comparison(self):
        router_results = [
            make_completion_result(
                prompt_id=f"p{i}",
                endpoint="model_router",
                prompt_tokens=50,
                completion_tokens=100,
                latency_ms=200.0 + i * 10,
            )
            for i in range(5)
        ]
        baseline_results = [
            make_completion_result(
                prompt_id=f"p{i}",
                endpoint="baseline:gpt-4o",
                prompt_tokens=50,
                completion_tokens=100,
                latency_ms=400.0 + i * 10,
            )
            for i in range(5)
        ]
        pricing = {
            "model_router": PricingConfig(input=0.50, output=1.50),
            "gpt-4o": PricingConfig(input=2.50, output=10.00),
            "gpt-4o-mini": PricingConfig(input=0.15, output=0.60),
        }

        metrics = compute_metrics(router_results, baseline_results, pricing)

        assert metrics.model_router.total_requests == 5
        assert metrics.baseline.total_requests == 5
        assert metrics.comparison is not None
        # Router should be cheaper
        assert metrics.comparison.cost_savings_ratio > 0
        # Router should be faster
        assert metrics.comparison.latency_diff_mean_ms < 0

    def test_with_category_map(self):
        router_results = [
            make_completion_result(prompt_id="p1", endpoint="model_router", latency_ms=100),
            make_completion_result(prompt_id="p2", endpoint="model_router", latency_ms=200),
        ]
        baseline_results = [
            make_completion_result(prompt_id="p1", endpoint="baseline:gpt-4o", latency_ms=300),
            make_completion_result(prompt_id="p2", endpoint="baseline:gpt-4o", latency_ms=400),
        ]
        pricing = {
            "model_router": PricingConfig(input=0.50, output=1.50),
            "gpt-4o": PricingConfig(input=2.50, output=10.00),
        }
        category_map = {"p1": "code", "p2": "qa"}

        metrics = compute_metrics(router_results, baseline_results, pricing, category_map)

        assert "code" in metrics.model_router.latency_by_category
        assert "qa" in metrics.model_router.latency_by_category

    def test_handles_all_errors(self):
        router_results = [
            make_completion_result(prompt_id="p1", endpoint="model_router", status="error"),
        ]
        baseline_results = [
            make_completion_result(prompt_id="p1", endpoint="baseline:gpt-4o", status="error"),
        ]
        pricing = {"model_router": PricingConfig(input=0.5, output=1.5)}

        metrics = compute_metrics(router_results, baseline_results, pricing)
        assert metrics.model_router.error_count == 1
        assert metrics.model_router.latency is None
