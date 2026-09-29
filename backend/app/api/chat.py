"""HTTP routes: POST /api/chat, GET /api/health, GET /api/schemes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.catalog import AMC_NAME, SCHEMES
from app.core.config import get_settings
from app.llm import provider
from app.llm.errors import LLMRateLimitedError, LLMUnavailableError
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, SchemeInfo
from app.rag import vector_store
from app.rag.vector_store import VectorStoreUnavailableError
from app.safety.rate_limit import enforce_rate_limit
from app.services.answer_pipeline import KnowledgeBaseEmptyError, answer_question

router = APIRouter(prefix="/api")

OLLAMA_DOWN = "The local AI service is currently unavailable. Please make sure Ollama is running."
HOSTED_DOWN = "The AI service is currently unavailable. Please try again in a moment."
BUSY = "The assistant is handling many questions right now. Please try again in a minute."
KB_DOWN = "The knowledge base is currently unavailable. Please try again."


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(enforce_rate_limit)])
async def chat(req: ChatRequest) -> ChatResponse:
    # The question lives only in memory for the duration of this request.
    try:
        return await answer_question(req.question, scheme_hint=req.scheme)
    except LLMRateLimitedError:
        raise HTTPException(status_code=503, detail={"code": "llm_busy", "message": BUSY}) from None
    except LLMUnavailableError:
        local = get_settings().llm_provider == "ollama" or get_settings().embedding_provider == "ollama"
        message = OLLAMA_DOWN if local else HOSTED_DOWN
        raise HTTPException(status_code=503, detail={"code": "llm_unavailable", "message": message}) from None
    except (VectorStoreUnavailableError, KnowledgeBaseEmptyError):
        raise HTTPException(status_code=503, detail={"code": "knowledge_base_unavailable", "message": KB_DOWN}) from None


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    llm_ok = await provider.is_available()
    chroma_ok = vector_store.is_available() and vector_store.count() > 0
    return HealthResponse(status="ok" if llm_ok and chroma_ok else "degraded", llm=llm_ok, chromadb=chroma_ok)


@router.get("/schemes", response_model=list[SchemeInfo])
async def schemes() -> list[SchemeInfo]:
    return [SchemeInfo(name=s.name, amc=AMC_NAME, category=s.category) for s in SCHEMES]
