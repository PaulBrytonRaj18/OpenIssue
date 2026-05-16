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

    # Database
    DATABASE_URL: str = "postgresql://issuecompass:issuecompass@localhost:5432/issuecompass"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

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
        return errors


@lru_cache()
def get_settings() -> Settings:
    return Settings()
