#!/usr/bin/env python3
"""Generate sample reports with mock data to validate reporting and charting code.

Usage:
    python scripts/generate_sample_report.py
    python scripts/generate_sample_report.py --output-dir results/sample-demo
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src import configure_console_encoding

configure_console_encoding()

from src.client import CompletionResult
from src.config import EvalConfig, EndpointConfig, PricingConfig
from src.dataset import Prompt
from src.judge import AbsoluteScore, JudgeResult
from src.metrics import compute_metrics, compute_quality_metrics
from src.report import generate_report


# ── Mock data configuration ─────────────────────────────────────────────────

CATEGORIES = [
    "code_generation",
    "technical_knowledge",
    "creative_writing",
    "math",
    "reasoning",
    "summarization",
    "general_knowledge",
    "instruction_following",
]

# Latency profiles (mean, stddev) in ms — router is faster on average
LATENCY_PROFILES = {
    "model_router": {
        "code_generation":       (320, 80),
        "technical_knowledge":   (280, 60),
        "creative_writing":      (350, 90),
        "math":                  (250, 50),
        "reasoning":             (380, 100),
        "summarization":         (220, 40),
        "general_knowledge":     (260, 55),
        "instruction_following": (300, 70),
    },
    "baseline": {
        "code_generation":       (450, 90),
        "technical_knowledge":   (420, 70),
        "creative_writing":      (480, 100),
        "math":                  (380, 60),
        "reasoning":             (520, 120),
        "summarization":         (350, 50),
        "general_knowledge":     (400, 65),
        "instruction_following": (430, 80),
    },
}

# Token profiles (prompt_mean, prompt_std, completion_mean, completion_std)
TOKEN_PROFILES = {
    "model_router": (80, 30, 200, 80),
    "baseline":     (80, 30, 250, 100),
}


def _generate_mock_prompts(n: int, seed: int = 42) -> list[Prompt]:
    """Create N diverse mock prompts."""
    rng = random.Random(seed)
    prompts = []
    for i in range(n):
        cat = CATEGORIES[i % len(CATEGORIES)]
        difficulty = rng.choice(["easy", "medium", "hard"])
        prompts.append(Prompt(
            id=f"mock-{i+1:04d}",
            prompt=f"[Mock prompt {i+1}] Category: {cat}, difficulty: {difficulty}",
            category=cat,
            difficulty=difficulty,
            ground_truth=None,
            metadata={},
        ))
    return prompts


def _generate_mock_results(
    prompts: list[Prompt],
    endpoint: str,
    seed: int = 42,
    error_rate: float = 0.02,
) -> list[CompletionResult]:
    """Generate realistic mock completion results."""
    rng = random.Random(seed)
    results = []
    token_profile = TOKEN_PROFILES["model_router" if "router" in endpoint else "baseline"]
    latency_profiles = LATENCY_PROFILES["model_router" if "router" in endpoint else "baseline"]

    for prompt in prompts:
        # Determine if this is an error
        is_error = rng.random() < error_rate
        cat = prompt.category or "general_knowledge"

        lat_mean, lat_std = latency_profiles.get(cat, (350, 80))
        latency = max(50, rng.gauss(lat_mean, lat_std))

        pt_mean, pt_std, ct_mean, ct_std = token_profile
        prompt_tokens = max(10, int(rng.gauss(pt_mean, pt_std)))
        completion_tokens = max(10, int(rng.gauss(ct_mean, ct_std)))

        model_name = "gpt-4o-mini" if "router" in endpoint else "gpt-4o"

        results.append(CompletionResult(
            request_id=f"req-{endpoint}-{prompt.id}",
            prompt_id=prompt.id,
            endpoint=endpoint,
            model_name=model_name,
            response_text=f"[Mock response for {prompt.id}]" if not is_error else "",
            prompt_tokens=prompt_tokens if not is_error else 0,
            completion_tokens=completion_tokens if not is_error else 0,
            total_tokens=(prompt_tokens + completion_tokens) if not is_error else 0,
            latency_ms=round(latency, 2),
            status="success" if not is_error else "error",
            error_message=None if not is_error else "Mock API error for testing",
            timestamp="2026-04-22T12:00:00Z",
        ))

    return results


def _generate_mock_judge_results(
    prompts: list[Prompt],
    seed: int = 77,
) -> list[JudgeResult]:
    """Generate realistic mock judge results — router wins ~55% of the time."""
    rng = random.Random(seed)
    results = []

    for prompt in prompts:
        # ~3% judge error rate
        if rng.random() < 0.03:
            results.append(JudgeResult(prompt_id=prompt.id, error="Mock judge timeout"))
            continue

        # Weighted outcome: router wins 55%, baseline 25%, tie 20%
        roll = rng.random()
        if roll < 0.55:
            winner = "model_router"
        elif roll < 0.80:
            winner = "baseline"
        else:
            winner = "tie"

        # Generate correlated scores
        base_quality = rng.gauss(3.8, 0.6)
        if winner == "model_router":
            r_bonus, b_bonus = 0.4, -0.2
        elif winner == "baseline":
            r_bonus, b_bonus = -0.2, 0.4
        else:
            r_bonus, b_bonus = 0.0, 0.0

        def _score(base: float, bonus: float) -> int:
            return max(1, min(5, round(base + bonus + rng.gauss(0, 0.3))))

        r_base = base_quality + r_bonus
        b_base = base_quality + b_bonus

        router_score = AbsoluteScore(
            accuracy=_score(r_base, rng.gauss(0, 0.2)),
            completeness=_score(r_base, rng.gauss(0, 0.2)),
            clarity=_score(r_base, rng.gauss(0, 0.2)),
            helpfulness=_score(r_base, rng.gauss(0, 0.2)),
        )
        baseline_score = AbsoluteScore(
            accuracy=_score(b_base, rng.gauss(0, 0.2)),
            completeness=_score(b_base, rng.gauss(0, 0.2)),
            clarity=_score(b_base, rng.gauss(0, 0.2)),
            helpfulness=_score(b_base, rng.gauss(0, 0.2)),
        )

        results.append(JudgeResult(
            prompt_id=prompt.id,
            pairwise_winner=winner,
            router_score=router_score,
            baseline_score=baseline_score,
            judge_model="gpt-4o",
            latency_ms=round(rng.gauss(2000, 500), 2),
        ))

    return results


def main():
    parser = argparse.ArgumentParser(description="Generate sample evaluation reports with mock data")
    parser.add_argument(
        "--output-dir",
        default="results/sample-report",
        help="Directory to write sample reports (default: results/sample-report)",
    )
    parser.add_argument(
        "--num-prompts",
        type=int,
        default=100,
        help="Number of mock prompts to generate (default: 100)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    n = args.num_prompts

    print(f"\n{'='*60}")
    print(f"  Generating Sample Report — {n} mock prompts")
    print(f"{'='*60}\n")

    # Generate mock data
    prompts = _generate_mock_prompts(n)
    print(f"Generated {len(prompts)} mock prompts across {len(CATEGORIES)} categories")

    router_results = _generate_mock_results(prompts, "model_router", seed=42, error_rate=0.02)
    baseline_results = _generate_mock_results(prompts, "baseline:gpt-4o", seed=99, error_rate=0.03)

    router_ok = sum(1 for r in router_results if r.status == "success")
    baseline_ok = sum(1 for r in baseline_results if r.status == "success")
    print(f"Model Router: {router_ok}/{n} successful")
    print(f"Baseline:     {baseline_ok}/{n} successful")

    # Build category map
    category_map = {p.id: p.category for p in prompts if p.category}

    # Compute metrics
    pricing = {
        "model_router": PricingConfig(input=0.50, output=1.50),
        "gpt-4o": PricingConfig(input=2.50, output=10.00),
    }
    metrics = compute_metrics(router_results, baseline_results, pricing, category_map)

    # Generate mock judge results for quality evaluation
    print("\nGenerating mock quality evaluation data...")
    judge_results = _generate_mock_judge_results(prompts, seed=77)
    judge_ok = sum(1 for j in judge_results if j.error is None)
    print(f"Judge results: {judge_ok}/{len(judge_results)} successful")
    metrics.quality = compute_quality_metrics(
        judge_results=judge_results,
        category_map=category_map,
        router_cost_usd=metrics.model_router.cost.estimated_cost_usd if metrics.model_router.cost else 0,
        baseline_cost_usd=metrics.baseline.cost.estimated_cost_usd if metrics.baseline.cost else 0,
        router_mean_latency_ms=metrics.model_router.latency.mean_ms if metrics.model_router.latency else 0,
        baseline_mean_latency_ms=metrics.baseline.latency.mean_ms if metrics.baseline.latency else 0,
    )
    print(f"Quality: Router {metrics.quality.router_win_rate:.0%} win rate, "
          f"{metrics.quality.router_wins}W/{metrics.quality.baseline_wins}L/{metrics.quality.ties}T")

    # Build a mock config for the report
    config = EvalConfig(
        name="sample-demo-report",
        dataset="datasets/mock_100_prompts.jsonl",
        sample_size=n,
        random_seed=42,
        model_router=EndpointConfig(
            type="azure_openai",
            endpoint_url="https://demo-router.openai.azure.com",
            api_key="***",
            deployment_name="model-router",
            parameters={"temperature": 0.7, "max_tokens": 1024},
        ),
        baseline=EndpointConfig(
            type="azure_openai",
            endpoint_url="https://demo-baseline.openai.azure.com",
            api_key="***",
            deployment_name="gpt-4o",
            parameters={"temperature": 0.7, "max_tokens": 1024},
        ),
        pricing=pricing,
        max_parallel_requests=5,
        request_timeout_seconds=60,
        max_retries=3,
        output_directory=str(output_dir),
        output_formats=["markdown", "csv", "json"],
    )

    # Generate reports
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerating reports in {output_dir}/")

    generate_report(
        metrics=metrics,
        config=config,
        router_results=router_results,
        baseline_results=baseline_results,
        prompts=prompts,
        output_dir=output_dir,
        formats=["markdown", "csv", "json"],
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"  Sample report generated in: {output_dir}/")
    print(f"{'='*60}")
    print("\nFiles:")
    for f in sorted(output_dir.iterdir()):
        size = f.stat().st_size
        unit = "KB" if size > 1024 else "B"
        display_size = size / 1024 if size > 1024 else size
        print(f"  {f.name:40s} {display_size:>8.1f} {unit}")
    print()


if __name__ == "__main__":
    main()
