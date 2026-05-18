import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.core.database import get_db
from app.core.ratelimit import limiter
from app.models.models import Issue, Repository, User
from app.routes.auth import get_current_user
from app.schemas.schemas import (
    ContributorMatch,
    IssuePublic,
    MaintainerOverview,
    MaintainerRepo,
    MaintainerRepoDetail,
    RepositoryPublic,
)
from app.services import github_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintainer", tags=["maintainer"])


@router.get("/overview", response_model=MaintainerOverview)
@limiter.limit("20/minute")
async def get_maintainer_overview(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get an overview of all repos the current user maintains on GitHub
    that are indexed in the system, with aggregate issue stats.
    Rate-limited to 20/min. Cached 5 minutes."""
    user = current_user

    cache_key = f"maintainer:overview:{user.id}"
    cached = await cache_get(cache_key)
    if cached:
        return MaintainerOverview(**cached)

    repos_data = await github_service.fetch_user_repos(
        user.github_username.lower()
    )
    if not repos_data:
        return MaintainerOverview(
            total_repos=0, total_open_issues=0,
            total_good_first_issues=0, total_help_wanted_issues=0,
            total_potential_contributors=0, repos=[],
        )

    repo_full_names = [r["full_name"] for r in repos_data if not r.get("fork") and not r.get("archived")]

    result = await db.execute(
        select(Repository).where(Repository.full_name.in_(repo_full_names))
    )
    indexed_repos = {r.full_name: r for r in result.scalars().all()}

    maintainer_repos = []
    for rd in repos_data:
        full_name = rd["full_name"]
        if full_name not in indexed_repos:
            continue

        db_repo = indexed_repos[full_name]

        issues_result = await db.execute(
            select(
                func.count(Issue.id),
                func.sum(func.cast(Issue.is_good_first_issue, func.Integer())),
                func.sum(func.cast(Issue.is_help_wanted, func.Integer())),
                func.avg(Issue.complexity_score),
            ).where(
                and_(
                    Issue.repository_id == db_repo.id,
                    Issue.state == "open",
                )
            )
        )
        row = issues_result.one()
        total_issues = row[0] or 0
        gfi_count = row[1] or 0
        hw_count = row[2] or 0
        avg_complexity = float(row[3] or 0.0)

        maintainer_repos.append(
            MaintainerRepo(
                id=db_repo.id,
                full_name=db_repo.full_name,
                name=db_repo.name,
                description=db_repo.description,
                owner_login=db_repo.owner_login,
                html_url=db_repo.html_url,
                stars=db_repo.stars,
                forks=db_repo.forks,
                primary_language=db_repo.primary_language,
                open_issues_count=db_repo.open_issues_count,
                total_issues=total_issues,
                good_first_issues=gfi_count,
                help_wanted_issues=hw_count,
                avg_complexity=avg_complexity,
            )
        )

    total_open = sum(r.total_issues for r in maintainer_repos)
    total_gfi = sum(r.good_first_issues for r in maintainer_repos)
    total_hw = sum(r.help_wanted_issues for r in maintainer_repos)

    result = MaintainerOverview(
        total_repos=len(maintainer_repos),
        total_open_issues=total_open,
        total_good_first_issues=total_gfi,
        total_help_wanted_issues=total_hw,
        total_potential_contributors=0,
        repos=maintainer_repos,
    )
    await cache_set(cache_key, result.model_dump(), ttl=300)
    return result


@router.get("/repos/{repo_id}", response_model=MaintainerRepoDetail)
@limiter.limit("30/minute")
async def get_maintainer_repo_detail(
    request: Request,
    repo_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed info for a specific repo, including its open issues. Rate-limited to 30/min."""
    user = current_user

    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.owner_login.lower() != user.github_username.lower():
        raise HTTPException(
            status_code=403,
            detail="You do not own this repository",
        )

    issues_result = await db.execute(
        select(Issue).where(
            and_(
                Issue.repository_id == repo.id,
                Issue.state == "open",
            )
        ).order_by(Issue.updated_at.desc().nullslast())
    )
    issues = issues_result.scalars().all()

    total = len(issues)
    gfi_count = sum(1 for i in issues if i.is_good_first_issue)
    hw_count = sum(1 for i in issues if i.is_help_wanted)
    avg_complexity = float(
        sum(i.complexity_score for i in issues) / total if total > 0 else 0.0
    )

    repo_summary = MaintainerRepo(
        id=repo.id,
        full_name=repo.full_name,
        name=repo.name,
        description=repo.description,
        owner_login=repo.owner_login,
        html_url=repo.html_url,
        stars=repo.stars,
        forks=repo.forks,
        primary_language=repo.primary_language,
        open_issues_count=repo.open_issues_count,
        total_issues=total,
        good_first_issues=gfi_count,
        help_wanted_issues=hw_count,
        avg_complexity=avg_complexity,
    )

    issue_public_list = []
    for issue in issues:
        issue_public_list.append(
            IssuePublic(
                id=issue.id,
                github_id=issue.github_id,
                number=issue.number,
                title=issue.title,
                body=issue.body,
                html_url=issue.html_url,
                state=issue.state,
                labels=issue.labels,
                is_good_first_issue=issue.is_good_first_issue,
                is_help_wanted=issue.is_help_wanted,
                required_skills=issue.required_skills,
                complexity_score=issue.complexity_score,
                comments=issue.comments,
                created_at=issue.created_at,
                repository=RepositoryPublic.model_validate(repo),
            )
        )

    return MaintainerRepoDetail(
        repo=repo_summary,
        issues=issue_public_list,
    )


@router.get("/repos/{repo_id}/contributors", response_model=List[ContributorMatch])
@limiter.limit("10/minute")
async def get_suggested_contributors(
    request: Request,
    repo_id: int,
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find users whose skill fingerprints match issues in this repo."""

    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    issues_result = await db.execute(
        select(Issue).where(
            and_(
                Issue.repository_id == repo.id,
                Issue.state == "open",
            )
        ).limit(20)
    )
    repo_issues = issues_result.scalars().all()
    if not repo_issues:
        return []

    all_required_skills = set()
    for issue in repo_issues:
        if issue.required_skills:
            skills = issue.required_skills.get("skills", [])
            if isinstance(skills, list):
                all_required_skills.update(s.lower() for s in skills)

    users_result = await db.execute(
        select(User).where(User.skill_json.isnot(None)).limit(100)
    )
    users = users_result.scalars().all()

    contributors = []
    for other_user in users:
        if not other_user.skill_json:
            continue
        user_skills = other_user.skill_json.get("top_skills", [])
        user_skills_lower = [s.lower() for s in user_skills]

        matched = all_required_skills & set(user_skills_lower)
        if not matched:
            continue

        score = len(matched) / max(len(all_required_skills), 1)
        score = min(score * 1.5, 1.0)

        contributors.append(
            ContributorMatch(
                user_id=other_user.id,
                github_username=other_user.github_username,
                github_avatar_url=other_user.github_avatar_url,
                match_score=round(score, 3),
                matching_skills=list(matched)[:10],
                why_matched=f"Skills match {len(matched)} required skill(s) for issues in {repo.full_name}",
            )
        )

    contributors.sort(key=lambda c: c.match_score, reverse=True)
    return contributors[:limit]
