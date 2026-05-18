import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import parse_dt
from app.models.models import Issue, Repository, User
from app.services import ai_service, matching_service, scoring_service, skill_service

logger = logging.getLogger(__name__)

DIFFICULTY_TERMS = {
    "beginner": ["beginner", "easy", "simple", "starter", "first", "good first",
                 "good-first", "junior", "entry", "low hanging", "trivial",
                 "newcomer", "novice", "basic", "introductory"],
    "intermediate": ["intermediate", "medium", "moderate", "standard", "normal"],
    "advanced": ["advanced", "complex", "difficult", "expert", "hard", "challenging",
                 "deep", "core", "major", "senior"],
}

LANGUAGE_ALIASES = {
    "python": ["python", "py", "django", "flask", "fastapi"],
    "javascript": ["javascript", "js", "ecmascript", "node", "nodejs", "express"],
    "typescript": ["typescript", "ts", "type script", "deno", "bun"],
    "react": ["react", "reactjs", "react.js", "jsx", "tsx"],
    "rust": ["rust", "rs"],
    "go": ["go", "golang"],
    "ruby": ["ruby", "rb", "rails", "ruby on rails"],
    "java": ["java", "spring", "spring boot", "kotlin"],
    "cpp": ["c++", "cpp", "cplusplus"],
    "c": ["c"],
    "csharp": ["c#", "csharp", "c sharp", "dotnet", ".net"],
    "swift": ["swift", "ios"],
    "kotlin": ["kotlin", "kt", "android"],
    "php": ["php", "laravel"],
    "scala": ["scala"],
    "r": ["r", "rstats"],
    "docker": ["docker", "container", "dockerfile"],
    "kubernetes": ["kubernetes", "k8s"],
    "postgresql": ["postgresql", "postgres", "psql", "sql"],
    "redis": ["redis"],
    "mongodb": ["mongodb", "mongo", "nosql"],
}

LABEL_TERMS = {
    "good_first": ["good first issue", "good-first", "good first", "beginner friendly", "starter"],
    "help_wanted": ["help wanted", "help-wanted"],
}

CATEGORY_KEYWORDS = {
    "frontend": ["frontend", "front-end", "front end", "ui", "ux", "css", "html",
                 "web", "react", "vue", "angular", "svelte"],
    "backend": ["backend", "back-end", "back end", "api", "rest", "server",
                "fastapi", "django", "flask", "express", "spring"],
    "database": ["database", "db", "sql", "nosql", "postgres", "mysql", "redis",
                 "mongodb", "cassandra"],
    "devops": ["devops", "docker", "kubernetes", "ci", "cd", "deploy", "cloud",
               "aws", "gcp", "azure", "terraform"],
    "ai_ml": ["ai", "ml", "machine learning", "deep learning", "nlp", "data science",
              "pytorch", "tensorflow", "llm", "neural"],
    "mobile": ["mobile", "android", "ios", "swift", "kotlin", "flutter", "react native"],
    "systems": ["systems", "embedded", "firmware", "kernel", "driver", "low-level"],
}


@dataclass
class SearchIntent:
    keywords: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    difficulty: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    raw_query: str = ""

    @property
    def is_empty(self) -> bool:
        return not any([self.keywords, self.languages, self.difficulty,
                        self.labels, self.topics, self.categories])


async def parse_natural_query(query: str) -> SearchIntent:
    query_lower = query.lower().strip()
    intent = SearchIntent(raw_query=query)

    if ai_service.AI_ENABLED:
        try:
            ai_result = await ai_service.parse_query_with_ai(query)
            if ai_result:
                intent.languages = ai_result.get("languages", [])
                intent.difficulty = ai_result.get("difficulty") or None
                intent.labels = ai_result.get("labels", [])
                intent.keywords = ai_result.get("keywords", [])[:10]
                cats = ai_result.get("categories", [])
                if isinstance(cats, list):
                    intent.categories = cats
                return intent
        except Exception as e:
            logger.debug("AI query parsing failed, falling back to regex: %s", e)

    # 1. Detect difficulty
    for level, terms in DIFFICULTY_TERMS.items():
        for term in terms:
            if term in query_lower:
                intent.difficulty = level
                break

    # 2. Detect languages and technologies
    matched_langs = set()
    for canon, aliases in LANGUAGE_ALIASES.items():
        for alias in aliases:
            if re.search(rf'\b{re.escape(alias)}\b', query_lower):
                matched_langs.add(canon)
                break
    intent.languages = list(matched_langs)

    # 3. Detect labels
    for canon, terms in LABEL_TERMS.items():
        for term in terms:
            if term in query_lower:
                intent.labels.append(canon)
                break

    # 4. Detect categories
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf'\b{re.escape(kw)}\b', query_lower):
                intent.categories.append(cat)
                break

    # 5. Extract remaining keywords (remove matched terms)
    matched_phrases = set()
    for aliases in LANGUAGE_ALIASES.values():
        matched_phrases.update(aliases)
    for terms in DIFFICULTY_TERMS.values():
        matched_phrases.update(terms)
    for terms in LABEL_TERMS.values():
        matched_phrases.update(terms)
    for keywords in CATEGORY_KEYWORDS.values():
        matched_phrases.update(keywords)

    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#.-]{1,}\b', query_lower)
    remaining = [w for w in words if w not in matched_phrases and len(w) > 2]
    intent.keywords = remaining[:10]

    return intent


