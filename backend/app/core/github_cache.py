"""
GitHub API response caching layer.

Wraps github_service functions with Redis-backed TTL caching to:
  - Reduce GitHub API consumption (5000 req/hr limit)
  - Speed up repeated lookups (user profiles, repos, searches)
  - Gracefully degrade when Redis or GitHub is unavailable

Cache TTLs are chosen based on data freshness requirements:
  - User profile: 1 hour (infrequently changes)
  - User repos: 30 minutes (changes with new pushes)
  - Repo languages: 24 hours (very stable)
  - Issue searches: 10 minutes (moderately dynamic)
  - Trending repos: 30 minutes (daily-ish cadence)
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.cache import cache_get, cache_get_with_stale, cache_set

logger = logging.getLogger(__name__)

GITHUB_CACHE_PREFIX = "gh:"

# TTLs in seconds
TTL_USER = 3600
TTL_USER_REPOS = 1800
TTL_REPO_LANGUAGES = 86400
TTL_REPO_ISSUES = 600
TTL_SEARCH_GLOBAL = 600
TTL_SEARCH_TEXT = 600
TTL_TRENDING_REPOS = 1800


def _gh_key(*parts: str) -> str:
    return f"{GITHUB_CACHE_PREFIX}{':'.join(parts)}"


async def cached_fetch_user(username: str, fetcher) -> Optional[Dict[str, Any]]:
    """Cache wrapper around github_service.fetch_user()."""
    key = _gh_key("user", username.lower())

    async def _fetch():
        result = await fetcher(username)
        return result

    return await cache_get_with_stale(key, TTL_USER, _fetch)


async def cached_fetch_user_repos(username: str, fetcher) -> List[Dict[str, Any]]:
    """Cache wrapper around github_service.fetch_user_repos()."""
    key = _gh_key("repos", username.lower())

    async def _fetch():
        result = await fetcher(username)
        return result or []

    return await cache_get_with_stale(key, TTL_USER_REPOS, _fetch)


async def cached_fetch_repo_languages(full_name: str, fetcher) -> Dict[str, int]:
    """Cache wrapper around github_service.fetch_repo_languages()."""
    key = _gh_key("lang", full_name.lower().replace("/", ":"))

    async def _fetch():
        result = await fetcher(full_name)
        return result or {}

    return await cache_get_with_stale(key, TTL_REPO_LANGUAGES, _fetch)


async def cached_fetch_issues_for_repo(
    full_name: str,
    labels: str,
    state: str,
    per_page: int,
    fetcher,
) -> List[Dict[str, Any]]:
    """Cache wrapper around github_service.fetch_issues_for_repo()."""
    key = _gh_key("issues", full_name.lower().replace("/", ":"), labels, state, str(per_page))

    async def _fetch():
        result = await fetcher(full_name, labels, state, per_page)
        return result or []

    return await cache_get_with_stale(key, TTL_REPO_ISSUES, _fetch)


async def cached_search_issues_global(
    language: Optional[str],
    label: str,
    per_page: int,
    page: int,
    fetcher,
) -> Dict[str, Any]:
    """Cache wrapper around github_service.search_issues_global()."""
    key = _gh_key(
        "search-global",
        hashlib.md5(f"{language or ''}:{label}:{per_page}:{page}".encode()).hexdigest()[:12],
    )

    async def _fetch():
        result = await fetcher(language, label, per_page, page)
        return result or {"items": [], "total_count": 0}

    return await cache_get_with_stale(key, TTL_SEARCH_GLOBAL, _fetch)


async def cached_search_issues_free_text(
    query: str,
    language: Optional[str],
    per_page: int,
    page: int,
    fetcher,
) -> Dict[str, Any]:
    """Cache wrapper around github_service.search_issues_free_text()."""
    key = _gh_key(
        "search-text",
        hashlib.md5(f"{query.lower()}:{language or ''}:{per_page}:{page}".encode()).hexdigest()[:12],
    )

    async def _fetch():
        result = await fetcher(query, language, per_page, page)
        return result or {"items": [], "total_count": 0}

    return await cache_get_with_stale(key, TTL_SEARCH_TEXT, _fetch)


async def cached_search_trending_repos(
    language: Optional[str],
    per_page: int,
    fetcher,
) -> List[Dict[str, Any]]:
    """Cache wrapper around github_service.search_trending_repos()."""
    key = _gh_key("trending", language or "all", str(per_page))

    async def _fetch():
        result = await fetcher(language, per_page)
        return result or []

    return await cache_get_with_stale(key, TTL_TRENDING_REPOS, _fetch)


def get_github_cache_metrics() -> dict:
    """Return GitHub cache-specific metrics for monitoring."""
    from app.core.cache import cache_stats
    stats = cache_stats()
    return {
        "prefix": GITHUB_CACHE_PREFIX,
        "ttl_user": TTL_USER,
        "ttl_repos": TTL_USER_REPOS,
        "ttl_languages": TTL_REPO_LANGUAGES,
        "ttl_issues": TTL_REPO_ISSUES,
        "ttl_search_global": TTL_SEARCH_GLOBAL,
        "ttl_search_text": TTL_SEARCH_TEXT,
        "ttl_trending": TTL_TRENDING_REPOS,
        "global_stats": stats,
    }
