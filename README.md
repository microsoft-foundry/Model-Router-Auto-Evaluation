# Microsoft Foundry — Model Router Auto Evaluation

> **New here?** Start with the **[QUICKSTART](QUICKSTART.md)** for a no-keys-needed demo in under 2 minutes, then come back here for the full reference. If you prefer Jupyter, jump straight into **[WALKTHROUGH.ipynb](WALKTHROUGH.ipynb)**.

## What is this?

**Model Router** is a Microsoft Foundry feature that automatically picks the cheapest model that can answer each prompt well. This toolkit answers the question every team asks before adopting it: **"Will Model Router actually save me money on *my* workload without hurting quality?"**

You plug in your prompts, point at your endpoints, and get a side-by-side report comparing Model Router to any baseline model on three things that matter: **quality**, **cost**, and **latency**.

## What You Get

Automated quality, cost, and latency evaluation of Microsoft Foundry Model Router against any baseline model — bring your own prompts, get a full report in one command.

- **Zero-friction start** — run with mock data first to explore the reports and dashboard, no API keys needed
- **Scale when ready** — handles 1,000+ prompts with concurrency, async I/O, checkpoints, and resume
- **Flexible data import** — load prompts from JSONL, CSV, or a SQL database
- **24 models pre-configured** — all pricing built into the YAML config, including router markup
- **Fully configurable** — swap the judge model, baseline model, scoring prompts, and concurrency limits
- **One-file HTML dashboard** — self-contained report with 8 embedded charts; share it, attach it to a PR, no server needed
- **Anti-bias judge** — every pairwise comparison runs twice with A/B order swapped; disagreements become ties, eliminating LLM position bias
- **Value & efficiency scores** — quality-per-dollar and quality-per-second ratios so you can weigh trade-offs, not just raw numbers
- **Compare runs** — diff two evaluations side-by-side to track improvements across configs, baselines, or time
- **Crash-safe & auto-retry** — append-only checkpoints lose at most one in-flight request; exponential backoff handles rate limits automatically

**Optional: Foundry cloud evaluation** — submit results to Microsoft Foundry as a post-processing step for cloud-based quality (score_model), cost, and latency grading. Adds governance, CI/CD integration, RBAC, and Foundry portal observability.

## What it Measures
Benchmark **Microsoft Foundry Model Router** against a baseline model on **quality**, **cost**, and **latency** — then decide whether the router is right for your workload.

| Metric | What it measures |
|--------|-----------------|
| **Quality** | LLM-as-a-judge pairwise + absolute scoring (1–5) |
| **Cost** | Per-model token pricing with router markup formula |
| **Latency** | Response time — mean, p50, p90, p95, p99 |
| **Value & Efficiency** | Quality-per-dollar and quality-per-second composite scores |
| **Model Distribution** | Which models the router selects and how often |

---

## Get Started

