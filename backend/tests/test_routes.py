"""Route integration tests with mocked database."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.database import get_db
from app.models.models import User
from app.routes.auth import create_access_token
from fastapi.testclient import TestClient


def _make_mock_user(user_id: int = 1) -> MagicMock:
    """Create a mock User instance that can pass Pydantic validation."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.github_id = 12345
    user.github_username = "testuser"
    user.github_avatar_url = "https://avatars.githubusercontent.com/u/12345"
    user.github_name = "Test User"
    user.github_bio = "A test user"
    user.github_location = None
    user.github_blog = None
    user.email = "test@example.com"
    user.public_repos = 10
    user.followers = 5
    user.skill_json = None
    user.skill_vector = None
    user.skill_last_updated = None
    user.created_at = datetime(2025, 1, 1)
    user.last_login = None
    user.saved_issues = []
    return user


def _make_mock_session():
    """Create a mock async session."""
    session = AsyncMock()

    async def execute_side_effect(*args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_mock_user()
        result.scalar.return_value = 0
        result.fetchall.return_value = []
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.add = MagicMock()
    session.commit = AsyncMock(return_value=None)
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 1) or setattr(obj, "created_at", datetime(2025, 1, 1)))
    session.close = AsyncMock()
    return session


@pytest.fixture
def client():
    """TestClient with mocked DB init and overridden DB dependency."""
    mock_session = _make_mock_session()

    async def override_get_db():
        yield mock_session

    with patch("app.core.database.init_db", return_value=None):
        from main import app

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            yield c

        app.dependency_overrides.clear()


class TestHealthEndpoints:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "IssueCompass API"
        assert data["status"] == "running"

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAuthEndpoints:
    def test_github_callback_returns_token(self, client):
        payload = {
            "github_id": 12345,
            "github_username": "testuser",
            "github_avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "github_name": "Test User",
            "github_bio": "A test user",
            "email": "test@example.com",
            "public_repos": 10,
            "followers": 5,
        }
        resp = client.post("/api/v1/auth/github/callback", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_get_me_without_token_returns_422(self, client):
        """Missing required Authorization header => 422, not 401."""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 422

    def test_get_me_with_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp.status_code == 401

    def test_get_me_with_valid_token(self, client):
        token = create_access_token({"sub": "1"})
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text


class TestIssuesEndpoints:
    def test_get_matches_without_token_returns_422(self, client):
        resp = client.get("/api/v1/issues/matches")
        assert resp.status_code == 422

    def test_stats(self, client):
        resp = client.get("/api/v1/issues/stats")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_users" in data
        assert "total_issues_indexed" in data
        assert "total_repos_indexed" in data


class TestGitHubEndpoints:
    def test_analyze_without_token_returns_422(self, client):
        resp = client.post("/api/v1/github/analyze/testuser")
        assert resp.status_code == 422

    @patch("app.routes.github.github_service.fetch_user_repos")
    def test_analyze_profile(self, mock_fetch_repos, client):
        mock_fetch_repos.return_value = [
            {
                "name": "my-project",
                "language": "Python",
                "topics": ["api", "web"],
                "stargazers_count": 10,
                "fork": False,
            },
        ]
        token = create_access_token({"sub": "1"})
        resp = client.post(
            "/api/v1/github/analyze/testuser",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text

    def test_get_fingerprint_without_token_returns_422(self, client):
        resp = client.get("/api/v1/github/fingerprint")
        assert resp.status_code == 422


class TestCORSMiddleware:
    def test_cors_headers(self, client):
        resp = client.options(
            "/api/v1/auth/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
