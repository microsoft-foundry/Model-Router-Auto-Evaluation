# Evaluation Methodology

How this tool measures quality, cost, and latency — and the statistical techniques used to keep results reliable.

> **Audience:** This page is for readers who want to understand *why* the numbers in the dashboard say what they do, evaluate whether the methodology is sound for their use case, or extend it. If you just want to run an evaluation and read the results, [QUICKSTART](../QUICKSTART.md) and [how-to-interpret-results.md](how-to-interpret-results.md) are enough.

## Plain-English summary

For every prompt in your dataset:

1. The tool sends the prompt to **Model Router** and to your chosen **baseline model** (e.g. GPT‑5).
2. It records both responses, plus how long each took and how many tokens they used.
3. A separate, more capable **judge model** reads the two responses and:
   - Scores each one independently on accuracy, completeness, clarity, and helpfulness (1–5).
   - Compares them head-to-head and picks a winner — **twice**, with the order swapped, to cancel out the LLM's tendency to prefer whichever response it sees first.
4. Cost is computed from token counts and the per-million-token prices in your config.
5. Everything is aggregated into the dashboard you see.

The rest of this page is the technical detail behind those steps.

## Quality evaluation: LLM-as-a-judge

"LLM-as-a-judge" means **using one language model to grade the output of another**. It's faster and cheaper than human grading, and — if done carefully — produces results that correlate well with human preferences. The two key risks are (a) judges with weak instructions give noisy scores, and (b) judges have systematic biases. We address both below.

### Pairwise comparison (dual-ordering)

For each prompt, the judge model compares the two responses side by side and picks a winner (A, B, or TIE).

**Anti-bias measure:** Each comparison is run **twice** with the responses swapped:

1. **Order 1:** A = Router response, B = Baseline response
2. **Order 2:** A = Baseline response, B = Router response

The final verdict:
- If both orderings agree → that's the winner
- If they disagree → position bias detected → TIE

This prevents the judge from favouring whichever response appears first (a well-documented LLM bias). It costs 2× judge calls but is the simplest way to get an unbiased pairwise signal.

### Absolute scoring

Each response is scored independently on four dimensions (1–5 scale):

| Dimension | What it measures |
|-----------|-----------------|
| **Accuracy** | Factual correctness of the response |
| **Completeness** | Whether all parts of the prompt are addressed |
| **Clarity** | Writing quality, structure, readability |
| **Helpfulness** | How useful the response would be to the user |

The overall score is the unweighted average of all four dimensions.

### Judge model

By default, the judge uses **gpt-5** (configurable in `configs/default.yaml`). The judge model should be:
- **More capable than the models being evaluated** (or at least comparable) — a weaker judge gives noisier scores
- **Consistent** — the same model should be used across the full evaluation
- **Not one of the models being evaluated** — to avoid self-preference bias

## Cost calculation

### Baseline model

```
cost = (input_price × prompt_tokens + output_price × completion_tokens) / 1,000,000
```

### Model Router

The router adds a markup on input tokens, on top of the underlying model's per-token cost:

```
cost = router_markup_input × prompt_tokens / 1,000,000
     + underlying_model_input × prompt_tokens / 1,000,000
     + underlying_model_output × completion_tokens / 1,000,000
```

The underlying model is identified from each API response's `model` field and matched to pricing via prefix matching (e.g. `gpt-5-mini-2025-08-07` matches `gpt-5-mini`).

### Pricing source

All prices are in USD per 1 million tokens, configured in the YAML config under `pricing:`. The default config includes 24 models with current Azure pricing. **Update these whenever Azure pricing changes** — the tool can't fetch them automatically.

## Latency measurement

Latency is measured as **wall-clock time** from the start of the API call to receiving the complete response (not streaming). This includes:
- Network round-trip time
- Model inference time
- Any queuing time at the endpoint

For fairness, the two endpoints are called **sequentially** per prompt (router first, then baseline), so neither is disadvantaged by concurrent load on the same endpoint.

Statistics reported:
- Mean, median (p50), p90, p95, p99, min, max
- Per-category breakdown (if categories are in the dataset)

> **Why percentiles matter more than mean:** A few slow outliers can drag the mean up dramatically. p95 ("95% of requests were faster than this") tells you about real worst-case user experience.

## Statistical considerations

### Sample size

More prompts → more reliable conclusions. Rule of thumb:

| Prompts | Statistical power |
|---------|------------------|
| < 30 | Directional only — not statistically significant |
| 30–100 | Moderate — useful for initial assessment |
| 100–500 | Good — reliable comparisons |
| 500+ | Strong — production-grade benchmarking |

### Confidence intervals

Quality win rates include bootstrap confidence intervals (1000 resamples, 95% CI) when the sample size is sufficient (n ≥ 20). A win rate of "55% ± 8%" is much weaker evidence of router superiority than "55% ± 2%".

### Category balance

Ensure your dataset has enough prompts per category (ideally 10+) for meaningful per-category breakdowns. Categories with fewer than 5 prompts may show high variance and shouldn't drive decisions.

---

## Foundry cloud evaluation mapping

When you run `scripts/run_foundry_eval.py`, the same evaluation data is submitted to Microsoft Foundry for cloud-based grading. The Foundry graders map directly to the local methodology:

### Quality graders

| Foundry grader | Type | Local equivalent | Notes |
|----------------|------|-----------------|-------|
| `quality_absolute_router` | `score_model` | Router absolute score (1–5) | Same rubric: rates response quality on a 1–5 scale |
| `quality_absolute_baseline` | `score_model` | Baseline absolute score (1–5) | Same rubric applied to the baseline model |
| `quality_pairwise` | `score_model` | Pairwise win rate | Compares router vs baseline head-to-head, score ≥ 3 = router wins |

