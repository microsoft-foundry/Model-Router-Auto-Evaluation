"""Build Foundry testing criteria (score_model graders) from YAML templates.

Each score_model grader uses {{item.*}} data mappings to reference fields
from the transformer JSONL. The grader sends prompts to the judge model and
expects a numeric score in the configured range.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml


def _load_template(template_path: str | Path) -> Dict[str, Any]:
    """Load a grader prompt template from YAML."""
    path = Path(template_path)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_quality_criteria(
    model_deployment: str,
    absolute_template_path: str,
    pairwise_template_path: str,
    pass_threshold: int = 3,
    score_range: List[int] | None = None,
) -> List[Dict[str, Any]]:
    """Build score_model testing criteria for quality grading.

    Creates three graders:
    1. absolute_router — scores the router response independently
    2. absolute_baseline — scores the baseline response independently
    3. pairwise_comparison — compares router vs baseline

    Args:
        model_deployment: Model deployment name for the judge.
        absolute_template_path: Path to absolute scoring prompt template.
        pairwise_template_path: Path to pairwise comparison prompt template.
        pass_threshold: Minimum score to pass.
        score_range: [min, max] score range (default [1, 5]).

    Returns:
        List of testing criteria dicts for the Foundry evals API.
    """
    if score_range is None:
        score_range = [1, 5]

    absolute_tmpl = _load_template(absolute_template_path)
    pairwise_tmpl = _load_template(pairwise_template_path)

    absolute_input = absolute_tmpl.get("input", [])
    pairwise_input = pairwise_tmpl.get("input", [])

    criteria: List[Dict[str, Any]] = []

    # 1. Absolute score for router response
    router_input = _substitute_response_field(absolute_input, "router_response")
    criteria.append({
        "type": "score_model",
        "name": "quality_absolute_router",
        "model": model_deployment,
        "input": router_input,
        "range": score_range,
        "pass_threshold": pass_threshold,
    })

    # 2. Absolute score for baseline response
    baseline_input = _substitute_response_field(absolute_input, "baseline_response")
    criteria.append({
        "type": "score_model",
        "name": "quality_absolute_baseline",
        "model": model_deployment,
        "input": baseline_input,
        "range": score_range,
        "pass_threshold": pass_threshold,
    })

    # 3. Pairwise comparison (uses both responses directly via {{item.*}})
    criteria.append({
        "type": "score_model",
        "name": "quality_pairwise",
        "model": model_deployment,
        "input": pairwise_input,
        "range": score_range,
        "pass_threshold": pass_threshold,
    })

    return criteria


def _substitute_response_field(
    input_messages: List[Dict[str, str]],
    response_field: str,
) -> List[Dict[str, str]]:
    """Replace {{item.response}} with the specific response field.

    The absolute template uses a generic {{item.response}} placeholder.
    For router scoring, we replace it with {{item.router_response}}.
    For baseline scoring, we replace it with {{item.baseline_response}}.
    """
    result = []
    for msg in input_messages:
        content = msg.get("content", "")
        content = content.replace("{{item.response}}", f"{{{{item.{response_field}}}}}")
        result.append({"role": msg["role"], "content": content})
    return result


def build_custom_evaluator_criteria(
    evaluator_name: str,
    evaluator_code: str,
    pass_threshold: float = 0.5,
) -> Dict[str, Any]:
    """Build a testing criterion using an inline Python grader.

    The OpenAI evals API supports a 'python' grader type that runs
    code inline — no separate evaluator registration needed.

    Args:
        evaluator_name: Name for the criterion.
        evaluator_code: Python source code with a grade(sample, item) function.
        pass_threshold: Minimum score to pass.

    Returns:
        A single testing criterion dict.
    """
    return {
        "type": "python",
        "name": evaluator_name,
        "source": evaluator_code,
        "pass_threshold": pass_threshold,
    }
