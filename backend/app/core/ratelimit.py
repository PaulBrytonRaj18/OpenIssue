"""Centralized rate limiting configuration for IssueCompass.

Provides tiered rate limits:
  - DEFAULT: 60 requests/minute for most endpoints
  - STRICT:  10 requests/minute for expensive/AI endpoints
  - AUTH:    5 requests/minute for auth endpoints
"""

import jwt as jose_jwt
from fastapi import Request
from slowapi import Limiter

from app.core.config import get_settings

settings = get_settings()


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
    storage_uri=settings.REDIS_URL,
)
