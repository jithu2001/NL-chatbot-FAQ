"""Minimal async/sync Ollama client over httpx (local only)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings


from app.llm.errors import LLMUnavailableError

# Kept as an alias so callers can catch provider-agnostic errors.
OllamaUnavailableError = LLMUnavailableError


def _base() -> str:
    return get_settings().ollama_base_url


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(get_settings().ollama_timeout_seconds, connect=5.0)


def embed_sync(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed a batch of texts (used by the ingestion CLI)."""
    model = model or get_settings().ollama_embed_model
    try:
        r = httpx.post(f"{_base()}/api/embed", json={"model": model, "input": texts}, timeout=_timeout())
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaUnavailableError(f"Embedding request failed: {exc}") from exc
    return r.json()["embeddings"]


async def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    model = model or get_settings().ollama_embed_model
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            r = await client.post(f"{_base()}/api/embed", json={"model": model, "input": texts})
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaUnavailableError("Embedding request failed") from exc
    return r.json()["embeddings"]


async def chat(system: str, user: str, model: str | None = None) -> str:
    """Return the answer text. A trailing partial sentence is removed when the
    generation stopped because it hit the token limit."""
    settings = get_settings()
    payload = {
        "model": model or settings.ollama_model,
        "stream": False,
        "keep_alive": "30m",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": 0,
            "top_p": 0.9,
            "num_ctx": settings.ollama_num_ctx,
            "num_predict": 320,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            r = await client.post(f"{_base()}/api/chat", json=payload)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaUnavailableError("Chat request failed") from exc
    body = r.json()
    text = (body.get("message") or {}).get("content", "").strip()
    if body.get("done_reason") == "length":
        cut = max(text.rfind(". "), text.rfind(".\n"))
        text = text[: cut + 1] if cut > 0 else text
    return text


async def warm_up() -> None:
    """Load the chat and embedding models into memory so the first question is fast."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=5.0)) as client:
            await client.post(f"{_base()}/api/embed", json={"model": settings.ollama_embed_model, "input": ["warm up"]})
            await client.post(f"{_base()}/api/generate", json={
                "model": settings.ollama_model, "prompt": "", "keep_alive": "30m",
                "options": {"num_ctx": settings.ollama_num_ctx}})
    except httpx.HTTPError:
        pass  # Ollama not running yet; /api/health will report it.


async def is_available() -> bool:
    """True when Ollama answers and both configured models are installed."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{_base()}/api/tags")
            r.raise_for_status()
    except httpx.HTTPError:
        return False
    names = {m.get("name", "") for m in r.json().get("models", [])}
    names |= {n.split(":")[0] for n in names if n.endswith(":latest")}

    def installed(model: str) -> bool:
        return model in names or f"{model}:latest" in names

    return installed(settings.ollama_model) and installed(settings.ollama_embed_model)
