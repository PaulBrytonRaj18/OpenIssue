"""
Production Redis cache for IssueCompass.

Features:
  - Connection lifecycle tied to FastAPI lifespan (init/close)
  - Retry with exponential backoff for transient failures
  - Cache stampede protection via probabilistic early expiry
  - Namespace prefixing to avoid key collisions
  - Cache hit/miss metrics for monitoring
  - Graceful degradation when Redis is down
  - Cache latency tracking per operation
  - Request deduplication for in-flight operations
"""

import asyncio
import json
import logging
import random
import time
from collections import defaultdict
from typing import Any, Callable, Optional

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: Optional[aioredis.Redis] = None
_available: bool = False

_hits: int = 0
_misses: int = 0
_cache_latencies: list[float] = []  # rolling window of latencies

# In-flight request deduplication: cache_key -> asyncio.Task
_in_flight: dict[str, asyncio.Task] = {}

PREFIX = settings.REDIS_PREFIX


def _key(key: str) -> str:
    """Apply namespace prefix to a cache key."""
    return f"{PREFIX}{key}"


def _should_early_expire(ttl: float, beta: float = 1.0) -> bool:
    """
    Probabilistic early expiry (aka "fails at 11").
    Returns True with increasing probability as TTL approaches zero.
    Prevents all requests from hitting the DB at once when a key expires.
    """
    if ttl <= 0:
        return True
    p = beta * abs(random.random() - 0.5) * 4 / max(ttl, 1)
    return random.random() < min(p, 0.15)


async def init_redis() -> None:
    """Create the Redis connection pool. Call during app startup."""
    global _redis, _available
    try:
        retry = Retry(ExponentialBackoff(cap=2, base=0.5), retries=3)
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
            retry=retry,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            health_check_interval=30,
        )
        await _redis.ping()
        _available = True
        logger.info("Redis connected: %s", settings.REDIS_URL)
    except Exception as e:
        _available = False
        logger.warning("Redis unavailable, caching disabled: %s", e)


async def close_redis() -> None:
    """Close the Redis connection pool. Call during app shutdown."""
    global _redis, _available
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception as e:
            logger.warning("Redis close error: %s", e)
    _redis = None
    _available = False
    _in_flight.clear()
    logger.info("Redis connection closed")


async def get_redis() -> Optional[aioredis.Redis]:
    """Return the Redis client if available, None otherwise."""
    return _redis if _available else None


def _record_latency(seconds: float) -> None:
    """Track cache operation latency in a rolling window."""
    _cache_latencies.append(seconds)
    if len(_cache_latencies) > 1000:
        _cache_latencies.pop(0)


async def cache_get(key: str) -> Optional[Any]:
    """
    Get a cached value. Returns None on miss or error.
    Includes cache hit/miss tracking and latency monitoring.
    """
    global _hits, _misses
    start = time.monotonic()
    client = await get_redis()
    if client is None:
        _misses += 1
        _record_latency(time.monotonic() - start)
        return None
    try:
        data = await client.get(_key(key))
        _record_latency(time.monotonic() - start)
        if data is None:
            _misses += 1
            return None
        _hits += 1
        return json.loads(data)
    except (ConnectionError, TimeoutError) as e:
        _misses += 1
        _record_latency(time.monotonic() - start)
        return None
    except Exception as e:
        _misses += 1
        _record_latency(time.monotonic() - start)
        return None


async def cache_get_with_stale(
    key: str,
    ttl: int,
    fetcher: Callable[[], Any],
) -> Any:
    """
    Get from cache with probabilistic early expiry.

    If the cached value is near expiry, recompute it in the background
    (stale-while-revalidate). Also deduplicates concurrent requests
    for the same key to avoid stampedes.

    Args:
        key: Cache key
        ttl: TTL in seconds for the cache entry
        fetcher: Async callable that returns the fresh value

    Returns:
        The cached or freshly computed value
    """
    start = time.monotonic()
    client = await get_redis()
    if client is None:
        value = await fetcher()
        _record_latency(time.monotonic() - start)
        return value

    prefixed = _key(key)
    try:
        data = await client.get(prefixed)
        if data is not None:
            remaining = await client.ttl(prefixed)
            global _hits
            _hits += 1
            _record_latency(time.monotonic() - start)
            if _should_early_expire(float(remaining), beta=min(ttl / 60, 5.0)):
                _refresh_in_background(key, ttl, fetcher)
            return json.loads(data)
    except Exception as e:
        _record_latency(time.monotonic() - start)

    global _misses
    _misses += 1
    _record_latency(time.monotonic() - start)

    # Check in-flight dedup before fetching
    existing = _in_flight.get(key)
    if existing is not None:
        logger.debug("Dedup: waiting for in-flight request: %s", key)
        try:
            return await existing
        except Exception:
            pass

    # Execute and cache
    task = asyncio.create_task(fetcher())
    _in_flight[key] = task
    try:
        value = await task
        await cache_set(key, value, ttl=ttl)
        return value
    finally:
        _in_flight.pop(key, None)


