# Architecture

Technical design, component diagram, and extension points for the Model Router Evaluation toolkit.

> **Audience:** This page is for contributors who want to read or extend the source code, not for users running evaluations. If you just want to run an evaluation, the [QUICKSTART](../QUICKSTART.md), [how-to-run-live-eval.md](how-to-run-live-eval.md), and [how-to-interpret-results.md](how-to-interpret-results.md) cover everything you need.

## Component diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        scripts/run_eval.py                       │
│                       (CLI entry point)                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                        src/runner.py                              │
│                    (Evaluation orchestrator)                      │
│                                                                  │
│  1. Load dataset        ──▶ src/dataset.py                       │
│  2. Load checkpoint     ──▶ checkpoint_eval.jsonl (if --resume)  │
│  3. Run eval prompts    ──▶ src/client.py  ──▶ Azure OpenAI API  │
│  4. Compute metrics     ──▶ src/metrics.py                       │
│  5. Load judge ckpt     ──▶ checkpoint_judge.jsonl (if --resume) │
│  6. Run judge           ──▶ src/judge.py   ──▶ Azure OpenAI API  │
│  7. Generate report     ──▶ src/report.py + src/charts.py        │
│                              + src/dashboard.py                  │
└──────────────────────────────────────────────────────────────────┘
```

## Module Reference

| Module | Responsibility |
|--------|---------------|
| `config.py` | Load YAML config, substitute `${ENV_VAR}` references, validate |
| `dataset.py` | Load JSONL datasets, validate schema, optional sampling |
| `client.py` | `EvalClient` — async API calls with semaphore, retry, latency capture |
| `runner.py` | Orchestrator — checkpoint/resume, signal handling, progress bars |
| `judge.py` | `Judge` — pairwise (dual-ordering) + absolute scoring, anti-bias |
| `metrics.py` | Aggregate cost, latency, quality, model distribution |
| `charts.py` | Generate matplotlib charts (8 chart types) |
| `dashboard.py` | Generate self-contained HTML dashboard with embedded charts |
| `report.py` | Generate Markdown, CSV, and JSON outputs |

## Data Flow

```
JSONL dataset
    │
    ▼
┌─────────┐     ┌─────────────────┐     ┌──────────────┐
│ Prompts │────▶│ EvalClient      │────▶│ CompletionResult │──┐
│ (list)  │     │ (router+base)   │     │ (per endpoint)   │  │
└─────────┘     └─────────────────┘     └──────────────────┘  │
                                                               │
                ┌─────────────────┐     ┌──────────────┐      │
                │ Judge           │────▶│ JudgeResult   │──┐   │
                │ (4 calls/prompt)│     │ (per prompt)  │  │   │
                └─────────────────┘     └──────────────┘  │   │
                                                          │   │
                ┌─────────────────────────────────────────┘   │
                │                                             │
                ▼                                             ▼
         ┌──────────┐                               ┌──────────────┐
         │ Quality  │                               │ Cost/Latency │
         │ Metrics  │                               │ Metrics      │
         └────┬─────┘                               └──────┬───────┘
              │                                            │
              └──────────────┬─────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ EvalMetrics    │
                    │ (combined)     │
                    └────────┬───────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         report.md     dashboard.html   results.json
         results.csv   chart_*.png      raw_results.jsonl
```

## Key Design Decisions

### Sequential per-prompt, parallel across prompts

Each prompt calls router then baseline **sequentially** to ensure fair latency comparison (no interference from concurrent requests to the same endpoint). Multiple prompts run in parallel via `asyncio.as_completed()`.

### Semaphore-based concurrency

A single `asyncio.Semaphore` controls how many API calls are in flight simultaneously. This is simpler and more predictable than a worker pool, and integrates naturally with async/await.

### Checkpoint as append-only JSONL

Results are appended one line at a time with `flush()`. This is crash-safe — even a power loss loses at most one in-flight result. The tradeoff is that checkpoint files grow linearly; they're cleaned up on successful completion.

### Signal-based graceful shutdown

SIGINT is caught by a signal handler that sets an `asyncio.Event`. The event loop checks this between prompts, allowing in-flight requests to complete naturally. This avoids the complexity of cancellation and ensures data integrity.

### Dual-ordering for pairwise judge

Position bias (preferring response A because it appears first) is a known issue with LLM judges. Running each comparison twice with swapped order and requiring agreement for a non-tie verdict eliminates this bias at the cost of 2x judge calls.

## Extension Points

| Want to... | Where to look |
|------------|--------------|
| Add a new chart type | `src/charts.py` — add a function, register in `generate_charts()` |
| Add a new metric | `src/metrics.py` — add to `EndpointMetrics` or `EvalMetrics` |
| Support a new API provider | `src/client.py` — add a branch in `_build_client()` |
| Change judge scoring | `configs/judge_prompts/*.yaml` — edit the prompt templates |
| Add a new report format | `src/report.py` — add alongside `_generate_markdown()` etc. |
| Change the dashboard layout | `src/dashboard.py` — edit the HTML template |

## Foundry Cloud Evaluation (Optional)

An optional post-processing layer submits evaluation results to Microsoft Foundry for cloud-based grading.

```
┌──────────────────────────────────────────────────────────────┐
│  Original Pipeline (unchanged)                                │
│  configs/*.yaml → measure endpoints → raw_results.jsonl       │
└──────────────────────────┬───────────────────────────────────┘
                           │ raw_results.jsonl + results.json
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  src/foundry/ (new, optional)                                 │
│  transformer → client → graders/custom_evaluators →           │
│  runner → report                                              │
│  ↕ Microsoft Foundry cloud (eval runs, portal)                 │
└──────────────────────────────────────────────────────────────┘
```

| Module | Responsibility |
|--------|---------------|
| `foundry/config.py` | Load `configs/foundry.yaml`, env var substitution |
| `foundry/transformer.py` | Pair router+baseline per prompt into Foundry JSONL |
| `foundry/client.py` | `FoundryEvalClient` wrapping `AIProjectClient` |
| `foundry/graders.py` | Build `score_model` testing criteria from YAML templates |
| `foundry/custom_evaluators.py` | Register code-based evaluators for cost & latency |
| `foundry/runner.py` | End-to-end orchestrator |
| `foundry/report.py` | Markdown + JSON report from Foundry results |

**Design principle:** Zero impact on the core evaluation flow. No Foundry imports in existing code.
