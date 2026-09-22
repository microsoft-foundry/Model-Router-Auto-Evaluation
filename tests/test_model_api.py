"""Tests for the shared Chat Completions and Responses API adapter."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config import EndpointConfig
from src.model_api import request_model


def _config(api_mode: str) -> EndpointConfig:
    return EndpointConfig(
        type="openai_compatible",
        endpoint_url="https://example.services.ai.azure.com/openai/v1",
        api_key="test-key",
        deployment_name="test-deployment",
        api_mode=api_mode,
        parameters={"max_tokens": 256},
    )


@pytest.mark.asyncio
async def test_chat_completions_request_is_normalized():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="chat reply"))],
        model="served-chat-model",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4, total_tokens=14),
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )

    reply = await request_model(client, _config("chat_completions"), "hello")

    create.assert_awaited_once_with(
        model="test-deployment",
        messages=[{"role": "user", "content": "hello"}],
        max_completion_tokens=256,
    )
    assert reply.text == "chat reply"
    assert reply.model == "served-chat-model"
    assert (reply.prompt_tokens, reply.completion_tokens, reply.total_tokens) == (10, 4, 14)


@pytest.mark.asyncio
async def test_responses_request_is_normalized():
    response = SimpleNamespace(
        output_text="responses reply",
        model="served-responses-model",
        usage=SimpleNamespace(input_tokens=12, output_tokens=5, total_tokens=17),
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(responses=SimpleNamespace(create=create))

    reply = await request_model(
        client,
        _config("responses"),
        "hello",
        system_content="be concise",
    )

    create.assert_awaited_once_with(
        model="test-deployment",
        input="hello",
        max_output_tokens=256,
        instructions="be concise",
    )
    assert reply.text == "responses reply"
    assert reply.model == "served-responses-model"
    assert (reply.prompt_tokens, reply.completion_tokens, reply.total_tokens) == (12, 5, 17)