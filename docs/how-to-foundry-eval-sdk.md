# How to: Foundry Cloud Evaluation

Submit your Model Router evaluation results to **Microsoft Foundry** for cloud-based grading with governance, CI/CD integration, RBAC, and portal visibility.

## Prerequisites

1. **Complete a local evaluation** — run `python scripts/run_eval.py` first to generate `raw_results.jsonl` and `results.json`
2. **Microsoft Foundry project** — an Microsoft Foundry project with a deployed model
3. **Azure CLI** — `az login` for authentication (no API keys needed)

## Setup

```bash
# Install Foundry SDK dependencies
pip install -e ".[foundry]"

# Authenticate with Azure
az login

# Set environment variables (or add to .env)
export AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com
export AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5
```

## Quick Start

```bash
# Dry run — validates config, transforms data, no API calls
python scripts/run_foundry_eval.py --dry-run

# Full evaluation using default results directory
python scripts/run_foundry_eval.py --input-dir results/full-eval

# Custom config
python scripts/run_foundry_eval.py --config configs/foundry.yaml --input-dir results/full-eval
```

## Configuration

Edit `configs/foundry.yaml` to customize:

```yaml
foundry:
  project_endpoint: "${AZURE_AI_PROJECT_ENDPOINT}"
  model_deployment_name: "${AZURE_AI_MODEL_DEPLOYMENT_NAME}"

graders:
  quality:
    enabled: true
    pass_threshold: 3
    range: [1, 5]
  cost:
    enabled: true
    evaluator_name: "mr_cost_comparison"
    pass_threshold: 0.5
  latency:
    enabled: true
    evaluator_name: "mr_latency_comparison"
    pass_threshold: 0.5
```

## What Gets Graded

| Dimension | Method | Score Scale |
|-----------|--------|------------|
| **Quality** | `score_model` grader (LLM-based) | 1–5 (3 = pass) |
| **Cost** | Code-based custom evaluator | 0.0–1.0 (0.5 = parity) |
| **Latency** | Code-based custom evaluator | 0.0–1.0 (0.5 = parity) |

For cost and latency: scores > 0.5 mean the router wins, < 0.5 means the baseline wins.

## CLI Options

```
--config PATH       Foundry config file (default: configs/foundry.yaml)
--input-dir PATH    Directory with raw_results.jsonl + results.json
--dataset PATH      Original dataset for prompt text enrichment
--dry-run           Validate and transform without calling Foundry
--skip-quality      Skip LLM quality graders (only run cost/latency)
--skip-custom       Skip cost/latency evaluators (only run quality)
```

## Output

Results are written to the directory specified in `configs/foundry.yaml`:

| File | Content |
|------|---------|
| `foundry_input.jsonl` | Transformed input data (paired router + baseline) |
| `report.md` | Markdown summary with grader scores |
| `results.json` | Machine-readable results |

A link to the **Foundry portal** is printed if available, where you can drill into individual results.

## Cleanup

To remove registered custom evaluators from your Foundry project:

```bash
python scripts/cleanup_foundry_evaluators.py
```

## Architecture

The Foundry integration is a separate `src/foundry/` subpackage with zero impact on the core evaluation flow. See [architecture.md](architecture.md) for the component diagram.
