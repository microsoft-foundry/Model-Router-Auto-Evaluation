"""Self-contained HTML dashboard with key metrics and embedded charts."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict, List

from .metrics import EvalMetrics, LatencyStats


def _b64_img(path: Path) -> str:
    """Read a PNG and return a base64 data-URI string."""
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _latency_ratio_str(
    router: LatencyStats | None,
    baseline: LatencyStats | None,
) -> tuple[str, str]:
    """Return (ratio_text, css_class) for the latency comparison."""
    if not router or not baseline or router.mean_ms == 0:
        return "N/A", "neutral"
    if router.mean_ms < baseline.mean_ms:
        ratio = baseline.mean_ms / router.mean_ms
        return f"{ratio:.1f}x faster", "positive"
    else:
        ratio = router.mean_ms / baseline.mean_ms
        return f"{ratio:.1f}x slower", "negative"


def _pct_str(value: float) -> tuple[str, str]:
    """Return (formatted_pct, css_class) for a percentage value."""
    if value > 0:
        return f"+{value:.1f}%", "positive"
    elif value < 0:
        return f"{value:.1f}%", "negative"
    return "0%", "neutral"


def generate_dashboard(
    metrics: EvalMetrics,
    eval_name: str,
    baseline_label: str,
    chart_files: List[str],
    output_dir: Path,
) -> str:
    """Generate a self-contained HTML dashboard.

    Args:
        metrics: Computed evaluation metrics.
        eval_name: Name of the evaluation run.
        baseline_label: Display name of the baseline model.
        chart_files: List of chart PNG filenames in output_dir.
        output_dir: Directory containing charts and where dashboard is saved.

    Returns:
        Filename of the generated dashboard.
    """
    rm = metrics.model_router
    bm = metrics.baseline
    comp = metrics.comparison

    # ── KPI cards ────────────────────────────────────────────────────────
    cost_savings_text, cost_class = ("N/A", "neutral")
    if comp:
        cost_savings_text, cost_class = _pct_str(comp.cost_savings_ratio * 100)

    latency_text, latency_class = _latency_ratio_str(rm.latency, bm.latency)

    router_cost_str = f"${rm.cost.estimated_cost_usd:.4f}" if rm.cost else "N/A"
    baseline_cost_str = f"${bm.cost.estimated_cost_usd:.4f}" if bm.cost else "N/A"

    router_mean_str = f"{rm.latency.mean_ms:.0f}ms" if rm.latency else "N/A"
    baseline_mean_str = f"{bm.latency.mean_ms:.0f}ms" if bm.latency else "N/A"

    router_p50_str = f"{rm.latency.median_ms:.0f}ms" if rm.latency else "N/A"
    baseline_p50_str = f"{bm.latency.median_ms:.0f}ms" if bm.latency else "N/A"

    router_p90_str = f"{rm.latency.p90_ms:.0f}ms" if rm.latency else "N/A"
    baseline_p90_str = f"{bm.latency.p90_ms:.0f}ms" if bm.latency else "N/A"

    router_success = f"{rm.successful_requests}/{rm.total_requests}"
    baseline_success = f"{bm.successful_requests}/{bm.total_requests}"

    router_pct = (rm.successful_requests / rm.total_requests * 100) if rm.total_requests else 0
    baseline_pct = (bm.successful_requests / bm.total_requests * 100) if bm.total_requests else 0

    # ── Quality KPI data ─────────────────────────────────────────────────
    quality_kpis = ""
    q = metrics.quality
    if q and q.total_judged > 0:
        # Win rate card
        if q.router_win_rate >= q.baseline_win_rate:
            wr_class = "positive"
        else:
            wr_class = "negative"
        quality_kpis += f"""
    <div class="kpi-card">
      <div class="label">Quality Win Rate</div>
      <div class="value {wr_class}">{q.router_win_rate:.0%}</div>
      <div class="detail">{q.router_wins}W / {q.baseline_wins}L / {q.ties}T</div>
    </div>"""
        # Average quality score card
        if q.router_overall and q.baseline_overall:
            quality_kpis += f"""
    <div class="kpi-card">
      <div class="label">Avg Quality Score</div>
      <div class="value">{q.router_overall.mean:.2f}</div>
      <div class="detail">Baseline {q.baseline_overall.mean:.2f} (1-5 scale)</div>
    </div>"""

    # ── Embed chart images ───────────────────────────────────────────────
    chart_html_blocks: Dict[str, str] = {}
    priority_charts = [
        "chart_cost_comparison.png",
        "chart_latency_comparison.png",
        "chart_latency_distribution.png",
        "chart_model_distribution.png",
        "chart_category_latency.png",
        "chart_win_rates.png",
        "chart_score_comparison.png",
    ]
    for fname in priority_charts:
        chart_path = output_dir / fname
        if fname in chart_files and chart_path.exists():
            chart_html_blocks[fname] = _b64_img(chart_path)

    # ── Build HTML ───────────────────────────────────────────────────────
    charts_section = ""
    chart_titles = {
        "chart_cost_comparison.png": "Cost Comparison",
        "chart_latency_comparison.png": "Latency by Percentile",
        "chart_latency_distribution.png": "Latency Distribution",
        "chart_model_distribution.png": "Model Router &mdash; Model Distribution",
        "chart_category_latency.png": "Per-Category Latency",
        "chart_win_rates.png": "Quality: Win Rates",
        "chart_score_comparison.png": "Quality: Score Comparison",
    }
    for fname in priority_charts:
        if fname in chart_html_blocks:
            title = chart_titles.get(fname, fname)
            charts_section += f"""
            <div class="chart-card">
                <h3>{title}</h3>
                <img src="{chart_html_blocks[fname]}" alt="{title}">
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Model Router Evaluation — {_esc(eval_name)}</title>
<style>
  :root {{
    --blue: #2563EB;
    --purple: #9333EA;
    --green: #16A34A;
    --red: #DC2626;
    --gray-50: #F9FAFB;
    --gray-100: #F3F4F6;
    --gray-200: #E5E7EB;
    --gray-400: #9CA3AF;
    --gray-600: #4B5563;
    --gray-800: #1F2937;
    --gray-900: #111827;
    --radius: 12px;
    --shadow: 0 1px 3px rgba(0,0,0,.1), 0 1px 2px rgba(0,0,0,.06);
    --shadow-lg: 0 4px 12px rgba(0,0,0,.1);
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--gray-50);
    color: var(--gray-800);
    line-height: 1.5;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}

  /* Header */
  .header {{
    background: linear-gradient(135deg, var(--blue), var(--purple));
    color: white;
    padding: 32px;
    border-radius: var(--radius);
    margin-bottom: 24px;
    box-shadow: var(--shadow-lg);
  }}
  .header h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 4px; }}
  .header .subtitle {{ opacity: 0.85; font-size: 0.95rem; }}

  /* KPI row */
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}
  .kpi-card {{
    background: white;
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
    text-align: center;
  }}
  .kpi-card .label {{
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--gray-400);
    margin-bottom: 6px;
  }}
  .kpi-card .value {{
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.2;
  }}
  .kpi-card .detail {{
    font-size: 0.82rem;
    color: var(--gray-600);
    margin-top: 4px;
  }}
  .positive {{ color: var(--green); }}
  .negative {{ color: var(--red); }}
  .neutral  {{ color: var(--gray-600); }}

  /* Charts grid */
  .charts-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
    gap: 20px;
    margin-bottom: 24px;
  }}
  .chart-card {{
    background: white;
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
  }}
  .chart-card h3 {{
    font-size: 0.95rem;
    margin-bottom: 12px;
    color: var(--gray-800);
  }}
  .chart-card img {{
    width: 100%;
    height: auto;
    border-radius: 8px;
  }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 16px;
    font-size: 0.78rem;
    color: var(--gray-400);
  }}

  .sample-warning {{
    margin: 16px 0;
    padding: 12px 16px;
    border: 1px solid #f0ad4e;
    border-radius: 8px;
    background: #fff8e5;
    color: #7a4b00;
    font-weight: 600;
  }}

  @media (max-width: 640px) {{
    .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>Model Router Evaluation Dashboard</h1>
    <div class="subtitle">{_esc(eval_name)} &mdash; {rm.total_requests} prompts &mdash; Model Router vs {_esc(baseline_label)}</div>
  </div>

  {f'<div class="sample-warning">Smoke test: only {rm.total_requests} prompts were evaluated. Do not treat this run as statistically reliable evidence.</div>' if rm.total_requests < 30 else ''}

  <!-- KPI Cards -->
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="label">Cost Savings</div>
      <div class="value {cost_class}">{cost_savings_text}</div>
      <div class="detail">Router {router_cost_str} vs Baseline {baseline_cost_str}</div>
    </div>
    <div class="kpi-card">
      <div class="label">Latency (Mean)</div>
      <div class="value {latency_class}">{latency_text}</div>
      <div class="detail">Router {router_mean_str} vs Baseline {baseline_mean_str}</div>
    </div>
    <div class="kpi-card">
      <div class="label">Latency P50</div>
      <div class="value">{router_p50_str}</div>
      <div class="detail">Baseline {baseline_p50_str}</div>
    </div>
    <div class="kpi-card">
      <div class="label">Latency P90</div>
      <div class="value">{router_p90_str}</div>
      <div class="detail">Baseline {baseline_p90_str}</div>
    </div>
    <div class="kpi-card">
      <div class="label">Router Reliability</div>
      <div class="value">{router_pct:.0f}%</div>
      <div class="detail">{router_success} successful</div>
    </div>
    <div class="kpi-card">
      <div class="label">Baseline Reliability</div>
      <div class="value">{baseline_pct:.0f}%</div>
      <div class="detail">{baseline_success} successful</div>
    </div>
    {quality_kpis}
  </div>

  <!-- Charts -->
  <div class="charts-grid">
    {charts_section}
  </div>

  <!-- Footer -->
  <div class="footer">
    Generated by Microsoft Foundry Model Router Evaluation Tool
  </div>

</div>
</body>
</html>"""

    fname = "dashboard.html"
    (output_dir / fname).write_text(html, encoding="utf-8")
    return fname


# ── Helpers ──────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
