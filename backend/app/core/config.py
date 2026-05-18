from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ".env"


class Settings(BaseSettings):
    # App
    APP_NAME: str = "IssueCompass"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = ""

    # Metrics
    METRICS_API_KEY: str = ""

    # Cookie
    COOKIE_SECURE: bool = False

    # Database
    DATABASE_URL: str = "postgresql://issuecompass:issuecompass@localhost:5432/issuecompass"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_SOCKET_TIMEOUT: int = 3
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 3
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_PREFIX: str = "ic:"

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_API_BASE: str = "https://api.github.com"
    GITHUB_GRAPHQL_URL: str = "https://api.github.com/graphql"

    # JWT
    SECRET_KEY: str = "change_this_in_production_use_random_string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Groq AI
    GROQ_API_KEY: str = ""
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_EMBED_MODEL: str = ""
    AI_ENABLED: bool = True

    # Jina AI (embeddings)
    JINA_API_KEY: str = ""
    JINA_API_BASE: str = "https://api.jina.ai/v1"
    JINA_EMBED_MODEL: str = "jina-embeddings-v3"
    JINA_EMBED_DIMS: int = 128
    EMBEDDINGS_ENABLED: bool = True

    # ARQ Worker
    WORKER_CONCURRENCY: int = 4
    WORKER_CRON_INDEX_INTERVAL: int = 3600
    WORKER_CRON_SEARCH_CHECK_INTERVAL: int = 1800

    # Matching
    MATCH_SCORE_THRESHOLD: float = 0.3
    MAX_MATCHES_PER_USER: int = 50

    model_config = SettingsConfigDict(env_file=_find_env_file(), extra="ignore")

    def check_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.SECRET_KEY or self.SECRET_KEY == "change_this_in_production_use_random_string":
            errors.append(
                "SECRET_KEY is not set or still default. "
                "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if not self.GITHUB_TOKEN:
            errors.append(
                "GITHUB_TOKEN is required. Create one at https://github.com/settings/tokens "
                "(scopes: public_repo, read:user)"
            )
        if self.EMBEDDINGS_ENABLED and not self.JINA_API_KEY:
            errors.append(
                "JINA_API_KEY is required when EMBEDDINGS_ENABLED=true. "
                "Get one at https://jina.ai/embeddings"
            )
        return errors


@lru_cache()
def get_settings() -> Settings:
    return Settings()
