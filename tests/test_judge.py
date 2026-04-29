"""Tests for judge parsing, dual-ordering resolution, and quality metrics."""


from src.judge import (
    AbsoluteScore,
    JudgeResult,
    PairwiseVerdict,
    _parse_absolute_scores,
    _parse_pairwise_verdict,
    _resolve_dual_ordering,
)
from src.metrics import (
    compute_quality_metrics,
    _score_stats,
    _bootstrap_ci,
)


# ── Pairwise parsing ────────────────────────────────────────────────────────


class TestParsePairwiseVerdict:
    def test_a_better(self):
        v = _parse_pairwise_verdict("Analysis...\nVERDICT: A_BETTER")
        assert v.winner == "A"

    def test_b_better(self):
        v = _parse_pairwise_verdict("VERDICT: B_BETTER\nDone.")
        assert v.winner == "B"

    def test_tie(self):
        v = _parse_pairwise_verdict("Both are good.\nVERDICT: TIE")
        assert v.winner == "TIE"

    def test_case_insensitive(self):
        v = _parse_pairwise_verdict("verdict: a_better")
        assert v.winner == "A"

    def test_no_verdict_defaults_tie(self):
        v = _parse_pairwise_verdict("I think A is better but I'm not sure.")
        assert v.winner == "TIE"

    def test_raw_output_preserved(self):
        text = "Some analysis\nVERDICT: B_BETTER"
        v = _parse_pairwise_verdict(text)
        assert v.raw_output == text


# ── Absolute score parsing ───────────────────────────────────────────────────


class TestParseAbsoluteScores:
    def test_valid_scores(self):
        text = "Analysis...\nSCORES: accuracy=4 completeness=3 clarity=5 helpfulness=4"
        s = _parse_absolute_scores(text)
        assert s is not None
        assert s.accuracy == 4
        assert s.completeness == 3
        assert s.clarity == 5
        assert s.helpfulness == 4
        assert s.overall == 4.0

    def test_clamping_high(self):
        text = "SCORES: accuracy=9 completeness=3 clarity=5 helpfulness=4"
        s = _parse_absolute_scores(text)
        assert s.accuracy == 5  # clamped

    def test_clamping_low(self):
        text = "SCORES: accuracy=0 completeness=3 clarity=5 helpfulness=4"
        s = _parse_absolute_scores(text)
        assert s.accuracy == 1  # clamped

    def test_no_match_returns_none(self):
        s = _parse_absolute_scores("No scores here.")
        assert s is None

    def test_case_insensitive(self):
        text = "scores: accuracy=4 completeness=3 clarity=5 helpfulness=4"
        s = _parse_absolute_scores(text)
        assert s is not None


# ── Dual-ordering resolution ─────────────────────────────────────────────────


class TestResolveDualOrdering:
    def test_both_agree_router(self):
        """Router first: A wins (router), Baseline first: B wins (router) → router."""
        rf = PairwiseVerdict(winner="A", raw_output="")
        bf = PairwiseVerdict(winner="B", raw_output="")
        assert _resolve_dual_ordering(rf, bf) == "model_router"

    def test_both_agree_baseline(self):
        """Router first: B wins (baseline), Baseline first: A wins (baseline) → baseline."""
        rf = PairwiseVerdict(winner="B", raw_output="")
        bf = PairwiseVerdict(winner="A", raw_output="")
        assert _resolve_dual_ordering(rf, bf) == "baseline"

    def test_both_tie(self):
        rf = PairwiseVerdict(winner="TIE", raw_output="")
        bf = PairwiseVerdict(winner="TIE", raw_output="")
        assert _resolve_dual_ordering(rf, bf) == "tie"

    def test_disagreement_becomes_tie(self):
        """Position bias detected: both say A wins → disagree → tie."""
        rf = PairwiseVerdict(winner="A", raw_output="")
        bf = PairwiseVerdict(winner="A", raw_output="")
        assert _resolve_dual_ordering(rf, bf) == "tie"

    def test_one_tie_one_winner(self):
        """One says tie, other says router → disagree → tie."""
        rf = PairwiseVerdict(winner="A", raw_output="")
        bf = PairwiseVerdict(winner="TIE", raw_output="")
        assert _resolve_dual_ordering(rf, bf) == "tie"


# ── Quality metrics computation ──────────────────────────────────────────────


