"""Application settings loaded from environment variables / .env files.

Lookup order (first match wins for each variable):
  1. Real process environment variables
  2. backend/.env
  3. <project root>/.env
  4. Built-in defaults

Relative paths (e.g. CHROMA_PERSIST_DIRECTORY) are resolved against the
directory of the .env file they came from, so both `backend/.env`
(`../data/chroma`) and the root `.env` (`./data/chroma`) point to the same place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

_DEFAULTS: dict[str, str] = {
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.1:8b",
    "OLLAMA_EMBED_MODEL": "nomic-embed-text",
    "CHROMA_PERSIST_DIRECTORY": "../data/chroma",
    "TOP_K": "5",
    "RELEVANCE_THRESHOLD": "0.70",
    "SOURCES_CSV": "../data/sources.csv",
    "DOCUMENTS_DIR": "../data/documents",
    "DEFAULT_SCHEME": "Parag Parikh Flexi Cap Fund",
    "OLLAMA_NUM_CTX": "8192",
    "OLLAMA_TIMEOUT_SECONDS": "120",
    "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
    "RATE_LIMIT_PER_MINUTE": "12",
}

_PATH_KEYS = {"CHROMA_PERSIST_DIRECTORY", "SOURCES_CSV", "DOCUMENTS_DIR"}


def _lookup(key: str, files: list[tuple[Path, dict[str, str | None]]]) -> tuple[str, Path]:
    if key in os.environ:
        return os.environ[key], Path.cwd()
    for base, values in files:
        value = values.get(key)
        if value is not None and value != "":
            return value, base
    return _DEFAULTS[key], BACKEND_DIR


def _resolve_path(value: str, base: Path) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_embed_model: str
    chroma_persist_directory: Path
    top_k: int
    relevance_threshold: float
    sources_csv: Path
    documents_dir: Path
    default_scheme: str
    ollama_num_ctx: int
    ollama_timeout_seconds: float
    cors_origins: list[str]
    rate_limit_per_minute: int

    collection_name: str = "mutual_fund_faq"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    files: list[tuple[Path, dict[str, str | None]]] = []
    for env_file in (BACKEND_DIR / ".env", PROJECT_ROOT / ".env"):
        if env_file.is_file():
            files.append((env_file.parent, dotenv_values(env_file)))

    raw: dict[str, str] = {}
    for key in _DEFAULTS:
        value, base = _lookup(key, files)
        raw[key] = str(_resolve_path(value, base)) if key in _PATH_KEYS else value

    return Settings(
        ollama_base_url=raw["OLLAMA_BASE_URL"].rstrip("/"),
        ollama_model=raw["OLLAMA_MODEL"],
        ollama_embed_model=raw["OLLAMA_EMBED_MODEL"],
        chroma_persist_directory=Path(raw["CHROMA_PERSIST_DIRECTORY"]),
        top_k=int(raw["TOP_K"]),
        relevance_threshold=float(raw["RELEVANCE_THRESHOLD"]),
        sources_csv=Path(raw["SOURCES_CSV"]),
        documents_dir=Path(raw["DOCUMENTS_DIR"]),
        default_scheme=raw["DEFAULT_SCHEME"],
        ollama_num_ctx=int(raw["OLLAMA_NUM_CTX"]),
        ollama_timeout_seconds=float(raw["OLLAMA_TIMEOUT_SECONDS"]),
        cors_origins=[o.strip() for o in raw["CORS_ORIGINS"].split(",") if o.strip()],
        rate_limit_per_minute=int(raw["RATE_LIMIT_PER_MINUTE"]),
    )
