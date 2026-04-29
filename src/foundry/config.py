"""Foundry-specific configuration loader.

Loads configs/foundry.yaml with environment variable substitution,
reusing the shared utility from src.env_utils.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

from src.env_utils import (
    substitute_env_vars as _substitute_env_vars,
    substitute_env_vars_optional as _substitute_env_vars_optional,
)


@dataclass
class FoundryConfig:
    """Microsoft Foundry connection settings."""
    project_endpoint: str
    model_deployment_name: str


@dataclass
class QualityGraderConfig:
    """Quality grader settings."""
    enabled: bool = True
    absolute_template: str = "configs/grader_prompts/quality_absolute.yaml"
    pairwise_template: str = "configs/grader_prompts/quality_pairwise.yaml"
    pass_threshold: int = 3
    range: List[int] = field(default_factory=lambda: [1, 5])


@dataclass
class CustomEvaluatorConfig:
    """Cost or latency custom evaluator settings."""
    enabled: bool = True
    evaluator_name: str = ""
    pass_threshold: float = 0.5


@dataclass
class OutputConfig:
    """Output settings."""
    directory: str = "results/foundry-eval"
    formats: List[str] = field(default_factory=lambda: ["markdown", "json"])


@dataclass
class CloudEvalConfig:
    """Top-level Foundry cloud evaluation configuration."""
    foundry: FoundryConfig
    quality: QualityGraderConfig
    cost: CustomEvaluatorConfig
    latency: CustomEvaluatorConfig
    output: OutputConfig


def load_foundry_config(
    config_path: str | Path,
    strict: bool = True,
) -> CloudEvalConfig:
    """Load and validate a Foundry configuration file.

    Args:
        config_path: Path to the YAML config file.
        strict: If True, raise on missing env vars. If False, allow empty values (dry-run).

    Returns:
        Validated CloudEvalConfig instance.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

    substitute = _substitute_env_vars if strict else _substitute_env_vars_optional

    # Parse foundry section
    foundry_raw = substitute(raw.get("foundry", {}))
    foundry = FoundryConfig(
        project_endpoint=foundry_raw.get("project_endpoint", ""),
        model_deployment_name=foundry_raw.get("model_deployment_name", ""),
    )

    # Parse graders section
    graders = raw.get("graders", {})

    quality_raw = graders.get("quality", {})
    quality = QualityGraderConfig(
        enabled=quality_raw.get("enabled", True),
        absolute_template=quality_raw.get("absolute_template", "configs/grader_prompts/quality_absolute.yaml"),
        pairwise_template=quality_raw.get("pairwise_template", "configs/grader_prompts/quality_pairwise.yaml"),
        pass_threshold=quality_raw.get("pass_threshold", 3),
        range=quality_raw.get("range", [1, 5]),
    )

    cost_raw = graders.get("cost", {})
    cost = CustomEvaluatorConfig(
        enabled=cost_raw.get("enabled", True),
        evaluator_name=cost_raw.get("evaluator_name", "mr_cost_comparison"),
        pass_threshold=cost_raw.get("pass_threshold", 0.5),
    )

    latency_raw = graders.get("latency", {})
    latency = CustomEvaluatorConfig(
        enabled=latency_raw.get("enabled", True),
        evaluator_name=latency_raw.get("evaluator_name", "mr_latency_comparison"),
        pass_threshold=latency_raw.get("pass_threshold", 0.5),
    )

    # Parse output section
    output_raw = raw.get("output", {})
    output = OutputConfig(
        directory=output_raw.get("directory", "results/foundry-eval"),
        formats=output_raw.get("formats", ["markdown", "json"]),
    )

    return CloudEvalConfig(
        foundry=foundry,
        quality=quality,
        cost=cost,
        latency=latency,
        output=output,
    )
