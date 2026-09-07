"""Chart generation for evaluation reports using matplotlib."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server/CI usage
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from .metrics import EvalMetrics, LatencyStats, CostStats, QualityMetrics

# ── Style constants ──────────────────────────────────────────────────────────
ROUTER_COLOR = "#2563EB"   # Blue
BASELINE_COLOR = "#9333EA"  # Purple
SAVINGS_COLOR = "#16A34A"   # Green
WARN_COLOR = "#DC2626"      # Red
BG_COLOR = "#FAFAFA"
GRID_COLOR = "#E5E7EB"
FONT_FAMILY = "sans-serif"

CHART_DPI = 150
CHART_WIDTH = 10
CHART_HEIGHT_SINGLE = 5
CHART_HEIGHT_DOUBLE = 7


def _apply_style(ax: plt.Axes) -> None:
    """Apply consistent styling to an axis."""
    ax.set_facecolor(BG_COLOR)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.spines["bottom"].set_color(GRID_COLOR)


def generate_all_charts(
    metrics: EvalMetrics,
    router_latencies: List[float],
    baseline_latencies: List[float],
    output_dir: Path,
    baseline_label: str = "Baseline",
) -> List[str]:
    """Generate all charts and return list of saved file paths.

    Args:
        metrics: Computed evaluation metrics.
        router_latencies: Raw latency values (ms) for model router.
        baseline_latencies: Raw latency values (ms) for baseline.
        output_dir: Directory to save chart PNGs.
        baseline_label: Display name for the baseline model.

    Returns:
        List of generated chart filenames (relative to output_dir).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    charts: List[str] = []

    # 1. Cost comparison bar chart
    if metrics.model_router.cost and metrics.baseline.cost:
        fname = _chart_cost_comparison(
            metrics.model_router.cost,
            metrics.baseline.cost,
            metrics.comparison.cost_savings_ratio if metrics.comparison else None,
            baseline_label,
            output_dir,
        )
        charts.append(fname)

    # 2. Latency comparison bar chart (percentiles)
    if metrics.model_router.latency and metrics.baseline.latency:
        fname = _chart_latency_comparison(
            metrics.model_router.latency,
            metrics.baseline.latency,
            baseline_label,
            output_dir,
        )
        charts.append(fname)

    # 3. Latency distribution histogram
    if router_latencies and baseline_latencies:
        fname = _chart_latency_distribution(
            router_latencies, baseline_latencies, baseline_label, output_dir
        )
        charts.append(fname)

    # 4. Per-category latency comparison
    if metrics.model_router.latency_by_category and metrics.baseline.latency_by_category:
        fname = _chart_category_latency(
            metrics.model_router.latency_by_category,
            metrics.baseline.latency_by_category,
            baseline_label,
            output_dir,
        )
        charts.append(fname)

    # 5. Cost breakdown (input vs output tokens)
    if metrics.model_router.cost and metrics.baseline.cost:
        fname = _chart_cost_breakdown(
            metrics.model_router.cost,
            metrics.baseline.cost,
            baseline_label,
            output_dir,
        )
        charts.append(fname)

    # 6. Model distribution pie chart (model router)
    if metrics.model_router.model_distribution and len(metrics.model_router.model_distribution) > 1:
        fname = _chart_model_distribution(
            metrics.model_router.model_distribution,
            output_dir,
        )
        charts.append(fname)

    # 7. Quality: Win rates bar chart
    if metrics.quality and metrics.quality.total_judged > 0:
        fname = _chart_win_rates(metrics.quality, baseline_label, output_dir)
        charts.append(fname)

    # 8. Quality: Score comparison grouped bar
    if (
        metrics.quality
        and metrics.quality.router_by_dimension
        and metrics.quality.baseline_by_dimension
    ):
        fname = _chart_score_comparison(
            metrics.quality, baseline_label, output_dir
        )
        charts.append(fname)

    plt.close("all")
    return charts


# ── Individual chart generators ──────────────────────────────────────────────

