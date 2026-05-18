"""
GitHub REST API client with Redis-backed caching.

Every external HTTP call to GitHub is automatically cached via Redis,
reducing API consumption and improving response latency.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.cache import cache_get_with_stale
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

HEADERS = {
    "Authorization": f"token {settings.GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Cache key prefixes
_GITHUB_CACHE_PREFIX = "gh:"

# TTLs in seconds based on data freshness
TTL_USER = 3600           # GitHub profile rarely changes
TTL_USER_REPOS = 1800     # Repos change with pushes
TTL_REPO_LANGUAGES = 86400  # Language mix is very stable
TTL_REPO_ISSUES = 600     # Issues change frequently
TTL_SEARCH_GLOBAL = 600   # Search results are time-sensitive
TTL_SEARCH_TEXT = 600
TTL_TRENDING_REPOS = 1800 # Trending changes daily


def _cache_key(*parts: str) -> str:
    return f"{_GITHUB_CACHE_PREFIX}{':'.join(parts)}"


async def _cached_fetch(cache_key: str, ttl: int, fetcher) -> Any:
    """Fetch with stale-while-revalidate cache pattern and dedup."""
    return await cache_get_with_stale(cache_key, ttl, fetcher)


async def fetch_user(username: str) -> Optional[Dict[str, Any]]:
    """Fetch a GitHub user's public profile. Cached 1 hour."""
    key = _cache_key("user", username.lower())

    async def _fetch():
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/users/{username}",
                headers=HEADERS,
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return None

    return await _cached_fetch(key, TTL_USER, _fetch)


async def fetch_user_repos(username: str, per_page: int = 100) -> List[Dict[str, Any]]:
    """Fetch all public repos for a user. Cached 30 minutes."""
    key = _cache_key("repos", username.lower())

    async def _fetch():
        repos = []
        page = 1
        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{settings.GITHUB_API_BASE}/users/{username}/repos",
                    headers=HEADERS,
                    params={
                        "per_page": per_page,
                        "page": page,
                        "sort": "updated",
                        "type": "owner",
                    },
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                repos.extend(data)
                if len(data) < per_page:
                    break
                page += 1
        return repos

    return await _cached_fetch(key, TTL_USER_REPOS, _fetch)


async def fetch_repo_languages(full_name: str) -> Dict[str, int]:
    """Fetch language breakdown for a repo. Cached 24 hours."""
    key = _cache_key("lang", full_name.lower().replace("/", ":"))

    async def _fetch():
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/repos/{full_name}/languages",
                headers=HEADERS,
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return {}

    return await _cached_fetch(key, TTL_REPO_LANGUAGES, _fetch)


async def fetch_issues_for_repo(
    full_name: str,
    labels: str = "good first issue,help wanted",
    state: str = "open",
    per_page: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch issues from a specific repo. Cached 10 minutes."""
    key = _cache_key("issues", full_name.lower().replace("/", ":"), labels, state, str(per_page))

    async def _fetch():
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/repos/{full_name}/issues",
                headers=HEADERS,
                params={
                    "labels": labels,
                    "state": state,
                    "per_page": per_page,
                    "sort": "updated",
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                return [i for i in resp.json() if "pull_request" not in i]
            return []

    return await _cached_fetch(key, TTL_REPO_ISSUES, _fetch)


async def search_issues_global(
    language: Optional[str] = None,
    label: str = "good first issue",
    per_page: int = 50,
    page: int = 1,
) -> Dict[str, Any]:
    """Search GitHub for good first issues globally. Cached 10 minutes."""
    key = _cache_key(
        "search-global",
        hashlib.md5(f"{language or ''}:{label}:{per_page}:{page}".encode()).hexdigest()[:12],
    )

    async def _fetch():
        query = f'label:"{label}" state:open'
        if language:
            query += f" language:{language}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/search/issues",
                headers=HEADERS,
                params={
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"items": [], "total_count": 0}

    return await _cached_fetch(key, TTL_SEARCH_GLOBAL, _fetch)


async def search_issues_free_text(
    query: str,
    language: Optional[str] = None,
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """Search GitHub issues by free text query. Cached 10 minutes."""
    key = _cache_key(
        "search-text",
        hashlib.md5(f"{query.lower()}:{language or ''}:{per_page}:{page}".encode()).hexdigest()[:12],
    )

    async def _fetch():
        q = f'{query} state:open'
        if language:
            q += f" language:{language}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/search/issues",
                headers=HEADERS,
                params={
                    "q": q,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"items": [], "total_count": 0}

    return await _cached_fetch(key, TTL_SEARCH_TEXT, _fetch)


async def search_trending_repos(
    language: Optional[str] = None,
    per_page: int = 30,
) -> List[Dict[str, Any]]:
    """Search for recently active, popular repos. Cached 30 minutes."""
    key = _cache_key("trending", language or "all", str(per_page))

    async def _fetch():
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        query = f"stars:>100 pushed:>{since} fork:false"
        if language:
            query += f" language:{language}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/search/repositories",
                headers=HEADERS,
                params={
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": per_page,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return resp.json().get("items", [])
            return []

    return await _cached_fetch(key, TTL_TRENDING_REPOS, _fetch)
