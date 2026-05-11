import logging
import os
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.database import init_db
from app.routes import auth, github, issues
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import jwt as jose_jwt
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("openissue")

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
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


limiter = Limiter(key_func=rate_limit_key, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OpenIssue API starting up...")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database init failed (tables may already exist): %s", e)
    yield
    logger.info("OpenIssue API shutting down")


app = FastAPI(
    title="OpenIssue API",
    description="Match open-source contributors to issues they can actually solve.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.state.limiter = limiter


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": str(getattr(exc, "retry_after", ""))},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# CORS — allow Next.js frontends
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://open-issue.vercel.app",
    "https://openissue.netlify.app",
]
if production_frontend := os.environ.get("FRONTEND_URL"):
    ALLOWED_ORIGINS.append(production_frontend)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (v1)
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(github.router, prefix=API_PREFIX)
app.include_router(issues.router, prefix=API_PREFIX)


@app.get("/")
async def root():
    return {
        "name": "OpenIssue API",
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
