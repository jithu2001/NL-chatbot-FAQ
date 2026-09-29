"""Persistent ChromaDB vector store (collection: mutual_fund_faq).

Embeddings are always computed by us (Ollama) and passed in explicitly, so
Chroma never downloads or runs its own embedding model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings


class VectorStoreUnavailableError(RuntimeError):
    """Raised when ChromaDB cannot be opened or queried."""


@dataclass
class RetrievedChunk:
    id: str
    text: str
    metadata: dict[str, Any]
    similarity: float  # cosine similarity in [-1, 1]; higher is better


_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        path = get_settings().chroma_persist_directory
        path.mkdir(parents=True, exist_ok=True)
        try:
            _client = chromadb.PersistentClient(
                path=str(path),
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
            )
        except Exception as exc:  # noqa: BLE001 - surface as a single error type
            raise VectorStoreUnavailableError("Could not open ChromaDB") from exc
    return _client


class EmbeddingModelMismatchError(VectorStoreUnavailableError):
    """The index was built with a different embedding model than configured."""


def get_collection():
    settings = get_settings()
    client = get_client()
    try:
        try:
            collection = client.get_collection(settings.collection_name, embedding_function=None)
        except Exception:  # noqa: BLE001 - does not exist yet
            return client.create_collection(
                name=settings.collection_name,
                metadata={"hnsw:space": "cosine", "embedding_model": settings.embedding_model_id},
                embedding_function=None,
            )
        stored = (collection.metadata or {}).get("embedding_model")
        if stored is None and collection.count() > 0:
            stored = "ollama:nomic-embed-text"  # indexes built before the model was recorded
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreUnavailableError("Could not open collection") from exc
    if stored and stored != settings.embedding_model_id:
        raise EmbeddingModelMismatchError(
            f"Index was built with '{stored}' but '{settings.embedding_model_id}' is configured. "
            "Run: python scripts/reset_vector_db.py --yes && python scripts/ingest_sources.py")
    return collection


def upsert_chunks(ids: list[str], documents: list[str], embeddings: list[list[float]],
                  metadatas: list[dict[str, Any]]) -> None:
    get_collection().upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)


def delete_source(source_id: str) -> None:
    get_collection().delete(where={"source_id": source_id})


def source_fingerprint(source_id: str) -> tuple[int, str | None]:
    """Return (chunk_count, content_hash) currently stored for a source."""
    res = get_collection().get(where={"source_id": source_id}, include=["metadatas"])
    metas = res.get("metadatas") or []
    hashes = {m.get("content_hash") for m in metas if m}
    return len(metas), (hashes.pop() if len(hashes) == 1 else None)


def indexed_source_ids() -> set[str]:
    res = get_collection().get(include=["metadatas"])
    return {m["source_id"] for m in res.get("metadatas") or [] if m and m.get("source_id")}


def count() -> int:
    return get_collection().count()


def query(embedding: list[float], top_k: int, where: dict[str, Any] | None = None) -> list[RetrievedChunk]:
    try:
        res = get_collection().query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except VectorStoreUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreUnavailableError("Vector query failed") from exc

    chunks: list[RetrievedChunk] = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True):
        chunks.append(RetrievedChunk(id=cid, text=doc or "", metadata=dict(meta or {}), similarity=1.0 - float(dist)))
    return chunks


def get_neighbors(meta: dict[str, Any], window: int = 1) -> dict[int, str]:
    """Texts of the chunks next to a chunk (same source and page), keyed by chunk_index."""
    source_id, index = meta.get("source_id"), meta.get("chunk_index")
    if not source_id or not isinstance(index, int):
        return {}
    ids = [f"{source_id}-chunk-{n:04d}" for n in range(index - window, index + window + 1) if n > 0 and n != index]
    res = get_collection().get(ids=ids, include=["documents", "metadatas"])
    out: dict[int, str] = {}
    for doc, m in zip(res.get("documents") or [], res.get("metadatas") or [], strict=True):
        if m and m.get("page") == meta.get("page"):
            out[int(m["chunk_index"])] = doc or ""
    return out


def reset_collection() -> None:
    client = get_client()
    name = get_settings().collection_name
    existing = {c.name if hasattr(c, "name") else c for c in client.list_collections()}
    if name in existing:
        client.delete_collection(name)
    get_collection()


def stored_count_any_model() -> int:
    """Chunk count without the embedding-model check (for the reset script)."""
    name = get_settings().collection_name
    try:
        return get_client().get_collection(name).count()
    except Exception:  # noqa: BLE001 - collection may not exist
        return 0


def is_available() -> bool:
    try:
        get_collection().count()
        return True
    except Exception:  # noqa: BLE001
        return False
