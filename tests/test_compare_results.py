"""Regression tests for scripts.compare_results."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_compare_results_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "compare_results.py"
    spec = importlib.util.spec_from_file_location("compare_results", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _row_map(rows):
    return {(row["category"], row["metric"]): row for row in rows}


def _base_run():
    return {
        "model_router": {
            "total_requests": 10,
            "latency": {"mean_ms": 100.0, "p90_ms": 120.0, "p99_ms": 140.0},
            "cost": {"estimated_cost_usd": 1.0},
        },
        "baseline": {
            "total_requests": 10,
            "latency": {"mean_ms": 150.0, "p90_ms": 180.0, "p99_ms": 210.0},
            "cost": {"estimated_cost_usd": 2.0},
        },
    }


def test_compare_reads_nested_quality_metrics():
    mod = _load_compare_results_module()
    run_a = _base_run() | {
        "quality": {
            "pairwise": {
                "router_win_rate": 0.4,
                "baseline_win_rate": 0.2,
                "tie_rate": 0.4,
            },
            "absolute_scores": {
                "router_overall": 4.2,
                "baseline_overall": 3.8,
            },
            "win_rate_by_category": {
                "math": {
                    "router_win_rate": 1.0,
                    "baseline_win_rate": 0.0,
                    "tie_rate": 0.0,
                },
            },
        },
    }
    run_b = _base_run() | {
        "quality": {
            "pairwise": {
                "router_win_rate": 0.5,
                "baseline_win_rate": 0.3,
                "tie_rate": 0.2,
            },
            "absolute_scores": {
                "router_overall": 4.5,
                "baseline_overall": 4.0,
            },
            "win_rate_by_category": {
                "math": {
                    "router_win_rate": 0.5,
                    "baseline_win_rate": 0.5,
                    "tie_rate": 0.0,
                },
            },
        },
    }

    rows = _row_map(mod.compare(run_a, run_b, "run-a", "run-b"))

    assert rows[("Quality", "router_win_rate")]["run_a"] == 0.4
    assert rows[("Quality", "router_win_rate")]["run_b"] == 0.5
    assert rows[("Quality", "baseline_overall")]["run_a"] == 3.8
    assert rows[("Quality", "router_overall")]["run_b"] == 4.5
    assert rows[("Quality by Category", "math router_win_rate")]["run_a"] == 1.0
    assert rows[("Quality by Category", "math baseline_win_rate")]["run_b"] == 0.5


def test_compare_keeps_legacy_flat_quality_metrics():
    mod = _load_compare_results_module()
    run_a = _base_run() | {
        "quality": {
            "router_win_rate": 0.4,
            "baseline_win_rate": 0.2,
            "tie_rate": 0.4,
            "router_mean_score": 4.1,
            "baseline_mean_score": 3.7,
        },
    }
    run_b = _base_run() | {
        "quality": {
            "router_win_rate": 0.6,
            "baseline_win_rate": 0.1,
            "tie_rate": 0.3,
            "router_mean_score": 4.4,
            "baseline_mean_score": 3.9,
        },
    }

    rows = _row_map(mod.compare(run_a, run_b, "run-a", "run-b"))

    assert rows[("Quality", "router_win_rate")]["run_a"] == 0.4
    assert rows[("Quality", "baseline_win_rate")]["run_b"] == 0.1
    assert rows[("Quality", "router_overall")]["run_a"] == 4.1
    assert rows[("Quality", "baseline_overall")]["run_b"] == 3.9