def _chart_cost_comparison(
    router_cost: CostStats,
    baseline_cost: CostStats,
    savings_ratio: Optional[float],
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Bar chart comparing total estimated cost."""
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)
    _apply_style(ax)

    labels = ["Model Router", baseline_label]
    costs = [router_cost.estimated_cost_usd, baseline_cost.estimated_cost_usd]
    colors = [ROUTER_COLOR, BASELINE_COLOR]

    bars = ax.bar(labels, costs, color=colors, width=0.5, edgecolor="white", linewidth=1.5)

    # Add value labels on bars
    for bar, cost in zip(bars, costs):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(costs) * 0.02,
            f"${cost:.4f}",
            ha="center", va="bottom", fontweight="bold", fontsize=12,
        )

    # Add savings annotation
    if savings_ratio is not None and savings_ratio != 0:
        pct = savings_ratio * 100
        color = SAVINGS_COLOR if pct > 0 else WARN_COLOR
        sign = "savings" if pct > 0 else "increase"
        ax.annotate(
            f"{abs(pct):.1f}% cost {sign}",
            xy=(0.5, 0.92), xycoords="axes fraction",
            ha="center", fontsize=14, fontweight="bold", color=color,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, alpha=0.9),
        )

    ax.set_ylabel("Estimated Cost (USD)", fontsize=12)
    ax.set_title("Cost Comparison", fontsize=14, fontweight="bold", pad=20)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.4f"))

    fig.tight_layout()
    fname = "chart_cost_comparison.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


def _chart_latency_comparison(
    router_latency: LatencyStats,
    baseline_latency: LatencyStats,
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Grouped bar chart comparing latency percentiles."""
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)
    _apply_style(ax)

    percentiles = ["Mean", "P50", "P90", "P95", "P99"]
    router_vals = [
        router_latency.mean_ms, router_latency.median_ms,
        router_latency.p90_ms, router_latency.p95_ms, router_latency.p99_ms,
    ]
    baseline_vals = [
        baseline_latency.mean_ms, baseline_latency.median_ms,
        baseline_latency.p90_ms, baseline_latency.p95_ms, baseline_latency.p99_ms,
    ]

    x = range(len(percentiles))
    width = 0.35

    bars1 = ax.bar([i - width / 2 for i in x], router_vals, width,
                   label="Model Router", color=ROUTER_COLOR, edgecolor="white", linewidth=1)
    bars2 = ax.bar([i + width / 2 for i in x], baseline_vals, width,
                   label=baseline_label, color=BASELINE_COLOR, edgecolor="white", linewidth=1)

    # Value labels
    for bar in list(bars1) + list(bars2):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + max(baseline_vals + router_vals) * 0.01,
                f"{h:.0f}", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(list(x))
    ax.set_xticklabels(percentiles, fontsize=11)
    ax.set_ylabel("Latency (ms)", fontsize=12)
    ax.set_title("Latency Comparison by Percentile", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11, loc="upper left")

    # Nx ratio annotation for mean
    if router_latency.mean_ms > 0 and baseline_latency.mean_ms > 0:
        if router_latency.mean_ms < baseline_latency.mean_ms:
            ratio = baseline_latency.mean_ms / router_latency.mean_ms
            label = f"{ratio:.1f}x faster"
            color = SAVINGS_COLOR
        else:
            ratio = router_latency.mean_ms / baseline_latency.mean_ms
            label = f"{ratio:.1f}x slower"
            color = WARN_COLOR
        ax.annotate(
            label,
            xy=(0.5, 0.93), xycoords="axes fraction",
            ha="center", fontsize=14, fontweight="bold", color=color,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, alpha=0.9),
        )

    fig.tight_layout()
    fname = "chart_latency_comparison.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


