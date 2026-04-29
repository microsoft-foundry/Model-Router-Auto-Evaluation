# How To: Run a Live Evaluation

This guide walks you through running a real evaluation of Microsoft Foundry Model Router against a baseline model using your Azure endpoints.

## Prerequisites

- Python 3.9+
- A Microsoft Foundry **Model Router** deployment
- An Azure OpenAI **baseline model** deployment (e.g. GPT-5, GPT-4o)
- API keys for both endpoints

## Step 1: Install

```bash
git clone https://github.com/<your-org>/model-router-eval.git
cd model-router-eval
pip install -e .
```

Or use the setup script:

```bash
# Windows
.\scripts\setup.ps1

# Linux / macOS
bash scripts/setup.sh
```

## Step 2: Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` with your real values:

```
AZURE_MODEL_ROUTER_ENDPOINT=https://your-resource.services.ai.azure.com/models
AZURE_MODEL_ROUTER_KEY=your-model-router-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your-azure-openai-key
```

> **Security note:** `.env` is gitignored and never committed.

## Step 3: Configure the Evaluation

The default config (`configs/default.yaml`) is ready to use. Key settings to review:

| Setting | Where | Default |
|---------|-------|---------|
| Baseline model | `endpoints.baseline.deployment_name` | `gpt-5` |
| Number of prompts | `evaluation.sample_size` | `null` (all) |
| Judge enabled | `judge.enabled` | `true` |
| Concurrency | `concurrency.max_parallel_requests` | `5` |

To change the baseline model, edit `configs/default.yaml`:

```yaml
endpoints:
  baseline:
    deployment_name: "gpt-4o"   # or any model you want to compare against
```

## Step 4: Validate (Dry Run)

Before making API calls, validate your config and dataset:

```bash
python scripts/run_eval.py --dry-run
```

This checks:
- All environment variables resolve
- Dataset file loads and parses correctly
- Config values are valid

## Step 5: Run the Evaluation

```bash
# Full eval with default config
python scripts/run_eval.py

# With a custom dataset
python scripts/run_eval.py --dataset my_prompts.jsonl

# Subset of prompts
python scripts/run_eval.py --sample-size 50

# Custom output directory
python scripts/run_eval.py --output-dir results/my-eval
```

You'll see a progress bar:

```
Evaluating: 100%|████████████████| 10/10 [00:42<00:00, 4.2s/prompt]
Judging:    100%|████████████████| 10/10 [01:15<00:00, 7.5s/prompt]
```

## Step 6: View Results

Open the HTML dashboard:

```bash
# The path is printed at the end of the run
# e.g. results/default/dashboard.html
```

See [how-to-interpret-results.md](how-to-interpret-results.md) for a guide to every chart and metric.

## Common Options

```bash
# Resume an interrupted run
python scripts/run_eval.py --resume --output-dir results/my-eval

# Use a different config preset
python scripts/run_eval.py --config configs/large_scale.yaml

# Disable judge (cost + latency only)
# Edit configs/default.yaml: judge.enabled: false
```

## Next Steps

- [Submit results to Foundry for cloud grading](how-to-foundry-eval-sdk.md)
- [Cross-validate local vs Foundry results](../scripts/cross_validate.py): `python scripts/cross_validate.py`
- [Bring your own dataset](how-to-custom-dataset.md)
- [Scale to 1000 prompts](how-to-resume-and-scale.md)
- [Compare two runs](how-to-compare-runs.md)
