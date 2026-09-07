"""Cost, latency, and quality metrics aggregation."""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from .client import CompletionResult
from .config import PricingConfig

if TYPE_CHECKING:
    from .judge import JudgeResult


@dataclass
class LatencyStats:
    """Latency statistics for an endpoint."""
    count: int
    mean_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float


@dataclass
class CostStats:
    """Cost statistics for an endpoint."""
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    cost_per_prompt_avg_usd: float
    cost_per_prompt_p50_usd: float
    cost_per_prompt_p95_usd: float


@dataclass
class EndpointMetrics:
    """Aggregated metrics for a single endpoint."""
    endpoint: str
    total_requests: int
    successful_requests: int
    error_count: int
    timeout_count: int
    latency: Optional[LatencyStats]
    cost: Optional[CostStats]
    # Per-category latency breakdown
    latency_by_category: Dict[str, LatencyStats] = field(default_factory=dict)
    # Model distribution (model_name -> count) — useful for model router
    model_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class ComparisonMetrics:
    """Comparative metrics between model router and baseline."""
    cost_savings_ratio: float       # (baseline_cost - router_cost) / baseline_cost
    latency_diff_mean_ms: float     # router_mean - baseline_mean (negative = router faster)
    latency_diff_p50_ms: float


@dataclass
class ScoreStats:
    """Statistics for absolute scores (1-5 scale)."""
    mean: float
    median: float
    std: float
    min: float
    max: float
    count: int


@dataclass
class QualityMetrics:
    """Quality evaluation metrics."""
    # Pairwise win rates
    router_win_rate: float        # fraction of non-tie wins
    baseline_win_rate: float
    tie_rate: float
    router_wins: int
    baseline_wins: int
    ties: int
    total_judged: int

    # Absolute score summaries
    router_overall: Optional[ScoreStats] = None
    baseline_overall: Optional[ScoreStats] = None
    router_by_dimension: Dict[str, ScoreStats] = field(default_factory=dict)
    baseline_by_dimension: Dict[str, ScoreStats] = field(default_factory=dict)

    # Per-category pairwise
    win_rate_by_category: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Composite value scores
    router_value_score: Optional[float] = None    # quality / cost
    baseline_value_score: Optional[float] = None
    router_efficiency_score: Optional[float] = None  # quality / latency
    baseline_efficiency_score: Optional[float] = None

    # Confidence
    router_win_rate_ci: Optional[tuple] = None  # (lower, upper) 95% bootstrap CI


@dataclass
class EvalMetrics:
    """Complete evaluation metrics."""
    model_router: EndpointMetrics
    baseline: EndpointMetrics
    comparison: Optional[ComparisonMetrics]
    quality: Optional[QualityMetrics] = None