def _chart_latency_distribution(
    router_latencies: List[float],
    baseline_latencies: List[float],
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Overlapping histogram of latency distributions."""
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)
    _apply_style(ax)

    # Determine shared bin range
    all_vals = router_latencies + baseline_latencies
    bin_min = min(all_vals) * 0.9
    bin_max = max(all_vals) * 1.1
    n_bins = min(40, max(10, len(all_vals) // 5))

    ax.hist(router_latencies, bins=n_bins, range=(bin_min, bin_max),
            alpha=0.6, color=ROUTER_COLOR, label="Model Router", edgecolor="white")
    ax.hist(baseline_latencies, bins=n_bins, range=(bin_min, bin_max),
            alpha=0.6, color=BASELINE_COLOR, label=baseline_label, edgecolor="white")

    ax.set_xlabel("Latency (ms)", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title("Latency Distribution", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)

    fig.tight_layout()
    fname = "chart_latency_distribution.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


def _chart_category_latency(
    router_by_cat: Dict[str, LatencyStats],
    baseline_by_cat: Dict[str, LatencyStats],
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Grouped horizontal bar chart of mean latency per category."""
    all_categories = sorted(set(router_by_cat.keys()) | set(baseline_by_cat.keys()))
    if not all_categories:
        return ""

    fig, ax = plt.subplots(
        figsize=(CHART_WIDTH, max(CHART_HEIGHT_SINGLE, len(all_categories) * 0.8 + 2)),
        dpi=CHART_DPI,
    )
    _apply_style(ax)

    y = range(len(all_categories))
    height = 0.35

    router_vals = [router_by_cat[c].mean_ms if c in router_by_cat else 0 for c in all_categories]
    baseline_vals = [baseline_by_cat[c].mean_ms if c in baseline_by_cat else 0 for c in all_categories]

    ax.barh([i + height / 2 for i in y], baseline_vals, height,
            label=baseline_label, color=BASELINE_COLOR, edgecolor="white", linewidth=1)
    ax.barh([i - height / 2 for i in y], router_vals, height,
            label="Model Router", color=ROUTER_COLOR, edgecolor="white", linewidth=1)

    ax.set_yticks(list(y))
    ax.set_yticklabels(all_categories, fontsize=11)
    ax.set_xlabel("Mean Latency (ms)", fontsize=12)
    ax.set_title("Per-Category Latency Comparison", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11, loc="lower right")

    fig.tight_layout()
    fname = "chart_category_latency.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


def _chart_cost_breakdown(
    router_cost: CostStats,
    baseline_cost: CostStats,
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Stacked bar chart showing input vs output token cost."""
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)
    _apply_style(ax)

    labels = ["Model Router", baseline_label]
    # We don't store per-type cost, so approximate from token counts
    # This is a visual breakdown — exact cost depends on pricing config
    router_input = router_cost.total_prompt_tokens
    router_output = router_cost.total_completion_tokens
    baseline_input = baseline_cost.total_prompt_tokens
    baseline_output = baseline_cost.total_completion_tokens

    input_tokens = [router_input, baseline_input]
    output_tokens = [router_output, baseline_output]

    bars1 = ax.bar(labels, input_tokens, width=0.5,
                   label="Prompt Tokens", color=ROUTER_COLOR, alpha=0.7, edgecolor="white")
    bars2 = ax.bar(labels, output_tokens, width=0.5, bottom=input_tokens,
                   label="Completion Tokens", color=BASELINE_COLOR, alpha=0.7, edgecolor="white")

    # Value labels
    for bar, val in zip(bars1, input_tokens):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                    f"{val:,}", ha="center", va="center", fontsize=10, color="white", fontweight="bold")
    for bar, bottom, val in zip(bars2, input_tokens, output_tokens):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bottom + val / 2,
                    f"{val:,}", ha="center", va="center", fontsize=10, color="white", fontweight="bold")

    ax.set_ylabel("Tokens", fontsize=12)
    ax.set_title("Token Usage Breakdown", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    fig.tight_layout()
    fname = "chart_token_breakdown.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


def _chart_model_distribution(
    model_distribution: Dict[str, int],
    output_dir: Path,
) -> str:
    """Pie chart showing which underlying models the router selected."""
    # Sort by count descending
    sorted_models = sorted(model_distribution.items(), key=lambda x: -x[1])
    labels = [m for m, _ in sorted_models]
    sizes = [c for _, c in sorted_models]
    total = sum(sizes)

    # Color palette for distinct models
    cmap = matplotlib.colormaps.get_cmap("Set2").resampled(max(len(labels), 3))
    colors = [cmap(i) for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%\n({int(round(pct / 100 * total))})",
        colors=colors,
        startangle=90,
        pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=2),
    )
    for t in autotexts:
        t.set_fontsize(10)
        t.set_fontweight("bold")

    ax.legend(
        wedges, labels,
        title="Model",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1),
        fontsize=10,
    )
    ax.set_title("Model Router — Model Distribution", fontsize=14, fontweight="bold")

    fig.tight_layout()
    fname = "chart_model_distribution.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


# ── Quality charts ───────────────────────────────────────────────────────────

TIE_COLOR = "#6B7280"  # Gray for ties


def _chart_win_rates(
    quality: QualityMetrics,
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Bar chart showing pairwise win/tie/loss counts and rates."""
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)
    _apply_style(ax)

    labels = ["Model Router", "Tie", baseline_label]
    values = [quality.router_wins, quality.ties, quality.baseline_wins]
    colors = [ROUTER_COLOR, TIE_COLOR, BASELINE_COLOR]

    bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor="white", linewidth=1.5)

    # Value + rate labels
    total = quality.total_judged
    for bar, val in zip(bars, values):
        rate = val / total * 100 if total > 0 else 0
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(values) * 0.02,
            f"{val} ({rate:.0f}%)",
            ha="center", va="bottom", fontsize=12, fontweight="bold",
        )

    ax.set_ylabel("Count", fontsize=12)
    ax.set_title("Pairwise Quality Win Rates", fontsize=14, fontweight="bold")

    # CI annotation
    if quality.router_win_rate_ci:
        lo, hi = quality.router_win_rate_ci
        ax.annotate(
            f"Router win rate 95% CI: [{lo:.1%}, {hi:.1%}]",
            xy=(0.5, 0.97), xycoords="axes fraction",
            ha="center", fontsize=10, color=TIE_COLOR,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=GRID_COLOR),
        )

    fig.tight_layout()
    fname = "chart_win_rates.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname


