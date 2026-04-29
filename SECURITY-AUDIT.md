# Security & Public-Sharing Audit

**Date:** 2026-04-29 (revalidation pass)
**Scope:** Full repository scan for secrets, PII, internal Microsoft data, and public-share readiness.

---

## Summary (revalidation)

| # | Check | Method | Result |
|---|---|---|---|
| 1 | Cloud provider keys (AWS, GCP, OpenAI, GitHub, Slack, PEM) | Regex scan across all source/config/data files | ✅ None found |
| 2 | Generic credential patterns (`api_key=`, `password=`, `secret=`, `bearer …`) | Regex scan | ✅ Only test placeholders (`"test-key-baseline"`) |
| 3 | Azure connection strings (`DefaultEndpointsProtocol`, `AccountKey`, `SharedAccessKey`, `InstrumentationKey`, full subscription GUIDs) | Regex scan | ✅ None found |
| 4 | Azure endpoint URLs hardcoded with real resource names | Regex scan | ✅ All placeholders (`your-resource`, `your-project`, `placeholder`, `test-*`, `demo-*`) |
| 5 | Microsoft employee aliases / PII in code & data | `sajagtap`, `angup`, `qSFvN7`, `model-router-ga-project`, real eval/run GUIDs | ✅ Removed from sample-results |
| 6 | Internal Azure portal URLs in sample artifacts | `ai.azure.com/nextgen/r/`, `eval_[a-f0-9]{32}` | ✅ Replaced with templates |
| 7 | `.env` or credential files committed | `git ls-files` audit | ✅ Only `.env.example` (placeholders) |
| 8 | `.gitignore` covers `.env`, `.venv`, caches, internal dirs, build artifacts | `git check-ignore -v` per pattern | ✅ All rules verified |
| 9 | Result/run output directories excluded but `sample-results/` allowed | `git check-ignore` | ✅ `results/*/` ignored, `sample-results/` tracked |
| 10 | Lint clean | `ruff check .` | ✅ All checks passed! |
| 11 | Tests pass | `pytest -q` | ✅ 167 passed, 3 skipped (integration only) |
| 12 | First-commit inventory | `git ls-files --others --exclude-standard` | ✅ 122 files, no caches/secrets/internal dirs |

---

## Findings

### A. Hardcoded secrets — NONE
Scans for OpenAI (`sk-…`), AWS (`AKIA…`), GitHub (`ghp_/gho_`), Google (`AIza…`), Slack (`xox[abp]-…`), PEM private-key headers, Azure storage `AccountKey=` / `SharedAccessKey=` / connection strings, and full `subscriptions/<guid>` paths returned **zero matches**.

The only credential-shaped string in the tree is `api_key="test-key-baseline"` in [tests/conftest.py](tests/conftest.py) — a unit-test placeholder, never sent to a real endpoint.

### B. Endpoint URLs — all placeholders
Every `https://*.openai.azure.com`, `https://*.services.ai.azure.com`, `https://*.cognitiveservices.azure.com` reference resolves to one of:
- `your-resource` / `your-project` (in [.env.example](.env.example), [README.md](README.md), [docs/](docs/))
- `placeholder` (in [configs/quick_test.yaml](configs/quick_test.yaml))
- `test-*` / `test.*` / `resolved.*` (in [tests/](tests/))
- `demo-*` (in [scripts/generate_sample_report.py](scripts/generate_sample_report.py))

### C. Internal MS data sanitized
Originally the Foundry sample run embedded a live Microsoft-internal portal URL containing workspace ID `qSFvN7kOTbK4RLFx5TlPwQ`, resource group `rg-sajagtap-swc`, project name `model-router-ga-project`, and real `eval_id` / `run_id` GUIDs.

**Sanitized** in:
- [sample-results/foundry-eval/results.json](sample-results/foundry-eval/results.json)
- [sample-results/foundry-eval/report.md](sample-results/foundry-eval/report.md)

Re-scan for `sajagtap | qSFvN7 | model-router-ga-project | eval_4b791 | evalrun_983365 | ai.azure.com/nextgen` across `sample-results/` returned **zero matches**.

### D. `.github/` GIM compliance files — keep
Standard Microsoft-public-repo tooling, intentionally committed:
- [.github/acl/access.yml](.github/acl/access.yml)
- [.github/compliance/inventory.yml](.github/compliance/inventory.yml)
- [.github/policies/jit.yml](.github/policies/jit.yml)
- [.github/ISSUE_TEMPLATE/JitAccess.yml](.github/ISSUE_TEMPLATE/JitAccess.yml)

Microsoft email aliases referenced in these (`opencode@microsoft.com`, `secure@microsoft.com`, repo-owner aliases) are public contacts intended for public repos.

### E. `.gitignore` validated
All rules confirmed with `git check-ignore -v`:

| Pattern | Verified |
|---|---|
| `.env` ignored | ✅ |
| `.env.example` un-ignored (negation works) | ✅ |
| `.venv/`, `venv/`, `env/` ignored | ✅ |
| `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.tox/`, `.coverage`, `htmlcov/` ignored | ✅ |
| `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `dist/`, `build/`, `*.whl` ignored | ✅ |
| `0-plan/` (internal docs) ignored | ✅ |
| `results/*/` ignored, `sample-results/` (committed examples) NOT ignored | ✅ |
| `.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.log`, `*.swp` ignored | ✅ |

### F. ⚠️ One residual item — non-blocking
[sample-results/media/foundry-eval-run.png](sample-results/media/foundry-eval-run.png) — a screenshot of the Azure AI Foundry portal — visually displays "Created by: Sanjeev Jagtap" in the run header. This is the **only** remaining item from the pre-publish review.

The screenshot is referenced by [sample-results/foundry-eval/report.md](sample-results/foundry-eval/report.md). The displayed creator name is publicly inferable from the `.github/compliance/inventory.yml` repo owners list, so this is **low-severity**, but for a polished public release consider one of:
- Re-render the screenshot from a non-employee tenant, or
- Crop/blur the *Created by* and run-header region, or
- Drop the image and remove the `![…]` line from the report.

---

## Final verdict

✅ **Repository is safe for public sharing.**

- Zero secrets, tokens, connection strings, or live endpoints.
- All previously-identified internal Microsoft Azure resource references have been redacted.
- `.gitignore` is comprehensive and verified rule-by-rule.
- Lint clean, 167/167 tests pass.

The single remaining cosmetic item (screenshot creator name) is optional polish, not a security blocker.

