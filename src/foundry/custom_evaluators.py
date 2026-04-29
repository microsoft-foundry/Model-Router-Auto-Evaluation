"""Code-based custom evaluators for cost and latency comparison.

These evaluators are registered with Microsoft Foundry and run in a sandboxed
environment. They receive the full JSONL item and return a float score
in the range 0.0–1.0.

Score scale:
  0.5 = parity (router same as baseline)
  > 0.5 = router advantage (cheaper / faster)
  < 0.5 = baseline advantage
  1.0 = router is free / instant
  0.0 = router costs 2x / takes 2x as long
"""

from __future__ import annotations

import textwrap
from typing import Dict


# ── Cost evaluator source code ───────────────────────────────────────────────
# This code runs inside Foundry's sandboxed evaluator.
# It receives `item` (the JSONL row) and returns a float.

COST_EVALUATOR_CODE = textwrap.dedent('''\
    def grade(sample, item) -> float:
        """Score router vs baseline on cost.

        Score = 0.5 + (savings_ratio * 0.5)
        Where savings_ratio = (baseline_cost - router_cost) / baseline_cost

        Returns:
            float in [0.0, 1.0] where 0.5 = parity, >0.5 = router cheaper
        """
        router_cost = float(item.get("router_cost_usd", 0.0))
        baseline_cost = float(item.get("baseline_cost_usd", 0.0))

        if baseline_cost == 0.0:
            return 0.5  # No baseline cost to compare

        savings_ratio = (baseline_cost - router_cost) / baseline_cost
        score = 0.5 + (savings_ratio * 0.5)
        return max(0.0, min(1.0, score))
''')


# ── Latency evaluator source code ───────────────────────────────────────────

LATENCY_EVALUATOR_CODE = textwrap.dedent('''\
    def grade(sample, item) -> float:
        """Score router vs baseline on latency.

        Score = 0.5 + (speedup_ratio * 0.5)
        Where speedup_ratio = (baseline_latency - router_latency) / baseline_latency

        Returns:
            float in [0.0, 1.0] where 0.5 = parity, >0.5 = router faster
        """
        router_latency = float(item.get("router_latency_ms", 0.0))
        baseline_latency = float(item.get("baseline_latency_ms", 0.0))

        if baseline_latency == 0.0:
            return 0.5  # No baseline latency to compare

        speedup_ratio = (baseline_latency - router_latency) / baseline_latency
        score = 0.5 + (speedup_ratio * 0.5)
        return max(0.0, min(1.0, score))
''')


def get_evaluator_code(evaluator_type: str) -> str:
    """Get the source code for a custom evaluator.

    Args:
        evaluator_type: One of "cost" or "latency".

    Returns:
        Python source code string.
    """
    codes: Dict[str, str] = {
        "cost": COST_EVALUATOR_CODE,
        "latency": LATENCY_EVALUATOR_CODE,
    }
    if evaluator_type not in codes:
        raise ValueError(f"Unknown evaluator type: {evaluator_type}. Choose from: {list(codes)}")
    return codes[evaluator_type]


def register_custom_evaluators(
    client,
    model_deployment: str,
    cost_evaluator_name: str = "mr_cost_comparison",
    latency_evaluator_name: str = "mr_latency_comparison",
    cost_pass_threshold: float = 0.5,
    latency_pass_threshold: float = 0.5,
) -> Dict[str, str]:
    """Register cost and latency custom evaluators with Foundry.

    Args:
        client: A FoundryEvalClient instance (connected).
        model_deployment: Model deployment name.
        cost_evaluator_name: Name for the cost evaluator.
        latency_evaluator_name: Name for the latency evaluator.
        cost_pass_threshold: Pass threshold for cost evaluator.
        latency_pass_threshold: Pass threshold for latency evaluator.

    Returns:
        Dict mapping evaluator type to evaluator ID.
    """
    result: Dict[str, str] = {}

    cost_id = client.register_evaluator(
        evaluator_name=cost_evaluator_name,
        code=COST_EVALUATOR_CODE,
        deployment_name=model_deployment,
        pass_threshold=cost_pass_threshold,
    )
    result["cost"] = cost_id

    latency_id = client.register_evaluator(
        evaluator_name=latency_evaluator_name,
        code=LATENCY_EVALUATOR_CODE,
        deployment_name=model_deployment,
        pass_threshold=latency_pass_threshold,
    )
    result["latency"] = latency_id

    return result
