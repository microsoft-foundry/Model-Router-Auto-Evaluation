# How to: Foundry Cloud Evaluation

Submit your Model Router evaluation results to **Microsoft Foundry** for cloud-based grading with governance, CI/CD integration, RBAC, and portal visibility.

> **Audience:** Teams who want managed, reproducible grading runs that show up in the Microsoft Foundry portal alongside other evaluations — useful for sharing results with stakeholders, gating CI/CD on quality scores, or auditing model behaviour over time. If you just want a local HTML dashboard, the regular [live evaluation](how-to-run-live-eval.md) is enough.

## What's different from a local evaluation?

A **local eval** (`scripts/run_eval.py`) calls Azure endpoints from your machine and grades the responses with a judge model you configured. Results live on your laptop.

A **Foundry cloud eval** takes the responses you already collected locally and submits them to Microsoft Foundry, where managed graders re-score them server-side. Results show up in the [Foundry portal](https://ai.azure.com) with pass/fail indicators, per-prompt drill-down, and shareable links.

You typically run *both* — the local eval gives you charts and a dashboard, then the Foundry eval gives you a managed, auditable grading layer on top of the same raw data.

## Prerequisites

1. **Complete a local evaluation** — run [`python scripts/run_eval.py`](how-to-run-live-eval.md) first to generate `raw_results.jsonl` and `results.json`. The Foundry eval re-scores those files; it doesn't generate new responses.
2. **A Microsoft Foundry project** — with at least one model deployed (used as the cloud-side grader)
3. **Azure CLI** — `az login` for authentication (no API keys needed)

## Setup

```bash
# Install Foundry SDK dependencies
pip install -e ".[foundry]"

# Authenticate with Azure (uses your AAD identity, no API key)
az login

# Set environment variables (or add to .env)
export AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com
export AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5
```

Find your project endpoint in the Foundry portal under **Project settings → Overview**.

## Quick start

```bash
# Dry run — validates config, transforms data, no API calls
python scripts/run_foundry_eval.py --dry-run

# Full evaluation using default results directory
python scripts/run_foundry_eval.py --input-dir results/full-eval

# Custom config
python scripts/run_foundry_eval.py --config configs/foundry.yaml --input-dir results/full-eval
```

When the run completes, the script prints a portal URL where you can browse the graded results.

## Configuration

Edit `configs/foundry.yaml` to customize:

```yaml
foundry:
  project_endpoint: "${AZURE_AI_PROJECT_ENDPOINT}"
  model_deployment_name: "${AZURE_AI_MODEL_DEPLOYMENT_NAME}"

graders:
  quality:
    enabled: true
    pass_threshold: 3        # 1-5 scale; ≥3 = pass
    range: [1, 5]
  cost:
    enabled: true
    evaluator_name: "mr_cost_comparison"
    pass_threshold: 0.5      # 0-1 scale; ≥0.5 = router at least as cheap as baseline
  latency:
    enabled: true
    evaluator_name: "mr_latency_comparison"
    pass_threshold: 0.5      # 0-1 scale; ≥0.5 = router at least as fast as baseline
```

## What gets graded

| Dimension | Method | Score scale |
|-----------|--------|------------|
| **Quality** | `score_model` grader (LLM-based) | 1–5 (3 = pass) |
| **Cost** | Code-based custom evaluator | 0.0–1.0 (0.5 = parity) |
| **Latency** | Code-based custom evaluator | 0.0–1.0 (0.5 = parity) |

For cost and latency, scores > 0.5 mean the router wins, < 0.5 means the baseline wins. See [foundry-cost-latency-design.md](foundry-cost-latency-design.md) for *why* cost and latency use code-based graders rather than LLM graders.

## CLI options

```
--config PATH       Foundry config file (default: configs/foundry.yaml)
--input-dir PATH    Directory with raw_results.jsonl + results.json (the local eval output)
--dataset PATH      Original dataset for prompt text enrichment
--dry-run           Validate and transform without calling Foundry
--skip-quality      Skip LLM quality graders (only run cost/latency)
--skip-custom       Skip cost/latency evaluators (only run quality)
```

## Output

Results are written to the directory specified in `configs/foundry.yaml`:

| File | Content |
|------|---------|
| `foundry_input.jsonl` | Transformed input data (paired router + baseline) that was uploaded to Foundry |
| `report.md` | Markdown summary with grader scores and pass rates |
| `results.json` | Machine-readable results |

A link to the **Foundry portal** is printed if available, where you can drill into individual results.

## Cleanup

The Foundry eval registers custom evaluators (for cost and latency) in your project. To remove them:

```bash
python scripts/cleanup_foundry_evaluators.py
```

Safe to run any time — it only removes evaluators created by this tool.

## Architecture

The Foundry integration is a separate `src/foundry/` subpackage with zero impact on the core evaluation flow. See [architecture.md](architecture.md) for the component diagram and [foundry-cost-latency-design.md](foundry-cost-latency-design.md) for the design rationale.