def expand_query(intent: SearchIntent) -> str:
    terms = list(intent.keywords)
    for lang in intent.languages:
        canon = lang
        if canon not in terms:
            terms.append(canon)
    if intent.difficulty:
        terms.insert(0, intent.difficulty)
    return " ".join(terms)


async def smart_search(
    db: AsyncSession,
    query: str,
    user: Optional[User] = None,
    language_filter: Optional[str] = None,
    label_filter: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    use_semantic: bool = True,
) -> List[Dict[str, Any]]:
    intent = await parse_natural_query(query)

    if language_filter:
        intent.languages.append(language_filter)
    if label_filter:
        intent.labels.append(label_filter)
    if difficulty:
        intent.difficulty = difficulty

    results = await _db_search(
        db=db, intent=intent,
        limit=limit + offset * 2,
    )

    if len(results) < limit:
        github_results = await _github_fallback(query, intent)
        results.extend(github_results)

    if use_semantic and user and user.skill_vector and results:
        results = await _apply_semantic_scoring(results, intent)

    if user and user.skill_json:
        results = re_rank_results(results, user)

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[offset:offset + limit]


async def _db_search(
    db: AsyncSession,
    intent: SearchIntent,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    conditions = [Issue.state == "open"]

    if intent.languages:
        lang_conditions = [
            Repository.primary_language.ilike(lang)
            for lang in intent.languages
        ]
        conditions.append(or_(*lang_conditions))

    if intent.difficulty:
        if intent.difficulty == "beginner":
            conditions.append(
                or_(
                    Issue.complexity_score < 0.35,
                    Issue.is_good_first_issue.is_(True),
                )
            )
        elif intent.difficulty == "advanced":
            conditions.append(Issue.complexity_score > 0.65)

    if "good_first" in intent.labels:
        conditions.append(Issue.is_good_first_issue.is_(True))
    if "help_wanted" in intent.labels:
        conditions.append(Issue.is_help_wanted.is_(True))

    keyword_conditions = []
    for kw in intent.keywords:
        pattern = f"%{kw}%"
        keyword_conditions.append(
            or_(
                Issue.title.ilike(pattern),
                Issue.body.ilike(pattern),
            )
        )
    if keyword_conditions:
        conditions.append(or_(*keyword_conditions))

    query_stmt = (
        select(Issue, Repository)
        .join(Repository, Issue.repository_id == Repository.id)
        .where(and_(*conditions))
        .order_by(Issue.updated_at.desc().nullslast())
        .limit(limit)
    )

    result = await db.execute(query_stmt)
    rows = result.fetchall()

    scored = []
    for issue, repo in rows:
        issue_skills = issue.required_skills or {}
        keyword_match = _keyword_relevance_score(issue, intent)

        scored.append({
            "issue": issue,
            "repository": repo,
            "match_score": round(keyword_match, 4),
            "matching_skills": matching_service.find_matching_skills({}, issue_skills),
            "why_matched": _generate_why(intent, keyword_match, {}),
        })

    return scored


async def _github_fallback(
    query: str,
    intent: SearchIntent,
    per_page: int = 30,
) -> List[Dict[str, Any]]:
    from app.services import github_service
    try:
        results = await github_service.search_issues_free_text(
            query=query, per_page=per_page
        )
        items = results.get("items", [])
        parsed = []
        for item in items:
            repo_data = item.get("repository") or {}
            parsed.append({
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
                "why_matched": f"GitHub result for: {intent.raw_query or query}",
            })
        return parsed
    except Exception as e:
        logger.warning("GitHub fallback search failed: %s", e)
        return []


def _keyword_relevance_score(issue: Issue, intent: SearchIntent) -> float:
    text = f"{issue.title or ''} {issue.body or ''}".lower()
    label_text = " ".join(issue.labels or []).lower()
    combined = f"{text} {label_text}"

    score = 0.0
    total_weight = 0.0

    for kw in intent.keywords:
        if kw in combined:
            score += 1.0
        total_weight += 1.0

    for lang in intent.languages:
        if lang in combined:
            score += 1.5
        total_weight += 1.5

    if intent.difficulty and intent.difficulty in combined:
        score += 0.5
    total_weight += 0.5 if intent.difficulty else 0

    return score / total_weight if total_weight > 0 else 0.3


async def _apply_semantic_scoring(
    results: List[Dict[str, Any]],
    intent: SearchIntent,
) -> List[Dict[str, Any]]:
    query_vector = await _intent_to_vector(intent)

    for r in results:
        issue = r["issue"]
        if issue.skill_vector and query_vector:
            vec_sim = matching_service.cosine_similarity(query_vector, issue.skill_vector)
            r["match_score"] = round(r["match_score"] * 0.6 + vec_sim * 0.4, 4)
            if vec_sim > 0.5:
                r["why_matched"] = f"Semantic match (similarity: {vec_sim:.2f})"

    return results


async def _intent_to_vector(intent: SearchIntent) -> List[float]:
    title = expand_query(intent)
    body = " ".join(
        intent.keywords + intent.languages +
        ([intent.difficulty] if intent.difficulty else []) +
        intent.categories
    )
    labels = list(set(intent.labels))
    return await skill_service.issue_text_to_vector(title, body, labels)


def re_rank_results(
    results: List[Dict[str, Any]],
    user: User,
) -> List[Dict[str, Any]]:
    user_skills = user.skill_json or {}
    user_vector = user.skill_vector

    for r in results:
        issue = r["issue"]
        repo = r["repository"]

        if user_vector is not None and issue.skill_vector is not None:
            skill_sim = matching_service.cosine_similarity(user_vector, issue.skill_vector)
        else:
            skill_sim = 0.0

        repo_activity = scoring_service.compute_repo_activity_score(repo)
        freshness = scoring_service.compute_freshness_score(issue)
        issue_skills = issue.required_skills or {}
        interest_match = scoring_service.compute_interest_match(user_skills, issue_skills)
        popularity = scoring_service.compute_popularity_score(issue, repo)

        personal_score = scoring_service.compute_final_score(
            skill_similarity=skill_sim,
            repo_activity=repo_activity,
            freshness=freshness,
            interest_match=interest_match,
            popularity=popularity,
        )

        original = r.get("match_score", 0.5)
        r["match_score"] = round(original * 0.4 + personal_score * 0.6, 4)

        matching_skills = matching_service.find_matching_skills(user_skills, issue_skills)
        r["matching_skills"] = matching_skills
        r["why_matched"] = scoring_service.explain_score(
            skill_similarity=skill_sim,
            repo_activity=repo_activity,
            freshness=freshness,
            interest_match=interest_match,
            popularity=popularity,
            matching_skills=matching_skills,
        )

    return results


def _generate_why(
    intent: SearchIntent,
    score: float,
    extra: Dict[str, Any],
) -> str:
    parts = []
    if intent.languages:
        parts.append(f"matches {', '.join(intent.languages[:3])}")
    if intent.difficulty:
        parts.append(f"{intent.difficulty} level")
    if intent.labels:
        parts.append(intent.labels[0].replace("_", " "))
    if intent.keywords:
        parts.append(f"keyword: {', '.join(intent.keywords[:3])}")
    if parts:
        return "Found: " + ", ".join(parts)
    return "Matched your search query"


async def get_suggestions(
    db: AsyncSession,
    prefix: str,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    prefix_lower = prefix.lower().strip()
    if len(prefix_lower) < 2:
        return []

    result = await db.execute(
        select(Repository.primary_language)
        .where(
            and_(
                Repository.primary_language.isnot(None),
                Repository.primary_language.ilike(f"{prefix_lower}%"),
            )
        )
        .distinct()
        .limit(limit)
    )
    languages = [row[0] for row in result.fetchall() if row[0]]

    if languages:
        from sqlalchemy import func as sa_func
        count_result = await db.execute(
            select(
                Repository.primary_language,
                sa_func.count(Issue.id),
            )
            .join(Issue, Issue.repository_id == Repository.id)
            .where(
                and_(
                    Issue.state == "open",
                    Repository.primary_language.in_(languages),
                )
            )
            .group_by(Repository.primary_language)
        )
        count_map = {row[0]: row[1] for row in count_result.fetchall()}
    else:
        count_map = {}

    suggestions = [
        {
            "type": "language",
            "text": lang,
            "description": f"{count_map.get(lang, 0)} open issues",
        }
        for lang in languages
    ]

    return suggestions[:limit]
