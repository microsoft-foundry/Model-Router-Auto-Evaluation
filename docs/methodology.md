# Evaluation Methodology

How this tool measures quality, cost, and latency — and the statistical techniques used to ensure reliable results.

## Quality Evaluation: LLM-as-a-Judge

### Pairwise Comparison (Dual-Ordering)

For each prompt, the judge model compares the two responses side by side and picks a winner (A, B, or TIE).

**Anti-bias measure:** Each comparison is run **twice** with the responses swapped:

1. **Order 1:** A = Router response, B = Baseline response
2. **Order 2:** A = Baseline response, B = Router response

The final verdict:
- If both orderings agree → that's the winner
- If they disagree → position bias detected → TIE

This prevents the judge from favoring whichever response appears first (a well-documented LLM bias).

### Absolute Scoring

Each response is scored independently on four dimensions (1–5 scale):

| Dimension | What it measures |
|-----------|-----------------|
| **Accuracy** | Factual correctness of the response |
| **Completeness** | Whether all parts of the prompt are addressed |
| **Clarity** | Writing quality, structure, readability |
| **Helpfulness** | How useful the response would be to the user |

The overall score is the unweighted average of all four dimensions.

### Judge Model

By default, the judge uses **gpt-5** (configurable in `configs/default.yaml`). The judge model should be:
- More capable than the models being evaluated (or at least comparable)
- Consistent — the same model should be used across the full evaluation
- Not one of the models being evaluated (to avoid self-preference bias)

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
