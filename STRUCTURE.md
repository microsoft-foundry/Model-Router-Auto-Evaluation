# Project Structure

```
model-router-eval/
├── WALKTHROUGH.ipynb               # Interactive Jupyter walkthrough (start here)
├── QUICKSTART.md                    # CLI quickstart (no API keys needed)
├── configs/                        # Evaluation presets
│   ├── default.yaml                #   Standard config (24-model pricing)
│   ├── quick_test.yaml             #   5-prompt smoke test
│   ├── large_scale.yaml            #   1000+ prompt config
│   ├── foundry.yaml                #   Foundry SDK evaluation config
│   ├── judge_prompts/              #   Judge prompt templates
│   └── grader_prompts/             #   Foundry score grader prompt templates
│       ├── quality_absolute.yaml
│       └── quality_pairwise.yaml
├── datasets/                       # Evaluation prompts (JSONL, CSV, or database)
│   └── sample_custom.jsonl         #   10 diverse sample prompts
├── docs/                           # Guides and reference
│   ├── how-to-run-live-eval.md
│   ├── how-to-custom-dataset.md
│   ├── how-to-interpret-results.md
│   ├── how-to-resume-and-scale.md
│   ├── how-to-compare-runs.md
│   ├── methodology.md
│   ├── architecture.md
│   └── faq.md
├── scripts/                        # CLI tools
│   ├── run_eval.py                 #   Main evaluation entry point
│   ├── compare_results.py          #   Compare two evaluation runs
│   ├── export_results.py           #   Export results to CSV/JSON
│   ├── generate_sample_report.py   #   Generate mock reports
│   ├── demo.ps1 / demo.sh         #   One-command demo
│   ├── setup.ps1 / setup.sh       #   Environment setup
│   ├── run_foundry_eval.py        #   Foundry cloud evaluation entry point
│   ├── cross_validate.py          #   Cross-validate local vs Foundry results
│   └── cleanup_foundry_evaluators.py # Cleanup registered Foundry evaluators
├── src/                            # Core library
│   ├── runner.py                   #   Evaluation orchestrator
│   ├── client.py                   #   Async API client with retry
│   ├── judge.py                    #   LLM-as-a-judge evaluator
│   ├── metrics.py                  #   Cost, latency, quality metrics
│   ├── charts.py                   #   Chart generation
│   ├── dashboard.py                #   HTML dashboard builder
│   ├── report.py                   #   Report generation
│   ├── config.py                   #   Config loader
│   ├── dataset.py                  #   Dataset loader (JSONL, CSV, SQLite, SQLAlchemy)
│   └── foundry/                    #   Microsoft Foundry SDK integration (optional)
│       ├── __init__.py
│       ├── config.py               #   Foundry config loader
│       ├── client.py               #   FoundryEvalClient (AIProjectClient wrapper)
│       ├── transformer.py          #   raw_results → Foundry JSONL
│       ├── graders.py              #   Build score_model testing criteria
│       ├── custom_evaluators.py    #   Code-based cost/latency evaluators
│       ├── runner.py               #   Foundry evaluation orchestrator
│       └── report.py               #   Foundry report generation
├── tests/                          # Unit tests (149 tests + 3 live integration)
│   └── foundry/                    #   Foundry tests (SDK compat, mocked SDK, integration)
├── results/                        # Evaluation outputs
│   ├── full-eval/                  #   Local evaluation results
│   └── foundry-eval/               #   Foundry cloud evaluation results
├── .env.example                    # Credential template
├── pyproject.toml                  # Build config
└── requirements.txt                # Dependencies
```