The `score_model` graders use the same prompt templates (in `configs/grader_prompts/`) as the local judge prompts (`configs/judge_prompts/`), adapted for the Foundry evaluation API format.

### Cost and latency graders

| Foundry grader | Type | Local equivalent | Formula |
|----------------|------|-----------------|---------|
| `mr_cost_comparison` | `python` | Cost savings % | `1 - (router_cost / baseline_cost)` — higher is better |
| `mr_latency_comparison` | `python` | Latency diff | `1 - (router_latency / baseline_latency)` — higher means router is faster |

These are computed using Python-based graders that operate on the same cost and latency data used locally. See [foundry-cost-latency-design.md](foundry-cost-latency-design.md) for why this approach is used.

### Pass thresholds

| Grader | Pass condition | Interpretation |
|--------|---------------|----------------|
| Quality absolute | score ≥ 3 | Response is adequate or better |
| Quality pairwise | score ≥ 3 | Router is at least as good as baseline |
| Cost comparison | ratio ≥ 0.5 | Router saves ≥ 50% of baseline cost |
| Latency comparison | ratio ≥ 0.5 | Router is ≥ 50% faster than baseline |

### Interpreting cross-validation

When comparing local vs Foundry results (`scripts/cross_validate.py`):

- **Quality scores should correlate** — both use the same rubric, but Foundry uses a potentially different judge model, so ±0.5 mean-score difference is normal
- **Cost ratios should match closely** — both use the same pricing data, so differences > 5% indicate a data issue
- **Latency ratios should trend the same direction** — absolute values may differ due to rounding


## Cost Calculation

### Baseline model

```
cost = (input_price × prompt_tokens + output_price × completion_tokens) / 1,000,000
```

### Model Router

The router adds a markup on input tokens, on top of the underlying model's per-token cost:

```
cost = router_markup_input × prompt_tokens / 1,000,000
     + underlying_model_input × prompt_tokens / 1,000,000
     + underlying_model_output × completion_tokens / 1,000,000
```

The underlying model is identified from each API response's `model` field and matched to pricing via prefix matching (e.g. `gpt-5-mini-2025-08-07` matches `gpt-5-mini`).

### Pricing source

All prices are in USD per 1 million tokens, configured in the YAML config under `pricing:`. The default config includes 24 models with current Azure pricing.

## Latency Measurement

Latency is measured as **wall-clock time** from the start of the API call to receiving the complete response (not streaming). This includes:
- Network round-trip time
- Model inference time
- Any queuing time at the endpoint

For fairness, the two endpoints are called **sequentially** per prompt (router first, then baseline), so neither is disadvantaged by concurrent load.

Statistics reported:
- Mean, median (p50), p90, p95, p99, min, max
- Per-category breakdown (if categories are in the dataset)

## Statistical Considerations

### Sample size

| Prompts | Statistical power |
|---------|------------------|
| < 30 | Directional only — not statistically significant |
| 30–100 | Moderate — useful for initial assessment |
| 100–500 | Good — reliable comparisons |
| 500+ | Strong — production-grade benchmarking |

### Confidence intervals

Quality win rates include bootstrap confidence intervals (1000 resamples, 95% CI) when the sample size is sufficient (n ≥ 20).

### Category balance

Ensure your dataset has enough prompts per category (ideally 10+) for meaningful per-category breakdowns. Categories with fewer than 5 prompts may show high variance.

---

## Foundry Cloud Evaluation Mapping

When you run `scripts/run_foundry_eval.py`, the same evaluation data is submitted to Microsoft Foundry for cloud-based grading. The Foundry graders map directly to the local methodology:

### Quality graders

| Foundry Grader | Type | Local Equivalent | Notes |
|----------------|------|-----------------|-------|
| `quality_absolute_router` | `score_model` | Router absolute score (1-5) | Same rubric: rates response quality on a 1-5 scale |
| `quality_absolute_baseline` | `score_model` | Baseline absolute score (1-5) | Same rubric applied to the baseline model |
| `quality_pairwise` | `score_model` | Pairwise win rate | Compares router vs baseline head-to-head, score ≥ 3 = router wins |

The `score_model` graders use the same prompt templates (in `configs/grader_prompts/`) as the local judge prompts (`configs/judge_prompts/`), adapted for the Foundry evaluation API format.

### Cost and latency graders

| Foundry Grader | Type | Local Equivalent | Formula |
|----------------|------|-----------------|---------|
| `mr_cost_comparison` | `python` | Cost savings % | `1 - (router_cost / baseline_cost)` — higher is better |
| `mr_latency_comparison` | `python` | Latency diff | `1 - (router_latency / baseline_latency)` — higher means router is faster |

These are computed using Python-based graders that operate on the same cost and latency data used locally.

### Pass thresholds

| Grader | Pass Condition | Interpretation |
|--------|---------------|----------------|
| Quality absolute | score ≥ 3 | Response is adequate or better |
| Quality pairwise | score ≥ 3 | Router is at least as good as baseline |
| Cost comparison | ratio ≥ 0.5 | Router saves ≥ 50% of baseline cost |
| Latency comparison | ratio ≥ 0.5 | Router is ≥ 50% faster than baseline |

### Interpreting cross-validation

When comparing local vs Foundry results (`scripts/cross_validate.py`):

- **Quality scores should correlate** — both use the same rubric, but Foundry uses a potentially different judge model, so ±0.5 mean score difference is normal
- **Cost ratios should match closely** — both use the same pricing data, so differences > 5% indicate a data issue
- **Latency ratios should trend the same direction** — absolute values may differ due to rounding
