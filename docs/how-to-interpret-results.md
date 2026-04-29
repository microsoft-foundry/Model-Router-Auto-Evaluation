# How To: Interpret Results

A guide to every output file, chart, and metric in the evaluation report.

## Output Files

After an evaluation run, the output directory contains:

| File | What it is |
|------|-----------|
| `dashboard.html` | **Start here.** Self-contained HTML with all charts and metrics. |
| `report.md` | Markdown summary — good for pasting into docs or PRs. |
| `detailed_results.csv` | Per-prompt data: latency, tokens, model, status. |
| `results.json` | Machine-readable metrics for programmatic consumption. |
| `raw_results.jsonl` | Full API responses including response text. |
| `chart_*.png` | Individual chart images. |

## Charts

### Cost Comparison

Bar chart comparing total estimated cost (USD) for Model Router vs baseline. The router cost includes the markup on input tokens plus the underlying model's per-token pricing. Lower is better.

### Latency Comparison

Bar chart showing mean, p50, p90, p95, p99 latency for both endpoints. Shows whether the router adds latency overhead or finds faster models.

### Latency Distribution

Histogram showing the spread of per-prompt latencies. A tighter distribution means more predictable response times.

### Per-Category Latency

Grouped bar chart breaking down mean latency by prompt category (if categories are present in your dataset). Helps identify which types of prompts the router handles faster or slower.

### Token Usage Breakdown

Stacked bar chart showing prompt tokens vs completion tokens for each endpoint. Useful for understanding if one endpoint generates longer responses.

### Model Distribution

Pie chart showing which underlying models the router selected and how often. This reveals the router's strategy — e.g. routing simple prompts to cheaper/faster models and complex ones to more capable models.

### Pairwise Win Rates (Quality)

Bar chart showing the percentage of prompts where Model Router won, lost, or tied against the baseline in pairwise comparison. Uses dual-ordering to cancel position bias.

### Absolute Score Comparison

Bar chart comparing mean scores (1–5) across four dimensions: Accuracy, Completeness, Clarity, and Helpfulness.

## Key Metrics

### Cost

| Metric | Description |
|--------|-------------|
| `estimated_cost_usd` | Total estimated cost based on token counts and configured pricing |
| `cost_per_prompt_avg_usd` | Average cost per prompt |
| `cost_savings_ratio` | `(baseline_cost - router_cost) / baseline_cost` — positive means router is cheaper |

### Latency

| Metric | Description |
|--------|-------------|
| `mean_ms` | Average response time |
| `median_ms` | 50th percentile (p50) |
| `p90_ms` / `p95_ms` / `p99_ms` | Tail latency percentiles |
| `latency_diff_mean_ms` | `router_mean - baseline_mean` — negative means router is faster |

### Quality

| Metric | Description |
|--------|-------------|
| `router_win_rate` | % of prompts where router response was preferred |
| `baseline_win_rate` | % of prompts where baseline was preferred |
| `tie_rate` | % of prompts with no clear winner |
| `router_mean_overall` | Mean absolute score (1–5) across all dimensions |
| `baseline_mean_overall` | Same for baseline |

### Model Distribution

| Metric | Description |
|--------|-------------|
| `model_distribution` | Dict mapping model name → count of prompts served |

## Reading the Markdown Report

The `report.md` follows this structure:

1. **Header** — evaluation name, timestamp, prompt count
2. **Cost Summary** — total and per-prompt costs, savings ratio
3. **Latency Summary** — percentile table, per-category breakdown
4. **Model Distribution** — which models the router selected
5. **Quality Summary** — win rates, absolute scores (if judge was enabled)
6. **Configuration** — endpoints, pricing, concurrency settings used

## What Good Results Look Like

- **Cost savings > 0%** — the router found cheaper models for some prompts
- **Latency diff near 0 or negative** — router isn't adding significant overhead
- **Win rate >= 40%, loss rate < 20%** — quality is maintained or improved
- **Absolute scores within 0.3 of baseline** — no significant quality degradation
---

## Foundry Cloud Evaluation Results

If you ran `python scripts/run_foundry_eval.py`, the `results/foundry-eval/` directory contains:

| File | What it is |
|------|----------|
| `report.md` | Grader results table with mean scores and pass rates |
| `results.json` | Machine-readable: `grader_summary`, `per_item_scores`, `result_counts` |
| `foundry_input.jsonl` | The transformed data that was uploaded to Foundry |

### Foundry Grader Summary

The `grader_summary` in `results.json` contains per-grader statistics:

| Field | Description |
|-------|------------|
| `mean` | Average score across all prompts |
| `pass_rate` | Percentage of prompts that passed the threshold |
| `count` | Number of prompts scored |

### Foundry Graders Explained

| Grader | Type | Pass Threshold | What it measures |
|--------|------|---------------|------------------|
| `quality_absolute_router` | `score_model` | ≥ 3/5 | Router response quality |
| `quality_absolute_baseline` | `score_model` | ≥ 3/5 | Baseline response quality |
| `quality_pairwise` | `score_model` | ≥ 3/5 | Head-to-head: is router ≥ baseline? |
| `mr_cost_comparison` | `python` | ≥ 0.5 | Cost savings ratio: `1 - (router/baseline)` |
| `mr_latency_comparison` | `python` | ≥ 0.5 | Latency improvement ratio |

### Per-Item Scores

The `per_item_scores` array shows each prompt’s individual grader results, useful for identifying which prompts the router handles well or poorly.

### Cross-Validation

Run `python scripts/cross_validate.py` to compare local and Foundry results side by side. Both pipelines should agree on quality direction, cost savings (±5%), and latency trends.