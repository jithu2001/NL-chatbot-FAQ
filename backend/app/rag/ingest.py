"""Ingestion pipeline: official URL -> download -> extract -> clean -> chunk
-> embed (Ollama) -> upsert into ChromaDB.

Idempotent: chunk IDs are deterministic (SRC-001-chunk-0001 ...) and a
content hash is stored with every chunk, so re-running skips unchanged
sources and never creates duplicates.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.catalog import find_scheme_in_text
from app.core.config import get_settings
from app.core.sources import Source, load_sources
from app.llm.ollama_client import OllamaUnavailableError
from app.rag import vector_store
from app.rag.chunker import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS, CHUNKER_VERSION, chunk_text
from app.rag.embeddings import embed_documents
from app.rag.extractors import PageText, extract_html, extract_pdf

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) PowerUpMoney-FAQ-Ingest/1.0 (+official-sources-only)"


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict


def _cache_path(src: Source, is_pdf: bool) -> Path:
    return get_settings().documents_dir / f"{src.source_id}.{'pdf' if is_pdf else 'html'}"


def _cached(src: Source) -> tuple[bytes, bool] | None:
    for is_pdf in (True, False):
        p = _cache_path(src, is_pdf)
        if p.is_file() and p.stat().st_size > 0:
            return p.read_bytes(), is_pdf
    return None


def download(src: Source, refresh: bool = False) -> tuple[bytes, bool, str]:
    """Return (content, is_pdf, origin) where origin is 'downloaded' or 'cache'."""
    if not refresh and (hit := _cached(src)):
        return hit[0], hit[1], "cache"
    try:
        r = httpx.get(src.url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60)
        r.raise_for_status()
    except httpx.HTTPError:
        if hit := _cached(src):
            return hit[0], hit[1], "cache (download failed)"
        raise
    data = r.content
    is_pdf = data[:5] == b"%PDF-" or "pdf" in r.headers.get("content-type", "").lower()
    for stale in (True, False):
        _cache_path(src, stale).unlink(missing_ok=True)
    path = _cache_path(src, is_pdf)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, is_pdf, "downloaded"


def extract(data: bytes, is_pdf: bool) -> list[PageText]:
    return extract_pdf(data) if is_pdf else extract_html(data)


def build_chunks(src: Source, pages: list[PageText], content_hash: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        scheme = src.scheme
        if src.scheme == "Multiple":
            # Trust the page title when there is one; covers, indexes and
            # multi-fund tables mention every scheme in their body text.
            detected = find_scheme_in_text(page.heading) if page.heading else find_scheme_in_text(page.text)
            if detected == "OUT_OF_SCOPE":
                continue  # page about a scheme outside this assistant's scope
            scheme = detected or "General"
        header = f"Document: {src.title}\nScheme: {scheme}"
        if page.page is not None:
            header += f"\nPage: {page.page}"
        for piece in chunk_text(page.text):
            n = len(chunks) + 1
            meta = src.metadata() | {"scheme": scheme, "chunk_index": n, "content_hash": content_hash}
            if page.page is not None:
                meta["page"] = page.page
            chunks.append(Chunk(id=f"{src.source_id}-chunk-{n:04d}", text=f"{header}\n\n{piece}", metadata=meta))
    return chunks


def ingest_source(src: Source, *, refresh: bool = False, force: bool = False, log=print) -> int:
    data, is_pdf, origin = download(src, refresh=refresh)
    log(f"✓ {'Downloaded' if origin == 'downloaded' else 'Loaded from ' + origin} ({'PDF' if is_pdf else 'HTML'}, {len(data) // 1024} KB)")

    pages = extract(data, is_pdf)
    total_chars = sum(len(p.text) for p in pages)
    if total_chars < 200:
        raise ValueError("extracted text is too short; page may require JavaScript")
    log(f"✓ Extracted {len(pages)} page(s), {total_chars:,} characters")

    # Fingerprint = extracted text + chunking settings + embedding model, so a
    # change to any of them triggers re-indexing of this source.
    fingerprint = "\n".join(p.text for p in pages) + (
        f"|chunker={CHUNKER_VERSION}:{CHUNK_SIZE_TOKENS}:{CHUNK_OVERLAP_TOKENS}"
        f"|embed={get_settings().ollama_embed_model}")
    content_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    chunks = build_chunks(src, pages, content_hash)
    log(f"✓ {len(chunks)} chunks")

    stored_count, stored_hash = vector_store.source_fingerprint(src.source_id)
    if not force and stored_count == len(chunks) and stored_hash == content_hash:
        log("✓ Already indexed and unchanged - skipped")
        return len(chunks)

    embeddings = embed_documents([c.text for c in chunks])
    log("✓ Embedded")
    if stored_count:
        vector_store.delete_source(src.source_id)  # drop stale chunks before re-adding
    vector_store.upsert_chunks(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[c.metadata for c in chunks],
    )
    log("✓ Added to ChromaDB")
    return len(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest official sources from data/sources.csv into ChromaDB.")
    parser.add_argument("--refresh", action="store_true", help="re-download documents even if cached")
    parser.add_argument("--force", action="store_true", help="re-embed even if a source is unchanged")
    parser.add_argument("--only", nargs="*", metavar="SOURCE_ID", help="ingest only these source IDs")
    args = parser.parse_args(argv)

    print("Loading source registry...")
    sources = load_sources()
    if args.only:
        wanted = set(args.only)
        sources = [s for s in sources if s.source_id in wanted]
    print(f"{len(sources)} sources registered\n")

    total_chunks, ok, failed = 0, 0, []
    for i, src in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {src.title}  ({src.source_id})")
        try:
            total_chunks += ingest_source(src, refresh=args.refresh, force=args.force, log=lambda m: print("  " + m))
            ok += 1
        except OllamaUnavailableError as exc:
            print(f"  ✗ Ollama error: {exc}\n\nIs Ollama running and is '{get_settings().ollama_embed_model}' pulled?")
            return 2
        except Exception as exc:  # noqa: BLE001 - report and continue with other sources
            print(f"  ✗ Skipped: {type(exc).__name__}: {exc}")
            failed.append(src.source_id)
        print()

    print("Ingestion complete.")
    print(f"{ok} sources")
    print(f"{total_chunks} chunks")
    print(f"{vector_store.count()} chunks in collection '{get_settings().collection_name}'")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
