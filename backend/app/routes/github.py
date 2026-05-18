from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_get_with_stale, cache_set
from app.core.database import get_db
from app.core.ratelimit import limiter
from app.models.models import User
from app.routes.auth import get_current_user
from app.schemas.schemas import SkillFingerprint, UserPublic
from app.services import github_service, skill_service

router = APIRouter(prefix="/github", tags=["github"])


@router.post("/analyze/{username}", response_model=UserPublic)
@limiter.limit("5/minute")  # Strict: triggers AI/Groq
async def analyze_github_profile(
    request: Request,
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch GitHub data for a user, build skill fingerprint, store as vector.
    This is the core skill-building endpoint. Rate-limited to 5/min.
    """
    repos = await github_service.fetch_user_repos(username)
    if not repos and not current_user:
        raise HTTPException(status_code=404, detail="GitHub user not found or no repos")

    fingerprint = await skill_service.build_skill_fingerprint(repos)

    skill_vector = await skill_service.skill_fingerprint_to_vector(fingerprint)

    current_user.skill_json = fingerprint
    current_user.skill_vector = skill_vector
    current_user.skill_last_updated = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(current_user)

    from app.core.cache import cache_delete
    await cache_delete(f"auth:me:{current_user.id}")

    return UserPublic.model_validate(current_user)


@router.get("/user/{username}")
@limiter.limit("30/minute")
async def get_github_user(
    request: Request,
    username: str,
):
    """Proxy GitHub user data (public endpoint). Cached 1 hour."""
    cache_key = f"github:user:{username.lower()}"

    async def _fetch():
        user_data = await github_service.fetch_user(username)
        if not user_data:
            raise HTTPException(status_code=404, detail="GitHub user not found")
        return user_data

    return await cache_get_with_stale(cache_key, 3600, _fetch)


@router.get("/fingerprint", response_model=SkillFingerprint)
async def get_skill_fingerprint(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get current user's skill fingerprint."""
    user = current_user

    if not user.skill_json:
        raise HTTPException(
            status_code=404,
            detail="Skill fingerprint not generated yet. Run /github/analyze first.",
        )

    return SkillFingerprint(**user.skill_json)
