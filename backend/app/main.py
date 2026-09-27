"""FastAPI entry point: `uvicorn app.main:app --reload --port 8000` (from backend/)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router
from app.core.config import get_settings
from app.llm.ollama_client import warm_up

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # keep request details out of logs
logging.getLogger("chromadb").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(warm_up())  # don't block startup on model loading
    yield
    task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="PowerUp Money - Mutual Fund FAQ Assistant",
    description="Facts-only mutual fund FAQ assistant grounded in official AMC and AMFI sources.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo the submitted input back (it could contain PII).
    fields = sorted({".".join(str(p) for p in e.get("loc", [])[1:]) or "body" for e in exc.errors()})
    return JSONResponse(status_code=422, content={"detail": {
        "code": "invalid_request", "message": f"Invalid request field(s): {', '.join(fields)}"}})


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("powerup").error("unhandled error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": {
        "code": "internal_error", "message": "Something went wrong. Please try again."}})


app.include_router(router)
