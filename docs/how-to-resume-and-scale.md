# How To: Resume Interrupted Runs & Scale to 1000+ Prompts

## Checkpoint / Resume

Every result is flushed to disk immediately after the API call returns. If the process is interrupted (Ctrl+C, crash, machine reboot), all completed work is saved.

### How it works

Two checkpoint files are maintained in the output directory:

| File | Contents |
|------|----------|
| `checkpoint_eval.jsonl` | One line per API response (router + baseline) |
| `checkpoint_judge.jsonl` | One line per judge evaluation |

A prompt is "completed" only when **both** endpoints (model_router + baseline) have returned. A half-finished prompt is automatically re-evaluated on resume.

### Resume a run

```bash
python scripts/run_eval.py --resume --output-dir results/my-run
```

The runner:
1. Loads the checkpoint files
2. Identifies which prompt IDs are already done
3. Runs only the remaining prompts
4. Merges results and generates the full report

### Graceful shutdown

Pressing Ctrl+C triggers a graceful shutdown instead of a hard kill:

```
⚠ Evaluation interrupted. 523/1000 prompts saved to checkpoint.
  Resume with: python scripts/run_eval.py --resume --output-dir results/default
```

In-flight API calls finish, results are flushed, and the exact resume command is printed.

On successful completion, checkpoint files are automatically deleted.

## Scaling to 1000+ Prompts

### Use the large-scale config

```bash
python scripts/run_eval.py --config configs/large_scale.yaml
```

Key differences from default:

| Setting | Default | Large Scale |
|---------|---------|-------------|
| `max_parallel_requests` | 5 | 10 |
| `request_timeout_seconds` | 60 | 120 |
| `max_retries` | 3 | 5 |
| `judge.max_parallel` | 3 | 5 |
| `judge.timeout_seconds` | 90 | 120 |
| `judge.max_retries` | 2 | 3 |

### Time estimates

| Prompts | Eval phase | Judge phase | Total |
|---------|-----------|-------------|-------|
| 100 | ~3 min | ~10 min | ~13 min |
| 500 | ~17 min | ~55 min | ~72 min |
| 1,000 | ~35 min | ~110 min | ~2.5 hours |

These assume ~5 seconds per API call. Actual times vary by model latency and rate limits.

### Dealing with rate limits

If you see `429 Too Many Requests` errors:

1. **Reduce concurrency** — lower `max_parallel_requests` in your config
2. **Increase retries** — the built-in exponential backoff handles transient 429s
3. **Run across sessions** — use `--resume` to split a run across multiple sessions

### Multi-session workflow

```bash
# Session 1: start the run
python scripts/run_eval.py --config configs/large_scale.yaml --sample-size 1000

# (interrupted — e.g. end of day)

# Session 2: resume next day
python scripts/run_eval.py --resume --config configs/large_scale.yaml --output-dir results/large-scale
```

### Memory usage

All results are held in memory for metrics computation. For 1,000 prompts this is typically 50–200 MB, well within normal limits. The checkpoint files also serve as a disk-backed record.

## Concurrency Model

| Component | Mechanism | Purpose |
|-----------|-----------|---------|
| Eval API calls | `asyncio.Semaphore` (configurable) | Prevent overwhelming endpoints |
| Judge API calls | Separate `asyncio.Semaphore` | Independent limit for judge model |
| Per-prompt | Sequential (router → baseline) | Fair latency comparison |
| Overall dispatch | `asyncio.as_completed()` | Maximum throughput within semaphore limits |

All I/O is async — no threads are blocked. Retry logic uses exponential backoff (1s, 2s, 4s, ...).
