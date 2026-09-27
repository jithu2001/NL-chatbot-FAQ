"""The controlled source registry (data/sources.csv).

Every URL the assistant can ever display comes from this registry, either
directly or via ChromaDB metadata that was written from it at ingestion time.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings

REQUIRED_COLUMNS = (
    "source_id",
    "title",
    "scheme",
    "topic",
    "source_type",
    "url",
    "publication_date",
    "last_updated",
    "retrieved_date",
    "authority",
)

# Only official domains are accepted into the registry.
ALLOWED_DOMAINS = {
    "AMC": ("amc.ppfas.com", "www.hdfcfund.com", "hdfcfund.com", "files.hdfcfund.com"),
    "AMFI": ("www.amfiindia.com", "amfiindia.com", "portal.amfiindia.com"),
    "SEBI": ("www.sebi.gov.in", "sebi.gov.in", "investor.sebi.gov.in"),
}


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    scheme: str
    topic: str
    source_type: str
    url: str
    publication_date: str
    last_updated: str
    retrieved_date: str
    authority: str

    def metadata(self) -> dict[str, str]:
        return asdict(self)


class RegistryError(ValueError):
    pass


def _validate(row: dict[str, str], line: int) -> Source:
    missing = [c for c in REQUIRED_COLUMNS if not (row.get(c) or "").strip()]
    if missing:
        raise RegistryError(f"sources.csv line {line}: missing {', '.join(missing)}")
    src = Source(**{c: row[c].strip() for c in REQUIRED_COLUMNS})
    host = urlparse(src.url).hostname or ""
    allowed = ALLOWED_DOMAINS.get(src.authority)
    if allowed is None:
        raise RegistryError(f"{src.source_id}: authority must be one of {sorted(ALLOWED_DOMAINS)}")
    if urlparse(src.url).scheme != "https" or host not in allowed:
        raise RegistryError(f"{src.source_id}: URL host '{host}' is not an official {src.authority} domain")
    return src


def load_sources(path: Path | None = None) -> list[Source]:
    path = path or get_settings().sources_csv
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        cols = set(reader.fieldnames or [])
        if not set(REQUIRED_COLUMNS) <= cols:
            raise RegistryError(f"sources.csv must have columns: {', '.join(REQUIRED_COLUMNS)}")
        sources = [_validate(row, i + 2) for i, row in enumerate(reader)]
    ids = [s.source_id for s in sources]
    if len(ids) != len(set(ids)):
        raise RegistryError("sources.csv contains duplicate source_id values")
    return sources


@lru_cache(maxsize=1)
def registry() -> dict[str, Source]:
    return {s.source_id: s for s in load_sources()}


def find_source(*, scheme: str | None = None, source_type: str | None = None,
                title_contains: str | None = None) -> Source | None:
    for src in registry().values():
        if scheme is not None and src.scheme != scheme:
            continue
        if source_type is not None and src.source_type != source_type:
            continue
        if title_contains is not None and title_contains.lower() not in src.title.lower():
            continue
        return src
    return None
