from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Issue, Repository, User
from app.services import ai_service, scoring_service


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_matching_skills(
    user_skills: Dict[str, Any],
    issue_skills: Dict[str, Any],
) -> List[str]:
    user_langs = set(user_skills.get("languages", {}).keys())
    user_topics = set(user_skills.get("topics", []))
    user_top = set(user_skills.get("top_skills", []))

    issue_cats = issue_skills.get("categories", {})
    matching = set()
    for cat_skills in issue_cats.values():
        for skill in cat_skills:
            if skill in user_langs or skill in user_topics or skill in user_top:
                matching.add(skill)
    return list(matching)[:5]


async def get_matched_issues(
    db: AsyncSession,
    user: User,
    limit: int = 30,
    offset: int = 0,
    language_filter: Optional[str] = None,
    label_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    user_skill_json = user.skill_json or {}
    user_vector = user.skill_vector

    query = (
        select(Issue, Repository)
        .join(Repository, Issue.repository_id == Repository.id)
        .where(
            and_(
                Issue.state == "open",
                Issue.skill_vector.isnot(None),
            )
        )
    )

    if language_filter:
        query = query.where(Repository.primary_language.ilike(language_filter))

    if label_filter == "good_first":
        query = query.where(Issue.is_good_first_issue.is_(True))
    elif label_filter == "help_wanted":
        query = query.where(Issue.is_help_wanted.is_(True))

    pool_size = min(offset + limit * 3, 500)
    query = query.limit(pool_size)
    result = await db.execute(query)
    rows = result.fetchall()

    if not rows:
        return []

    scored = []
    for issue, repo in rows:
        if user_vector is not None and issue.skill_vector is not None:
            skill_sim = cosine_similarity(user_vector, issue.skill_vector)
        else:
            skill_sim = _keyword_score(user_skill_json, issue)

        repo_activity = scoring_service.compute_repo_activity_score(repo)
        freshness = scoring_service.compute_freshness_score(issue)
        issue_skills = issue.required_skills or {}
        interest_match = scoring_service.compute_interest_match(user_skill_json, issue_skills)
        popularity = scoring_service.compute_popularity_score(issue, repo)

        final_score = scoring_service.compute_final_score(
            skill_similarity=skill_sim,
            repo_activity=repo_activity,
            freshness=freshness,
            interest_match=interest_match,
            popularity=popularity,
        )

        matching_skills = find_matching_skills(user_skill_json, issue_skills)

        ai_explanation = None
        if ai_service.AI_ENABLED and user_skill_json and issue_skills:
            try:
                ai_explanation = await scoring_service.generate_ai_explanation(
                    user_skill_json, issue_skills, final_score
                )
            except Exception:
                pass

        why = ai_explanation or scoring_service.explain_score(
            skill_similarity=skill_sim,
            repo_activity=repo_activity,
            freshness=freshness,
            interest_match=interest_match,
            popularity=popularity,
            matching_skills=matching_skills,
        )

        scored.append({
            "issue": issue,
            "repository": repo,
            "match_score": round(final_score, 4),
            "matching_skills": matching_skills,
            "why_matched": why,
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[offset:offset + limit]


def _keyword_score(user_skills: Dict[str, Any], issue: Issue) -> float:
    user_langs = set(user_skills.get("languages", {}).keys())
    user_topics = set(user_skills.get("topics", []))
    all_user_skills = user_langs | user_topics

    issue_text = f"{issue.title or ''} {issue.body or ''}".lower()
    issue_labels = [lb.lower() for lb in (issue.labels or [])]

    matches = sum(
        1 for skill in all_user_skills
        if skill in issue_text or any(skill in lbl for lbl in issue_labels)
    )

    total = max(len(all_user_skills), 1)
    return min(matches / total, 1.0)


async def search_issues_keyword(
    db: AsyncSession,
    query: str,
    language_filter: Optional[str] = None,
    difficulty: Optional[str] = None,
    label_filter: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conditions = [Issue.state == "open"]

    if query:
        like_pattern = f"%{query}%"
        conditions.append(
            or_(
                Issue.title.ilike(like_pattern),
                Issue.body.ilike(like_pattern),
            )
        )

    if language_filter:
        conditions.append(Repository.primary_language.ilike(language_filter))

    if difficulty == "beginner":
        conditions.append(Issue.complexity_score < 0.35)
    elif difficulty == "intermediate":
        conditions.append(Issue.complexity_score.between(0.35, 0.65))
    elif difficulty == "advanced":
        conditions.append(Issue.complexity_score > 0.65)

    if label_filter == "good_first":
        conditions.append(Issue.is_good_first_issue.is_(True))
    elif label_filter == "help_wanted":
        conditions.append(Issue.is_help_wanted.is_(True))

    query_stmt = (
        select(Issue, Repository)
        .join(Repository, Issue.repository_id == Repository.id)
        .where(and_(*conditions))
        .order_by(Issue.updated_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query_stmt)
    rows = result.fetchall()

    scored = []
    for issue, repo in rows:
        scored.append({
            "issue": issue,
            "repository": repo,
            "match_score": 0.5,
            "matching_skills": [],
            "why_matched": f"Matched your search: {query}" if query else "All open issues",
        })

    return scored
