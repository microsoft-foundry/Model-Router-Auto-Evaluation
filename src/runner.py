"""Core evaluation runner — orchestrates prompts, API calls, and metrics.

Supports checkpoint/resume for long-running evaluations:
  - Results are written incrementally to JSONL checkpoint files.
  - On resume, completed prompt IDs are loaded and skipped.
  - Graceful shutdown on SIGINT saves progress and prints resume instructions.
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from tqdm import tqdm

from .client import CompletionResult, EvalClient
from .config import EvalConfig
from .dataset import Prompt, load_dataset
from .judge import Judge, JudgeResult, load_prompt_template
from .metrics import EvalMetrics, compute_metrics, compute_quality_metrics
from .report import generate_report


# ── Checkpoint helpers ───────────────────────────────────────────────────────
# Two JSONL files track progress in the output directory:
#   checkpoint_eval.jsonl  — one line per CompletionResult (router + baseline)
#   checkpoint_judge.jsonl — one line per JudgeResult
# On successful completion both are deleted; only raw_results.jsonl remains.

_EVAL_CHECKPOINT = "checkpoint_eval.jsonl"
_JUDGE_CHECKPOINT = "checkpoint_judge.jsonl"


def _result_to_dict(r: CompletionResult) -> dict:
    """Serialize a CompletionResult to a JSON-safe dict."""
    return {
        "request_id": r.request_id,
        "prompt_id": r.prompt_id,
        "endpoint": r.endpoint,
        "model_name": r.model_name,
        "response_text": r.response_text,
        "prompt_tokens": r.prompt_tokens,
        "completion_tokens": r.completion_tokens,
        "total_tokens": r.total_tokens,
        "latency_ms": r.latency_ms,
        "status": r.status,
        "error_message": r.error_message,
        "timestamp": r.timestamp,
    }


def _dict_to_result(d: dict) -> CompletionResult:
    """Deserialize a dict back into a CompletionResult."""
    return CompletionResult(
        request_id=d["request_id"],
        prompt_id=d["prompt_id"],
        endpoint=d["endpoint"],
        model_name=d["model_name"],
        response_text=d["response_text"],
        prompt_tokens=d["prompt_tokens"],
        completion_tokens=d["completion_tokens"],
        total_tokens=d["total_tokens"],
        latency_ms=d["latency_ms"],
        status=d["status"],
        error_message=d.get("error_message"),
        timestamp=d["timestamp"],
    )


def _judge_result_to_dict(j: JudgeResult) -> dict:
    """Serialize a JudgeResult to a JSON-safe dict."""
    d: dict = {
        "prompt_id": j.prompt_id,
        "pairwise_winner": j.pairwise_winner,
        "judge_model": j.judge_model,
        "latency_ms": j.latency_ms,
        "error": j.error,
    }
    if j.pairwise_router_first:
        d["pairwise_router_first"] = {"winner": j.pairwise_router_first.winner, "raw_output": j.pairwise_router_first.raw_output}
    if j.pairwise_baseline_first:
        d["pairwise_baseline_first"] = {"winner": j.pairwise_baseline_first.winner, "raw_output": j.pairwise_baseline_first.raw_output}
    if j.router_score:
        d["router_score"] = {"accuracy": j.router_score.accuracy, "completeness": j.router_score.completeness, "clarity": j.router_score.clarity, "helpfulness": j.router_score.helpfulness}
    if j.baseline_score:
        d["baseline_score"] = {"accuracy": j.baseline_score.accuracy, "completeness": j.baseline_score.completeness, "clarity": j.baseline_score.clarity, "helpfulness": j.baseline_score.helpfulness}
    return d


def _dict_to_judge_result(d: dict) -> JudgeResult:
    """Deserialize a dict back into a JudgeResult."""
    from .judge import AbsoluteScore, PairwiseVerdict

    jr = JudgeResult(
        prompt_id=d["prompt_id"],
        pairwise_winner=d.get("pairwise_winner"),
        judge_model=d.get("judge_model", ""),
        latency_ms=d.get("latency_ms", 0.0),
        error=d.get("error"),
    )
    if "pairwise_router_first" in d and d["pairwise_router_first"]:
        jr.pairwise_router_first = PairwiseVerdict(**d["pairwise_router_first"])
    if "pairwise_baseline_first" in d and d["pairwise_baseline_first"]:
        jr.pairwise_baseline_first = PairwiseVerdict(**d["pairwise_baseline_first"])
    if "router_score" in d and d["router_score"]:
        jr.router_score = AbsoluteScore(**d["router_score"])
    if "baseline_score" in d and d["baseline_score"]:
        jr.baseline_score = AbsoluteScore(**d["baseline_score"])
    return jr


def _load_eval_checkpoint(
    checkpoint_path: Path,
) -> Tuple[List[CompletionResult], List[CompletionResult], Set[str]]:
    """Load eval checkpoint and return (router_results, baseline_results, completed_prompt_ids).

    A prompt is only considered "completed" when BOTH endpoint results
    (model_router + baseline) are present, so a half-finished prompt
    from an interrupted run will be re-evaluated on resume.
    """
    router_results: List[CompletionResult] = []
    baseline_results: List[CompletionResult] = []
    completed: Set[str] = set()  # prompt_ids with BOTH endpoints done
    seen: Dict[str, List[str]] = {}  # prompt_id -> list of endpoint labels

    if not checkpoint_path.exists():
        return router_results, baseline_results, set()

    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            result = _dict_to_result(record)
            if result.endpoint == "model_router":
                router_results.append(result)
            else:
                baseline_results.append(result)
            seen.setdefault(result.prompt_id, []).append(result.endpoint)

    # A prompt is complete only when both endpoints have a result
    completed = {pid for pid, endpoints in seen.items() if len(endpoints) >= 2}
    return router_results, baseline_results, completed


def _load_judge_checkpoint(checkpoint_path: Path) -> Tuple[List[JudgeResult], Set[str]]:
    """Load judge checkpoint and return (judge_results, judged_prompt_ids)."""
    results: List[JudgeResult] = []
    judged: Set[str] = set()

    if not checkpoint_path.exists():
        return results, judged

    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            jr = _dict_to_judge_result(record)
            results.append(jr)
            judged.add(jr.prompt_id)

    return results, judged


class _CheckpointWriter:
    """Incremental JSONL checkpoint writer.

    Each result is serialized to JSON, written, and flushed to disk
    immediately so that progress is never lost — even on a hard crash
    only the single in-flight result may be missing.
    """

    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode so resume keeps existing data
        self._file = open(self._path, "a", encoding="utf-8")

    def write_eval_result(self, result: CompletionResult) -> None:
        self._file.write(json.dumps(_result_to_dict(result)) + "\n")
        self._file.flush()

    def write_judge_result(self, result: JudgeResult) -> None:
        self._file.write(json.dumps(_judge_result_to_dict(result)) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


# ── Graceful shutdown ────────────────────────────────────────────────────────
# Instead of letting Ctrl+C raise KeyboardInterrupt (which would lose all
# in-memory state), we intercept SIGINT (and SIGTERM on Unix) and set an
# asyncio Event.  The eval and judge loops check this event between prompts,
# allowing in-flight API calls to finish and results to be flushed before
# the process exits with a helpful "resume" command.

class _ShutdownRequested(Exception):
    """Raised when a graceful shutdown signal is received."""


_shutdown_event: Optional[asyncio.Event] = None


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> asyncio.Event:
    """Install SIGINT handler that sets an asyncio Event instead of raising."""
    event = asyncio.Event()

    def _handler(sig, frame):
        if not event.is_set():
            print("\n⚠ Shutdown requested — finishing in-flight requests…")
            event.set()

    # On Windows, only SIGINT is supported; on Unix we also catch SIGTERM
    signal.signal(signal.SIGINT, _handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _handler)

    return event


# ── Prompt runner ────────────────────────────────────────────────────────────

async def _run_prompt(
    client: EvalClient,
    prompt: Prompt,
) -> Tuple[CompletionResult, CompletionResult]:
    """Run a single prompt against both endpoints.

    Calls are made sequentially per prompt to ensure fair latency comparison.
    """
    router_result = await client.complete(
        prompt_id=prompt.id,
        prompt_text=prompt.prompt,
        endpoint_name="model_router",
    )
    baseline_result = await client.complete(
        prompt_id=prompt.id,
        prompt_text=prompt.prompt,
        endpoint_name="baseline",
    )
    return router_result, baseline_result


# ── Main evaluation ─────────────────────────────────────────────────────────

async def run_evaluation(config: EvalConfig, *, resume: bool = False) -> EvalMetrics:
    """Run the full evaluation pipeline with checkpoint/resume support.

    1. Load dataset
    2. (Resume) Load checkpoint if present, skip completed prompts
    3. Call both endpoints for remaining prompts (incremental save)
    4. Compute metrics
    5. (Resume) Load judge checkpoint, skip judged prompts
    6. Run quality evaluation for remaining prompts (incremental save)
    7. Generate report

    Args:
        config: Validated evaluation configuration.
        resume: If True, continue from the last checkpoint.

    Returns:
        Computed evaluation metrics.
    """
    print(f"\n{'='*60}")
    print(f"  Foundry Model Router Evaluation: {config.name}")
    print(f"{'='*60}\n")

    # Set up output and checkpoint directory
    output_dir = Path(config.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    eval_ckpt_path = output_dir / _EVAL_CHECKPOINT
    judge_ckpt_path = output_dir / _JUDGE_CHECKPOINT

    # Install graceful shutdown handler
    loop = asyncio.get_running_loop()
    shutdown_event = _install_signal_handlers(loop)

    # 1. Load dataset
    print(f"Loading dataset: {config.dataset}")
    prompts = load_dataset(
        dataset_path=config.dataset,
        sample_size=config.sample_size,
        random_seed=config.random_seed,
    )
    print(f"Loaded {len(prompts)} prompts")

    # Build category map for per-category analysis
    category_map: Dict[str, str] = {}
    for p in prompts:
        if p.category:
            category_map[p.id] = p.category

    # 2. Resume: load existing checkpoint
    #    --resume  → reload checkpoint JSONL, skip already-done prompt IDs
    #    no flag   → delete stale checkpoints (if any) and start fresh
    router_results: List[CompletionResult] = []
    baseline_results: List[CompletionResult] = []
    completed_ids: Set[str] = set()

    if resume and eval_ckpt_path.exists():
        router_results, baseline_results, completed_ids = _load_eval_checkpoint(eval_ckpt_path)
        print(f"\n✓ Resumed from checkpoint: {len(completed_ids)}/{len(prompts)} prompts already done")
    elif not resume and eval_ckpt_path.exists():
        # Fresh run — clear old checkpoints
        eval_ckpt_path.unlink()
        if judge_ckpt_path.exists():
            judge_ckpt_path.unlink()

    remaining_prompts = [p for p in prompts if p.id not in completed_ids]

    if not remaining_prompts:
        print("All prompts already completed — skipping evaluation phase.")
    else:
        # 3. Run evaluations
        print("\nEndpoints:")
        print(f"  Model Router: {config.model_router.deployment_name} @ {config.model_router.endpoint_url}")
        print(f"  Baseline:     {config.baseline.deployment_name} @ {config.baseline.endpoint_url}")
        print(f"\nConcurrency: {config.max_parallel_requests} parallel requests")
        print(f"Timeout: {config.request_timeout_seconds}s per request")
        print(f"Retries: {config.max_retries}")
        if remaining_prompts and len(remaining_prompts) < len(prompts):
            print(f"Remaining: {len(remaining_prompts)}/{len(prompts)} prompts\n")
        else:
            print()

        client = EvalClient(
            model_router_config=config.model_router,
            baseline_config=config.baseline,
            max_parallel=config.max_parallel_requests,
            timeout_seconds=config.request_timeout_seconds,
            max_retries=config.max_retries,
        )

        # Open checkpoint writer in append mode so resumed runs keep
        # existing data and only add new results.
        eval_writer = _CheckpointWriter(eval_ckpt_path)
        interrupted = False

        start_time = time.perf_counter()

        try:
            # Create all prompt futures up front — actual concurrency is
            # bounded by the semaphore inside EvalClient (max_parallel_requests).
            tasks = [
                asyncio.ensure_future(_run_prompt(client, prompt))
                for prompt in remaining_prompts
            ]

            with tqdm(total=len(tasks), desc="Evaluating", unit="prompt") as pbar:
                for coro in asyncio.as_completed(tasks):
                    # Check for graceful shutdown between prompts
                    if shutdown_event.is_set():
                        interrupted = True
                        break

                    router_result, baseline_result = await coro

                    # Flush each result to disk immediately — this is the
                    # core mechanism that makes checkpoint/resume work.
                    eval_writer.write_eval_result(router_result)
                    eval_writer.write_eval_result(baseline_result)

                    router_results.append(router_result)
                    baseline_results.append(baseline_result)
                    pbar.update(1)

            if interrupted:
                # Cancel remaining tasks
                for t in tasks:
                    if not t.done():
                        t.cancel()
                # Wait for cancellations to settle
                await asyncio.gather(*tasks, return_exceptions=True)

        finally:
            eval_writer.close()
            await client.close()

        elapsed = time.perf_counter() - start_time
        print(f"\nCompleted {len(remaining_prompts) - (len(tasks) - len(router_results) + len(completed_ids))} new prompts in {elapsed:.1f}s")

        if interrupted:
            done_count = len({r.prompt_id for r in router_results})
            print(f"\n⚠ Evaluation interrupted. {done_count}/{len(prompts)} prompts saved to checkpoint.")
            print(f"  Resume with: python scripts/run_eval.py --resume --output-dir {output_dir}")
            return compute_metrics(
                router_results=router_results,
                baseline_results=baseline_results,
                pricing=config.pricing,
                category_map=category_map,
            )

    # Report errors
    router_errors = sum(1 for r in router_results if r.status != "success")
    baseline_errors = sum(1 for r in baseline_results if r.status != "success")
    if router_errors > 0:
        print(f"  Model Router errors: {router_errors}/{len(router_results)}")
        for r in router_results:
            if r.status != "success":
                print(f"    [{r.prompt_id}] {r.error_message}")
    if baseline_errors > 0:
        print(f"  Baseline errors: {baseline_errors}/{len(baseline_results)}")
        for r in baseline_results:
            if r.status != "success":
                print(f"    [{r.prompt_id}] {r.error_message}")

    # 4. Compute metrics
    print("\nComputing metrics...")
    metrics = compute_metrics(
        router_results=router_results,
        baseline_results=baseline_results,
        pricing=config.pricing,
        category_map=category_map,
    )

    # 5. Quality evaluation (if judge is configured)
    judge_results: List[JudgeResult] = []
    if config.judge and config.judge.enabled and config.judge.endpoint:
        print("\nRunning quality evaluation (LLM-as-a-judge)...")
        print(f"  Judge model: {config.judge.endpoint.deployment_name}")
        print("  Mode: pairwise (dual-ordering) + absolute scoring")

        # Resume judge checkpoint
        judged_ids: Set[str] = set()
        if resume and judge_ckpt_path.exists():
            judge_results, judged_ids = _load_judge_checkpoint(judge_ckpt_path)
            print(f"  ✓ Resumed judge checkpoint: {len(judged_ids)} already judged")

        pairwise_tpl = load_prompt_template(config.judge.pairwise_template)
        absolute_tpl = load_prompt_template(config.judge.absolute_template)

        judge = Judge(
            judge_config=config.judge.endpoint,
            pairwise_template=pairwise_tpl,
            absolute_template=absolute_tpl,
            max_parallel=config.judge.max_parallel,
            timeout_seconds=config.judge.timeout_seconds,
            max_retries=config.judge.max_retries,
        )

        # Build lookup maps for responses
        router_map = {r.prompt_id: r for r in router_results}
        baseline_map = {r.prompt_id: r for r in baseline_results}

        judge_prompts = []
        for prompt in prompts:
            if prompt.id in judged_ids:
                continue  # Already judged in a previous run
            rr = router_map.get(prompt.id)
            br = baseline_map.get(prompt.id)
            # Only judge if both endpoints returned successful responses
            if rr and br and rr.status == "success" and br.status == "success":
                judge_prompts.append((prompt.id, prompt.prompt, rr.response_text, br.response_text))

        if not judge_prompts:
            print("  All prompts already judged — skipping judge phase.")
        else:
            if judged_ids:
                print(f"  Remaining: {len(judge_prompts)} prompts to judge")

            judge_writer = _CheckpointWriter(judge_ckpt_path)
            judge_interrupted = False

            try:
                judge_tasks = [
                    asyncio.ensure_future(
                        judge.evaluate(
                            prompt_id=pid,
                            prompt_text=ptxt,
                            router_response=rresp,
                            baseline_response=bresp,
                        )
                    )
                    for pid, ptxt, rresp, bresp in judge_prompts
                ]

                with tqdm(total=len(judge_tasks), desc="Judging", unit="prompt") as pbar:
                    for coro in asyncio.as_completed(judge_tasks):
                        if shutdown_event.is_set():
                            judge_interrupted = True
                            break

                        result = await coro
                        judge_writer.write_judge_result(result)
                        judge_results.append(result)
                        pbar.update(1)

                if judge_interrupted:
                    for t in judge_tasks:
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(*judge_tasks, return_exceptions=True)

            finally:
                judge_writer.close()
                await judge.close()

            if judge_interrupted:
                done_count = len({j.prompt_id for j in judge_results})
                print(f"\n⚠ Judge phase interrupted. {done_count} prompts judged and saved.")
                print(f"  Resume with: python scripts/run_eval.py --resume --output-dir {output_dir}")
                # Still compute partial metrics and generate report
                metrics.quality = compute_quality_metrics(
                    judge_results=judge_results,
                    category_map=category_map,
                    router_cost_usd=metrics.model_router.cost.estimated_cost_usd if metrics.model_router.cost else 0,
                    baseline_cost_usd=metrics.baseline.cost.estimated_cost_usd if metrics.baseline.cost else 0,
                    router_mean_latency_ms=metrics.model_router.latency.mean_ms if metrics.model_router.latency else 0,
                    baseline_mean_latency_ms=metrics.baseline.latency.mean_ms if metrics.baseline.latency else 0,
                )
                _generate_final_report(metrics, config, router_results, baseline_results, prompts, output_dir, eval_ckpt_path, judge_ckpt_path)
                return metrics

        judge_errors = sum(1 for j in judge_results if j.error is not None)
        print(f"Judging complete: {len(judge_results) - judge_errors}/{len(judge_results)} successful")
        if judge_errors > 0:
            print(f"  Judge errors: {judge_errors}")

        # Compute quality metrics
        metrics.quality = compute_quality_metrics(
            judge_results=judge_results,
            category_map=category_map,
            router_cost_usd=metrics.model_router.cost.estimated_cost_usd if metrics.model_router.cost else 0,
            baseline_cost_usd=metrics.baseline.cost.estimated_cost_usd if metrics.baseline.cost else 0,
            router_mean_latency_ms=metrics.model_router.latency.mean_ms if metrics.model_router.latency else 0,
            baseline_mean_latency_ms=metrics.baseline.latency.mean_ms if metrics.baseline.latency else 0,
        )

    # 6. Generate report and clean up checkpoints
    _generate_final_report(metrics, config, router_results, baseline_results, prompts, output_dir, eval_ckpt_path, judge_ckpt_path)

    return metrics


def _generate_final_report(
    metrics: EvalMetrics,
    config: EvalConfig,
    router_results: List[CompletionResult],
    baseline_results: List[CompletionResult],
    prompts: List[Prompt],
    output_dir: Path,
    eval_ckpt_path: Path,
    judge_ckpt_path: Path,
) -> None:
    """Generate final report, save raw results, and clean up checkpoints."""
    print(f"Generating report in {output_dir}/")
    generate_report(
        metrics=metrics,
        config=config,
        router_results=router_results,
        baseline_results=baseline_results,
        prompts=prompts,
        output_dir=output_dir,
        formats=config.output_formats,
    )

    # Save raw results as JSONL for debugging / further analysis
    _save_raw_results(router_results, baseline_results, output_dir)

    # Clean up checkpoint files on successful completion — the final
    # raw_results.jsonl and report files are the authoritative outputs.
    if eval_ckpt_path.exists():
        eval_ckpt_path.unlink()
    if judge_ckpt_path.exists():
        judge_ckpt_path.unlink()

    print(f"\n{'='*60}")
    print(f"  Evaluation complete. Results in: {output_dir}/")
    print(f"{'='*60}\n")


def _save_raw_results(
    router_results: List[CompletionResult],
    baseline_results: List[CompletionResult],
    output_dir: Path,
) -> None:
    """Save raw CompletionResult objects as JSONL."""
    raw_path = output_dir / "raw_results.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in router_results + baseline_results:
            f.write(json.dumps(_result_to_dict(r)) + "\n")
