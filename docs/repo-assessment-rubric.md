# Repository Assessment Rubric — Model Router Auto Evaluation

A structured rubric for evaluating how well this repository helps **beginners**, **intermediate users**, and **advanced users** understand and use Microsoft Foundry Model Router.

> **Purpose:** Provide a repeatable, evidence-based assessment so maintainers can identify gaps and prioritise improvements. Use this rubric on every major release.
>
> **Scope:** Covers documentation, getting-started experience, code quality, security/privacy, extensibility, and community fitness. Excludes correctness of the underlying Model Router service itself.

---

## How to use this rubric

1. Score each criterion **0–4** using the descriptors in the [Scoring scale](#scoring-scale) below.
2. Multiply by the criterion **weight** to get a weighted score.
3. Sum per persona to get a **persona total** out of 100.
4. Aggregate persona totals (equal weight) into the **overall repo score**.
5. Flag every criterion scoring **≤ 2** as a backlog item.

### Scoring scale

| Score | Meaning |
|:-:|---|
| **4** | Excellent — exceeds expectations; could be cited as a model for similar repos |
| **3** | Good — meets expectations; minor polish only |
| **2** | Adequate — works but has noticeable gaps that slow the user down |
| **1** | Poor — present but confusing, incomplete, or actively misleading |
| **0** | Missing — not addressed at all |

---

## Personas

| Persona | Profile | Primary goal |
|---|---|---|
| **Beginner** | Has used Python, may not know Azure, never used Foundry. May be a data scientist, PM, or student. | "Show me whether Model Router would help me." |
| **Intermediate** | Comfortable with Azure OpenAI, has run evaluations before. Wants to use this on real workloads. | "Help me run a defensible benchmark on my own data and act on the results." |
| **Advanced** | Platform engineer, ML researcher, or contributor. Cares about reproducibility, statistics, and extensibility. | "Help me extend the toolkit, automate it in CI, and trust the methodology." |

---

## Beginner rubric (weight total = 100)

| # | Criterion | Weight | What "good" looks like | How to evidence it |
|:-:|---|:-:|---|---|
| B1 | **Plain-English value proposition on the README front page** | 10 | One paragraph explains what Model Router is and what question this repo answers, before any code or feature list | Read first 200 words of `README.md` |
| B2 | **Zero-keys demo path** | 15 | A single command (or notebook click-through) produces a real-looking dashboard with no Azure account | Run `scripts/demo.ps1` / `demo.sh` or open `WALKTHROUGH.ipynb` |
| B3 | **QUICKSTART quality** | 15 | Step-by-step from clone → result, with OS-specific commands, expected outputs, and "what you should see" anchors | Read `QUICKSTART.md` cold |
| B4 | **Glossary / jargon control** | 8 | Terms like *baseline*, *judge*, *p95*, *router markup*, *position bias* are defined the first time they appear | Grep first usages; check `docs/how-to-interpret-results.md` glossary |
| B5 | **Prerequisites are explicit and complete** | 8 | Python version, OS support, Azure prerequisites, and how to verify each are stated up front | Check QUICKSTART "Before you start" section |
| B6 | **Errors are anticipated** | 10 | Common errors (PowerShell execution policy, `az login`, rate limits, missing deployment) are mentioned with fixes | Skim QUICKSTART + `docs/faq.md` |
| B7 | **Sample data ships with the repo** | 6 | At least one runnable dataset is in `datasets/` with README explaining its content | Check `datasets/README.md` |
| B8 | **First success in < 10 minutes** | 10 | A user with Python installed can reach an open dashboard in under 10 minutes | Measure end-to-end on a clean machine |
| B9 | **Visual reinforcement** | 6 | Screenshots, sample charts, or sample report links so the user knows what they're aiming for | Check `sample-results/` and README image refs |
| B10 | **Where-to-go-next signposting** | 6 | Clear "you finished — now read X next" links at the end of the demo path | End of QUICKSTART, end of WALKTHROUGH |
| B11 | **No assumed Foundry knowledge for the local path** | 6 | Local eval works without ever needing a Foundry project | Confirm Part 2 of QUICKSTART has no Foundry prerequisite |

---

## Intermediate rubric (weight total = 100)

| # | Criterion | Weight | What "good" looks like | How to evidence it |
|:-:|---|:-:|---|---|
| I1 | **Custom dataset support is well documented** | 12 | Schema, optional fields, JSONL/CSV/SQL all shown with examples and pitfalls | `docs/how-to-custom-dataset.md` |
| I2 | **Configuration is documented and discoverable** | 10 | Each YAML key explained; presets (`quick_test`, `default`, `large_scale`, `foundry`) compared in a single table | `configs/README.md` + key tables in docs |
| I3 | **Cost & latency methodology is transparent** | 12 | The cost formula and pricing source are written down; users can update prices themselves | `docs/methodology.md` cost section |
| I4 | **Resume / checkpoint behaviour is reliable and documented** | 10 | Behaviour under Ctrl+C, crash, and rate-limit is explicitly described and tested | `docs/how-to-resume-and-scale.md` + tests |
| I5 | **Rate-limit / 429 guidance is concrete** | 8 | Specific knobs (concurrency, retry count, multi-session resume) ranked by preference | `docs/how-to-resume-and-scale.md` |
| I6 | **Result interpretation guide** | 12 | Each chart has a "what it shows / why it matters / what good looks like" explanation | `docs/how-to-interpret-results.md` |
| I7 | **Run comparison tooling** | 6 | Built-in script to diff two runs with sensible defaults | `scripts/compare_results.py` + docs |
| I8 | **Dataset size guidance** | 6 | Rule-of-thumb table mapping prompt count to statistical confidence | Methodology sample-size table |
| I9 | **Multiple baseline / judge models supported** | 6 | Easy to swap baseline or judge without code changes | YAML config sections + worked example |
| I10 | **Foundry cloud eval as opt-in path** | 8 | Local eval is fully functional without Foundry; Foundry adds managed grading on top, clearly explained | `docs/how-to-foundry-eval-sdk.md` |
| I11 | **Reproducibility hooks** | 5 | Configs are committed, runs include the config used, deterministic seeds where possible | Run output structure, `report.md` config block |
| I12 | **Real-world example results** | 5 | At least one sample run is committed showing realistic output | `sample-results/full-eval/` |

---

## Advanced rubric (weight total = 100)

| # | Criterion | Weight | What "good" looks like | How to evidence it |
|:-:|---|:-:|---|---|
| A1 | **Architecture documentation** | 10 | Component diagram, data flow, extension points, async/concurrency model explained | `docs/architecture.md` |
| A2 | **Test coverage and CI** | 12 | Unit + integration tests, CI workflow, ability to run live tests separately | `tests/`, `.github/workflows/tests.yml` |
| A3 | **Code quality tooling** | 6 | Lint/format configured (`ruff`), type hints used, no dead deps | `pyproject.toml`, `ruff` clean run |
| A4 | **Statistical rigour** | 10 | Position-bias mitigation, percentile reporting, confidence intervals, sample-size guidance, judge-bias notes | `docs/methodology.md` |
| A5 | **Extensibility** | 8 | Clear places to plug in new graders, datasets, dashboards, model providers | Architecture doc + `src/foundry/custom_evaluators.py` example |
| A6 | **Foundry SDK integration depth** | 8 | Custom evaluators registered, cleanup script, cross-validation against local eval | `src/foundry/`, `scripts/cross_validate.py`, `scripts/cleanup_foundry_evaluators.py` |
| A7 | **Deterministic / reproducible runs** | 6 | Configs versioned with results, dataset hash captured, model versions logged | Inspect `results.json` + `report.md` |
| A8 | **Security and secret hygiene** | 10 | `.env.example` only, no committed secrets, `.gitignore` covers transient artefacts, no PII in samples | Secret scan, `git ls-files` audit |
| A9 | **License and compliance clarity** | 4 | License file present, compatible deps, attribution where needed | `LICENSE`, dep audit |
| A10 | **Issue / PR / contribution onboarding** | 8 | Issue templates, contributing section, PR expectations, security disclosure path | `.github/ISSUE_TEMPLATE/`, README contributing section |
| A11 | **Cross-validation between local and managed eval** | 6 | A documented way to verify the local pipeline agrees with Foundry | `scripts/cross_validate.py` + docs |
| A12 | **Operational notes for large runs** | 6 | Memory profile, throughput numbers, multi-session workflows | `docs/how-to-resume-and-scale.md` |
| A13 | **Documentation kept in sync with code** | 6 | Test counts, file paths, CLI flags in docs match the source | Spot-check 5 references |

---

## Aggregate scoring template

```
Beginner total      = Σ(score × weight)        / 100  → out of 4
Intermediate total  = Σ(score × weight)        / 100  → out of 4
Advanced total      = Σ(score × weight)        / 100  → out of 4
Overall repo score  = (Beginner + Intermediate + Advanced) / 3   → out of 4
```

Ratings:

| Overall | Verdict |
|:-:|---|
| 3.5 – 4.0 | Reference-quality |
| 3.0 – 3.49 | Production-ready |
| 2.5 – 2.99 | Usable with effort |
| 2.0 – 2.49 | Needs work before public sharing |
| < 2.0 | Not ready |

---

# Assessment of this repository (April 2026)

Applying the rubric above to the current repo state.

## Beginner persona — score

| # | Criterion | W | Score | Weighted | Evidence |
|:-:|---|:-:|:-:|:-:|---|
| B1 | Plain-English value prop | 10 | 4 | 40 | README "What is this?" + "New here?" banner; QUICKSTART "What is this project?" section |
| B2 | Zero-keys demo path | 15 | 4 | 60 | `scripts/demo.ps1` / `demo.sh` + WALKTHROUGH.ipynb both work without Azure; mock report committed |
| B3 | QUICKSTART quality | 15 | 4 | 60 | 3-part walkthrough (demo → live → Foundry), OS-specific blocks, expected outputs, "where to go next" |
| B4 | Glossary / jargon control | 8 | 3 | 24 | Glossary in `how-to-interpret-results.md`, plain-English intros across docs; some inline first-use definitions could still be added |
| B5 | Prerequisites explicit | 8 | 4 | 32 | QUICKSTART "Before you start" lists Python, Git, Azure; venv covered with PS execution-policy fix |
| B6 | Errors anticipated | 10 | 3 | 30 | FAQ + rate-limit guidance + execution-policy tip; could expand on common 401/403/quota errors per service |
| B7 | Sample data ships | 6 | 4 | 24 | `datasets/sample_custom.jsonl` + `zava_custom.jsonl` + `datasets/README.md` |
| B8 | First success < 10 min | 10 | 4 | 40 | Demo command produces dashboard in seconds; verified executable end-to-end |
| B9 | Visual reinforcement | 6 | 3 | 18 | `sample-results/` committed; README could embed a screenshot of the dashboard for stronger first impression |
| B10 | Where-to-go-next signposting | 6 | 4 | 24 | QUICKSTART "Where to go next"; docs/README reading order |
| B11 | No Foundry knowledge for local path | 6 | 4 | 24 | Foundry isolated in Part 3; `src/foundry/` is a separate subpackage |
| | **Beginner subtotal** | **100** | | **376 / 400** | |

**Beginner score: 3.76 / 4 — reference-quality**

Top 3 fixes:
1. Embed a screenshot of `dashboard.html` near the top of the README so the visual payoff is obvious before reading.
2. Add inline first-use definitions for *router markup* and *position bias* in the README (they currently appear without definition).
3. Expand FAQ with concrete 401/403/quota error symptoms and fixes.

---

## Intermediate persona — score

| # | Criterion | W | Score | Weighted | Evidence |
|:-:|---|:-:|:-:|:-:|---|
| I1 | Custom dataset support | 12 | 4 | 48 | `how-to-custom-dataset.md` covers JSONL/CSV/SQL with examples + quick recipe |
| I2 | Configuration documented | 10 | 3 | 30 | `configs/README.md` + per-doc tables; could add a single side-by-side comparison of all 4 presets |
| I3 | Cost methodology transparent | 12 | 4 | 48 | Formula in methodology + README; pricing in YAML; pricing-update warning added |
| I4 | Resume / checkpoint reliability | 10 | 4 | 40 | Documented + tested; graceful shutdown prints resume command |
| I5 | Rate-limit guidance concrete | 8 | 3 | 24 | Ranked list in resume-and-scale; could add a worked example of tuning down concurrency |
| I6 | Result interpretation guide | 12 | 4 | 48 | "60-second read", glossary, per-chart "why it matters" |
| I7 | Run comparison tooling | 6 | 4 | 24 | `compare_results.py` + scenarios doc |
| I8 | Dataset size guidance | 6 | 4 | 24 | Sample-size table in methodology |
| I9 | Multiple baseline/judge models | 6 | 4 | 24 | YAML swap shown; 24 models pre-priced |
| I10 | Foundry as opt-in path | 8 | 4 | 32 | Clearly contrasted "What's different from a local evaluation?" |
| I11 | Reproducibility hooks | 5 | 3 | 15 | Config block in `report.md`; could add dataset hash + model version pinning |
| I12 | Real-world sample results | 5 | 4 | 20 | `sample-results/full-eval/` committed |
| | **Intermediate subtotal** | **100** | | **377 / 400** | |

**Intermediate score: 3.77 / 4 — reference-quality**

Top 3 fixes:
1. Add a single side-by-side comparison table of all 4 config presets in `configs/README.md`.
2. Add a worked rate-limit-tuning example ("you saw 429s at concurrency 10; here's exactly what to change").
3. Capture dataset hash and model API versions in `results.json` for stronger reproducibility.

---

## Advanced persona — score

| # | Criterion | W | Score | Weighted | Evidence |
|:-:|---|:-:|:-:|:-:|---|
| A1 | Architecture documentation | 10 | 4 | 40 | Component diagram + data flow + concurrency model in `docs/architecture.md` |
| A2 | Test coverage and CI | 12 | 4 | 48 | 167 tests (3 skipped live-only), `.github/workflows/tests.yml`, integration marker |
| A3 | Code quality tooling | 6 | 4 | 24 | ruff configured with sensible per-file ignores; clean run |
| A4 | Statistical rigour | 10 | 4 | 40 | Dual-ordering anti-bias, percentiles, confidence intervals, sample-size guidance |
| A5 | Extensibility | 8 | 3 | 24 | `src/foundry/custom_evaluators.py` shows the pattern; docs could add a "how to add a new grader" recipe |
| A6 | Foundry SDK integration depth | 8 | 4 | 32 | Custom evaluators, cleanup script, cross-validation script |
| A7 | Deterministic runs | 6 | 2 | 12 | Configs versioned + report includes config; dataset hash and model API version not captured — re-runs aren't byte-stable |
| A8 | Security and secret hygiene | 10 | 4 | 40 | Secret scan clean, `.gitignore` hardened, `.env.example` only, sample data sanitised |
| A9 | License and compliance | 4 | 4 | 16 | MIT LICENSE present |
| A10 | Issue / PR / contribution onboarding | 8 | 4 | 32 | 4 issue forms + `config.yml` (Discussions/MSRC routing); README contributing section with direct template links |
| A11 | Cross-validation local vs managed | 6 | 4 | 24 | `scripts/cross_validate.py` + interpretation table in methodology |
| A12 | Operational notes for large runs | 6 | 3 | 18 | Time/memory tables present; could include a real 1000-prompt run-time/cost case study |
| A13 | Docs kept in sync with code | 6 | 3 | 18 | Test count corrected (149 → 167); CLI flags match; some sample-results paths could be re-verified |
| | **Advanced subtotal** | **100** | | **368 / 400** | |

**Advanced score: 3.68 / 4 — reference-quality**

Top 3 fixes:
1. **A7 reproducibility (lowest scoring)** — capture dataset SHA‑256, model API versions, and library version in `results.json`. Cheap and unblocks audit-grade reuse.
2. Add a "How to add a custom grader / dataset loader / chart" recipe to `architecture.md`.
3. Commit a documented 500‑ or 1,000‑prompt sample run with real-world timings and cost.

---

## Overall

| Persona | Score |
|---|:-:|
| Beginner | **3.76** |
| Intermediate | **3.77** |
| Advanced | **3.68** |
| **Overall** | **3.74 / 4 — reference-quality** |

The repo is in strong shape for public sharing. The few weak spots are concrete and fixable without architectural change:

- **Visuals on the README** — embed a dashboard screenshot
- **Reproducibility metadata** — dataset hash + model versions in `results.json`
- **Configuration comparison** — single table for all presets
- **Extension recipes** — short "how to add X" snippets for graders / loaders / charts
- **Run-time case study** — one published large-scale run with real numbers

Re-score after each major release to track regressions.
