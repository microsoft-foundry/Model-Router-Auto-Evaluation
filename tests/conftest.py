"""Shared test fixtures and mock data."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.client import CompletionResult
from src.config import EvalConfig, EndpointConfig, PricingConfig


@pytest.fixture
def sample_config(tmp_path):
    """Create a minimal EvalConfig for testing."""
    return EvalConfig(
        name="test-eval",
        dataset=str(tmp_path / "test_data.jsonl"),
        sample_size=None,
        random_seed=42,
        model_router=EndpointConfig(
            type="azure_openai",
            endpoint_url="https://test-router.openai.azure.com",
            api_key="test-key-router",
            deployment_name="model-router",
            parameters={"temperature": 0.7, "max_tokens": 1024},
        ),
        baseline=EndpointConfig(
            type="azure_openai",
            endpoint_url="https://test-baseline.openai.azure.com",
            api_key="test-key-baseline",
            deployment_name="gpt-4o",
            parameters={"temperature": 0.7, "max_tokens": 1024},
        ),
        pricing={
            "model_router": PricingConfig(input=0.50, output=1.50),
            "gpt-4o": PricingConfig(input=2.50, output=10.00),
        },
        max_parallel_requests=5,
        request_timeout_seconds=60,
        max_retries=3,
        output_directory=str(tmp_path / "results"),
        output_formats=["markdown", "csv", "json"],
    )


def make_completion_result(
    prompt_id: str = "p001",
    endpoint: str = "model_router",
    model_name: str = "gpt-4o-mini",
    response_text: str = "Test response",
    prompt_tokens: int = 50,
    completion_tokens: int = 100,
    latency_ms: float = 500.0,
    status: str = "success",
) -> CompletionResult:
    """Helper to create CompletionResult instances for testing."""
    return CompletionResult(
        request_id="test-req-id",
        prompt_id=prompt_id,
        endpoint=endpoint,
        model_name=model_name,
        response_text=response_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
        status=status,
        error_message=None if status == "success" else "Test error",
        timestamp="2026-04-22T00:00:00Z",
    )
