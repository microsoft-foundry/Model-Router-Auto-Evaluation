# Quickstart — From Zero to a Live Evaluation in Minutes

Welcome! This guide gets you from "I just cloned the repo" to a working evaluation report — even if you've never used Azure, Python virtual environments, or Microsoft Foundry before.

---

## What is this project?

**Microsoft Foundry Model Router** is a service that automatically picks the best AI model for each prompt — for example sending an easy question to a fast, cheap model and a hard one to a smarter, more expensive model. The promise is **"comparable quality at a lower average cost and latency."**

This repo is the **measurement tool** that tests whether that promise holds up *for your prompts*. It:

1. Sends a list of prompts to **Model Router** (the system being measured) and to a **baseline model** of your choice (e.g. GPT‑5 directly).
2. Records every response, how long it took, how many tokens it used, and what it cost.
3. Asks a separate **judge model** (LLM-as-a-judge) to score answer quality on accuracy, completeness, clarity, and helpfulness — including pairwise A/B comparisons with anti-bias dual ordering.
4. Produces an **HTML dashboard, Markdown report, CSV, and JSON** so you can decide whether Model Router is right for your workload.

You can run it three ways, in increasing order of setup:

| Mode | Needs Azure? | Time to first result | What it's for |
|------|:---:|---|---|
| **Demo** (Part 1) | ❌ No | ~30 seconds | Explore every chart and output format with **mock data** before deciding to invest more time |
| **Live local eval** (Part 2) | ✅ Yes | ~5–10 minutes | Run real prompts through Model Router + a baseline, scored locally with your own judge model |
| **Foundry cloud eval** (Part 3) | ✅ Yes (+ Foundry project) | ~10–20 minutes | Submit results to Microsoft Foundry's hosted evaluators for managed, reproducible grading |

> **Tip:** Always start with **Part 1**. It costs nothing, runs offline, and shows you exactly what the live evaluation will produce.

---

## Before you start (one-time setup)

You need:

- **Python 3.9 or newer.** Check with `python --version` (or `python3 --version` on macOS/Linux).
- **Git**, to clone the repo.
- (Parts 2 and 3 only) An **Azure subscription** with access to the Model Router service and at least one Azure OpenAI deployment to use as a baseline / judge.

### Create a Python virtual environment (strongly recommended)

A virtual environment (`venv`) is an isolated folder of Python packages so this project's dependencies don't conflict with anything else on your machine. **You only do this once per clone.**

<details>
<summary><b>Windows — PowerShell</b></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once, then try again.
</details>

<details>
<summary><b>Windows — Command Prompt (cmd.exe)</b></summary>

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```
</details>

<details>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
```
</details>

You'll know it worked when your terminal prompt shows `(.venv)` at the start. To leave the environment later, just type `deactivate`.

---

## Part 1: Explore the demo (no API keys needed)

This generates a **mock evaluation report** with synthetic data so you can see every chart, metric, and output file the tool produces — without spending a single API call.

### Run the demo

**Windows (PowerShell):**
```powershell
.\scripts\demo.ps1
```

**Linux / macOS:**
```bash
bash scripts/demo.sh
```

**Any OS, manually:**
```bash
pip install -e .
python scripts/generate_sample_report.py --output-dir results/demo
```

Then open `results/demo/dashboard.html` in your browser.

### What just happened?

The script:
1. Installed this repo as a Python package (the `pip install -e .` step) so the `src/` modules can be imported.
2. Generated 100 fake prompt/response pairs across 8 task categories.
3. Ran them through the same reporting pipeline the live eval uses.
4. Wrote a complete output set to `results/demo/`.

### What you'll see

| File | What it shows |
|------|---------------|
| **`dashboard.html`** | Interactive HTML dashboard with all charts — **open this first** |
| `report.md` | Markdown summary of cost, latency, quality, and model distribution |
| `detailed_results.csv` | Per-prompt breakdown you can open in Excel for further analysis |
| `results.json` | Machine-readable metrics for scripting/CI |
| `chart_*.png` | Individual chart images you can paste into slides |

