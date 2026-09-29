"""Chooses the LLM backend from LLM_PROVIDER ("groq" or "ollama")."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.llm import groq_client, ollama_client
from app.rag import embeddings


async def chat(system: str, user: str) -> str:
    if get_settings().llm_provider == "ollama":
        return await ollama_client.chat(system=system, user=user)
    return await groq_client.chat(system=system, user=user)


async def is_available() -> bool:
    if get_settings().llm_provider == "ollama":
        return await ollama_client.is_available()
    return await groq_client.is_available()


async def warm_up() -> None:
    """Load models so the first question is fast (local model and/or embedder)."""
    await asyncio.to_thread(embeddings.warm_up)
    if get_settings().llm_provider == "ollama":
        await ollama_client.warm_up()