def _make_judge_result(
    prompt_id: str,
    winner: str,
    router_scores: tuple = (4, 4, 4, 4),
    baseline_scores: tuple = (3, 3, 3, 3),
) -> JudgeResult:
    return JudgeResult(
        prompt_id=prompt_id,
        pairwise_winner=winner,
        router_score=AbsoluteScore(*router_scores),
        baseline_score=AbsoluteScore(*baseline_scores),
    )


class TestComputeQualityMetrics:
    def test_basic_win_rates(self):
        results = [
            _make_judge_result("1", "model_router"),
            _make_judge_result("2", "model_router"),
            _make_judge_result("3", "baseline"),
            _make_judge_result("4", "tie"),
        ]
        q = compute_quality_metrics(results)
        assert q.router_wins == 2
        assert q.baseline_wins == 1
        assert q.ties == 1
        assert q.total_judged == 4
        assert q.router_win_rate == 0.5
        assert q.baseline_win_rate == 0.25

    def test_empty_results(self):
        q = compute_quality_metrics([])
        assert q.total_judged == 0
        assert q.router_win_rate == 0.0

    def test_errors_filtered(self):
        results = [
            _make_judge_result("1", "model_router"),
            JudgeResult(prompt_id="2", error="timeout"),
        ]
        q = compute_quality_metrics(results)
        assert q.total_judged == 1

    def test_absolute_scores(self):
        results = [
            _make_judge_result("1", "model_router", (5, 4, 4, 5), (3, 3, 3, 3)),
            _make_judge_result("2", "baseline", (3, 3, 3, 3), (5, 5, 5, 5)),
        ]
        q = compute_quality_metrics(results)
        assert q.router_overall is not None
        assert q.baseline_overall is not None
        # Router: (4.5 + 3.0)/2 = 3.75, Baseline: (3.0 + 5.0)/2 = 4.0
        assert abs(q.router_overall.mean - 3.75) < 0.01
        assert abs(q.baseline_overall.mean - 4.0) < 0.01

    def test_per_category_win_rates(self):
        results = [
            _make_judge_result("1", "model_router"),
            _make_judge_result("2", "model_router"),
            _make_judge_result("3", "baseline"),
        ]
        category_map = {"1": "math", "2": "math", "3": "coding"}
        q = compute_quality_metrics(results, category_map=category_map)
        assert "math" in q.win_rate_by_category
        assert q.win_rate_by_category["math"]["router_win_rate"] == 1.0
        assert q.win_rate_by_category["coding"]["baseline_win_rate"] == 1.0

    def test_composite_scores(self):
        results = [_make_judge_result("1", "model_router", (4, 4, 4, 4), (4, 4, 4, 4))]
        q = compute_quality_metrics(
            results,
            router_cost_usd=1.0,
            baseline_cost_usd=2.0,
            router_mean_latency_ms=1000,
            baseline_mean_latency_ms=2000,
        )
        # Router quality = 4.0, cost = $1.0 → value = 4.0
        assert q.router_value_score == 4.0
        # Baseline quality = 4.0, cost = $2.0 → value = 2.0
        assert q.baseline_value_score == 2.0

    def test_bootstrap_ci(self):
        q = compute_quality_metrics([
            _make_judge_result(str(i), "model_router") for i in range(20)
        ])
        assert q.router_win_rate_ci is not None
        lo, hi = q.router_win_rate_ci
        assert lo <= 1.0 <= hi  # Should be very tight around 1.0


class TestScoreStatsHelper:
    def test_basic(self):
        s = _score_stats([3.0, 4.0, 5.0])
        assert s is not None
        assert s.count == 3
        assert s.mean == 4.0
        assert s.min == 3.0
        assert s.max == 5.0

    def test_empty(self):
        assert _score_stats([]) is None

    def test_single_value(self):
        s = _score_stats([4.0])
        assert s.std == 0.0


class TestBootstrapCI:
    def test_all_wins(self):
        lo, hi = _bootstrap_ci(10, 10)
        assert lo == 1.0
        assert hi == 1.0

    def test_no_wins(self):
        lo, hi = _bootstrap_ci(0, 10)
        assert lo == 0.0
        assert hi == 0.0

    def test_empty(self):
        lo, hi = _bootstrap_ci(0, 0)
        assert lo == 0.0
        assert hi == 0.0

    def test_mixed(self):
        lo, hi = _bootstrap_ci(5, 10)
        assert 0.0 < lo < 0.5
        assert 0.5 < hi < 1.0
