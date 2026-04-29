# How To: Interpret Results

A plain-language guide to every output file, chart, and metric the evaluation produces — so you can answer the only question that really matters: **"Should I use Model Router for my workload?"**

> **First time here?** Run the [QUICKSTART](../QUICKSTART.md) demo first. The dashboard you generated there has exactly the same charts as a real evaluation — just filled with synthetic data — so you can use this guide alongside the demo output.

## How to read a run in 60 seconds

Open `dashboard.html` and look at three things:

1. **Cost comparison chart** → Did Model Router save money? (Lower bar = cheaper.)
2. **Latency comparison chart** → Did Model Router add lag? (Look at p95/p99, not just mean.)
3. **Pairwise win rates / absolute scores** → Did quality hold up?

If cost dropped, latency stayed flat or improved, and quality is within 0.3 points of the baseline, Model Router is a win for your workload. The rest of this page explains *why* each chart says what it does.

## Glossary (terms that show up in the report)

| Term | Plain English |
|---|---|
| **Router** | The Model Router endpoint — the system being evaluated |
| **Baseline** | The fixed model you compared against (e.g. GPT‑5) |
| **p50 / p90 / p95 / p99** | Latency percentiles. p95 = 95% of requests were faster than this. The high percentiles tell you about *worst-case* user experience, not the average |
| **Pairwise win rate** | Out of all prompts, what % did the judge prefer the router's answer for? |
| **Absolute score** | A 1–5 grade per response on accuracy/completeness/clarity/helpfulness, given by the judge model |
| **Tie** | The judge couldn't pick a clear winner — either both responses were similar quality, or position bias was detected and the result was discarded |
| **Position bias** | LLM judges tend to prefer whichever response they see first. We run each comparison twice with swapped order to detect and neutralise this |

---

## Output files

After an evaluation run, the output directory contains:

| File | What it is |
|------|-----------|
| `dashboard.html` | **Start here.** Self-contained HTML with all charts and metrics — open in any browser, no server needed |
| `report.md` | Markdown summary — good for pasting into docs, PRs, or Slack |
| `detailed_results.csv` | Per-prompt data: latency, tokens, model, status — open in Excel for further analysis |
| `results.json` | Machine-readable metrics for programmatic consumption (CI gates, dashboards) |
| `raw_results.jsonl` | Full API responses including response text — useful when debugging quality issues |
| `chart_*.png` | Individual chart images — paste into slides |

## Charts

### Cost comparison

Bar chart comparing total estimated cost (USD) for Model Router vs baseline. The router cost includes the markup on input tokens plus the underlying model's per-token pricing. **Lower is better.**

### Latency comparison

Bar chart showing mean, p50, p90, p95, p99 latency for both endpoints. The mean can hide a long tail — always check p95/p99 to understand the *worst* user experience, not just the average.

### Latency distribution

Histogram showing the spread of per-prompt latencies. A tighter distribution means more predictable response times, which often matters more in production than raw average speed.

### Per-category latency

Grouped bar chart breaking down mean latency by prompt category (if your dataset has them). Helps identify which types of prompts the router handles faster or slower than the baseline.

### Token usage breakdown

Stacked bar chart showing prompt tokens vs completion tokens for each endpoint. If the router and baseline produce very different completion lengths, that affects both cost and latency — this chart shows it directly.

### Model distribution

Pie chart showing which underlying models the router picked, and how often. **This is the chart that explains *how* Model Router achieved its cost/latency numbers** — e.g. routing simple prompts to cheaper models and complex ones to more capable models.

### Pairwise win rates (quality)

Bar chart showing the percentage of prompts where Model Router won, lost, or tied against the baseline in a head-to-head judge comparison. Uses dual-ordering to cancel position bias (see Glossary).

### Absolute score comparison

Bar chart comparing mean scores (1–5) across four dimensions: Accuracy, Completeness, Clarity, and Helpfulness. Useful when the pairwise rate is close — absolute scores reveal whether "tie" means "both great" or "both mediocre".

## Key metrics

### Cost

| Metric | Description |
|--------|-------------|
| `estimated_cost_usd` | Total estimated cost based on token counts and configured pricing |
| `cost_per_prompt_avg_usd` | Average cost per prompt |
| `cost_savings_ratio` | `(baseline_cost - router_cost) / baseline_cost` — positive means router is cheaper |

### Latency

| Metric | Description |
|--------|-------------|
| `mean_ms` | Average response time (in milliseconds) |
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

### Model distribution

| Metric | Description |
|--------|-------------|
| `model_distribution` | Dict mapping model name → count of prompts served |

## Reading the Markdown report

`report.md` follows this structure:

1. **Header** — evaluation name, timestamp, prompt count
2. **Cost summary** — total and per-prompt costs, savings ratio
3. **Latency summary** — percentile table, per-category breakdown
4. **Model distribution** — which models the router picked
5. **Quality summary** — win rates, absolute scores (if judge was enabled)
6. **Configuration** — endpoints, pricing, concurrency settings used (so the run is reproducible)

## What good results look like

A "Model Router is working" result typically has:

- **Cost savings > 0%** — the router found cheaper models for at least some prompts
- **Latency diff near 0 or negative** — router isn't adding significant overhead
- **Win rate ≥ 40%, loss rate < 20%** — quality is maintained or improved
- **Absolute scores within 0.3 of baseline** — no significant quality degradation

If cost is way down but quality also dropped, the router is just picking cheap-and-bad models for your workload — that's not a win, and you may need a stricter routing policy or a different baseline.

---

## Foundry cloud evaluation results

If you also ran [`python scripts/run_foundry_eval.py`](how-to-foundry-eval-sdk.md), the `results/foundry-eval/` directory contains:

| File | What it is |
|------|----------|
| `report.md` | Grader results table with mean scores and pass rates |
| `results.json` | Machine-readable: `grader_summary`, `per_item_scores`, `result_counts` |
| `foundry_input.jsonl` | The transformed data that was uploaded to Foundry |

### Foundry grader summary

The `grader_summary` in `results.json` contains per-grader statistics:

| Field | Description |
|-------|------------|
| `mean` | Average score across all prompts |
| `pass_rate` | Percentage of prompts that passed the threshold |
| `count` | Number of prompts scored |

### Foundry graders explained

| Grader | Type | Pass threshold | What it measures |
|--------|------|---------------|------------------|
| `quality_absolute_router` | `score_model` | ≥ 3/5 | Router response quality |
| `quality_absolute_baseline` | `score_model` | ≥ 3/5 | Baseline response quality |
| `quality_pairwise` | `score_model` | ≥ 3/5 | Head-to-head: is router ≥ baseline? |
| `mr_cost_comparison` | `python` | ≥ 0.5 | Cost savings ratio: `1 - (router/baseline)` |
| `mr_latency_comparison` | `python` | ≥ 0.5 | Latency improvement ratio |

### Per-item scores

The `per_item_scores` array shows each prompt's individual grader results, useful for identifying which prompts the router handles well or poorly.

### Cross-validation

Run `python scripts/cross_validate.py` to compare local and Foundry results side by side. Both pipelines should agree on quality direction, cost savings (±5%), and latency trends. Larger disagreements usually mean the local judge model is materially different from the Foundry grader model.


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