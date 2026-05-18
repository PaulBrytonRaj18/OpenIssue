"""ARQ background worker — handles async tasks outside the request cycle.

Run with:  arq app.worker.WorkerSettings
Or via:    python -m app.worker
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from app.core.cache import close_redis, init_redis
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.database import engine as db_engine
from app.core.utils import parse_dt
from app.services import github_service, skill_service

logger = logging.getLogger("issuecompass.worker")

settings = get_settings()


async def startup(ctx):
    logger.info("ARQ worker started")
    await init_redis()


async def shutdown(ctx):
    logger.info("ARQ worker shutting down")
    await close_redis()
    await db_engine.dispose()


async def index_language_issues(ctx, language: str, label: str = "good first issue"):
    """Index issues for a single language+label combination."""
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.models import Issue, Repository

    logger.info("Indexing %s / %s", language, label)

    async with AsyncSessionLocal() as db:
        try:
            result = await github_service.search_issues_global(
                language=language, label=label, per_page=50
            )
            items = result.get("items", [])
            if not items:
                return {"language": language, "label": label, "indexed": 0}

            parsed = []
            for item in items:
                repo_url = item.get("repository_url", "")
                repo_full_name = repo_url.replace("https://api.github.com/repos/", "")
                if not repo_full_name or "/" not in repo_full_name:
                    continue
                repo_data = item.get("repository") or {}
                parsed.append({
                    "item": item,
                    "repo_full_name": repo_full_name,
                    "repo_data": repo_data,
                })

            if not parsed:
                return {"language": language, "label": label, "indexed": 0}

            all_full_names = list({p["repo_full_name"] for p in parsed})

            existing_repos = await db.execute(
                select(Repository).where(Repository.full_name.in_(all_full_names))
            )
            repo_map = {r.full_name: r for r in existing_repos.scalars().all()}

            new_repos = []
            for full_name in all_full_names:
                if full_name in repo_map:
                    continue
                p = next(p2 for p2 in parsed if p2["repo_full_name"] == full_name)
                rd = p["repo_data"]
                import hashlib
                stable_id = int(hashlib.md5(full_name.encode()).hexdigest()[:8], 16)
                new_repos.append({
                    "github_id": rd.get("id", stable_id),
                    "full_name": full_name,
                    "name": full_name.split("/")[-1],
                    "owner_login": full_name.split("/")[0],
                    "html_url": f"https://github.com/{full_name}",
                    "stars": rd.get("stargazers_count", 0),
                    "primary_language": rd.get("language"),
                    "topics": rd.get("topics", []),
                    "description": rd.get("description"),
                })

            if new_repos:
                stmt = pg_insert(Repository).values(new_repos)
                stmt = stmt.on_conflict_do_nothing(index_elements=["full_name"])
                await db.execute(stmt)
                await db.flush()
                result = await db.execute(
                    select(Repository).where(Repository.full_name.in_(all_full_names))
                )
                repo_map = {r.full_name: r for r in result.scalars().all()}

            all_github_ids = list({p["item"]["id"] for p in parsed})
            existing_issues = await db.execute(
                select(Issue).where(Issue.github_id.in_(all_github_ids))
            )
            existing_ids = {r.github_id for r in existing_issues.scalars().all()}

            new_issues = []
            for p in parsed:
                item = p["item"]
                if item["id"] in existing_ids:
                    continue
                repo = repo_map.get(p["repo_full_name"])
                if not repo:
                    continue

                labels = [lb["name"] for lb in item.get("labels", [])]
                title = item.get("title", "")
                body = item.get("body") or ""
                skills_task = skill_service.extract_required_skills(title, body, labels)
                vector_task = skill_service.issue_text_to_vector(title, body, labels)
                required_skills, skill_vector = await asyncio.gather(skills_task, vector_task)
                complexity = required_skills.get("complexity", 0.5)

                new_issues.append({
                    "github_id": item["id"],
                    "number": item["number"],
                    "title": title,
                    "body": body[:2000] if body else None,
                    "html_url": item["html_url"],
                    "state": item.get("state", "open"),
                    "labels": labels,
                    "is_good_first_issue": any("good first" in lb.lower() for lb in labels),
                    "is_help_wanted": any("help wanted" in lb.lower() for lb in labels),
                    "required_skills": required_skills,
                    "skill_vector": skill_vector,
                    "complexity_score": complexity,
                    "comments": item.get("comments", 0),
                    "author_login": item.get("user", {}).get("login"),
                    "created_at": parse_dt(item.get("created_at")),
                    "updated_at": parse_dt(item.get("updated_at")),
                    "repository_id": repo.id,
                })

            if new_issues:
                stmt = pg_insert(Issue).values(new_issues)
                stmt = stmt.on_conflict_do_nothing(index_elements=["github_id"])
                await db.execute(stmt)

            await db.commit()

            logger.info("Indexed %d items for %s / %s", len(new_issues), language, label)
            return {"language": language, "label": label, "indexed": len(new_issues)}

        except Exception as e:
            await db.rollback()
            logger.error("Indexing error %s/%s: %s", language, label, e)
            return {"language": language, "label": label, "indexed": 0, "error": str(e)}


async def full_index(ctx, languages: Optional[list] = None):
    """Index all configured languages with both GFI and HW labels."""
    if languages is None:
        languages = ["python", "javascript", "typescript", "go", "rust"]

    labels = ["good first issue", "help wanted"]
    sem = asyncio.Semaphore(3)
    async def run_with_limit(lang, label):
        async with sem:
            return await index_language_issues(ctx, lang, label)
    tasks = [
        run_with_limit(lang, label)
        for lang in languages
        for label in labels
    ]
    results = await asyncio.gather(*tasks)

    total = sum(r.get("indexed", 0) for r in results)
    logger.info("Full index complete: %d items indexed", total)

    from app.core.cache import cache_delete_pattern
    await cache_delete_pattern("trending:*")

    return {"total_indexed": total, "languages": languages}


async def check_saved_searches(ctx):
    """Periodically check saved searches for new issues."""
    from sqlalchemy import select

    from app.models.models import SavedSearch, User
    from app.services import search_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SavedSearch).where(SavedSearch.notify.is_(True))
        )
        searches = result.scalars().all()

        checked = 0
        for saved in searches:
            user_result = await db.execute(
                select(User).where(User.id == saved.user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            results = await search_service.smart_search(
                db=db, query=saved.query, user=user, limit=10, offset=0,
            )

            new_count = 0
            if saved.last_checked_at:
                new_count = sum(
                    1 for r in results
                    if r["issue"].created_at
                    and r["issue"].created_at > saved.last_checked_at
                )

            saved.last_checked_at = datetime.now(timezone.utc)
            if new_count > 0:
                logger.info(
                    "Saved search #%d '%s' has %d new results",
                    saved.id, saved.name, new_count,
                )
            checked += 1

        await db.commit()
        return {"searches_checked": checked}


def _parse_redis_url(url: str) -> dict:
    """Parse a Redis URL into ARQ-compatible redis_settings dict.

    Handles: redis://localhost:6379, redis://:pass@host:port, rediss://...
    Falls back to sensible defaults on parse failure.
    """
    try:
        parsed = urlparse(url)
        result = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 6379,
        }
        if parsed.password:
            result["password"] = parsed.password
        if parsed.username:
            result["username"] = parsed.username
        # Support Redis SSL
        if parsed.scheme == "rediss":
            result["ssl"] = True
        return result
    except Exception as e:
        logger.warning("Failed to parse REDIS_URL '%s', using defaults: %s", url, e)
        return {"host": "localhost", "port": 6379}


class WorkerSettings:
    redis_settings = _parse_redis_url(settings.REDIS_URL)
    functions = [full_index, index_language_issues, check_saved_searches]
    on_startup = startup
    on_shutdown = shutdown
    keep_result = 3600
    keep_result_failed = 86400
    max_tries = 3
    job_timeout = 300


if __name__ == "__main__":
    from arq import run_worker
    asyncio.run(run_worker(WorkerSettings))
