# Quickstart — From Demo to Live Eval in Minutes

This guide takes you from exploring the tool (no API keys) to running a real evaluation against Azure endpoints.

---

## Part 1: Explore Locally (No API Keys Needed)

Generate a **mock evaluation report** with synthetic data to explore every chart, metric, and output format before connecting to Azure.

> **No Azure credentials required.** No API calls are made. Everything runs locally in seconds.

---

## Run the Demo

### Windows

```powershell
.\scripts\demo.ps1
```

### Linux / macOS

```bash
bash scripts/demo.sh
```

### Manual (any OS)

```bash
# Create and activate a virtual environment first (recommended)
# Windows PowerShell:   python -m venv .venv && .\.venv\Scripts\Activate.ps1
# macOS / Linux:        python3 -m venv .venv && source .venv/bin/activate

pip install -e .
python scripts/generate_sample_report.py --output-dir results/demo
# Open results/demo/dashboard.html in your browser
```

---

## What You'll See

The demo generates 100 mock prompts across 8 categories and produces the full output suite:

| Output | What it shows |
|--------|---------------|
| **dashboard.html** | Interactive HTML dashboard with all charts — open this first |
| **report.md** | Markdown summary of cost, latency, quality, and model distribution |
| **detailed_results.csv** | Per-prompt breakdown for further analysis |
| **results.json** | Machine-readable metrics |
| **chart_*.png** | Individual chart images |

### Charts included

- Cost comparison (router vs baseline)
- Latency comparison (mean, p50, p90, p95, p99)
- Latency distribution histogram
- Per-category latency breakdown
- Token usage breakdown
- Model distribution pie chart
- Pairwise win rates (quality)
- Absolute score comparison

---

## Part 2: Run a Live Evaluation (API Keys Required)

When you're ready to run a live evaluation against your Azure endpoints:

1. Copy `.env.example` to `.env` and fill in your API keys
2. Edit `configs/default.yaml` if needed (endpoints, pricing, judge settings)
3. Run: `python scripts/run_eval.py`

---

## Part 3: Foundry Cloud Eval (Microsoft Foundry Required)

After your local run completes, submit results for cloud-based grading:

```bash
# Submit to Microsoft Foundry
python scripts/run_foundry_eval.py --input-dir results/full-eval

# Cross-validate local vs Foundry results
python scripts/cross_validate.py
```

See [docs/how-to-foundry-eval-sdk.md](docs/how-to-foundry-eval-sdk.md) for setup and [docs/faq.md](docs/faq.md) for troubleshooting.

See [docs/how-to-run-live-eval.md](docs/how-to-run-live-eval.md) for the full walkthrough.
