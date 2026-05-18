"""
Route-level response caching for expensive endpoints.

Provides a decorator to cache FastAPI endpoint responses with Redis,
handling both JSON-serializable responses and Pydantic models.

Cache keys incorporate request parameters to avoid stale cross-user pollution.

Routes that SHOULD be cached:
  - Public data endpoints (trending, stats, search)
  - Expensive DB query results (matches after initial fetch)
  - GitHub proxy results (user profiles)

Routes that should NOT be cached:
  - Mutations (POST, PUT, DELETE)
  - User-specific personalized data (unless keyed by user)
  - Auth endpoints
"""

import functools
import logging
from typing import Any, Callable, Optional

from app.core.cache import cache_get, cache_get_with_stale, cache_set

logger = logging.getLogger(__name__)

ROUTE_CACHE_PREFIX = "route:"


def cached_response(ttl_seconds: int):
    """
    Decorator for FastAPI route handlers that caches responses.

    The cache key is derived from the function name and its JSON-serializable
    arguments. Use for read-only (GET) endpoints with deterministic output.

    Args:
        ttl_seconds: How long to cache the response

    Usage:
        @router.get("/expensive")
        @cached_response(ttl_seconds=300)
        async def my_expensive_endpoint(...):
            ...
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            import hashlib
            import json

            # Build cache key from function name + serializable kwargs
            try:
                serializable = {
                    k: v for k, v in kwargs.items()
                    if isinstance(v, (str, int, float, bool, type(None)))
                }
                key_suffix = hashlib.md5(
                    json.dumps(serializable, sort_keys=True).encode()
                ).hexdigest()[:16]
            except Exception:
                key_suffix = "fallback"

            cache_key = f"{ROUTE_CACHE_PREFIX}{func.__name__}:{key_suffix}"

            cached = await cache_get(cache_key)
            if cached is not None:
                logger.debug("Route cache HIT: %s", cache_key)
                return cached

            result = await func(*args, **kwargs)

            # Only cache if result has a model_dump method (Pydantic) or is a dict
            if hasattr(result, "model_dump"):
                serialized = result.model_dump()
                await cache_set(cache_key, serialized, ttl=ttl_seconds)
            elif isinstance(result, dict):
                await cache_set(cache_key, result, ttl=ttl_seconds)

            return result
        return wrapper
    return decorator
