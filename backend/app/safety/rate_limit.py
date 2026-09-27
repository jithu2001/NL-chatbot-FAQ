"""Tiny in-memory sliding-window rate limiter for public (tunnelled) use.

Clients are keyed by a salted hash of their IP (taken from X-Forwarded-For
when behind ngrok / a proxy). Nothing is persisted or logged.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import get_settings

_SALT = os.urandom(16)
_hits: dict[str, deque[float]] = defaultdict(deque)
_WINDOW = 60.0

RATE_LIMITED = "You're asking questions a little too quickly. Please wait a moment and try again."


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    return hashlib.sha256(_SALT + ip.encode()).hexdigest()[:16]


def enforce_rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_per_minute
    if limit <= 0:
        return
    now = time.monotonic()
    q = _hits[_client_key(request)]
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail={"code": "rate_limited", "message": RATE_LIMITED})
    q.append(now)
    if len(_hits) > 10_000:  # bound memory: drop idle clients
        for key in [k for k, v in _hits.items() if not v or now - v[-1] > _WINDOW]:
            _hits.pop(key, None)