def _refresh_in_background(key: str, ttl: int, fetcher: Callable) -> None:
    """Recompute a cached value in background (fire-and-forget)."""
    async def _refresh():
        try:
            value = await fetcher()
            await cache_set(key, value, ttl=ttl)
            logger.debug("Cache refreshed early: %s", key)
        except Exception as e:
            pass

    try:
        loop = asyncio.get_running_loop()
        task = asyncio.ensure_future(_refresh(), loop=loop)
        task.add_done_callback(lambda t: (
            logger.warning("Background refresh %s failed: %s", key, t.exception())
            if t.exception() else None
        ))
    except RuntimeError:
        pass


async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """
    Set a cached value with TTL.
    Returns True if set successfully, False otherwise.
    """
    start = time.monotonic()
    client = await get_redis()
    if client is None:
        _record_latency(time.monotonic() - start)
        return False
    try:
        serialized = json.dumps(value, default=str)
        await client.setex(_key(key), ttl, serialized)
        _record_latency(time.monotonic() - start)
        return True
    except (ConnectionError, TimeoutError) as e:
        _record_latency(time.monotonic() - start)
        return False
    except Exception as e:
        _record_latency(time.monotonic() - start)
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a glob pattern.
    Returns number of keys deleted.
    """
    client = await get_redis()
    if client is None:
        return 0
    try:
        deleted = 0
        cursor = 0
        prefixed_pattern = _key(pattern)
        while True:
            cursor, keys = await client.scan(
                cursor=cursor, match=prefixed_pattern, count=100
            )
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        if deleted > 0:
            logger.info("Cache invalidated %d keys matching %s", deleted, pattern)
        return deleted
    except Exception as e:
        return 0


async def cache_delete(key: str) -> bool:
    """Delete a single cache key. Returns True if key existed."""
    client = await get_redis()
    if client is None:
        return False
    try:
        deleted = await client.delete(_key(key))
        return deleted > 0
    except Exception:
        return False


async def cache_exists(key: str) -> bool:
    """Check if a cache key exists without fetching its value."""
    client = await get_redis()
    if client is None:
        return False
    try:
        return await client.exists(_key(key)) > 0
    except Exception:
        return False


async def cache_ttl(key: str) -> int:
    """Get remaining TTL for a cache key. Returns -1 if no TTL, -2 if missing."""
    client = await get_redis()
    if client is None:
        return -2
    try:
        return await client.ttl(_key(key))
    except Exception:
        return -2


async def cache_ping() -> bool:
    """Check Redis connectivity health."""
    client = await get_redis()
    if client is None:
        return False
    try:
        return await client.ping()
    except Exception:
        return False


async def cache_health() -> dict:
    """Return detailed Redis health information."""
    client = await get_redis()
    if client is None:
        return {"available": False}
    try:
        info = await client.info()
        return {
            "available": True,
            "version": info.get("redis_version", "unknown"),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "total_keys": info.get("db0", {}).get("keys", 0) if "db0" in info else None,
        }
    except Exception:
        return {"available": True, "detail": "info_unavailable"}


def cache_stats() -> dict:
    """Return cache hit/miss metrics and latency for monitoring."""
    total = _hits + _misses
    rate = round(_hits / max(total, 1) * 100, 1)
    avg_latency = 0.0
    p99_latency = 0.0
    if _cache_latencies:
        sorted_lat = sorted(_cache_latencies)
        avg_latency = round(sum(sorted_lat) / len(sorted_lat) * 1000, 2)
        idx = int(len(sorted_lat) * 0.99)
        p99_latency = round(sorted_lat[min(idx, len(sorted_lat) - 1)] * 1000, 2)
    return {
        "available": _available,
        "hits": _hits,
        "misses": _misses,
        "total_requests": total,
        "hit_rate_percent": rate,
        "avg_latency_ms": avg_latency,
        "p99_latency_ms": p99_latency,
        "in_flight_dedup": len(_in_flight),
    }