**Charts included:**
- Cost comparison (router vs baseline)
- Latency comparison (mean, p50, p90, p95, p99)
- Latency distribution histogram
- Per-category latency breakdown
- Token usage breakdown
- Model distribution pie (which models did Model Router pick?)
- Pairwise win rates (quality A/B)
- Absolute score comparison

> When the dashboard opens, browse the charts and reports — these are exactly the same artefacts a live run produces, just generated from synthetic numbers.

---

## Part 2: Run a real evaluation against your Azure endpoints

When you're ready to measure Model Router on **your own** prompts and Azure resources:

### 1. Configure secrets
```bash
# Copy the template, then fill in your real values
cp .env.example .env       # macOS/Linux
copy .env.example .env     # Windows
```
Open `.env` and set the four endpoint URLs and API keys (router, baseline, judge, optional Foundry project). The file is in `.gitignore`, so your secrets won't be committed.

> **Note:** The value you set for `AZURE_BASELINE_DEPLOYMENT` must match a key in the `pricing` section of your config file. If you use a custom deployment name such as `gpt-4o-baseline`, add a matching entry under `pricing:` in `configs/default.yaml` with the same input/output rates. Otherwise baseline costs will show as $0.00 and the cost comparison will be inaccurate. This applies whether you are using Quick Deploy or Custom Deploy.

### 2. Pick or edit a config
- `configs/quick_test.yaml` — small, fast (~10 prompts) — good first run.
- `configs/default.yaml` — full benchmark (100 prompts).
- `configs/foundry.yaml` — adds Foundry cloud-eval submission.

### 3. Pick a dataset
- `datasets/sample_custom.jsonl` — 10 generic prompts across 8 categories (smoke test).
- `datasets/zava_custom.jsonl` — 25 retail-themed prompts (broader benchmark).
- Or supply your own JSONL — see [datasets/README.md](datasets/README.md) and [docs/how-to-custom-dataset.md](docs/how-to-custom-dataset.md).

### 4. Run it
```bash
python scripts/run_eval.py --config configs/quick_test.yaml --dataset datasets/sample_custom.jsonl
```

Results land in `results/<run-name>/` with the same files as the demo. The run is checkpointed, so if it's interrupted you can re-run the same command and it'll resume from where it stopped.

For the full walkthrough — environment variables, judge model setup, cost tuning, scaling to thousands of prompts — see **[docs/how-to-run-live-eval.md](docs/how-to-run-live-eval.md)**.

---

## Part 3: Foundry Cloud Evaluation (optional)

Microsoft Foundry can run **managed, reproducible graders** on your evaluation data so quality scores aren't tied to your local machine. After a local run completes:

```bash
# 1. Submit your raw results to Foundry for cloud-side grading
python scripts/run_foundry_eval.py --input-dir results/full-eval

# 2. Compare local judge scores with Foundry's grader scores
python scripts/cross_validate.py
```

See **[docs/how-to-foundry-eval-sdk.md](docs/how-to-foundry-eval-sdk.md)** for Foundry project setup, and **[docs/faq.md](docs/faq.md)** for common errors.

---

## Where to go next

| If you want to… | Read |
|---|---|
| Understand the methodology and why the metrics are designed this way | [docs/methodology.md](docs/methodology.md) |
| Use your own prompts | [docs/how-to-custom-dataset.md](docs/how-to-custom-dataset.md) |
| Interpret the dashboard | [docs/how-to-interpret-results.md](docs/how-to-interpret-results.md) |
| Compare two runs (e.g. before/after a model upgrade) | [docs/how-to-compare-runs.md](docs/how-to-compare-runs.md) |
| Scale to thousands of prompts | [docs/how-to-resume-and-scale.md](docs/how-to-resume-and-scale.md) |
| See the architecture | [docs/architecture.md](docs/architecture.md) |
| Step through the code | [WALKTHROUGH.ipynb](WALKTHROUGH.ipynb) |

Stuck? Check [docs/faq.md](docs/faq.md) or open an issue.
