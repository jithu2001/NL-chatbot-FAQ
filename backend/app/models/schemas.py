from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.catalog import SCHEME_NAMES


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    # Optional scheme selected in the UI; must be one of the supported schemes.
    scheme: str | None = None

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        return v

    @field_validator("scheme")
    @classmethod
    def _known_scheme(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if v not in SCHEME_NAMES:
            raise ValueError("unknown scheme")
        return v


class SourceInfo(BaseModel):
    title: str
    url: str
    source_type: str
    authority: str
    last_updated: str
    retrieved_date: str
    page: int | None = None


class ChatResponse(BaseModel):
    answer: str
    classification: str
    source: SourceInfo | None = None
    last_updated: str | None = None
    retrieved_date: str | None = None
    scheme: str | None = None
    # True when the question named no scheme and the default scheme was used.
    scheme_defaulted: bool = False


class HealthResponse(BaseModel):
    status: str
    llm: bool
    chromadb: bool


class SchemeInfo(BaseModel):
    name: str
    category: str


class ErrorDetail(BaseModel):
    code: str
    message: str
