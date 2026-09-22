# Configuration Presets

| Config | Prompts | Judge | Use case |
|--------|---------|-------|----------|
| [default.yaml](default.yaml) | All | Enabled | Standard evaluation |
| [quick_test.yaml](quick_test.yaml) | 5 | Disabled | Fast smoke test |
| [large_scale.yaml](large_scale.yaml) | All | Enabled | 1000+ prompts (higher concurrency, longer timeouts) |
| [live_demo.yaml](live_demo.yaml) | All | Enabled | Foundry OpenAI v1 live demo |
| [foundry.yaml](foundry.yaml) | — | — | Foundry cloud eval settings (graders, thresholds) |

Edit `default.yaml` to set your endpoint URLs, baseline model, and pricing.
Environment variables (`${VAR}`) are resolved from `.env`. Supported Foundry
model prices are refreshed from the Azure Retail Prices API and cached under
`.cache/`; YAML prices are retained as offline and ambiguity fallbacks.

Foundry OpenAI v1 endpoints use `type: openai_compatible` and a base URL
ending in `/openai/v1`. Set `api_mode` to `chat_completions` or `responses`;
do not append the operation name to `endpoint_url`.

## Prompt Templates

- [`judge_prompts/`](judge_prompts/) — Local LLM-as-judge prompt templates (absolute and pairwise)
- [`grader_prompts/`](grader_prompts/) — Foundry cloud grader prompt templates (quality_absolute and quality_pairwise)
