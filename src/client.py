"""Async API client for Azure OpenAI and OpenAI-compatible endpoints."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from openai import AsyncAzureOpenAI, AsyncOpenAI, APIError, APITimeoutError

from .config import EndpointConfig


@dataclass
class CompletionResult:
    """Result of a single completion request."""
    request_id: str
    prompt_id: str
    endpoint: str             # "model_router" or "baseline:<model_name>"
    model_name: str           # Actual model that served the request
    response_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float         # Wall-clock time
    status: str               # "success" | "error" | "timeout"
    error_message: Optional[str]
    timestamp: str            # ISO 8601


def _build_client(endpoint_config: EndpointConfig) -> AsyncAzureOpenAI | AsyncOpenAI:
    """Build an async OpenAI client from endpoint configuration."""
    if endpoint_config.type == "azure_openai":
        return AsyncAzureOpenAI(
            azure_endpoint=endpoint_config.endpoint_url,
            api_key=endpoint_config.api_key,
            api_version="2024-12-01-preview",
        )
    elif endpoint_config.type == "openai_compatible":
        return AsyncOpenAI(
            base_url=endpoint_config.endpoint_url,
            api_key=endpoint_config.api_key,
        )
    else:
        raise ValueError(
            f"Unknown endpoint type: '{endpoint_config.type}'. "
            f"Supported: 'azure_openai', 'openai_compatible'"
        )


class EvalClient:
    """Async client that calls endpoints and captures latency + token usage."""

    def __init__(
        self,
        model_router_config: EndpointConfig,
        baseline_config: EndpointConfig,
        max_parallel: int = 5,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ):
        self._router_config = model_router_config
        self._baseline_config = baseline_config
        self._router_client = _build_client(model_router_config)
        self._baseline_client = _build_client(baseline_config)
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    async def complete(
        self,
        prompt_id: str,
        prompt_text: str,
        endpoint_name: str,
    ) -> CompletionResult:
        """Send a prompt to the specified endpoint and capture results.

        Args:
            prompt_id: Identifier for the prompt being evaluated.
            prompt_text: The user prompt text.
            endpoint_name: "model_router" or "baseline".

        Returns:
            CompletionResult with response, latency, and token usage.
        """
        if endpoint_name == "model_router":
            client = self._router_client
            config = self._router_config
            endpoint_label = "model_router"
        elif endpoint_name == "baseline":
            client = self._baseline_client
            config = self._baseline_config
            endpoint_label = f"baseline:{config.deployment_name}"
        else:
            raise ValueError(f"Unknown endpoint_name: '{endpoint_name}'")

        request_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        async with self._semaphore:
            return await self._call_with_retry(
                client=client,
                config=config,
                prompt_id=prompt_id,
                prompt_text=prompt_text,
                endpoint_label=endpoint_label,
                request_id=request_id,
                timestamp=timestamp,
            )

    async def _call_with_retry(
        self,
        client: AsyncAzureOpenAI | AsyncOpenAI,
        config: EndpointConfig,
        prompt_id: str,
        prompt_text: str,
        endpoint_label: str,
        request_id: str,
        timestamp: str,
    ) -> CompletionResult:
        """Call the API with exponential backoff retry."""
        last_error: Optional[str] = None

        for attempt in range(self._max_retries):
            try:
                start_time = time.perf_counter()
                max_tok = config.parameters.get("max_tokens", 1024)
                # Build create kwargs; some models (e.g. gpt-5) only accept
                # default temperature=1, so we only include it when set and
                # non-default to maximize compatibility.
                create_kwargs: dict = {
                    "model": config.deployment_name,
                    "messages": [{"role": "user", "content": prompt_text}],
                    "max_completion_tokens": max_tok,
                }
                temp = config.parameters.get("temperature")
                if temp is not None:
                    create_kwargs["temperature"] = temp
                response = await asyncio.wait_for(
                    client.chat.completions.create(**create_kwargs),
                    timeout=self._timeout,
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # Extract response data
                choice = response.choices[0] if response.choices else None
                response_text = choice.message.content or "" if choice else ""
                model_name = response.model or config.deployment_name

                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                total_tokens = usage.total_tokens if usage else 0

                return CompletionResult(
                    request_id=request_id,
                    prompt_id=prompt_id,
                    endpoint=endpoint_label,
                    model_name=model_name,
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=round(elapsed_ms, 2),
                    status="success",
                    error_message=None,
                    timestamp=timestamp,
                )

            except asyncio.TimeoutError:
                last_error = f"Request timed out after {self._timeout}s"
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue

                return CompletionResult(
                    request_id=request_id,
                    prompt_id=prompt_id,
                    endpoint=endpoint_label,
                    model_name=config.deployment_name,
                    response_text="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=self._timeout * 1000,
                    status="timeout",
                    error_message=last_error,
                    timestamp=timestamp,
                )

            except (APIError, APITimeoutError) as e:
                last_error = f"{type(e).__name__}: {e}"
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue

            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                break

        # All retries exhausted or non-retryable error
        return CompletionResult(
            request_id=request_id,
            prompt_id=prompt_id,
            endpoint=endpoint_label,
            model_name=config.deployment_name,
            response_text="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=0,
            status="error",
            error_message=last_error,
            timestamp=timestamp,
        )

    async def close(self):
        """Close underlying HTTP clients."""
        await self._router_client.close()
        await self._baseline_client.close()