def _chart_score_comparison(
    quality: QualityMetrics,
    baseline_label: str,
    output_dir: Path,
) -> str:
    """Grouped bar chart comparing absolute scores by dimension."""
    dimensions = sorted(
        set(quality.router_by_dimension.keys()) | set(quality.baseline_by_dimension.keys())
    )
    if not dimensions:
        return ""

    # Add "Overall" as the first dimension
    dim_labels = ["Overall"] + [d.capitalize() for d in dimensions]

    router_vals = []
    baseline_vals = []

    # Overall
    router_vals.append(quality.router_overall.mean if quality.router_overall else 0)
    baseline_vals.append(quality.baseline_overall.mean if quality.baseline_overall else 0)

    # Per-dimension
    for dim in dimensions:
        r_s = quality.router_by_dimension.get(dim)
        b_s = quality.baseline_by_dimension.get(dim)
        router_vals.append(r_s.mean if r_s else 0)
        baseline_vals.append(b_s.mean if b_s else 0)

    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT_SINGLE), dpi=CHART_DPI)
    _apply_style(ax)

    import numpy as np
    x = np.arange(len(dim_labels))
    width = 0.35

    bars_r = ax.bar(x - width / 2, router_vals, width,
                    label="Model Router", color=ROUTER_COLOR, edgecolor="white", linewidth=1)
    bars_b = ax.bar(x + width / 2, baseline_vals, width,
                    label=baseline_label, color=BASELINE_COLOR, edgecolor="white", linewidth=1)

    # Value labels
    for bar in list(bars_r) + list(bars_b):
        h = bar.get_height()
        if h > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2, h + 0.05,
                f"{h:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(dim_labels, fontsize=11)
    ax.set_ylabel("Score (1-5)", fontsize=12)
    ax.set_ylim(0, 5.5)
    ax.set_title("Absolute Quality Scores by Dimension", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)

    fig.tight_layout()
    fname = "chart_score_comparison.png"
    fig.savefig(output_dir / fname, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fname
