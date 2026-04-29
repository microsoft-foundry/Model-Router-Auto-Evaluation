# Datasets

JSONL files with one prompt per line. See [docs/how-to-custom-dataset.md](../docs/how-to-custom-dataset.md) for the schema and examples.

| File | Prompts | Description |
|------|---------|-------------|
| [sample_custom.jsonl](sample_custom.jsonl) | 10 | Diverse sample across 8 categories |

To use your own dataset: `python scripts/run_eval.py --dataset path/to/yours.jsonl`
