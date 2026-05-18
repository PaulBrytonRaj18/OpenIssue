import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.models import Issue, Repository
from app.services import ai_service

logger = logging.getLogger(__name__)

SCORE_WEIGHTS = {
    "skill_match": 0.50,
    "popularity": 0.15,
    "repo_activity": 0.10,
    "interest_match": 0.15,
    "freshness": 0.10,
}


def compute_repo_activity_score(repo: Repository) -> float:
    score = 0.5
    if repo.is_archived:
        return 0.0
    if repo.stars > 10000:
        score += 0.2
    elif repo.stars > 1000:
        score += 0.15
    elif repo.stars > 100:
        score += 0.1
    if repo.last_indexed:
        days_since = (datetime.now(timezone.utc) - repo.last_indexed).days
        if days_since < 7:
            score += 0.15
        elif days_since < 30:
            score += 0.1
    if repo.forks > 100:
        score += 0.1
    return min(score, 1.0)


def compute_freshness_score(issue: Issue) -> float:
    if not issue.created_at:
        return 0.3
    days_old = (datetime.now(timezone.utc) - issue.created_at).days
    if days_old < 7:
        return 1.0
    if days_old < 30:
        return 0.8
    if days_old < 90:
        return 0.5
    return 0.2


def compute_popularity_score(issue: Issue, repo: Repository) -> float:
    score = 0.0
    if issue.comments > 20:
        score += 0.3
    elif issue.comments > 5:
        score += 0.2
    elif issue.comments > 0:
        score += 0.1
    if repo.stars > 10000:
        score += 0.4
    elif repo.stars > 1000:
        score += 0.3
    elif repo.stars > 100:
        score += 0.2
    elif repo.stars > 10:
        score += 0.1
    if repo.forks > 1000:
        score += 0.2
    elif repo.forks > 100:
        score += 0.1
    return min(score, 1.0)


def compute_interest_match(
    user_skills: Dict[str, Any],
    issue_skills: Dict[str, Any],
) -> float:
    user_langs = set(user_skills.get("languages", {}).keys())
    user_topics = set(user_skills.get("topics", []))
    user_cats = set(user_skills.get("categories", {}).keys())
    user_top = set(user_skills.get("top_skills", []))

    issue_cats = set(issue_skills.get("categories", {}).keys())
    issue_labels = set(issue_skills.get("labels", []))

    if not user_langs and not user_topics:
        return 0.3

    combined_user = user_langs | user_topics | user_cats | user_top
    combined_issue = issue_cats | issue_labels

    if not combined_issue:
        return 0.3

    matches = len(combined_user & combined_issue)
    total = max(len(combined_user), 1)
    return min(matches / total, 1.0)


def compute_final_score(
    skill_similarity: float,
    repo_activity: float,
    freshness: float,
    interest_match: float,
    popularity: float,
) -> float:
    return (
        SCORE_WEIGHTS["skill_match"] * skill_similarity
        + SCORE_WEIGHTS["repo_activity"] * repo_activity
        + SCORE_WEIGHTS["freshness"] * freshness
        + SCORE_WEIGHTS["interest_match"] * interest_match
        + SCORE_WEIGHTS["popularity"] * popularity
    )


async def generate_ai_explanation(
    user_skills: Dict[str, Any],
    issue_skills: Dict[str, Any],
    match_score: float,
) -> Optional[str]:
    """Try to generate an AI-powered explanation, returns None if unavailable."""
    if not ai_service.AI_ENABLED:
        return None
    try:
        return await ai_service.generate_match_explanation(
            user_skills, issue_skills, match_score
        )
    except Exception as e:
        logger.debug("AI explanation failed: %s", e)
        return None


def explain_score(
    skill_similarity: float,
    repo_activity: float,
    freshness: float,
    interest_match: float,
    popularity: float,
    matching_skills: List[str],
) -> str:
    parts = []

    final = compute_final_score(
        skill_similarity=skill_similarity,
        repo_activity=repo_activity,
        freshness=freshness,
        interest_match=interest_match,
        popularity=popularity,
    )

    if final > 0.8:
        parts.append("Strong match")
    elif final > 0.5:
        parts.append("Good match")
    else:
        parts.append("Partial match")

    score_pct = round(final * 100)
    parts.append(f"({score_pct}%)")

    if matching_skills:
        skill_str = ", ".join(matching_skills[:3])
        parts.append(f"— your {skill_str} skills align")

    repo_desc = []
    if popularity > 0.7:
        repo_desc.append("highly popular repo")
    elif popularity > 0.4:
        repo_desc.append("popular repo")

    if repo_activity > 0.7:
        repo_desc.append("very active")
    elif repo_activity > 0.4:
        repo_desc.append("active")

    if freshness > 0.7:
        repo_desc.append("recently updated")

    if repo_desc:
        parts.append(f"({', '.join(repo_desc)})")

    return " ".join(parts)
