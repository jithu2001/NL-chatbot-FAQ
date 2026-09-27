"""Local embeddings via Ollama (nomic-embed-text by default).

nomic-embed-text is trained with task prefixes; using them noticeably
improves retrieval quality, so documents and queries are prefixed differently.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.llm import ollama_client

_BATCH_SIZE = 16


def _uses_nomic_prefixes() -> bool:
    return "nomic" in get_settings().ollama_embed_model.lower()


def _doc_text(text: str) -> str:
    return f"search_document: {text}" if _uses_nomic_prefixes() else text


def _query_text(text: str) -> str:
    return f"search_query: {text}" if _uses_nomic_prefixes() else text


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Synchronous batch embedding used by the ingestion pipeline."""
    out: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = [_doc_text(t) for t in texts[i : i + _BATCH_SIZE]]
        out.extend(ollama_client.embed_sync(batch))
    return out


async def embed_query(text: str) -> list[float]:
    return (await ollama_client.embed([_query_text(text)]))[0]
