"""Report generation — Markdown, CSV, and JSON output."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

from .charts import generate_all_charts
from .client import CompletionResult
from .config import EvalConfig
from .dashboard import generate_dashboard
from .dataset import Prompt
from .metrics import EvalMetrics, LatencyStats, QualityMetrics


def generate_report(
    metrics: EvalMetrics,
    config: EvalConfig,
    router_results: List[CompletionResult],
    baseline_results: List[CompletionResult],
    prompts: List[Prompt],
    output_dir: Path,
    formats: List[str],
) -> None:
    """Generate evaluation report in requested formats."""
    # Generate charts
    router_latencies = [r.latency_ms for r in router_results if r.status == "success"]
    baseline_latencies = [r.latency_ms for r in baseline_results if r.status == "success"]
    baseline_label = config.baseline.deployment_name

    chart_files = generate_all_charts(
        metrics=metrics,
        router_latencies=router_latencies,
        baseline_latencies=baseline_latencies,
        output_dir=output_dir,
        baseline_label=baseline_label,
    )
    if chart_files:
        print(f"  ✓ Charts ({len(chart_files)}):     {', '.join(chart_files)}")

    if "markdown" in formats:
        _generate_markdown(metrics, config, output_dir, chart_files=chart_files)
        print(f"  ✓ Markdown report: {output_dir / 'report.md'}")

    if "csv" in formats:
        _generate_csv(router_results, baseline_results, prompts, output_dir)
        print(f"  ✓ CSV details:     {output_dir / 'detailed_results.csv'}")

    if "json" in formats:
        _generate_json(metrics, config, output_dir)
        print(f"  ✓ JSON metrics:    {output_dir / 'results.json'}")
    # Always generate dashboard
    dashboard_file = generate_dashboard(
        metrics=metrics,
        eval_name=config.name,
        baseline_label=baseline_label,
        chart_files=chart_files,
        output_dir=output_dir,
    )
    print(f"  \u2713 Dashboard:       {output_dir / dashboard_file}")

def _fmt_latency(stats: LatencyStats | None) -> Dict[str, str]:
    """Format latency stats for display."""
    if stats is None:
        return {"mean": "N/A", "p50": "N/A", "p90": "N/A", "p95": "N/A", "p99": "N/A"}
    return {
        "mean": f"{stats.mean_ms:.0f}ms",
        "p50": f"{stats.median_ms:.0f}ms",
        "p90": f"{stats.p90_ms:.0f}ms",
        "p95": f"{stats.p95_ms:.0f}ms",
        "p99": f"{stats.p99_ms:.0f}ms",
    }


def _latency_ratio(
    router_latency: LatencyStats | None,
    baseline_latency: LatencyStats | None,
) -> str:
    """Return a human-readable Nx ratio string (e.g. '1.4x')."""
    if not router_latency or not baseline_latency or router_latency.mean_ms == 0:
        return "N/A"
    if router_latency.mean_ms < baseline_latency.mean_ms:
        ratio = baseline_latency.mean_ms / router_latency.mean_ms
    else:
        ratio = router_latency.mean_ms / baseline_latency.mean_ms
    return f"{ratio:.1f}x"


def _generate_markdown(
    metrics: EvalMetrics,
    config: EvalConfig,
    output_dir: Path,
    chart_files: List[str] | None = None,
) -> None:
    """Generate a Markdown summary report."""
    rm = metrics.model_router
    bm = metrics.baseline
    comp = metrics.comparison

    rl = _fmt_latency(rm.latency)
    bl = _fmt_latency(bm.latency)

    lines = [
        f"# Evaluation Report: {config.name}",
        "",
        "## Executive Summary",
        "",
    ]
    if rm.total_requests < 30:
        lines += [
            "> [!WARNING]",
            f"> This run contains only {rm.total_requests} prompts. Treat it as a "
            "directional smoke test, not statistically reliable evidence.",
            "",
        ]

    # Executive summary
    if comp:
        savings_pct = comp.cost_savings_ratio * 100
        latency_direction = "faster" if comp.latency_diff_mean_ms < 0 else "slower"
        latency_ratio = _latency_ratio(rm.latency, bm.latency)
        summary = (
            f"Model Router was evaluated against **{config.baseline.deployment_name}** "
            f"on {rm.total_requests} prompts. "
            f"Model Router achieved **{savings_pct:+.1f}% cost savings** "
            f"and was **{latency_ratio} {latency_direction}** on average (mean latency)."
        )
        if metrics.quality:
            q = metrics.quality
            summary += (
                f" Quality evaluation: Model Router won **{q.router_win_rate:.0%}** "
                f"of pairwise comparisons ({q.router_wins}W / {q.baseline_wins}L / {q.ties}T)."
            )
        lines.append(summary)
    else:
        lines.append(
            f"Model Router was evaluated against **{config.baseline.deployment_name}** "
            f"on {rm.total_requests} prompts."
        )

    lines += [
        "",
        "---",
        "",
        "## Cost Analysis",
        "",
        "| Metric | Model Router | Baseline |",
        "|--------|-------------|----------|",
    ]

    if rm.cost and bm.cost:
        lines += [
            f"| Total tokens | {rm.cost.total_tokens:,} | {bm.cost.total_tokens:,} |",
            f"| Prompt tokens | {rm.cost.total_prompt_tokens:,} | {bm.cost.total_prompt_tokens:,} |",
            f"| Completion tokens | {rm.cost.total_completion_tokens:,} | {bm.cost.total_completion_tokens:,} |",
            f"| Estimated cost | ${rm.cost.estimated_cost_usd:.4f} | ${bm.cost.estimated_cost_usd:.4f} |",
            f"| Cost per prompt (avg) | ${rm.cost.cost_per_prompt_avg_usd:.6f} | ${bm.cost.cost_per_prompt_avg_usd:.6f} |",
            f"| Cost per prompt (p50) | ${rm.cost.cost_per_prompt_p50_usd:.6f} | ${bm.cost.cost_per_prompt_p50_usd:.6f} |",
            f"| Cost per prompt (p95) | ${rm.cost.cost_per_prompt_p95_usd:.6f} | ${bm.cost.cost_per_prompt_p95_usd:.6f} |",
        ]

    if comp:
        lines += [
            "",
            f"**Cost savings: {comp.cost_savings_ratio * 100:+.1f}%**",
        ]

    # Cost charts
    if chart_files:
        if "chart_cost_comparison.png" in chart_files:
            lines += ["", "![Cost Comparison](chart_cost_comparison.png)"]
        if "chart_token_breakdown.png" in chart_files:
            lines += ["", "![Token Breakdown](chart_token_breakdown.png)"]

    lines += [
        "",
        "---",
        "",
        "## Latency Analysis",
        "",
        "| Metric | Model Router | Baseline |",
        "|--------|-------------|----------|",
        f"| Mean | {rl['mean']} | {bl['mean']} |",
        f"| Median (p50) | {rl['p50']} | {bl['p50']} |",
        f"| p90 | {rl['p90']} | {bl['p90']} |",
        f"| p95 | {rl['p95']} | {bl['p95']} |",
        f"| p99 | {rl['p99']} | {bl['p99']} |",
    ]

    if comp:
        latency_direction = "faster" if comp.latency_diff_mean_ms < 0 else "slower"
        latency_ratio = _latency_ratio(rm.latency, bm.latency)
        lines += [
            "",
            f"**Model Router is {latency_ratio} {latency_direction} (mean)**",
        ]

    # Latency charts
    if chart_files:
        if "chart_latency_comparison.png" in chart_files:
            lines += ["", "![Latency Comparison](chart_latency_comparison.png)"]
        if "chart_latency_distribution.png" in chart_files:
            lines += ["", "![Latency Distribution](chart_latency_distribution.png)"]

    # Model distribution (model router)
    if rm.model_distribution and len(rm.model_distribution) > 1:
        lines += [
            "",
            "---",
            "",
            "## Model Router — Model Distribution",
            "",
            "The model router selected the following underlying models:",
            "",
            "| Model | Requests | Share |",
            "|-------|----------|-------|",
        ]
        total = sum(rm.model_distribution.values())
        for model, count in sorted(rm.model_distribution.items(), key=lambda x: -x[1]):
            share = count / total * 100 if total else 0
            lines.append(f"| {model} | {count} | {share:.1f}% |")

        if chart_files and "chart_model_distribution.png" in chart_files:
            lines += ["", "![Model Distribution](chart_model_distribution.png)"]

    # Per-category breakdown
    if rm.latency_by_category or bm.latency_by_category:
        all_categories = sorted(
            set(rm.latency_by_category.keys()) | set(bm.latency_by_category.keys())
        )
        if all_categories:
            lines += [
                "",
                "---",
                "",
                "## Per-Category Latency (Mean)",
                "",
                "| Category | Model Router | Baseline |",
                "|----------|-------------|----------|",
            ]
            for cat in all_categories:
                r_lat = rm.latency_by_category.get(cat)
                b_lat = bm.latency_by_category.get(cat)
                r_str = f"{r_lat.mean_ms:.0f}ms" if r_lat else "N/A"
                b_str = f"{b_lat.mean_ms:.0f}ms" if b_lat else "N/A"
                lines.append(f"| {cat} | {r_str} | {b_str} |")

            # Category chart
            if chart_files and "chart_category_latency.png" in chart_files:
                lines += ["", "![Per-Category Latency](chart_category_latency.png)"]

    # Quality section (if judge was used)
    if metrics.quality:
        lines += _quality_markdown_section(metrics.quality, chart_files)

    # Reliability
    lines += [
        "",
        "---",
        "",
        "## Reliability",
        "",
        "| Metric | Model Router | Baseline |",
        "|--------|-------------|----------|",
        f"| Total requests | {rm.total_requests} | {bm.total_requests} |",
        f"| Successful | {rm.successful_requests} | {bm.successful_requests} |",
        f"| Errors | {rm.error_count} | {bm.error_count} |",
        f"| Timeouts | {rm.timeout_count} | {bm.timeout_count} |",
    ]

    # Methodology
    lines += [
        "",
        "---",
        "",
        "## Methodology",
        "",
        f"- **Dataset**: {config.dataset}",
        f"- **Sample size**: {rm.total_requests} prompts",
        f"- **Model Router endpoint**: {config.model_router.deployment_name}",
        f"- **Baseline model**: {config.baseline.deployment_name}",
        f"- **Pricing source**: {config.pricing_metadata.get('type', 'yaml')}",
        f"- **Pricing region**: {config.pricing_metadata.get('region') or 'not specified'}",
        f"- **Temperature**: {config.model_router.parameters.get('temperature', 'N/A')}",
        f"- **Max tokens**: {config.model_router.parameters.get('max_tokens', 'N/A')}",
        f"- **Concurrency**: {config.max_parallel_requests} parallel requests",
        "",
        "Prompts were sent sequentially to each endpoint per-prompt (router then baseline) "
        "to ensure fair latency comparison. Concurrency was applied across prompts.",
    ]

    report_path = output_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _quality_markdown_section(
    q: QualityMetrics,
    chart_files: List[str] | None = None,
) -> List[str]:
    """Generate quality evaluation markdown lines."""
    lines = [
        "",
        "---",
        "",
        "## Quality Evaluation (LLM-as-a-Judge)",
        "",
        "### Pairwise Win Rates",
        "",
        "| Outcome | Count | Rate |",
        "|---------|-------|------|",
        f"| Model Router wins | {q.router_wins} | {q.router_win_rate:.1%} |",
        f"| Baseline wins | {q.baseline_wins} | {q.baseline_win_rate:.1%} |",
        f"| Ties | {q.ties} | {q.tie_rate:.1%} |",
        f"| **Total judged** | **{q.total_judged}** | |",
    ]

    if q.router_win_rate_ci:
        lines += [
            "",
            f"Router win rate 95% CI: [{q.router_win_rate_ci[0]:.1%}, {q.router_win_rate_ci[1]:.1%}]",
        ]

    # Win rate chart
    if chart_files and "chart_win_rates.png" in chart_files:
        lines += ["", "![Win Rates](chart_win_rates.png)"]

    # Absolute scores
    if q.router_overall and q.baseline_overall:
        lines += [
            "",
            "### Absolute Quality Scores (1-5 scale)",
            "",
            "| Dimension | Model Router | Baseline |",
            "|-----------|-------------|----------|",
        ]
        # Overall
        lines.append(
            f"| **Overall** | **{q.router_overall.mean:.2f}** | **{q.baseline_overall.mean:.2f}** |"
        )
        # Per-dimension
        all_dims = sorted(set(q.router_by_dimension.keys()) | set(q.baseline_by_dimension.keys()))
        for dim in all_dims:
            r_s = q.router_by_dimension.get(dim)
            b_s = q.baseline_by_dimension.get(dim)
            r_str = f"{r_s.mean:.2f}" if r_s else "N/A"
            b_str = f"{b_s.mean:.2f}" if b_s else "N/A"
            lines.append(f"| {dim.capitalize()} | {r_str} | {b_str} |")

    # Score comparison chart
    if chart_files and "chart_score_comparison.png" in chart_files:
        lines += ["", "![Score Comparison](chart_score_comparison.png)"]

    # Per-category win rates
    if q.win_rate_by_category:
        lines += [
            "",
            "### Per-Category Win Rates",
            "",
            "| Category | Router Win | Baseline Win | Tie | Count |",
            "|----------|-----------|-------------|-----|-------|",
        ]
        for cat in sorted(q.win_rate_by_category.keys()):
            wr = q.win_rate_by_category[cat]
            lines.append(
                f"| {cat} | {wr['router_win_rate']:.1%} | {wr['baseline_win_rate']:.1%} "
                f"| {wr['tie_rate']:.1%} | {wr['count']} |"
            )

    # Value / efficiency scores
    if q.router_value_score is not None or q.router_efficiency_score is not None:
        lines += [
            "",
            "### Composite Scores",
            "",
            "| Metric | Model Router | Baseline |",
            "|--------|-------------|----------|",
        ]
        if q.router_value_score is not None and q.baseline_value_score is not None:
            lines.append(
                f"| Quality / Cost (higher = better) | {q.router_value_score:.1f} | {q.baseline_value_score:.1f} |"
            )
        if q.router_efficiency_score is not None and q.baseline_efficiency_score is not None:
            lines.append(
                f"| Quality / Latency (higher = better) | {q.router_efficiency_score:.1f} | {q.baseline_efficiency_score:.1f} |"
            )

    return lines


def _generate_csv(
    router_results: List[CompletionResult],
    baseline_results: List[CompletionResult],
    prompts: List[Prompt],
    output_dir: Path,
) -> None:
    """Generate a detailed CSV with per-prompt results."""
    prompt_map = {p.id: p for p in prompts}
    router_map = {r.prompt_id: r for r in router_results}
    baseline_map = {r.prompt_id: r for r in baseline_results}

    csv_path = output_dir / "detailed_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "prompt_id", "category", "difficulty", "prompt_text",
            "router_model", "router_latency_ms", "router_prompt_tokens",
            "router_completion_tokens", "router_total_tokens", "router_status",
            "baseline_model", "baseline_latency_ms", "baseline_prompt_tokens",
            "baseline_completion_tokens", "baseline_total_tokens", "baseline_status",
        ])

        for prompt_id in prompt_map:
            p = prompt_map[prompt_id]
            rr = router_map.get(prompt_id)
            br = baseline_map.get(prompt_id)

            writer.writerow([
                prompt_id,
                p.category or "",
                p.difficulty or "",
                p.prompt[:200],  # Truncate long prompts in CSV
                rr.model_name if rr else "",
                rr.latency_ms if rr else "",
                rr.prompt_tokens if rr else "",
                rr.completion_tokens if rr else "",
                rr.total_tokens if rr else "",
                rr.status if rr else "",
                br.model_name if br else "",
                br.latency_ms if br else "",
                br.prompt_tokens if br else "",
                br.completion_tokens if br else "",
                br.total_tokens if br else "",
                br.status if br else "",
            ])


def _generate_json(metrics: EvalMetrics, config: EvalConfig, output_dir: Path) -> None:
    """Generate machine-readable JSON with aggregate metrics."""

    def _latency_dict(stats):
        if stats is None:
            return None
        return {
            "count": stats.count,
            "mean_ms": stats.mean_ms,
            "median_ms": stats.median_ms,
            "p90_ms": stats.p90_ms,
            "p95_ms": stats.p95_ms,
            "p99_ms": stats.p99_ms,
            "min_ms": stats.min_ms,
            "max_ms": stats.max_ms,
        }

    def _cost_dict(stats):
        if stats is None:
            return None
        return {
            "total_prompt_tokens": stats.total_prompt_tokens,
            "total_completion_tokens": stats.total_completion_tokens,
            "total_tokens": stats.total_tokens,
            "estimated_cost_usd": stats.estimated_cost_usd,
            "cost_per_prompt_avg_usd": stats.cost_per_prompt_avg_usd,
            "cost_per_prompt_p50_usd": stats.cost_per_prompt_p50_usd,
            "cost_per_prompt_p95_usd": stats.cost_per_prompt_p95_usd,
        }

    def _endpoint_dict(em):
        result = {
            "endpoint": em.endpoint,
            "total_requests": em.total_requests,
            "successful_requests": em.successful_requests,
            "error_count": em.error_count,
            "timeout_count": em.timeout_count,
            "latency": _latency_dict(em.latency),
            "cost": _cost_dict(em.cost),
        }
        if em.latency_by_category:
            result["latency_by_category"] = {
                cat: _latency_dict(stats)
                for cat, stats in em.latency_by_category.items()
            }
        if em.model_distribution:
            result["model_distribution"] = em.model_distribution
        return result

    output = {
        "evaluation_name": config.name,
        "dataset": config.dataset,
        "pricing_source": config.pricing_metadata,
        "pricing_used": {
            name: {"input": value.input, "output": value.output}
            for name, value in config.pricing.items()
        },
        "model_router": _endpoint_dict(metrics.model_router),
        "baseline": _endpoint_dict(metrics.baseline),
    }

    if metrics.comparison:
        output["comparison"] = {
            "cost_savings_ratio": metrics.comparison.cost_savings_ratio,
            "latency_diff_mean_ms": metrics.comparison.latency_diff_mean_ms,
            "latency_diff_p50_ms": metrics.comparison.latency_diff_p50_ms,
        }

    if metrics.quality:
        q = metrics.quality
        quality_output = {
            "pairwise": {
                "router_wins": q.router_wins,
                "baseline_wins": q.baseline_wins,
                "ties": q.ties,
                "total_judged": q.total_judged,
                "router_win_rate": q.router_win_rate,
                "baseline_win_rate": q.baseline_win_rate,
                "tie_rate": q.tie_rate,
            },
        }
        if q.router_overall:
            quality_output["absolute_scores"] = {
                "router_overall": q.router_overall.mean,
                "baseline_overall": q.baseline_overall.mean if q.baseline_overall else None,
                "router_by_dimension": {
                    k: v.mean for k, v in q.router_by_dimension.items()
                },
                "baseline_by_dimension": {
                    k: v.mean for k, v in q.baseline_by_dimension.items()
                },
            }
        if q.win_rate_by_category:
            quality_output["win_rate_by_category"] = q.win_rate_by_category
        if q.router_win_rate_ci:
            quality_output["router_win_rate_ci_95"] = list(q.router_win_rate_ci)
        output["quality"] = quality_output

    json_path = output_dir / "results.json"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
