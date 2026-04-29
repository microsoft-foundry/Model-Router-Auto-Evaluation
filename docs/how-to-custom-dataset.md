# How To: Bring Your Own Dataset

Evaluate Model Router on **your own prompts** instead of (or in addition to) the included sample datasets. This is the single most important thing you can do to make results meaningful — Model Router's behaviour depends on the type of prompts you send it, so the most useful benchmark is one built from prompts that look like your real workload.

> **What's a dataset here?** A plain text file with one prompt per line (or row). Each prompt has at minimum an `id` and a `prompt` text field. Optional fields like `category` and `difficulty` make the report richer but aren't required.

## Quick recipe (most common case)

1. Copy [datasets/sample_custom.jsonl](../datasets/sample_custom.jsonl) as a template.
2. Replace its prompts with 50–500 real prompts from your workload.
3. Run: `python scripts/run_eval.py --dataset path/to/yours.jsonl`

The rest of this page is reference material for when you need more than that.

---

Supported formats: **JSONL**, **CSV**, and **SQL databases** (SQLite built-in, others via SQLAlchemy).

## JSONL format (recommended)

One JSON object per line — easy to edit by hand, easy to generate from scripts:

```json
{"id": "001", "prompt": "Explain quantum entanglement in simple terms."}
{"id": "002", "prompt": "Write a Python function to merge two sorted lists.", "category": "code_generation", "difficulty": "medium"}
```

## CSV format

A spreadsheet-style file with a header row. Only `id` and `prompt` are required:

```csv
id,prompt,category,difficulty
001,Explain quantum entanglement in simple terms.,,
002,Write a Python function to merge two sorted lists.,code_generation,medium
```

> **Tip:** If your prompts contain commas or newlines, quote them: `"Hello, world"`. Excel and Google Sheets handle this automatically when you Save As CSV.

## Database

Point to a SQL database with a connection string. The table must have `id` and `prompt` columns.

```bash
# SQLite (built-in, no extra dependencies)
python scripts/run_eval.py --dataset "sqlite:///path/to/prompts.db?table=prompts"

# PostgreSQL, MySQL, etc. (requires: pip install -e ".[db]")
python scripts/run_eval.py --dataset "postgresql://user:pw@host/mydb?table=prompts"
```

## Field reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | **Yes** | string | Unique identifier for each prompt — used to track results and resume runs |
| `prompt` | **Yes** | string | The text sent to both endpoints |
| `category` | No | string | Grouping label (e.g. `code_generation`, `summarization`) — enables per-category charts |
| `difficulty` | No | string | `easy`, `medium`, or `hard` — used for difficulty breakdowns |
| `ground_truth` | No | string | Reference answer (reserved for future use) |
| `metadata` | No | object | Arbitrary key-value pairs for your own tracking |

## Tips for good datasets

### Use categories

Categories enable per-category breakdowns in the report — for example, you can see whether Model Router is faster on summarization than on code generation. Use consistent labels:

```json
{"id": "c01", "prompt": "Write a binary search in Python.", "category": "code_generation"}
{"id": "c02", "prompt": "Explain TCP vs UDP.", "category": "technical_knowledge"}
{"id": "c03", "prompt": "Summarize this article: ...", "category": "summarization"}
```

### Mix difficulty levels

Include easy, medium, and hard prompts. Model Router's value proposition ("send easy prompts to cheap models, hard ones to capable models") only shows up when your dataset has a mix.

### Use realistic prompts

Prompts that match your production workload give the most useful answer. Toy examples like "What is 2 + 2?" tell you very little about how Model Router will behave on your real traffic.

### Size recommendations

| Prompts | Use case |
|---------|----------|
| 10–50 | Quick smoke test — directional only, not statistically reliable |
| 100–500 | Meaningful comparison — can spot real differences |
| 1,000+ | Production-grade benchmark — use [`configs/large_scale.yaml`](../configs/large_scale.yaml) |

## Run with your dataset

```bash
# JSONL
python scripts/run_eval.py --dataset path/to/my_prompts.jsonl

# CSV
python scripts/run_eval.py --dataset path/to/my_prompts.csv

# SQLite database
python scripts/run_eval.py --dataset "sqlite:///prompts.db?table=prompts"

# Subset from any source (great for first runs)
python scripts/run_eval.py --dataset my_prompts.csv --sample-size 100
```

## Validate before running

```bash
python scripts/run_eval.py --dataset my_prompts.jsonl --dry-run
```

This prints:
- Number of prompts loaded
- Category distribution
- Any validation errors (missing `id`, missing `prompt`, duplicate IDs)

No API calls are made — fix any errors here before paying for a real run.

## Example: customer support dataset

```json
{"id": "cs-001", "prompt": "How do I reset my password?", "category": "account", "difficulty": "easy"}
{"id": "cs-002", "prompt": "My payment was charged twice. What should I do?", "category": "billing", "difficulty": "medium"}
{"id": "cs-003", "prompt": "Explain the difference between your Enterprise and Pro plans including all feature comparisons, pricing tiers, and migration paths.", "category": "product", "difficulty": "hard"}
```

## Example: code evaluation dataset

```json
{"id": "code-001", "prompt": "Implement an LRU cache in Python with O(1) get and put.", "category": "algorithms", "difficulty": "hard"}
{"id": "code-002", "prompt": "Write a SQL query to find employees who earn more than their manager.", "category": "sql", "difficulty": "medium"}
{"id": "code-003", "prompt": "Convert this JavaScript callback to use async/await: ...", "category": "refactoring", "difficulty": "easy"}
```

