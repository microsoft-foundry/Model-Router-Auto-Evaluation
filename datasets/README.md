# Datasets

JSONL files with one prompt per line. Each record has the schema `{"id", "prompt", "category", "difficulty"}`. See [docs/how-to-custom-dataset.md](../docs/how-to-custom-dataset.md) for the full schema, validation rules, and examples for building your own.

| File | Prompts | Categories | Difficulty mix | Description |
|------|---------|-----------|----------------|-------------|
| [sample_custom.jsonl](sample_custom.jsonl) | 10 | 8 (`code_generation`, `general_knowledge`, `creative_writing`, `instruction_following`, `math`, `reasoning`, `summarization`, `technical_knowledge`) | mixed easy/medium | **Generic smoke-test set.** A small, deliberately diverse sample covering the eight standard task categories used by the evaluation harness. Designed for quick validation runs, CI smoke tests, demos, and as a template for authoring your own dataset. Prompts are domain-agnostic (TCP vs UDP, palindrome function, French Revolution, etc.) so results highlight raw model capability rather than domain knowledge. |
| [zava_custom.jsonl](zava_custom.jsonl) | 25 | 8 (same set, weighted toward `code_generation` and `reasoning`) | 6 easy / 11 medium / 8 hard | **Retail-domain benchmark set.** A larger, scenario-driven dataset themed around the fictional **Zava** retail company. Prompts simulate realistic tasks a model would face inside a retail / e-commerce business: customer-service edge cases, transaction-analysis code, KPI explanations (CLV, AOV), policy summarization, marketing copy, inventory math, and operational reasoning. Use this set when you want to evaluate Model Router behaviour on grounded, business-context prompts rather than generic Q&A. |

## Choosing a dataset

- **Just trying the harness out?** Use `sample_custom.jsonl` — 10 prompts run in ~1–2 minutes and exercise every category and grader.
- **Comparing models for a real workload?** Use `zava_custom.jsonl` (25 prompts, broader difficulty distribution) or supply your own JSONL of representative production prompts.
- **Authoring a custom dataset?** Copy either file as a starting point and follow [docs/how-to-custom-dataset.md](../docs/how-to-custom-dataset.md).

## Running an evaluation

```bash
# Built-in sample
python scripts/run_eval.py --dataset datasets/sample_custom.jsonl

# Retail benchmark
python scripts/run_eval.py --dataset datasets/zava_custom.jsonl

# Your own
python scripts/run_eval.py --dataset path/to/yours.jsonl
```

