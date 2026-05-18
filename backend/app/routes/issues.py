import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.core.database import get_db
from app.core.ratelimit import limiter
from app.core.utils import parse_dt
from app.models.models import Issue, Repository, SavedIssue, User
from app.routes.auth import get_current_user, get_optional_current_user
from app.schemas.schemas import (
    IssueMatchResponse,
    IssuePublic,
    MatchedIssue,
    RepositoryPublic,
    SearchResult,
    SmartSearchResult,
    TrendingResult,
)
from app.services import github_service, matching_service, search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("/matches", response_model=IssueMatchResponse)
async def get_matched_issues(
    request: Request,
    current_user: User = Depends(get_current_user),
    language: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    limit: int = Query(30, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get personalized issue matches for the current user. Cached 5 minutes."""
    user = current_user

    cache_key = f"matches:{user.id}:{language or ''}:{label or ''}:{limit}:{offset}"
    cached = await cache_get(cache_key)
    if cached:
        return IssueMatchResponse(**cached)

    matches_raw = await matching_service.get_matched_issues(
        db=db,
        user=user,
        limit=limit,
        offset=offset,
        language_filter=language,
        label_filter=label,
    )

    matches = []
    for m in matches_raw:
        issue = m["issue"]
        repo = m["repository"]
        matches.append(
            MatchedIssue(
                issue=IssuePublic(
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
                    repository=RepositoryPublic(
                        id=repo.id,
                        full_name=repo.full_name,
                        name=repo.name,
                        description=repo.description,
                        owner_login=repo.owner_login,
                        html_url=repo.html_url,
                        stars=repo.stars,
                        primary_language=repo.primary_language,
                        topics=repo.topics,
                    ),
                ),
                match_score=m["match_score"],
                matching_skills=m["matching_skills"],
                why_matched=m["why_matched"],
            )
        )

    from app.schemas.schemas import SkillFingerprint
    user_skills = None
    if user.skill_json:
        try:
            user_skills = SkillFingerprint(**user.skill_json)
        except Exception:
            pass

    response = IssueMatchResponse(
        matches=matches,
        total=len(matches),
        user_skills=user_skills,
    )
    await cache_set(cache_key, response.model_dump(), ttl=300)
    return response


@router.post("/index")
@limiter.limit("3/minute")  # Strict: triggers background worker
async def index_issues(
    request: Request,
    background_tasks: BackgroundTasks,
    languages: List[str] = Query(
        default=["python", "javascript", "typescript", "go", "rust"]
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger background indexing of issues.
    Uses ARQ worker when available, falls back to BackgroundTasks.
    Rate-limited to 3/minute to prevent abuse.
    """
    from app.worker import full_index

    background_tasks.add_task(full_index, None, languages)
    return {
        "message": "Issue indexing started in background",
        "languages": languages,
    }


@router.post("/save/{issue_id}")
@limiter.limit("30/minute")
async def save_issue(
    request: Request,
    issue_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an issue to user's list."""
    user = current_user

    issue_exists = await db.execute(
        select(Issue).where(Issue.id == issue_id)
    )
    if not issue_exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Issue not found")

    existing = await db.execute(
        select(SavedIssue).where(
            SavedIssue.user_id == user.id,
            SavedIssue.issue_id == issue_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Already saved"}

    saved = SavedIssue(user_id=user.id, issue_id=issue_id)
    db.add(saved)
    await db.commit()
    return {"message": "Issue saved"}


@router.get("/saved", response_model=List[IssuePublic])
async def get_saved_issues(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's saved issues."""
    user = current_user

    result = await db.execute(
        select(Issue, Repository)
        .join(Repository, Issue.repository_id == Repository.id)
        .join(SavedIssue, SavedIssue.issue_id == Issue.id)
        .where(SavedIssue.user_id == user.id)
    )
    rows = result.fetchall()

    issues = []
    for issue, repo in rows:
        issues.append(
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
    return issues


@router.get("/search", response_model=SearchResult)
@limiter.limit("30/minute")
async def search_issues(
    request: Request,
    q: str = Query(..., min_length=1, description="Free-text search query"),
    language: Optional[str] = Query(None, description="Filter by language"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty: beginner, intermediate, advanced"),
    label: Optional[str] = Query(None, description="Filter by label: good_first, help_wanted"),
    limit: int = Query(30, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Search indexed issues by keyword with filters. Falls back to GitHub API if local results are sparse. Cached 30 minutes."""
    cache_key = f"search:{q}:{language or ''}:{difficulty or ''}:{label or ''}:{limit}:{offset}"

    cached = await cache_get(cache_key)
    if cached:
        return SearchResult(**cached)

    matches_raw = await matching_service.search_issues_keyword(
        db=db,
        query=q,
        language_filter=language,
        difficulty=difficulty,
        label_filter=label,
        limit=limit,
        offset=offset,
    )

    if len(matches_raw) < 5:
        github_results = await github_service.search_issues_free_text(
            query=q, language=language, per_page=limit
        )
        github_items = github_results.get("items", [])
        existing_ids = {m["issue"].github_id for m in matches_raw}

        for item in github_items:
            if item["id"] in existing_ids:
                continue
            repo_data = item.get("repository") or {}
            matches_raw.append({
                "issue": Issue(
                    github_id=item["id"],
                    number=item["number"],
                    title=item.get("title", ""),
                    body=(item.get("body") or "")[:2000],
                    html_url=item["html_url"],
                    state="open",
                    labels=[lb["name"] for lb in item.get("labels", [])],
                    is_good_first_issue=any("good first" in (lb.get("name", "") or "").lower() for lb in item.get("labels", [])),
                    is_help_wanted=any("help wanted" in (lb.get("name", "") or "").lower() for lb in item.get("labels", [])),
                    comments=item.get("comments", 0),
                    created_at=parse_dt(item.get("created_at")),
                    updated_at=parse_dt(item.get("updated_at")),
                    complexity_score=0.5,
                ),
                "repository": Repository(
                    full_name=repo_data.get("full_name", ""),
                    name=(repo_data.get("full_name") or "").split("/")[-1],
                    owner_login=(repo_data.get("full_name") or "").split("/")[0] if repo_data.get("full_name") else "",
                    html_url=repo_data.get("html_url", ""),
                    stars=repo_data.get("stargazers_count", 0),
                    primary_language=repo_data.get("language"),
                    description=repo_data.get("description"),
                ),
                "match_score": 0.5,
                "matching_skills": [],
                "why_matched": f"GitHub result for: {q}",
            })

    matches = []
    for m in matches_raw:
        issue = m["issue"]
        repo = m["repository"]
        matches.append(
            MatchedIssue(
                issue=IssuePublic(
                    id=getattr(issue, "id", 0),
                    github_id=getattr(issue, "github_id", 0),
                    number=getattr(issue, "number", 0),
                    title=issue.title,
                    body=getattr(issue, "body", None),
                    html_url=issue.html_url,
                    state=getattr(issue, "state", "open"),
                    labels=getattr(issue, "labels", []),
                    is_good_first_issue=getattr(issue, "is_good_first_issue", False),
                    is_help_wanted=getattr(issue, "is_help_wanted", False),
                    required_skills=getattr(issue, "required_skills", None),
                    complexity_score=getattr(issue, "complexity_score", 0.5),
                    comments=getattr(issue, "comments", 0),
                    created_at=getattr(issue, "created_at", None),
                    repository=RepositoryPublic(
                        id=getattr(repo, "id", 0),
                        full_name=repo.full_name,
                        name=getattr(repo, "name", ""),
                        description=getattr(repo, "description", None),
                        owner_login=repo.owner_login,
                        html_url=repo.html_url,
                        stars=getattr(repo, "stars", 0),
                        primary_language=getattr(repo, "primary_language", None),
                        topics=getattr(repo, "topics", None),
                    ),
                ),
                match_score=m["match_score"],
                matching_skills=m["matching_skills"],
                why_matched=m["why_matched"],
            )
        )

    result = SearchResult(matches=matches, total=len(matches), query=q)
    await cache_set(cache_key, result.model_dump(), ttl=1800)
    return result


@router.get("/trending", response_model=TrendingResult)
async def get_trending_issues(
    request: Request,
    language: Optional[str] = Query(None, description="Filter trending by language"),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return trending issues from active repositories. Cached 1 hour."""
    cache_key = f"trending:{language or 'all'}:{limit}"

    cached = await cache_get(cache_key)
    if cached:
        return TrendingResult(**cached)

    trending_repos = await github_service.search_trending_repos(
        language=language, per_page=min(limit, 30)
    )

    if not trending_repos:
        return TrendingResult(matches=[], total=0, language=language)

    matches_raw = []
    for repo_data in trending_repos[:10]:
        full_name = repo_data.get("full_name", "")
        if not full_name:
            continue

        result = await db.execute(
            select(Issue, Repository)
            .join(Repository, Issue.repository_id == Repository.id)
            .where(
                and_(
                    Repository.full_name == full_name,
                    Issue.state == "open",
                    Issue.is_good_first_issue.is_(True),
                )
            )
            .order_by(Issue.updated_at.desc().nullslast())
            .limit(5)
        )
        rows = result.fetchall()

        if rows:
            for issue, repo in rows:
                matches_raw.append({
                    "issue": issue,
                    "repository": repo,
                    "match_score": 0.0,
                    "matching_skills": [],
                    "why_matched": f"Trending repository — {repo_data.get('stargazers_count', 0)} stars, active project",
                })
        else:
            github_issues = await github_service.fetch_issues_for_repo(
                full_name=full_name, labels="good first issue", per_page=3
            )
            for item in github_issues:
                matches_raw.append({
                    "issue": Issue(
                        github_id=item["id"],
                        number=item["number"],
                        title=item.get("title", ""),
                        body=(item.get("body") or "")[:2000],
                        html_url=item["html_url"],
                        state="open",
                        labels=[lb["name"] for lb in item.get("labels", [])],
                        is_good_first_issue=True,
                        is_help_wanted=any("help wanted" in (lb.get("name", "") or "").lower() for lb in item.get("labels", [])),
                        comments=item.get("comments", 0),
                        created_at=parse_dt(item.get("created_at")),
                        updated_at=parse_dt(item.get("updated_at")),
                        complexity_score=0.5,
                    ),
                    "repository": Repository(
                        full_name=full_name,
                        name=full_name.split("/")[-1],
                        owner_login=full_name.split("/")[0],
                        html_url=repo_data.get("html_url", f"https://github.com/{full_name}"),
                        stars=repo_data.get("stargazers_count", 0),
                        primary_language=repo_data.get("language"),
                        description=repo_data.get("description"),
                    ),
                    "match_score": 0.0,
                    "matching_skills": [],
                    "why_matched": f"Trending repository — {repo_data.get('stargazers_count', 0)} stars, active project",
                })

    matches = []
    for m in matches_raw:
        issue = m["issue"]
        repo = m["repository"]
        matches.append(
            MatchedIssue(
                issue=IssuePublic(
                    id=getattr(issue, "id", 0),
                    github_id=getattr(issue, "github_id", 0),
                    number=getattr(issue, "number", 0),
                    title=issue.title,
                    body=getattr(issue, "body", None),
                    html_url=issue.html_url,
                    state=getattr(issue, "state", "open"),
                    labels=getattr(issue, "labels", []),
                    is_good_first_issue=getattr(issue, "is_good_first_issue", False),
                    is_help_wanted=getattr(issue, "is_help_wanted", False),
                    required_skills=getattr(issue, "required_skills", None),
                    complexity_score=getattr(issue, "complexity_score", 0.5),
                    comments=getattr(issue, "comments", 0),
                    created_at=getattr(issue, "created_at", None),
                    repository=RepositoryPublic(
                        id=getattr(repo, "id", 0),
                        full_name=repo.full_name,
                        name=getattr(repo, "name", ""),
                        description=getattr(repo, "description", None),
                        owner_login=repo.owner_login,
                        html_url=repo.html_url,
                        stars=getattr(repo, "stars", 0),
                        primary_language=getattr(repo, "primary_language", None),
                        topics=getattr(repo, "topics", None),
                    ),
                ),
                match_score=m["match_score"],
                matching_skills=m["matching_skills"],
                why_matched=m["why_matched"],
            )
        )

    result = TrendingResult(matches=matches[:limit], total=len(matches[:limit]), language=language)
    await cache_set(cache_key, result.model_dump(), ttl=3600)
    return result


@router.get("/smart-search", response_model=SmartSearchResult)
@limiter.limit("20/minute")  # Expensive: uses AI
async def smart_search_issues(
    request: Request,
    q: str = Query(..., min_length=1, description="Natural language search query"),
    language: Optional[str] = Query(None, description="Filter by language"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    label: Optional[str] = Query(None, description="Filter by label"),
    limit: int = Query(30, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Smart search with natural language understanding + optional personalization. Rate-limited to 20/min. Cached 10 min."""
    user = current_user

    cache_key = f"smart:{q}:{language or ''}:{difficulty or ''}:{label or ''}:{limit}:{offset}:{'auth' if user else 'anon'}"
    cached = await cache_get(cache_key)
    if cached:
        return SmartSearchResult(**cached)

    matches_raw = await search_service.smart_search(
        db=db,
        query=q,
        user=user,
        language_filter=language,
        difficulty=difficulty,
        label_filter=label,
        limit=limit,
        offset=offset,
        use_semantic=True,
    )

    intent = await search_service.parse_natural_query(q)
    matches = []
    for m in matches_raw:
        issue = m["issue"]
        repo = m["repository"]
        matches.append(
            MatchedIssue(
                issue=IssuePublic(
                    id=getattr(issue, "id", 0),
                    github_id=getattr(issue, "github_id", 0),
                    number=getattr(issue, "number", 0),
                    title=issue.title,
                    body=getattr(issue, "body", None),
                    html_url=issue.html_url,
                    state=getattr(issue, "state", "open"),
                    labels=getattr(issue, "labels", []),
                    is_good_first_issue=getattr(issue, "is_good_first_issue", False),
                    is_help_wanted=getattr(issue, "is_help_wanted", False),
                    required_skills=getattr(issue, "required_skills", None),
                    complexity_score=getattr(issue, "complexity_score", 0.5),
                    comments=getattr(issue, "comments", 0),
                    created_at=getattr(issue, "created_at", None),
                    repository=RepositoryPublic(
                        id=getattr(repo, "id", 0),
                        full_name=repo.full_name,
                        name=getattr(repo, "name", ""),
                        description=getattr(repo, "description", None),
                        owner_login=repo.owner_login,
                        html_url=repo.html_url,
                        stars=getattr(repo, "stars", 0),
                        primary_language=getattr(repo, "primary_language", None),
                        topics=getattr(repo, "topics", None),
                    ),
                ),
                match_score=m["match_score"],
                matching_skills=m["matching_skills"],
                why_matched=m["why_matched"],
            )
        )

    result = SmartSearchResult(
        matches=matches,
        total=len(matches),
        query=q,
        intent={
            "keywords": intent.keywords,
            "languages": intent.languages,
            "difficulty": intent.difficulty,
            "labels": intent.labels,
            "categories": intent.categories,
        },
        personalized=user is not None,
    )
    await cache_set(cache_key, result.model_dump(), ttl=600)
    return result


@router.get("/stats")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Platform statistics. Cached 5 minutes."""
    cache_key = "platform:stats"

    cached = await cache_get(cache_key)
    if cached:
        return cached

    user_count = await db.execute(select(func.count(User.id)))
    issue_count = await db.execute(select(func.count(Issue.id)))
    repo_count = await db.execute(select(func.count(Repository.id)))

    result = {
        "total_users": user_count.scalar() or 0,
        "total_issues_indexed": issue_count.scalar() or 0,
        "total_repos_indexed": repo_count.scalar() or 0,
    }
    await cache_set(cache_key, result, ttl=300)
    return result
