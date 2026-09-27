import asyncio
import dataclasses

import httpx
import pytest

from app.core import config
from app.llm import groq_client
from app.llm.errors import LLMRateLimitedError, LLMUnavailableError


def _use_transport(monkeypatch, handler, api_key="test-key"):
    settings = dataclasses.replace(config.get_settings(), groq_api_key=api_key, groq_base_url="https://groq.test/v1")
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(groq_client.httpx, "AsyncClient", client_factory)


def test_chat_returns_content_and_sends_key(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": " The SIP is ₹1,000. "}, "finish_reason": "stop"}]})

    _use_transport(monkeypatch, handler)
    assert asyncio.run(groq_client.chat("sys", "q")) == "The SIP is ₹1,000."
    assert seen == {"auth": "Bearer test-key", "url": "https://groq.test/v1/chat/completions"}


def test_length_cutoff_drops_partial_sentence(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "First fact. Second fact is cut"}, "finish_reason": "length"}]})

    _use_transport(monkeypatch, handler)
    assert asyncio.run(groq_client.chat("sys", "q")) == "First fact."


def test_rate_limit_raises_specific_error(monkeypatch):
    _use_transport(monkeypatch, lambda request: httpx.Response(429, json={"error": "rate limited"}))
    with pytest.raises(LLMRateLimitedError):
        asyncio.run(groq_client.chat("sys", "q"))


def test_server_error_and_missing_key(monkeypatch):
    _use_transport(monkeypatch, lambda request: httpx.Response(500))
    with pytest.raises(LLMUnavailableError):
        asyncio.run(groq_client.chat("sys", "q"))
    _use_transport(monkeypatch, lambda request: httpx.Response(200), api_key="")
    with pytest.raises(LLMUnavailableError):
        asyncio.run(groq_client.chat("sys", "q"))
