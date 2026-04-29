# FAQ & Troubleshooting

## Setup

### `python: command not found`

Install Python 3.9+ from [python.org](https://python.org). On Linux, you may need `python3` instead of `python`.

### `ModuleNotFoundError: No module named 'src'`

Run from the repo root directory, and install the package first:

```bash
pip install -e .
```

### `EnvironmentError: Environment variable 'AZURE_MODEL_ROUTER_KEY' is not set`

Create a `.env` file from the template:

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

---

## Authentication

### `401 Unauthorized` or `403 Forbidden`

- Double-check your API keys in `.env`
- Ensure the endpoint URLs are correct (no trailing slashes, correct resource names)
- Verify your Azure subscription has access to the Model Router and baseline model deployments

### Which endpoint URL format should I use?

| Endpoint | URL format |
|----------|-----------|
| Model Router | `https://<resource>.services.ai.azure.com/models` |
| Azure OpenAI (baseline/judge) | `https://<resource>.openai.azure.com` |

---

## Running Evaluations

### `max_tokens` vs `max_completion_tokens`

Some newer models (e.g. GPT-5) require `max_completion_tokens` instead of `max_tokens`. The client handles this automatically — just use `max_tokens` in your config and it will be mapped correctly.

### `temperature` not supported

Some models only accept `temperature=1` (default). If you get a `temperature` error, remove it from your config:

```yaml
endpoints:
  baseline:
    parameters:
      max_tokens: 1024
      # Don't set temperature for gpt-5
```

### `429 Too Many Requests`

You're hitting rate limits. Options:

1. **Reduce concurrency** — lower `max_parallel_requests` in your config
2. **Wait and retry** — the built-in retry with exponential backoff handles transient 429s
3. **Use `--resume`** — split the run across multiple sessions
4. **Request higher limits** — contact Azure support for your deployment

### Evaluation is very slow

- Check `max_parallel_requests` — increase it (e.g. 10) if your endpoint supports it
- Use `configs/large_scale.yaml` for production-scale runs
- The judge phase takes 4 API calls per prompt — disable it for speed: `judge.enabled: false`

### How long will 1000 prompts take?

Rough estimates at default concurrency:

| Phase | Time |
|-------|------|
| Eval (5 parallel) | ~35 minutes |
| Judge (3 parallel) | ~110 minutes |
| **Total** | **~2.5 hours** |

See [how-to-resume-and-scale.md](how-to-resume-and-scale.md) for tuning.

---

## Quality / Judge

### Judge scores seem random

- Ensure the judge model is capable (gpt-5 or gpt-4o recommended)
- Check the judge prompt templates in `configs/judge_prompts/` — they should match your evaluation criteria
- With small samples (< 30), variance is expected

### What does "position bias detected → TIE" mean?

The judge evaluated the same pair twice with swapped ordering and gave different winners. This means the judge's preference was based on position (first vs second) rather than actual quality. The result is recorded as a tie to avoid bias.

### Can I use a different judge model?

Yes. Edit `configs/default.yaml`:

```yaml
judge:
  endpoint:
    deployment_name: "gpt-4o"  # or any capable model
```

---

## Results & Reports

### `results.json` is empty or missing fields

Ensure the evaluation completed successfully. If it was interrupted, use `--resume` to finish it.

### Charts are missing from the dashboard

The `matplotlib` package is required. Install it:

```bash
pip install matplotlib
```

### How do I export results to Excel?

```bash
python scripts/export_results.py results/my-run --format csv --output results.csv
```

---

## Foundry Cloud Evaluation

### `ModuleNotFoundError: No module named 'azure.ai.projects'`

Install the Foundry extras:

```bash
pip install -e ".[foundry]"
```

Requires `azure-ai-projects>=2.1.0,<3.0` and `azure-identity>=1.15`.

### `DefaultAzureCredential` authentication fails

Run `az login` before running the Foundry eval:

```bash
az login
# If you have multiple tenants:
az login --tenant YOUR_TENANT_ID
```

### `AZURE_AI_PROJECT_ENDPOINT` is not set

Add it to your `.env` file. The format is:

```
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project-name>
```

You can find this URL in the Microsoft Foundry portal under **Project settings → Overview**.

### `stored_evaluator` is not a valid criteria type

This error means the SDK version doesn't support `stored_evaluator`. As of v2.1.0, the valid testing criteria types are:

- `score_model` — LLM-based grading
- `python` — code-based custom evaluator (used for cost/latency graders)
- `label_model` — classification
- `string_check` — regex/exact match
- `text_similarity` — embedding-based

The tool uses `score_model` for quality graders and `python` for cost/latency graders. No evaluator registration is needed.

### `file_content` is not a valid data source type

Use `jsonl` instead. The `file_content` type was removed in azure-ai-projects v2.1.0. The correct data source format is:

```python
data_source={"type": "jsonl", "source": {"type": "file_id", "id": file_id}}
```

### `ResultCounts` object has no attribute `items`

The `result_counts` field from the SDK is a typed object, not a plain dict. Convert it with `model_dump()` before iterating:

```python
counts = run_result.result_counts.model_dump()  # → {"passed": 4, "failed": 6, ...}
```

### Report shows "No grader results available" but the run completed

The live API returns `results` as a **list** of grader dicts, not a dict keyed by grader name:

```json
{"results": [{"name": "quality_absolute_router", "score": 4.0, "passed": true}, ...]}
```

If you see this, your `report.py` may be expecting the older dict format. The current code handles both formats.

### Some baseline responses scored 1/5

This happens when the baseline model returns an **empty response** for a prompt. An empty response is scored 1/5 on all quality dimensions (Poor: incomplete, not useful). This is a data issue — the baseline model failed to generate output — not a bug in the scoring.

To investigate, check the `foundry_input.jsonl` file for empty `baseline_response` fields.

### Foundry eval is slow (takes > 5 minutes)

The `score_model` graders call the judge model 3 times per prompt (router absolute, baseline absolute, pairwise). For 10 prompts, that's 30 LLM calls plus 20 Python grader executions. Typical time is 1–3 minutes.

If it's much slower:
- Check your endpoint's rate limits and quotas
- The `AZURE_AI_MODEL_DEPLOYMENT_NAME` model must have sufficient capacity
- Try `--skip-quality` to run only cost/latency graders (instant)

### How do I cross-validate local vs Foundry results?

```bash
python scripts/cross_validate.py
```

This compares `results/full-eval/results.json` against `results/foundry-eval/results.json` and prints a correlation table. Both should agree on quality direction, cost savings (within ~5%), and latency trends.

Open the CSV in Excel or Google Sheets.

---

## Platform

### Windows path issues

Use forward slashes or raw strings in config files:

```yaml
dataset: "datasets/my_prompts.jsonl"   # Forward slashes work on all platforms
```

### Does it work on macOS / Linux?

Yes. Setup scripts are provided for both:

```bash
# macOS / Linux
bash scripts/setup.sh
bash scripts/demo.sh

# Windows
.\scripts\setup.ps1
.\scripts\demo.ps1
```