def _percentile(data: List[float], pct: float) -> float:
    """Calculate percentile from sorted data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _compute_latency_stats(results: List[CompletionResult]) -> Optional[LatencyStats]:
    """Compute latency statistics from successful results."""
    latencies = [r.latency_ms for r in results if r.status == "success"]
    if not latencies:
        return None

    return LatencyStats(
        count=len(latencies),
        mean_ms=round(statistics.mean(latencies), 2),
        median_ms=round(statistics.median(latencies), 2),
        p90_ms=round(_percentile(latencies, 90), 2),
        p95_ms=round(_percentile(latencies, 95), 2),
        p99_ms=round(_percentile(latencies, 99), 2),
        min_ms=round(min(latencies), 2),
        max_ms=round(max(latencies), 2),
    )


def _compute_cost_stats(
    results: List[CompletionResult],
    pricing: Optional[PricingConfig],
    all_pricing: Optional[Dict[str, PricingConfig]] = None,
    router_markup_pricing: Optional[PricingConfig] = None,
) -> Optional[CostStats]:
    """Compute cost statistics from results.

    For model router results, the total cost per request is:
        router_markup_input_price * input_tokens
        + underlying_LLM_input_price * input_tokens
        + underlying_LLM_output_price * output_tokens

    Args:
        results: Completion results to compute costs for.
        pricing: Default pricing for this endpoint (used for baseline).
        all_pricing: All pricing configs keyed by model name (for model router).
        router_markup_pricing: Model router markup pricing (input-only charge).
    """
    billable = [
        r for r in results
        if r.prompt_tokens > 0 or r.completion_tokens > 0 or r.total_tokens > 0
    ]
    if not billable:
        return None

    total_prompt_tokens = sum(r.prompt_tokens for r in billable)
    total_completion_tokens = sum(r.completion_tokens for r in billable)
    total_tokens = total_prompt_tokens + total_completion_tokens

    # Per-prompt costs
    per_prompt_costs = []
    for r in billable:
        cost = _compute_single_result_cost(r, pricing, all_pricing, router_markup_pricing)
        r.estimated_cost_usd = cost
        per_prompt_costs.append(cost)

    estimated_cost = sum(per_prompt_costs)

    return CostStats(
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=round(estimated_cost, 6),
        cost_per_prompt_avg_usd=round(statistics.mean(per_prompt_costs), 6) if per_prompt_costs else 0.0,
        cost_per_prompt_p50_usd=round(statistics.median(per_prompt_costs), 6) if per_prompt_costs else 0.0,
        cost_per_prompt_p95_usd=round(_percentile(per_prompt_costs, 95), 6) if per_prompt_costs else 0.0,
    )


def _compute_single_result_cost(
    r: CompletionResult,
    pricing: Optional[PricingConfig],
    all_pricing: Optional[Dict[str, PricingConfig]] = None,
    router_markup_pricing: Optional[PricingConfig] = None,
) -> float:
    """Compute cost for a single completion result.

    For model router: markup (input only) + underlying model (input + output).
    For baseline: simple input + output pricing.
    """
    if router_markup_pricing and all_pricing:
        # Model router cost formula:
        #   router_markup_input * input_tokens + LLM_input * input_tokens + LLM_output * output_tokens
        markup_cost = (r.prompt_tokens / 1_000_000) * router_markup_pricing.input
        # Find underlying model pricing by matching model_name against all_pricing keys
        llm_pricing = _resolve_model_pricing(r.model_name, all_pricing)
        if llm_pricing:
            llm_cost = (
                (r.prompt_tokens / 1_000_000) * llm_pricing.input
                + (r.completion_tokens / 1_000_000) * llm_pricing.output
            )
        else:
            llm_cost = 0.0
        return markup_cost + llm_cost
    elif pricing:
        return (
            (r.prompt_tokens / 1_000_000) * pricing.input
            + (r.completion_tokens / 1_000_000) * pricing.output
        )
    return 0.0


def _resolve_model_pricing(
    model_name: str,
    all_pricing: Dict[str, PricingConfig],
) -> Optional[PricingConfig]:
    """Resolve pricing for a model name, trying exact match then prefix match."""
    # Exact match
    if model_name in all_pricing:
        return all_pricing[model_name]
    # Try matching by prefix (e.g. "gpt-5-2025-08-07" matches "gpt-5")
    for key in sorted(all_pricing.keys(), key=len, reverse=True):
        if model_name.startswith(key):
            return all_pricing[key]
    return None


def _compute_endpoint_metrics(
    results: List[CompletionResult],
    pricing: Optional[PricingConfig],
    category_map: Optional[Dict[str, str]] = None,
    all_pricing: Optional[Dict[str, PricingConfig]] = None,
    router_markup_pricing: Optional[PricingConfig] = None,
) -> EndpointMetrics:
    """Compute aggregated metrics for one endpoint."""
    endpoint = results[0].endpoint if results else "unknown"
    successful = [r for r in results if r.status == "success"]
    errors = [r for r in results if r.status == "error"]
    timeouts = [r for r in results if r.status == "timeout"]

    latency = _compute_latency_stats(results)
    cost = _compute_cost_stats(results, pricing, all_pricing, router_markup_pricing)

    # Per-category latency breakdown
    latency_by_category: Dict[str, LatencyStats] = {}
    if category_map:
        category_results: Dict[str, List[CompletionResult]] = {}
        for r in results:
            cat = category_map.get(r.prompt_id, "uncategorized")
            category_results.setdefault(cat, []).append(r)

        for cat, cat_results in category_results.items():
            cat_latency = _compute_latency_stats(cat_results)
            if cat_latency:
                latency_by_category[cat] = cat_latency

    # Model distribution (which underlying models were used)
    model_distribution: Dict[str, int] = {}
    for r in successful:
        model_distribution[r.model_name] = model_distribution.get(r.model_name, 0) + 1

    return EndpointMetrics(
        endpoint=endpoint,
        total_requests=len(results),
        successful_requests=len(successful),
        error_count=len(errors),
        timeout_count=len(timeouts),
        latency=latency,
        cost=cost,
        latency_by_category=latency_by_category,
        model_distribution=model_distribution,
    )


def compute_metrics(
    router_results: List[CompletionResult],
    baseline_results: List[CompletionResult],
    pricing: Dict[str, PricingConfig],
    category_map: Optional[Dict[str, str]] = None,
) -> EvalMetrics:
    """Compute all evaluation metrics.

    Args:
        router_results: Results from model router endpoint.
        baseline_results: Results from baseline endpoint.
        pricing: Pricing configuration by endpoint/model name.
        category_map: Mapping of prompt_id -> category for per-category analysis.

    Returns:
        Complete EvalMetrics with per-endpoint and comparison metrics.
    """
    # Resolve pricing for each endpoint
    router_pricing = pricing.get("model_router")
    baseline_pricing = None
    # Try to match baseline pricing by deployment name from results
    if baseline_results:
        baseline_endpoint = baseline_results[0].endpoint
        # baseline endpoint is like "baseline:gpt-4o"
        model_name = baseline_endpoint.split(":")[-1] if ":" in baseline_endpoint else baseline_endpoint
        baseline_pricing = pricing.get(model_name, pricing.get("baseline"))

    # For model router: pass all pricing so we can compute per-request cost
    # based on the underlying model selected by the router.
    # router_markup_pricing = the model_router pricing entry (input-only markup).
    router_metrics = _compute_endpoint_metrics(
        router_results, router_pricing, category_map,
        all_pricing=pricing,
        router_markup_pricing=router_pricing,
    )
    baseline_metrics = _compute_endpoint_metrics(baseline_results, baseline_pricing, category_map)

    # Comparison metrics
    comparison = None
    if router_metrics.cost and baseline_metrics.cost:
        router_cost = router_metrics.cost.estimated_cost_usd
        baseline_cost = baseline_metrics.cost.estimated_cost_usd
        cost_savings = (
            (baseline_cost - router_cost) / baseline_cost
            if baseline_cost > 0
            else 0.0
        )

        latency_diff_mean = 0.0
        latency_diff_p50 = 0.0
        if router_metrics.latency and baseline_metrics.latency:
            latency_diff_mean = round(
                router_metrics.latency.mean_ms - baseline_metrics.latency.mean_ms, 2
            )
            latency_diff_p50 = round(
                router_metrics.latency.median_ms - baseline_metrics.latency.median_ms, 2
            )

        comparison = ComparisonMetrics(
            cost_savings_ratio=round(cost_savings, 4),
            latency_diff_mean_ms=latency_diff_mean,
            latency_diff_p50_ms=latency_diff_p50,
        )

    return EvalMetrics(
        model_router=router_metrics,
        baseline=baseline_metrics,
        comparison=comparison,
    )


# ── Quality metrics ──────────────────────────────────────────────────────────

def _score_stats(values: List[float]) -> Optional[ScoreStats]:
    """Compute summary statistics for a list of score values."""
    if not values:
        return None
    return ScoreStats(
        mean=round(statistics.mean(values), 3),
        median=round(statistics.median(values), 3),
        std=round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        min=min(values),
        max=max(values),
        count=len(values),
    )


def _bootstrap_ci(
    wins: int,
    total: int,
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap confidence interval for a win rate."""
    if total == 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    outcomes = [1] * wins + [0] * (total - wins)
    boot_rates = []
    for _ in range(n_boot):
        sample = rng.choices(outcomes, k=total)
        boot_rates.append(sum(sample) / total)
    boot_rates.sort()
    lo_idx = int((1 - ci) / 2 * n_boot)
    hi_idx = int((1 + ci) / 2 * n_boot) - 1
    return (round(boot_rates[lo_idx], 4), round(boot_rates[hi_idx], 4))


