"""YAML configuration loader with environment variable substitution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.env_utils import substitute_env_vars as _substitute_env_vars


@dataclass
class EndpointConfig:
    type: str
    endpoint_url: str
    api_key: str
    deployment_name: str
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "temperature": 0.7,
        "max_tokens": 1024,
    })


@dataclass
class PricingConfig:
    input: float  # USD per 1M tokens
    output: float  # USD per 1M tokens


@dataclass
class JudgeConfig:
    """Configuration for LLM-as-a-judge quality evaluation."""
    enabled: bool = False
    endpoint: Optional[EndpointConfig] = None
    pairwise_template: str = "configs/judge_prompts/pairwise.yaml"
    absolute_template: str = "configs/judge_prompts/absolute.yaml"
    max_parallel: int = 3
    timeout_seconds: int = 90
    max_retries: int = 2


@dataclass
class EvalConfig:
    """Top-level evaluation configuration."""

    # Evaluation metadata
    name: str
    dataset: str
    sample_size: Optional[int]
    random_seed: int

    # Endpoints
    model_router: EndpointConfig
    baseline: EndpointConfig

    # Pricing
    pricing: Dict[str, PricingConfig]

    # Concurrency
    max_parallel_requests: int
    request_timeout_seconds: int
    max_retries: int

    # Output
    output_directory: str
    output_formats: List[str]

    # Judge (quality evaluation)
    judge: Optional[JudgeConfig] = None


def load_config(config_path: str | Path) -> EvalConfig:
    """Load and validate a YAML configuration file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Validated EvalConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        EnvironmentError: If required environment variables are missing.
        ValueError: If required config fields are missing or invalid.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

    # Substitute environment variables
    config = _substitute_env_vars(raw)

    # Validate required top-level sections
    for section in ["evaluation", "endpoints", "pricing", "concurrency", "output"]:
        if section not in config:
            raise ValueError(f"Missing required config section: '{section}'")

    eval_section = config["evaluation"]
    endpoints = config["endpoints"]
    pricing_raw = config["pricing"]
    concurrency = config["concurrency"]
    output = config["output"]

    # Validate endpoints
    for ep_name in ["model_router", "baseline"]:
        if ep_name not in endpoints:
            raise ValueError(f"Missing required endpoint: '{ep_name}'")
        ep = endpoints[ep_name]
        for field_name in ["type", "endpoint_url", "api_key", "deployment_name"]:
            if field_name not in ep:
                raise ValueError(f"Endpoint '{ep_name}' missing required field: '{field_name}'")

    # Build endpoint configs
    def _build_endpoint(data: dict) -> EndpointConfig:
        return EndpointConfig(
            type=data["type"],
            endpoint_url=data["endpoint_url"],
            api_key=data["api_key"],
            deployment_name=data["deployment_name"],
            parameters=data.get("parameters", {"temperature": 0.7, "max_tokens": 1024}),
        )

    # Build pricing configs
    pricing = {}
    for name, prices in pricing_raw.items():
        pricing[name] = PricingConfig(
            input=float(prices.get("input", 0)),
            output=float(prices.get("output", 0)),
        )

    eval_config = EvalConfig(
        name=eval_section.get("name", "unnamed-eval"),
        dataset=eval_section.get("dataset", "datasets/sample_custom.jsonl"),
        sample_size=eval_section.get("sample_size"),
        random_seed=eval_section.get("random_seed", 42),
        model_router=_build_endpoint(endpoints["model_router"]),
        baseline=_build_endpoint(endpoints["baseline"]),
        pricing=pricing,
        max_parallel_requests=concurrency.get("max_parallel_requests", 5),
        request_timeout_seconds=concurrency.get("request_timeout_seconds", 60),
        max_retries=concurrency.get("max_retries", 3),
        output_directory=output.get("directory", "results"),
        output_formats=output.get("formats", ["markdown", "csv"]),
    )

    # Optional judge configuration
    judge_section = config.get("judge")
    if judge_section and judge_section.get("enabled", False):
        judge_ep = judge_section.get("endpoint", {})
        for field_name in ["type", "endpoint_url", "api_key", "deployment_name"]:
            if field_name not in judge_ep:
                raise ValueError(f"Judge endpoint missing required field: '{field_name}'")

        eval_config.judge = JudgeConfig(
            enabled=True,
            endpoint=EndpointConfig(
                type=judge_ep["type"],
                endpoint_url=judge_ep["endpoint_url"],
                api_key=judge_ep["api_key"],
                deployment_name=judge_ep["deployment_name"],
                parameters=judge_ep.get("parameters", {}),
            ),
            pairwise_template=judge_section.get(
                "pairwise_template", "configs/judge_prompts/pairwise.yaml"
            ),
            absolute_template=judge_section.get(
                "absolute_template", "configs/judge_prompts/absolute.yaml"
            ),
            max_parallel=judge_section.get("max_parallel", 3),
            timeout_seconds=judge_section.get("timeout_seconds", 90),
            max_retries=judge_section.get("max_retries", 2),
        )

    return eval_config
