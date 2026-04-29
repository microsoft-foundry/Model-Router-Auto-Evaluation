# How To: Bring Your Own Dataset

Evaluate Model Router on your own prompts instead of (or in addition to) the included sample dataset.

Supported formats: **JSONL**, **CSV**, and **SQL databases** (SQLite built-in, others via SQLAlchemy).

## JSONL Format

Create a JSONL file with one prompt per line:

```json
{"id": "001", "prompt": "Explain quantum entanglement in simple terms."}
{"id": "002", "prompt": "Write a Python function to merge two sorted lists.", "category": "code_generation", "difficulty": "medium"}
```

## CSV Format

Create a CSV file with a header row. Only `id` and `prompt` columns are required:

```csv
id,prompt,category,difficulty
001,Explain quantum entanglement in simple terms.,,
002,Write a Python function to merge two sorted lists.,code_generation,medium
```

## Database

Point to a SQL database with a connection string. The table must have `id` and `prompt` columns.

```bash
# SQLite (built-in, no extra dependencies)
python scripts/run_eval.py --dataset "sqlite:///path/to/prompts.db?table=prompts"

# PostgreSQL, MySQL, etc. (requires: pip install -e ".[db]")
python scripts/run_eval.py --dataset "postgresql://user:pw@host/mydb?table=prompts"
```

## Field Reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | **Yes** | string | Unique identifier for each prompt |
| `prompt` | **Yes** | string | The text sent to both endpoints |
| `category` | No | string | Grouping label (e.g. `code_generation`, `summarization`) |
| `difficulty` | No | string | `easy`, `medium`, or `hard` |
| `ground_truth` | No | string | Reference answer (reserved for future use) |
| `metadata` | No | object | Arbitrary key-value pairs for your own tracking |

## Tips for Good Datasets

### Use categories

Categories enable per-category breakdowns in the report. Use consistent labels:

```json
{"id": "c01", "prompt": "Write a binary search in Python.", "category": "code_generation"}
{"id": "c02", "prompt": "Explain TCP vs UDP.", "category": "technical_knowledge"}
{"id": "c03", "prompt": "Summarize this article: ...", "category": "summarization"}
```

### Mix difficulty levels

Include easy, medium, and hard prompts to see how the router handles different complexity levels.

### Use realistic prompts

Use prompts that match your production workload — the router's model selection depends on the prompt content.

### Size recommendations

| Prompts | Use case |
|---------|----------|
| 10–50 | Quick smoke test |
| 100–500 | Meaningful statistical comparison |
| 1,000+ | Production-grade benchmark (use `configs/large_scale.yaml`) |

## Run with Your Dataset

```bash
# JSONL
python scripts/run_eval.py --dataset path/to/my_prompts.jsonl

# CSV
python scripts/run_eval.py --dataset path/to/my_prompts.csv

# SQLite database
python scripts/run_eval.py --dataset "sqlite:///prompts.db?table=prompts"

# Subset from any source
python scripts/run_eval.py --dataset my_prompts.csv --sample-size 100
```

## Validate Before Running

```bash
python scripts/run_eval.py --dataset my_prompts.jsonl --dry-run
```

This prints:
- Number of prompts loaded
- Category distribution
- Any validation errors (missing `id`, missing `prompt`, duplicate IDs)

## Example: Customer Support Dataset

```json
{"id": "cs-001", "prompt": "How do I reset my password?", "category": "account", "difficulty": "easy"}
{"id": "cs-002", "prompt": "My payment was charged twice. What should I do?", "category": "billing", "difficulty": "medium"}
{"id": "cs-003", "prompt": "Explain the difference between your Enterprise and Pro plans including all feature comparisons, pricing tiers, and migration paths.", "category": "product", "difficulty": "hard"}
```

## Example: Code Evaluation Dataset

```json
{"id": "code-001", "prompt": "Implement a LRU cache in Python with O(1) get and put.", "category": "algorithms", "difficulty": "hard"}
{"id": "code-002", "prompt": "Write a SQL query to find employees who earn more than their manager.", "category": "sql", "difficulty": "medium"}
{"id": "code-003", "prompt": "Convert this JavaScript callback to use async/await: ...", "category": "refactoring", "difficulty": "easy"}
```
