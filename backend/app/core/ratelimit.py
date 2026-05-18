"""Centralized rate limiting configuration for IssueCompass.

Provides tiered rate limits:
  - DEFAULT: 60 requests/minute for most endpoints
  - STRICT:  10 requests/minute for expensive/AI endpoints
  - AUTH:    5 requests/minute for auth endpoints
"""

import logging

import jwt as jose_jwt
from fastapi import Request
from slowapi import Limiter

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _resolve_storage_uri() -> str:
    """Return a storage URI for rate limiting.

    Uses in-memory storage — the `limits` library used by SlowAPI
    does not gracefully handle Redis connection errors at runtime,
    and switching to `memory://` eliminates that class of outage.

    The Redis-backed cache in `app.core.cache` still handles caching
    independently and degrades gracefully on its own.
    """
    raw = settings.REDIS_URL
    if raw.startswith(("redis://", "rediss://")):
        remote_hosts = ("localhost", "127.0.0.1", "0.0.0.0", "redis")
        host = raw.split("@")[-1].split(":")[0] if "@" in raw else raw.split("://")[1].split(":")[0]
        if host not in remote_hosts:
            logger.info(
                "Rate limiting using in-memory storage (Redis host %s is remote; "
                "the `limits` library does not handle connection errors gracefully). "
                "Redis is still used for caching.",
                host,
            )
            return "memory://"
        return raw
    if raw and not raw.startswith("memory://"):
        logger.warning(
            "REDIS_URL has unsupported scheme for rate limiting "
            "(expected redis:// or rediss://, got %s). "
            "Falling back to in-memory rate limiting.",
            raw.split("://")[0] if "://" in raw else "none",
        )
    return "memory://"


def rate_limit_key(request: Request) -> str:
    """Rate-limit by user ID (from JWT) when authenticated, else by client IP."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = jose_jwt.decode(
                auth_header[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return f"ip:{real_ip}"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    if request.client:
        return f"ip:{request.client.host}"
    return "ip:unknown"


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["60/minute"],
    storage_uri=_resolve_storage_uri(),
)
