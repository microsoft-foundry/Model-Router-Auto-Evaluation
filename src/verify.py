"""Post-eval output verification.

Validates that evaluation results are complete and consistent.
Runs automatically after eval scripts — prints a clear pass/fail summary
so users know immediately if something went wrong.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


class VerifyResult:
    """Collects pass/fail checks with messages."""

    def __init__(self, label: str):
        self.label = label
        self.checks: list[tuple[bool, str]] = []

    def ok(self, msg: str):
        self.checks.append((True, msg))

    def fail(self, msg: str):
        self.checks.append((False, msg))

    @property
    def passed(self) -> bool:
        return all(ok for ok, _ in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for ok, _ in self.checks if ok)

    @property
    def failed_count(self) -> int:
        return sum(1 for ok, _ in self.checks if not ok)

    def print_summary(self, file=sys.stdout):
        total = len(self.checks)
        print(f"\n{'=' * 60}", file=file)
        print(f"  Output Verification: {self.label}", file=file)
        print(f"{'=' * 60}", file=file)
        for ok, msg in self.checks:
            icon = "✓" if ok else "✗"
            print(f"  {icon} {msg}", file=file)
        print(f"{'─' * 60}", file=file)
        if self.passed:
            print(f"  All {total} checks passed.", file=file)
        else:
            print(f"  {self.failed_count}/{total} checks FAILED.", file=file)
        print(f"{'=' * 60}\n", file=file)


def verify_local_eval(output_dir: str | Path) -> VerifyResult:
    """Verify local evaluation output in the given directory."""
    output_dir = Path(output_dir)
    result = VerifyResult("Local Evaluation")

    # 1. results.json exists and is valid JSON
    results_file = output_dir / "results.json"
    if not results_file.exists():
        result.fail(f"results.json not found in {output_dir}")
        return result
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        result.ok("results.json exists and is valid JSON")
    except (json.JSONDecodeError, OSError) as e:
        result.fail(f"results.json is not valid JSON: {e}")
        return result

    # 2. Required top-level keys
    for key in ("model_router", "baseline"):
        if key in data:
            result.ok(f"'{key}' section present")
        else:
            result.fail(f"'{key}' section missing")

    # 3. Request counts and error rates
    for endpoint in ("model_router", "baseline"):
        ep_data = data.get(endpoint, {})
        total = ep_data.get("total_requests", 0)
        errors = ep_data.get("error_count", 0)
        successful = ep_data.get("successful_requests", 0)

        if total == 0:
            result.fail(f"{endpoint}: no requests recorded")
        elif errors == 0:
            result.ok(f"{endpoint}: {successful}/{total} requests succeeded (0 errors)")
        else:
            error_rate = errors / total * 100
            if error_rate > 20:
                result.fail(f"{endpoint}: {error_rate:.0f}% error rate ({errors}/{total})")
            else:
                result.ok(f"{endpoint}: {successful}/{total} succeeded ({errors} errors, {error_rate:.0f}%)")

    # 4. Cost data present
    for endpoint in ("model_router", "baseline"):
        cost = data.get(endpoint, {}).get("cost", {})
        if cost.get("estimated_cost_usd") is not None:
            result.ok(f"{endpoint}: cost data present (${cost['estimated_cost_usd']:.4f})")
        else:
            result.fail(f"{endpoint}: cost data missing")

    # 5. Latency data present
    for endpoint in ("model_router", "baseline"):
        latency = data.get(endpoint, {}).get("latency", {})
        if latency.get("mean_ms") is not None:
            result.ok(f"{endpoint}: latency data present (mean {latency['mean_ms']:.0f}ms)")
        else:
            result.fail(f"{endpoint}: latency data missing")

    # 6. Report and dashboard files
    for fname in ("report.md", "dashboard.html"):
        fpath = output_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            result.ok(f"{fname} generated ({fpath.stat().st_size:,} bytes)")
        else:
            result.fail(f"{fname} missing or empty")

    # 7. Raw results exist
    raw = output_dir / "raw_results.jsonl"
    if raw.exists():
        with open(raw, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        result.ok(f"raw_results.jsonl present ({line_count} rows)")
    else:
        result.fail("raw_results.jsonl missing")

    return result


def verify_foundry_eval(output_dir: str | Path) -> VerifyResult:
    """Verify Foundry cloud evaluation output."""
    output_dir = Path(output_dir)
    result = VerifyResult("Foundry Cloud Evaluation")

    # 1. results.json exists and is valid JSON
    results_file = output_dir / "results.json"
    if not results_file.exists():
        result.fail(f"results.json not found in {output_dir}")
        return result
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        result.ok("results.json exists and is valid JSON")
    except (json.JSONDecodeError, OSError) as e:
        result.fail(f"results.json is not valid JSON: {e}")
        return result

    # 2. Status is completed
    status = data.get("status")
    if status == "completed":
        result.ok(f"Evaluation status: {status}")
    elif status:
        result.fail(f"Evaluation status: {status} (expected 'completed')")
    else:
        result.fail("Evaluation status missing")

    # 3. Eval/run IDs present
    if data.get("eval_id") and data.get("run_id"):
        result.ok(f"Eval ID: {data['eval_id']}")
    else:
        result.fail("eval_id or run_id missing")

    # 4. Result counts
    counts = data.get("result_counts", {})
    total = counts.get("total", 0)
    errored = counts.get("errored", 0)
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)

    if total > 0:
        result.ok(f"Results: {total} total ({passed} passed, {failed} failed, {errored} errored)")
    else:
        result.fail("No result counts recorded")

    if total > 0 and errored / total > 0.2:
        result.fail(f"High error rate: {errored}/{total} ({errored/total*100:.0f}%)")
    elif total > 0:
        result.ok(f"Error rate acceptable ({errored}/{total})")

    # 5. Grader summary
    graders = data.get("grader_summary", {})
    if graders:
        result.ok(f"Grader summary: {len(graders)} graders returned")
        for name, stats in graders.items():
            mean = stats.get("mean")
            pass_rate = stats.get("pass_rate")
            if mean is not None and pass_rate is not None:
                result.ok(f"  {name}: mean={mean:.2f}, pass_rate={pass_rate:.0f}%")
            else:
                result.fail(f"  {name}: incomplete data (mean={mean}, pass_rate={pass_rate})")
    else:
        result.fail("Grader summary missing or empty")

    # 6. Per-item scores present
    per_item = data.get("per_item_scores", [])
    if per_item:
        result.ok(f"Per-item scores: {len(per_item)} items")
    else:
        result.fail("Per-item scores missing")

    # 7. Report file
    report = output_dir / "report.md"
    if report.exists() and report.stat().st_size > 0:
        result.ok(f"report.md generated ({report.stat().st_size:,} bytes)")
    else:
        result.fail("report.md missing or empty")

    return result