def compute_quality_metrics(
    judge_results: List["JudgeResult"],
    category_map: Optional[Dict[str, str]] = None,
    router_cost_usd: float = 0.0,
    baseline_cost_usd: float = 0.0,
    router_mean_latency_ms: float = 0.0,
    baseline_mean_latency_ms: float = 0.0,
) -> QualityMetrics:
    """Compute quality metrics from judge results.

    Args:
        judge_results: List of JudgeResult from the judge module.
        category_map: prompt_id -> category mapping.
        router_cost_usd: Total router cost for composite score.
        baseline_cost_usd: Total baseline cost for composite score.
        router_mean_latency_ms: Router mean latency for efficiency score.
        baseline_mean_latency_ms: Baseline mean latency for efficiency score.

    Returns:
        QualityMetrics with win rates, scores, and composite metrics.
    """
    # Filter out errored results
    valid = [j for j in judge_results if j.error is None and j.pairwise_winner is not None]

    router_wins = sum(1 for j in valid if j.pairwise_winner == "model_router")
    baseline_wins = sum(1 for j in valid if j.pairwise_winner == "baseline")
    ties = sum(1 for j in valid if j.pairwise_winner == "tie")
    total = len(valid)

    router_wr = router_wins / total if total > 0 else 0.0
    baseline_wr = baseline_wins / total if total > 0 else 0.0
    tie_r = ties / total if total > 0 else 0.0

    # Absolute scores
    router_overalls = [j.router_score.overall for j in valid if j.router_score]
    baseline_overalls = [j.baseline_score.overall for j in valid if j.baseline_score]

    dimensions = ["accuracy", "completeness", "clarity", "helpfulness"]
    router_by_dim: Dict[str, ScoreStats] = {}
    baseline_by_dim: Dict[str, ScoreStats] = {}
    for dim in dimensions:
        r_vals = [getattr(j.router_score, dim) for j in valid if j.router_score]
        b_vals = [getattr(j.baseline_score, dim) for j in valid if j.baseline_score]
        r_stats = _score_stats([float(v) for v in r_vals])
        b_stats = _score_stats([float(v) for v in b_vals])
        if r_stats:
            router_by_dim[dim] = r_stats
        if b_stats:
            baseline_by_dim[dim] = b_stats

    # Per-category win rates
    win_by_cat: Dict[str, Dict[str, float]] = {}
    if category_map:
        cat_results: Dict[str, List] = {}
        for j in valid:
            cat = category_map.get(j.prompt_id, "uncategorized")
            cat_results.setdefault(cat, []).append(j)
        for cat, results in cat_results.items():
            c_total = len(results)
            c_router = sum(1 for j in results if j.pairwise_winner == "model_router")
            c_baseline = sum(1 for j in results if j.pairwise_winner == "baseline")
            c_tie = sum(1 for j in results if j.pairwise_winner == "tie")
            win_by_cat[cat] = {
                "router_win_rate": round(c_router / c_total, 4) if c_total else 0,
                "baseline_win_rate": round(c_baseline / c_total, 4) if c_total else 0,
                "tie_rate": round(c_tie / c_total, 4) if c_total else 0,
                "count": c_total,
            }

    # Composite scores: quality per dollar, quality per second
    r_overall_mean = statistics.mean(router_overalls) if router_overalls else 0.0
    b_overall_mean = statistics.mean(baseline_overalls) if baseline_overalls else 0.0

    r_value = round(r_overall_mean / router_cost_usd, 2) if router_cost_usd > 0 else None
    b_value = round(b_overall_mean / baseline_cost_usd, 2) if baseline_cost_usd > 0 else None
    r_efficiency = round(r_overall_mean / (router_mean_latency_ms / 1000), 2) if router_mean_latency_ms > 0 else None
    b_efficiency = round(b_overall_mean / (baseline_mean_latency_ms / 1000), 2) if baseline_mean_latency_ms > 0 else None

    # Bootstrap CI for router win rate
    ci = _bootstrap_ci(router_wins, total) if total >= 20 else None

    return QualityMetrics(
        router_win_rate=round(router_wr, 4),
        baseline_win_rate=round(baseline_wr, 4),
        tie_rate=round(tie_r, 4),
        router_wins=router_wins,
        baseline_wins=baseline_wins,
        ties=ties,
        total_judged=total,
        router_overall=_score_stats(router_overalls),
        baseline_overall=_score_stats(baseline_overalls),
        router_by_dimension=router_by_dim,
        baseline_by_dimension=baseline_by_dim,
        win_rate_by_category=win_by_cat,
        router_value_score=r_value,
        baseline_value_score=b_value,
        router_efficiency_score=r_efficiency,
        baseline_efficiency_score=b_efficiency,
        router_win_rate_ci=ci,
    )
