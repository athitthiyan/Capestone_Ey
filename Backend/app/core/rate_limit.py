"""Minimal fixed-window rate limiter for auth endpoints.

In-process (per-worker) by design - good enough to blunt credential-stuffing
and registration-enumeration bursts from a single client without adding a
Redis round trip to every login attempt. A multi-worker/multi-instance
deployment should front this with a shared limiter (e.g. an API gateway or
Redis-backed limiter); this is a defense-in-depth floor, not the only layer.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 60
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, bucket: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{bucket}:{host}"


def enforce_rate_limit(request: Request, *, bucket: str, max_requests: int) -> None:
    key = _client_key(request, bucket)
    now = time.monotonic()
    window = _hits[key]

    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()

    if len(window) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again shortly.",
        )

    window.append(now)
