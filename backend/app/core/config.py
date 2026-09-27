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
    # Providers: "groq" (hosted, default) or "ollama" (fully local) for the LLM;
    # "fastembed" (in-process CPU, default) or "ollama" for embeddings.
    "LLM_PROVIDER": "groq",
    "EMBEDDING_PROVIDER": "fastembed",
    "GROQ_API_KEY": "",
    "GROQ_MODEL": "llama-3.1-8b-instant",
    "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
    "FASTEMBED_MODEL": "BAAI/bge-small-en-v1.5",
    "FASTEMBED_CACHE_DIR": "",
    "CHUNK_SIZE_TOKENS": "",      # empty = provider default
    "CHUNK_OVERLAP_TOKENS": "",
    "LLM_TIMEOUT_SECONDS": "60",
    "SERVE_FRONTEND_DIR": "",     # path to a built frontend (dist/) to serve from FastAPI
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
_OPTIONAL_PATH_KEYS = {"FASTEMBED_CACHE_DIR", "SERVE_FRONTEND_DIR"}

# Chunk sizes per embedding model: bge-small reads at most 512 word pieces,
# so its chunks are smaller than those for nomic-embed-text (8k context).
_CHUNK_DEFAULTS = {"fastembed": (350, 60), "ollama": (900, 150)}


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
    llm_provider: str
    embedding_provider: str
    groq_api_key: str
    groq_model: str
    groq_base_url: str
    fastembed_model: str
    fastembed_cache_dir: Path | None
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    llm_timeout_seconds: float
    serve_frontend_dir: Path | None
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

    @property
    def embedding_model_id(self) -> str:
        """Identifies the vectors in the index; must match between ingestion and queries."""
        if self.embedding_provider == "ollama":
            return f"ollama:{self.ollama_embed_model}"
        return f"fastembed:{self.fastembed_model}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    files: list[tuple[Path, dict[str, str | None]]] = []
    for env_file in (BACKEND_DIR / ".env", PROJECT_ROOT / ".env"):
        if env_file.is_file():
            files.append((env_file.parent, dotenv_values(env_file)))

    raw: dict[str, str] = {}
    for key in _DEFAULTS:
        value, base = _lookup(key, files)
        if key in _PATH_KEYS or (key in _OPTIONAL_PATH_KEYS and value):
            value = str(_resolve_path(value, base))
        raw[key] = value

    llm_provider = raw["LLM_PROVIDER"].strip().lower()
    embedding_provider = raw["EMBEDDING_PROVIDER"].strip().lower()
    if llm_provider not in ("groq", "ollama"):
        raise ValueError("LLM_PROVIDER must be 'groq' or 'ollama'")
    if embedding_provider not in ("fastembed", "ollama"):
        raise ValueError("EMBEDDING_PROVIDER must be 'fastembed' or 'ollama'")
    chunk_default, overlap_default = _CHUNK_DEFAULTS[embedding_provider]

    return Settings(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        groq_api_key=raw["GROQ_API_KEY"].strip(),
        groq_model=raw["GROQ_MODEL"],
        groq_base_url=raw["GROQ_BASE_URL"].rstrip("/"),
        fastembed_model=raw["FASTEMBED_MODEL"],
        fastembed_cache_dir=Path(raw["FASTEMBED_CACHE_DIR"]) if raw["FASTEMBED_CACHE_DIR"] else None,
        chunk_size_tokens=int(raw["CHUNK_SIZE_TOKENS"] or chunk_default),
        chunk_overlap_tokens=int(raw["CHUNK_OVERLAP_TOKENS"] or overlap_default),
        llm_timeout_seconds=float(raw["LLM_TIMEOUT_SECONDS"]),
        serve_frontend_dir=Path(raw["SERVE_FRONTEND_DIR"]) if raw["SERVE_FRONTEND_DIR"] else None,
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
