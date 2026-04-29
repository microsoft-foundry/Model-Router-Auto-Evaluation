# Foundry Evaluation Integration — Design Rationale

## Context
The Foundry Evaluations service integration is a separate post-processing layer — the core eval flow is untouched. See [how-to-foundry-eval-sdk.md](how-to-foundry-eval-sdk.md) for details and [faq.md](faq.md) for Foundry troubleshooting.

Foundry Evaluation natively supports **quality grading** via `score_model` graders — LLM-as-a-judge evaluators that score text responses. 

It **does not** natively support **cost benchmarking** or **latency benchmarking** as built-in evaluation dimensions. For cost and latency — which Foundry doesn't evaluate out of the box — we use `python` graders that score pre-computed metrics from the local eval run. This gives you a unified quality + cost + latency view in a single Foundry eval, while keeping the door open for native support when it arrives.

This repo extends Foundry to cover all three dimensions (quality, cost, latency) in a single eval run using a pattern built on supported SDK primitives.

---

## Approach

We use Foundry's `python` grader type to run custom cost and latency scoring code inside the Foundry eval pipeline. The key insight: **cost and latency data is pre-computed during the local eval run and embedded into the JSONL data that gets uploaded to Foundry.** The Python graders then perform simple arithmetic on that pre-computed data.

### How it works

```
Local eval run (scripts/run_eval.py)
  ├── Calls Model Router + Baseline for each prompt
  ├── Records cost (tokens × pricing) and latency (wall clock) per request
  └── Writes raw_results.jsonl + results.json

Transformer (src/foundry/transformer.py)
  ├── Reads raw_results.jsonl
  ├── Enriches each row with: router_cost_usd, baseline_cost_usd,
  │   router_latency_ms, baseline_latency_ms, router_response, baseline_response
  └── Writes foundry_input.jsonl

Foundry eval submission (src/foundry/runner.py)
  ├── Uploads foundry_input.jsonl as a Foundry file
  ├── Creates eval with 5 graders:
  │   ├── quality_absolute_router    (score_model) — rates router response 1-5
  │   ├── quality_absolute_baseline  (score_model) — rates baseline response 1-5
  │   ├── quality_pairwise           (score_model) — head-to-head comparison
  │   ├── mr_cost_comparison         (python)      — scores cost savings
  │   └── mr_latency_comparison      (python)      — scores latency improvement
  └── All 5 graders run in a single eval run, producing unified results
```

### Score design for cost and latency graders

Both custom graders return a float in `[0.0, 1.0]`:

| Score | Meaning |
|-------|---------|
| 1.0   | Router is free / instant compared to baseline |
| 0.75  | Router saves ~50% vs baseline |
| 0.5   | Parity — router and baseline are equivalent |
| 0.25  | Router costs ~50% more / is ~50% slower |
| 0.0   | Router costs 2× more / takes 2× as long |

Formula (cost): `score = 0.5 + ((baseline_cost - router_cost) / baseline_cost) × 0.5`

Formula (latency): `score = 0.5 + ((baseline_latency - router_latency) / baseline_latency) × 0.5`

The default pass threshold is `≥ 0.5` (router is at least as good as baseline).

---

## What's genuinely good about this pattern

1. **Uses official SDK primitives** — the `python` grader type is a supported Foundry feature, not a hack. Cost and latency scores flow through the same eval pipeline as quality, producing unified results in the Foundry portal.

2. **Single eval run, three dimensions** — Quality (`score_model`), cost (`python`), and latency (`python`) graders all execute in one `evals.create()` / `runs.create()` call. Users see one results page, not three separate workflows.

3. **Pre-computed data, not live measurement** — The transformer bakes cost and latency data into the JSONL before upload. The Python graders just do arithmetic. This is deterministic and reproducible.

4. **Portal integration** — Results appear in the Microsoft Foundry portal alongside quality scores, with pass/fail indicators, mean scores, and per-item drill-down.

---

## What to be transparent about

| Aspect | Reality |
|--------|---------|
| **Cost/latency are not "evaluated by Foundry"** | Foundry just runs your Python code. The actual cost/latency data comes from the local eval run — Foundry doesn't measure anything. |
| **Pass/fail thresholds are a convention** | The 0.5 threshold ("router must be at least as good as baseline to pass") is a convention we chose, not a Foundry standard. Teams should tune thresholds to their requirements. |
| **No Foundry-native cost/latency benchmarking exists** | This fills a gap. If Foundry adds native support later, this pattern becomes tech debt. |
| **Scores are relative, not absolute** | A cost score of 0.95 means "router is much cheaper than *this specific baseline*," not "router is cheap in absolute terms." |
| **Data freshness** | Cost and latency data reflect the local eval run conditions (network, load, pricing at the time). Re-running the local eval may produce different numbers. |

---

## Recommended framing

When communicating this approach to customers or stakeholders:

> "Foundry Evaluations supports quality grading natively via `score_model` graders. For cost and latency — which Foundry doesn't evaluate out of the box — we use `python` graders that score pre-computed metrics from the local eval run. This gives you a unified quality + cost + latency view in a single Foundry eval, while keeping the door open for native support when it arrives."

This framing is honest, positions the approach as a **pattern** (not a product feature), and doesn't overstate what Foundry is doing under the hood.

---

## Files involved

| File | Role |
|------|------|
| [`src/foundry/custom_evaluators.py`](../src/foundry/custom_evaluators.py) | Python grader source code for cost and latency |
| [`src/foundry/graders.py`](../src/foundry/graders.py) | Builds `score_model` criteria for quality graders |
| [`src/foundry/transformer.py`](../src/foundry/transformer.py) | Enriches local results into Foundry JSONL format |
| [`src/foundry/runner.py`](../src/foundry/runner.py) | Orchestrates eval creation, file upload, run execution |
| [`configs/foundry.yaml`](../configs/foundry.yaml) | Grader configuration and thresholds |
| [`configs/grader_prompts/`](../configs/grader_prompts/) | Quality grader prompt templates |

---

## Future considerations

- If Foundry adds native cost/latency evaluation, migrate from `python` graders to the built-in equivalent and remove the custom evaluator code.
- The `python` grader sandbox has limited library access — the grader code intentionally uses only built-in Python (no imports).
- The score formula could be made configurable via `configs/foundry.yaml` if teams want different sensitivity curves.
