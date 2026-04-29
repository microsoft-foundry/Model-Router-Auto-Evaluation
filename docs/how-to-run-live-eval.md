# How To: Run a Live Evaluation

This guide walks you through running a real evaluation of Microsoft Foundry **Model Router** against a baseline model using your own Azure endpoints. By the end you'll have an HTML dashboard showing how Model Router compares to your chosen baseline on **cost, latency, and quality** — for prompts you care about.

> **Brand new to this repo?** Read the [QUICKSTART](../QUICKSTART.md) first — it explains what Model Router is, what this tool measures, and how to try the offline demo before spending any API calls.

## What is a "live evaluation"?

A live evaluation calls real Azure endpoints with real prompts and records what happens. Specifically:

1. For every prompt, the tool calls **Model Router** (the system being measured) and a **baseline model** of your choice (e.g. GPT‑5 directly).
2. It records the response text, latency, token counts, and cost for each.
3. A separate **judge model** (LLM-as-a-judge) reads both responses and scores them on accuracy, completeness, clarity, and helpfulness.
4. Charts, a Markdown report, a CSV, and a JSON summary are written to disk.

This costs real Azure API tokens — typically a few cents for a quick test, a few dollars for a full benchmark. Use `--dry-run` first to confirm everything is wired up before spending money.

## Prerequisites

- **Python 3.9+** — check with `python --version`
- **A Microsoft Foundry Model Router deployment** in your Azure subscription
- **An Azure OpenAI baseline model deployment** (e.g. GPT‑5, GPT‑4o) — this is what the router gets compared against
- **API keys** for both endpoints (you'll paste these into a `.env` file)
- *(Recommended)* a Python virtual environment — see [QUICKSTART](../QUICKSTART.md#before-you-start-one-time-setup)

## Step 1: Install

```bash
git clone https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation.git
cd Model-Router-Auto-Evaluation
pip install -e .
```

Or use the setup script (creates a venv and installs everything):

```bash
# Windows
.\scripts\setup.ps1

# Linux / macOS
bash scripts/setup.sh
```

## Step 2: Configure credentials

```bash
cp .env.example .env       # macOS / Linux
copy .env.example .env     # Windows
```

Open `.env` and fill in your real values:

```
AZURE_MODEL_ROUTER_ENDPOINT=https://your-resource.services.ai.azure.com/models
AZURE_MODEL_ROUTER_KEY=your-model-router-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your-azure-openai-key
```

> **Security note:** `.env` is listed in `.gitignore` and will never be committed. The endpoint URLs in `.env.example` are placeholders — they don't connect to anything until you replace them.

**Where do these values come from?**
- *Azure Portal → your Foundry resource → Keys and Endpoint*
- *Azure Portal → your Azure OpenAI resource → Keys and Endpoint*

## Step 3: Configure the evaluation (optional)

The default config (`configs/default.yaml`) works out of the box. The settings most people change first:

| Setting | Where in the YAML | Default | What it controls |
|---------|-------|---------|---|
| Baseline model | `endpoints.baseline.deployment_name` | `gpt-5` | Which model the router is compared against |
| Number of prompts | `evaluation.sample_size` | `null` (all) | How many dataset prompts to use |
| Judge enabled | `judge.enabled` | `true` | Whether to run quality scoring (costs extra API calls) |
| Concurrency | `concurrency.max_parallel_requests` | `5` | How many prompts run in parallel |

To change the baseline model, edit `configs/default.yaml`:

```yaml
endpoints:
  baseline:
    deployment_name: "gpt-4o"   # any model deployed in your Azure OpenAI resource
```

> **Tip:** Start with `configs/quick_test.yaml` (10 prompts) to verify everything works end-to-end before running a bigger benchmark.

## Step 4: Validate (dry run, no API calls)

Before making real API calls, validate your config and dataset:

```bash
python scripts/run_eval.py --dry-run
```

This checks:
- All `${ENV_VAR}` references in the YAML resolve from `.env`
- The dataset file loads and has valid `id` + `prompt` fields
- Config values are within accepted ranges

Fix any errors here before moving on — they only get more expensive once real calls start.

## Step 5: Run the evaluation

```bash
# Full eval with default config
python scripts/run_eval.py

# With a custom dataset
python scripts/run_eval.py --dataset my_prompts.jsonl

# Subset of prompts (great for first runs)
python scripts/run_eval.py --sample-size 50

# Custom output directory (so runs don't overwrite each other)
python scripts/run_eval.py --output-dir results/my-eval
```

You'll see two progress bars — first the eval phase (router + baseline), then the judge phase:

```
Evaluating: 100%|████████████████| 10/10 [00:42<00:00, 4.2s/prompt]
Judging:    100%|████████████████| 10/10 [01:15<00:00, 7.5s/prompt]
```

## Step 6: View results

The path is printed at the end of the run, e.g. `results/default/dashboard.html`. Open that file in any browser — no server needed, the HTML is self-contained.

👉 See [how-to-interpret-results.md](how-to-interpret-results.md) for a guide to every chart and metric in plain language.

## Common options

```bash
# Resume an interrupted run (Ctrl+C, crash, end of day)
python scripts/run_eval.py --resume --output-dir results/my-eval

# Use a different config preset
python scripts/run_eval.py --config configs/large_scale.yaml

# Disable the judge (cost + latency only — faster, cheaper)
# Edit configs/default.yaml: judge.enabled: false
```

## Next steps

- [Submit results to Foundry for cloud grading](how-to-foundry-eval-sdk.md) — managed graders with portal visibility
- [Bring your own dataset](how-to-custom-dataset.md) — JSONL, CSV, or SQL
- [Scale to 1,000 prompts](how-to-resume-and-scale.md) — checkpointing, multi-session runs
- [Compare two runs](how-to-compare-runs.md) — A/B test configs or models
- [Cross-validate local vs Foundry results](../scripts/cross_validate.py): `python scripts/cross_validate.py`

