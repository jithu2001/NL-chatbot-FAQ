"""Groq chat client (OpenAI-compatible Chat Completions API) over httpx.

Works with any OpenAI-compatible endpoint via GROQ_BASE_URL, e.g. Ollama's
http://localhost:11434/v1 for offline testing.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.core.config import get_settings
from app.llm.errors import LLMRateLimitedError, LLMUnavailableError

log = logging.getLogger("powerup.groq")

_health_cache: tuple[float, bool] | None = None
_HEALTH_TTL = 300.0  # seconds; avoids spending rate limit on health checks


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().groq_api_key}", "Content-Type": "application/json"}


async def chat(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise LLMUnavailableError("GROQ_API_KEY is not set")
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_completion_tokens": 320,
    }
    if _is_reasoning_model(settings.groq_model):
        # GPT-OSS models reason before answering: keep it short, keep it out of
        # the response, and leave room for it in the completion budget.
        payload.update({"reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 1500})
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)) as client:
            r = await client.post(f"{settings.groq_base_url}/chat/completions", json=payload, headers=_headers())
    except httpx.HTTPError as exc:
        raise LLMUnavailableError("Groq request failed") from exc
    if r.status_code == 429:
        log.warning("Groq rate limit reached (HTTP 429)")
        raise LLMRateLimitedError("Groq rate limit reached")
    if r.status_code >= 400:
        # Log Groq's error code/message only - never the prompt or question.
        try:
            err = r.json().get("error") or {}
        except ValueError:
            err = {}
        log.error("Groq HTTP %s: %s - %s", r.status_code, err.get("code") or err.get("type"),
                  str(err.get("message", ""))[:200])
        raise LLMUnavailableError(f"Groq returned HTTP {r.status_code}")

    choice = (r.json().get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "").strip()
    if choice.get("finish_reason") == "length":
        cut = max(text.rfind(". "), text.rfind(".\n"))
        text = text[: cut + 1] if cut > 0 else text
    return text


def _is_reasoning_model(model: str) -> bool:
    return model.startswith("openai/gpt-oss")


async def is_available() -> bool:
    """Key valid AND the configured model is available to it (cached)."""
    global _health_cache
    settings = get_settings()
    if not settings.groq_api_key:
        return False
    now = time.monotonic()
    if _health_cache and now - _health_cache[0] < _HEALTH_TTL:
        return _health_cache[1]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            r = await client.get(f"{settings.groq_base_url}/models", headers=_headers())
        ok = r.status_code == 200
        if ok:
            available = {m.get("id") for m in r.json().get("data", [])}
            if available and settings.groq_model not in available:
                log.error("GROQ_MODEL '%s' is not available to this API key", settings.groq_model)
                ok = False
    except (httpx.HTTPError, ValueError):
        ok = False
    _health_cache = (now, ok)
    return ok
