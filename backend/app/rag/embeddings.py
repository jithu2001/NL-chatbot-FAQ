"""Embeddings, selected by EMBEDDING_PROVIDER.

- "fastembed" (default): BAAI/bge-small-en-v1.5 via ONNX Runtime, in-process on
  CPU (~150 MB RAM, no API key) - suits small hosts such as Render's free tier.
- "ollama": nomic-embed-text via a local Ollama server. nomic is trained with
  task prefixes, so documents and queries are prefixed differently.

Changing the provider/model changes the vectors: re-run ingestion.
"""

from __future__ import annotations

import asyncio
import threading

from app.core.config import get_settings
from app.llm import ollama_client

_BATCH_SIZE = 16
_model = None
_model_lock = threading.Lock()
# The API server uses one thread (small hosts); ingestion can use every core.
_threads: int | None = 1


def use_all_cores() -> None:
    global _threads
    _threads = None


def _fastembed_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from fastembed import TextEmbedding

                settings = get_settings()
                kwargs = {"threads": _threads}
                if settings.fastembed_cache_dir:
                    kwargs["cache_dir"] = str(settings.fastembed_cache_dir)
                _model = TextEmbedding(settings.fastembed_model, **kwargs)
    return _model


def warm_up() -> None:
    if get_settings().embedding_provider == "fastembed":
        list(_fastembed_model().query_embed(["warm up"]))


def _nomic_prefix(kind: str, text: str) -> str:
    return f"search_{kind}: {text}" if "nomic" in get_settings().ollama_embed_model.lower() else text


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Synchronous batch embedding used by the ingestion pipeline."""
    if get_settings().embedding_provider == "fastembed":
        return [v.tolist() for v in _fastembed_model().passage_embed(texts, batch_size=_BATCH_SIZE)]
    out: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        out.extend(ollama_client.embed_sync([_nomic_prefix("document", t) for t in texts[i : i + _BATCH_SIZE]]))
    return out


async def embed_query(text: str) -> list[float]:
    if get_settings().embedding_provider == "fastembed":
        vec = await asyncio.to_thread(lambda: next(iter(_fastembed_model().query_embed([text]))))
        return vec.tolist()
    return (await ollama_client.embed([_nomic_prefix("query", text)]))[0]
