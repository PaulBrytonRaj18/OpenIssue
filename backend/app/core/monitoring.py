"""Request monitoring middleware and structured logging for IssueCompass."""

import logging
import time
from collections import deque
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("issuecompass.http")

_request_count = 0
_request_durations: deque[float] = deque(maxlen=1000)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        global _request_count
        _request_count += 1
        start = time.monotonic()

        response = await call_next(request)

        duration = time.monotonic() - start
        _request_durations.append(duration)

        logger.info(
            "%s %s %d %.3fs",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response


def get_metrics() -> dict:
    """Return basic request metrics."""
    global _request_count
    recent = list(_request_durations)
    avg_duration = 0.0
    if recent:
        avg_duration = sum(recent) / len(recent)
    p99 = 0.0
    if recent:
        sorted_durations = sorted(recent)
        idx = int(len(sorted_durations) * 0.99)
        p99 = sorted_durations[min(idx, len(sorted_durations) - 1)]
    return {
        "total_requests": _request_count,
        "avg_duration_seconds": round(avg_duration, 4),
        "p99_duration_seconds": round(p99, 4),
        "recent_requests": len(recent),
    }


def setup_monitoring(app: FastAPI) -> None:
    """Attach monitoring middleware to the app."""
    app.add_middleware(RequestLogMiddleware)
