# Documentation

Guides for getting started, running evaluations, and understanding the results.

> **New here?** Start with the [QUICKSTART](../QUICKSTART.md) at the repo root — it explains what this tool does and walks you through a 30-second offline demo. Once you've seen the demo, the guides below take you deeper.

## Suggested reading order

**If you just want to run an evaluation (most readers):**
1. [QUICKSTART](../QUICKSTART.md) — 30-second demo, no Azure needed
2. [how-to-run-live-eval.md](how-to-run-live-eval.md) — your first real evaluation against Azure
3. [how-to-interpret-results.md](how-to-interpret-results.md) — understand the dashboard
4. [how-to-custom-dataset.md](how-to-custom-dataset.md) — try your own prompts
5. [faq.md](faq.md) — when something doesn't work

**If you're scaling up or comparing models:**
- [how-to-resume-and-scale.md](how-to-resume-and-scale.md) — running 1,000+ prompts safely
- [how-to-compare-runs.md](how-to-compare-runs.md) — diff two evaluation runs

**If you want managed cloud-side grading:**
- [how-to-foundry-eval-sdk.md](how-to-foundry-eval-sdk.md) — submit results to Microsoft Foundry

**If you want to understand or extend the tool (advanced):**
- [methodology.md](methodology.md) — scoring, bias mitigation, cost formulas
- [architecture.md](architecture.md) — module diagram and extension points
- [foundry-cost-latency-design.md](foundry-cost-latency-design.md) — how cost & latency graders work in Foundry

## All guides

| Guide | Audience | Description |
|-------|----------|-------------|
| [how-to-run-live-eval.md](how-to-run-live-eval.md) | All users | End-to-end: credentials → config → run → results |
| [how-to-custom-dataset.md](how-to-custom-dataset.md) | All users | Bring your own prompts (JSONL, CSV, or SQL) |
| [how-to-interpret-results.md](how-to-interpret-results.md) | All users | Every chart and metric explained in plain language |
| [how-to-resume-and-scale.md](how-to-resume-and-scale.md) | Intermediate | Checkpoint/resume and 1,000-prompt scaling |
| [how-to-compare-runs.md](how-to-compare-runs.md) | Intermediate | Diff two evaluation runs to track improvements |
| [how-to-foundry-eval-sdk.md](how-to-foundry-eval-sdk.md) | Intermediate | Cloud-based grading via Microsoft Foundry |
| [foundry-cost-latency-design.md](foundry-cost-latency-design.md) | Advanced | Why cost/latency use `python` graders in Foundry |
| [methodology.md](methodology.md) | Advanced | Scoring rubrics, bias mitigation, cost formula |
| [architecture.md](architecture.md) | Advanced | Component diagram and data flow |
| [faq.md](faq.md) | All users | Troubleshooting and common questions |