| Step | Action | Link |
|------|--------|------|
| **0** | **Explore interactively** — step through the pipeline in Jupyter (no API keys) | [WALKTHROUGH.ipynb](WALKTHROUGH.ipynb) |
| **0b** | **Or run the CLI quickstart** — one command, open the dashboard | [QUICKSTART.md](QUICKSTART.md) |
| **1** | **Install** — clone and `pip install -e .` | [Setup](#1-install) |
| **2** | **Credentials** — create `.env` with your Azure keys | [Credentials](#2-credentials) |
| **3** | **Configure** — review `configs/default.yaml` | [Configuration](#3-configuration) |
| **4** | **Run** — `python scripts/run_eval.py` | [Run an Evaluation](#4-run-an-evaluation) |
| **5** | **Results** — open `results/*/dashboard.html` | [View Results](#5-view-results) |
| **6** | **Go deeper** — guides, methodology, architecture | [docs/](docs/) |

---

### 0. Explore (No Keys Required)

Open **[WALKTHROUGH.ipynb](WALKTHROUGH.ipynb)** and click **Run All** — see every chart, metric, and table inline in under 2 minutes. No API keys, no config, no installs beyond the base package.

Or run the **CLI quickstart** if you prefer a terminal:

```bash
# Windows
.\scripts\demo.ps1

# Linux / macOS
bash scripts/demo.sh
```

See [QUICKSTART.md](QUICKSTART.md) for the CLI quickstart details.

### Run Against Deployed Models

The live demo calls an existing Microsoft Foundry Model Router deployment,
baseline deployment, and judge deployment. It consumes billable tokens.

#### Prerequisites

- Complete the installation steps below so `.venv` exists.
- Ensure the Router, baseline, and judge deployments already exist.

Create the local environment file:

```powershell
Copy-Item .env.example .env
# Edit .env with your endpoints, API keys, deployment names, and Azure region.
```

The `.env` file is excluded by `.gitignore` and must not be committed. After
configuring it, run:

```powershell
.\scripts\demo.ps1 -Live
```

The script loads the deployed model configuration from `.env`, refreshes
supported model prices from the Azure Retail Prices API, evaluates all 25
prompts in `datasets/zava_custom.jsonl`, and opens the generated dashboard. To
resume an interrupted live evaluation, add `-Resume`.

> The judge should ideally be a deployment distinct from both evaluated
> endpoints to reduce self-preference bias.

See [Run a Live Evaluation](docs/how-to-run-live-eval.md) for dataset,
configuration, security, and troubleshooting details.

### 1. Install

**Prerequisites:** Python 3.9+, a Microsoft Foundry Model Router endpoint, and an Azure OpenAI baseline endpoint.

```bash
git clone https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation.git
cd Model-Router-Auto-Evaluation
```

#### Create a virtual environment (recommended)

A virtual environment keeps this project's dependencies isolated from your system Python.

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

</details>

<details>
<summary><strong>Windows (Command Prompt)</strong></summary>

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

</details>

<details>
<summary><strong>macOS / Linux</strong></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
```

</details>

> **Tip:** You'll know the virtual environment is active when you see `(.venv)` at the start of your terminal prompt. To deactivate later, run `deactivate`.

#### Install the package

```bash
pip install -e ".[dev]"
```

### 2. Credentials

```bash
cp .env.example .env
# Edit .env with your endpoints and API keys
```

| Variable | Description |
|----------|-------------|
| `AZURE_MODEL_ROUTER_ENDPOINT` | Model Router endpoint URL |
| `AZURE_MODEL_ROUTER_KEY` | Model Router API key |
| `AZURE_MODEL_ROUTER_DEPLOYMENT` | Model Router deployment name (e.g. `model-router`) |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL (baseline) |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key (baseline) |
| `AZURE_BASELINE_DEPLOYMENT` | Baseline model deployment name (e.g. `gpt-5`) |
| `AZURE_JUDGE_ENDPOINT` | Judge model endpoint URL (can be same as baseline) |
| `AZURE_JUDGE_KEY` | Judge model API key |
| `AZURE_JUDGE_DEPLOYMENT` | Judge model deployment name (e.g. `gpt-5`) |
| `AZURE_AI_PROJECT_ENDPOINT` | Microsoft Foundry project endpoint (optional, for cloud eval) |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Foundry judge model deployment (optional, for cloud eval) |

### 3. Configuration

Edit `configs/default.yaml` to set endpoints, baseline model, pricing, and judge settings.

- **Azure retail pricing refresh** — supported Foundry model token prices are
  refreshed from the public Azure Retail Prices API and cached for 24 hours;
  YAML prices remain fallbacks
- **24 models pre-configured** — Azure OpenAI, Anthropic, xAI, DeepSeek, Meta
- **LLM-as-a-judge** enabled by default; configure via `AZURE_JUDGE_*` env vars or `judge.endpoint` in YAML
- **Environment variables** (`${VAR}`) are resolved from `.env` at load time

To swap the baseline or judge model, update the deployment name in `.env` or override in YAML:

```yaml
# configs/default.yaml
endpoints:
  baseline:
    deployment_name: gpt-5
judge:
  endpoint:
    deployment_name: gpt-5
  max_parallel: 3
```

See [configs/](configs/) for all presets (`quick_test`, `large_scale`, `foundry`).

### 4. Run an Evaluation

```bash
# Dry-run — validate config and dataset, no API calls
python scripts/run_eval.py --dry-run

# Full evaluation (default: 10 sample prompts)
python scripts/run_eval.py

# Custom dataset / sample size (JSONL, CSV, or database)
python scripts/run_eval.py --dataset my_prompts.jsonl --sample-size 100
python scripts/run_eval.py --dataset my_prompts.csv
python scripts/run_eval.py --dataset "sqlite:///prompts.db?table=prompts"

# Resume an interrupted run from checkpoint
python scripts/run_eval.py --resume --output-dir results/my-run
```

For large-scale runs (500–1000+ prompts), see [docs/how-to-resume-and-scale.md](docs/how-to-resume-and-scale.md).

### 5. View Results

Results are written to `results/<run-name>/`:

| File | What |
|------|------|
| `dashboard.html` | Self-contained HTML dashboard with all charts |
| `report.md` | Markdown summary |
| `results.json` | Machine-readable metrics |
| `detailed_results.csv` | Per-prompt detail for further analysis |

**Compare runs** or **export to CSV/JSON**:

```bash
python scripts/compare_results.py results/run-a results/run-b
python scripts/export_results.py results/my-run --format csv
```

---

## How It Works

The evaluation pipeline runs in five stages:

```
Load Dataset → Resume Checkpoint → Eval Prompts → Judge (LLM) → Generate Report
                                     ↓ flush         ↓ flush
                               checkpoint_eval   checkpoint_judge
```

**Checkpoint/resume** — every result is flushed to disk immediately. If interrupted (Ctrl+C or crash), `--resume` picks up where you left off. See [docs/how-to-resume-and-scale.md](docs/how-to-resume-and-scale.md).

**Graceful shutdown** — SIGINT is caught, in-flight requests finish, then exit with a resume command.

**Concurrency** — `asyncio.Semaphore` controls parallel API calls (default: 5 eval, 3 judge). Per-prompt, router and baseline are called sequentially for fair latency comparison.

**Auto-retry** — API calls retry with exponential backoff (`2^attempt` seconds) on transient errors and 429 rate limits, so large runs survive throttling without manual intervention.

### Cost Formula

```
Router cost = router_markup × input_tokens
            + underlying_model_input × input_tokens
            + underlying_model_output × output_tokens
```

The underlying model is identified from each response and matched to pricing via prefix matching. See [docs/methodology.md](docs/methodology.md) for full details.

### Quality Evaluation

| Method | Description |
|--------|-------------|
| **Pairwise** | Side-by-side comparison with dual-ordering to cancel position bias |
| **Absolute** | Independent scoring on Accuracy, Completeness, Clarity, Helpfulness (1–5) |

See [docs/methodology.md](docs/methodology.md) for statistical methodology and sample size guidance.

---

## Dataset Format

Supports **JSONL**, **CSV**, and **SQL databases**. Only `id` and `prompt` are required; all other fields are optional.

**JSONL** (one JSON object per line):
```json
{"id": "001", "prompt": "Explain quantum entanglement in simple terms."}
{"id": "002", "prompt": "Write a Python function to merge two sorted lists.", "category": "code_generation"}
```

**CSV** (header row with `id` and `prompt` columns):
```csv
id,prompt,category,difficulty
001,Explain quantum entanglement in simple terms.,,
002,Write a Python function to merge two sorted lists.,code_generation,easy
```

**Database** (SQLite built-in; other DBs via `pip install -e ".[db]"`):
```bash
python scripts/run_eval.py --dataset "sqlite:///prompts.db?table=prompts"
python scripts/run_eval.py --dataset "postgresql://user:pw@host/db?table=prompts"
```

Optional fields: `category`, `difficulty`, `ground_truth`, `metadata`. See [docs/how-to-custom-dataset.md](docs/how-to-custom-dataset.md).

---

> **[Project Structure →](STRUCTURE.md)** — full file/folder map with annotations

---

## Documentation

Full guides live in [`docs/`](docs/) — start with the [docs index](docs/README.md) for a suggested reading order tailored to your goal.

### Start here (beginners)

| Guide | Description |
|-------|-------------|
| [WALKTHROUGH.ipynb](WALKTHROUGH.ipynb) | Interactive step-by-step in Jupyter — see every chart inline (no API keys) |
| [QUICKSTART.md](QUICKSTART.md) | CLI quickstart — one command, open the dashboard |
| [How to Run a Live Eval](docs/how-to-run-live-eval.md) | End-to-end walkthrough with real Azure endpoints |
| [Interpreting Results](docs/how-to-interpret-results.md) | What each chart and metric means, with a glossary |
| [Custom Datasets](docs/how-to-custom-dataset.md) | JSONL / CSV / SQL schemas, examples, best practices |
| [FAQ](docs/faq.md) | Troubleshooting, rate limits, Foundry issues |

### Going deeper (intermediate)

| Guide | Description |
|-------|-------------|
| [Resume & Scale](docs/how-to-resume-and-scale.md) | Checkpoint/resume, 1,000+ prompt runs, rate limits |
| [Compare Runs](docs/how-to-compare-runs.md) | Side-by-side diff of two evaluations |
| [Methodology](docs/methodology.md) | Scoring, cost formula, statistical approach, judge bias mitigation |

### Microsoft Foundry cloud evaluation

| Guide | Description |
|-------|-------------|
| [Foundry Cloud Eval](docs/how-to-foundry-eval-sdk.md) | Run grading in Microsoft Foundry with managed graders + portal visibility |
| [Cost & Latency Design](docs/foundry-cost-latency-design.md) | Why we use Python graders for cost/latency in Foundry (advanced) |

### Contributors

| Guide | Description |
|-------|-------------|
| [Architecture](docs/architecture.md) | Component design, data flow, extension points |
| [STRUCTURE.md](STRUCTURE.md) | Annotated file/folder map of the whole repo |

---

## Foundry Cloud Evaluation (Optional)

Submit your evaluation results to **Microsoft Foundry** for cloud-based grading with governance, RBAC, and portal visibility.

```bash
# Install Foundry SDK dependencies
pip install -e ".[foundry]"

# Authenticate
az login

# Add Foundry variables to your .env (see .env.example)
# AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com
# AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5

# Dry run (validate config + transform data, no API calls)
python scripts/run_foundry_eval.py --dry-run

# Full cloud evaluation
python scripts/run_foundry_eval.py --input-dir results/full-eval

# Cross-validate local vs Foundry results
python scripts/cross_validate.py
```

The Foundry integration is a separate post-processing layer — the core eval flow is untouched. See [docs/how-to-foundry-eval-sdk.md](docs/how-to-foundry-eval-sdk.md) for details and [docs/faq.md](docs/faq.md) for Foundry troubleshooting.

> **How cost & latency work in Foundry:** Foundry Evaluations supports quality grading natively via `score_model` graders. For cost and latency — which Foundry doesn't evaluate out of the box — we use `python` graders that score pre-computed metrics from the local eval run. This gives you a unified quality + cost + latency view in a single Foundry eval, while keeping the door open for native support when it arrives. See [docs/foundry-cost-latency-design.md](docs/foundry-cost-latency-design.md) for the full design rationale.

---

## Running Tests

```bash
# All unit tests (167 tests; 3 live-integration tests are skipped without Azure credentials)
pytest tests/ -v

# Skip live integration tests
pytest tests/ -v -m "not integration"

# Only SDK compatibility checks
pytest tests/foundry/test_sdk_compat.py -v

# Only Foundry integration tests (requires az login + env vars)
pytest tests/foundry/test_integration.py -v -m integration
```

---

## Contributing

1. Fork the repo and create a feature branch
2. Install dev dependencies: `pip install -e ".[dev]"`
3. Run tests: `pytest`
4. Open a PR with a clear description

### Reporting issues and feedback

We welcome bug reports, feature requests, documentation fixes, and general feedback:

- 🐛 **Bug?** [Open a bug report](https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation/issues/new?template=bug_report.yml)
- ✨ **Feature idea?** [Open a feature request](https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation/issues/new?template=feature_request.yml)
- 📚 **Docs unclear?** [File a documentation issue](https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation/issues/new?template=documentation.yml)
- 💬 **General feedback or experience report?** [Share feedback](https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation/issues/new?template=feedback.yml) or use [GitHub Discussions](https://github.com/microsoft-foundry/Model-Router-Auto-Evaluation/discussions) for open-ended questions.
- 🔒 **Security vulnerability?** Please report privately via the [Microsoft Security Response Center](https://www.microsoft.com/msrc), not as a public issue.

---

## License

MIT — see [LICENSE](LICENSE) for details.
