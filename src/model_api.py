"""Shared OpenAI client construction and request handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI

from .config import EndpointConfig


ModelClient = AsyncAzureOpenAI | AsyncOpenAI


@dataclass
class ModelReply:
    """Normalized response from either supported OpenAI API mode."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def build_model_client(config: EndpointConfig) -> ModelClient:
    """Build an async client from endpoint configuration."""
    if config.type == "azure_openai":
        return AsyncAzureOpenAI(
            azure_endpoint=config.endpoint_url,
            api_key=config.api_key,
            api_version="2024-12-01-preview",
        )
    if config.type == "openai_compatible":
        return AsyncOpenAI(
            base_url=config.endpoint_url,
            api_key=config.api_key,
        )
    raise ValueError(
        f"Unknown endpoint type: '{config.type}'. "
        "Supported: 'azure_openai', 'openai_compatible'"
    )


async def request_model(
    client: ModelClient,
    config: EndpointConfig,
    user_content: str,
    *,
    system_content: str | None = None,
    max_tokens: int | None = None,
) -> ModelReply:
    """Call the configured API mode and return a normalized reply."""
    token_limit = max_tokens or config.parameters.get("max_tokens", 1024)
    temperature = config.parameters.get("temperature")

    if config.api_mode == "responses":
        create_kwargs: dict[str, Any] = {
            "model": config.deployment_name,
            "input": user_content,
            "max_output_tokens": token_limit,
        }
        if system_content:
            create_kwargs["instructions"] = system_content
        if temperature is not None:
            create_kwargs["temperature"] = temperature

        response = await client.responses.create(**create_kwargs)
        usage = response.usage
        prompt_tokens = usage.input_tokens if usage else 0
        completion_tokens = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens
        return ModelReply(
            text=response.output_text or "",
            model=response.model or config.deployment_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    messages = []
    if system_content:
        messages.append({"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_content})
    create_kwargs = {
        "model": config.deployment_name,
        "messages": messages,
        "max_completion_tokens": token_limit,
    }
    if temperature is not None:
        create_kwargs["temperature"] = temperature

    response = await client.chat.completions.create(**create_kwargs)
    choice = response.choices[0] if response.choices else None
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens
    return ModelReply(
        text=choice.message.content or "" if choice else "",
        model=response.model or config.deployment_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )