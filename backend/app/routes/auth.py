import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_delete, cache_get, cache_set
from app.core.config import get_settings
from app.core.database import get_db
from app.core.ratelimit import limiter
from app.models.models import User
from app.schemas.schemas import GitHubUserData, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

TOKEN_COOKIE_NAME = "ic_token"


class AuthStateResponse(BaseModel):
    state: str


def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get(TOKEN_COOKIE_NAME)


def _set_token_cookie(response: Response, token: str) -> None:
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )


def _unset_token_cookie(response: Response) -> None:
    response.delete_cookie(
        key=TOKEN_COOKIE_NAME,
        path="/",
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(request)
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_optional_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    token = _extract_token(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
    except jwt.PyJWTError:
        return None
    result = await db.execute(select(User).where(User.id == int(user_id)))
    return result.scalar_one_or_none()


@router.get("/state", response_model=AuthStateResponse)
@limiter.limit("30/minute")
async def get_auth_state(request: Request):
    """Generate a short-lived signed state token for OAuth CSRF protection."""
    state_data = {
        "purpose": "auth_state",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": secrets.token_urlsafe(16),
    }
    state = jwt.encode(state_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return AuthStateResponse(state=state)


@router.post("/github/callback", response_model=TokenResponse)
@limiter.limit("10/minute")
async def github_callback(
    request: Request,
    github_data: GitHubUserData,
    x_auth_state: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the Next.js frontend after GitHub OAuth completes.
    Creates or updates the user, returns a JWT.
    """
    if x_auth_state:
        try:
            state_payload = jwt.decode(
                x_auth_state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            if state_payload.get("purpose") != "auth_state":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid auth state",
                )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired auth state. Please sign in again.",
            )

    result = await db.execute(
        select(User).where(User.github_id == github_data.github_id)
    )
    user = result.scalar_one_or_none()

    if user:
        user.github_avatar_url = github_data.github_avatar_url
        user.github_name = github_data.github_name
        user.github_bio = github_data.github_bio
        user.public_repos = github_data.public_repos
        user.followers = github_data.followers
        user.last_login = datetime.now(timezone.utc)
    else:
        user = User(
            github_id=github_data.github_id,
            github_username=github_data.github_username,
            github_avatar_url=github_data.github_avatar_url,
            github_name=github_data.github_name,
            github_bio=github_data.github_bio,
            email=github_data.email,
            public_repos=github_data.public_repos,
            followers=github_data.followers,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    await cache_delete(f"auth:me:{user.id}")

    access_token = create_access_token({"sub": str(user.id)})

    resp = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublic.model_validate(user),
    )
    response = Response(
        content=resp.model_dump_json(),
        media_type="application/json",
        status_code=200,
    )
    _set_token_cookie(response, access_token)
    return response


@router.get("/me", response_model=UserPublic)
@limiter.limit("30/minute")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile. Cached for 30 seconds."""
    user = current_user
    cache_key = f"auth:me:{user.id}"

    cached = await cache_get(cache_key)
    if cached:
        return UserPublic(**cached)

    result = UserPublic.model_validate(user)
    await cache_set(cache_key, result.model_dump(), ttl=30)
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token. Returns a new JWT."""
    current_user.last_login = datetime.now(timezone.utc)
    await db.commit()
    new_token = create_access_token({"sub": str(current_user.id)})

    await cache_delete(f"auth:me:{current_user.id}")

    resp = TokenResponse(
        access_token=new_token,
        token_type="bearer",
        user=UserPublic.model_validate(current_user),
    )
    response = Response(
        content=resp.model_dump_json(),
        media_type="application/json",
        status_code=200,
    )
    _set_token_cookie(response, new_token)
    return response
