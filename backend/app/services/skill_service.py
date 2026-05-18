import hashlib
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from app.services import ai_service
from app.services.github_service import fetch_user_repos

logger = logging.getLogger(__name__)


def _stable_hash(text: str, modulus: int) -> int:
    """Deterministic stable hash for consistent vector positions."""
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16) % modulus


SKILL_CATEGORIES = {
    "frontend": [
        "javascript", "typescript", "react", "vue", "angular", "svelte",
        "nextjs", "nuxtjs", "html", "css", "tailwind", "sass", "webpack",
        "vite", "redux", "graphql", "frontend",
    ],
    "backend": [
        "python", "fastapi", "django", "flask", "nodejs", "express",
        "java", "spring", "golang", "rust", "ruby", "rails", "php",
        "laravel", "dotnet", "csharp", "kotlin", "scala", "backend",
        "rest-api", "microservices",
    ],
    "database": [
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "sqlite", "database", "sql", "nosql", "cassandra", "firebase",
        "supabase", "prisma", "sqlalchemy", "orm",
    ],
    "devops": [
        "docker", "kubernetes", "terraform", "ansible", "jenkins",
        "github-actions", "ci-cd", "aws", "gcp", "azure", "linux",
        "nginx", "devops", "infrastructure", "cloud",
    ],
    "ai_ml": [
        "python", "pytorch", "tensorflow", "keras", "scikit-learn",
        "machine-learning", "deep-learning", "nlp", "computer-vision",
        "jupyter", "pandas", "numpy", "transformers", "llm", "ai",
        "data-science",
    ],
    "mobile": [
        "swift", "kotlin", "react-native", "flutter", "dart", "android",
        "ios", "mobile",
    ],
    "systems": [
        "rust", "c", "cpp", "c++", "assembly", "embedded", "firmware",
        "systems", "low-level",
    ],
}

SKILL_VECTOR_DIMS = 128


async def build_skill_fingerprint(
    repos: List[Dict[str, Any]],
    languages_map: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    """
    Analyze repos to produce a structured skill fingerprint.
    Uses AI (Groq) when available, falls back to regex-based analysis.
    """
    # Try AI-powered analysis first
    if ai_service.AI_ENABLED:
        try:
            ai_fingerprint = await ai_service.analyze_skills_with_ai(repos)
            if ai_fingerprint:
                return _merge_ai_fingerprint(ai_fingerprint, repos, languages_map)
        except Exception as e:
            logger.debug("AI skill analysis failed, falling back to regex: %s", e)

    return _build_fingerprint_regex(repos, languages_map)


def _merge_ai_fingerprint(
    ai_result: Dict[str, Any],
    repos: List[Dict[str, Any]],
    languages_map: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    """Merge AI analysis with computed stats for a richer fingerprint."""
    total_repos = len([r for r in repos if not r.get("fork")])
    total_stars = sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork"))

    lang_totals = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        lang = repo.get("language")
        if lang:
            lang_lower = lang.lower()
            lang_totals[lang_lower] = lang_totals.get(lang_lower, 0) + 1

    if languages_map:
        for repo_langs in languages_map.values():
            for lang, bytes_count in repo_langs.items():
                lang_lower = lang.lower()
                lang_totals[lang_lower] = lang_totals.get(lang_lower, 0) + max(1, bytes_count // 10000)

    total_lang_weight = sum(lang_totals.values()) or 1
    languages_normalized = {
        lang: round(count / total_lang_weight, 3)
        for lang, count in sorted(lang_totals.items(), key=lambda x: -x[1])
    }

    top_skills = ai_result.get("top_skills", [])
    if not top_skills:
        all_skill_scores = {**lang_totals}
        topic_counts: Dict[str, int] = {}
        for repo in repos:
            if repo.get("fork"):
                continue
            for topic in repo.get("topics", []) or []:
                topic_counts[topic.lower()] = topic_counts.get(topic.lower(), 0) + 1
        all_skill_scores.update(topic_counts)
        top_skills = [s for s, _ in sorted(all_skill_scores.items(), key=lambda x: -x[1])][:10]

    categories = ai_result.get("categories", {})
    if not categories:
        all_skills = set(lang_totals.keys())
        for cat, keywords in SKILL_CATEGORIES.items():
            matched = [s for s in all_skills if any(kw in s for kw in keywords)]
            if matched:
                categories[cat] = list(set(matched))[:10]

    experience_level = ai_result.get("experience_level", "intermediate")
    if total_repos < 5 and experience_level == "intermediate":
        experience_level = "beginner"

    return {
        "languages": ai_result.get("languages", languages_normalized),
        "topics": sorted(set(
            ai_result.get("categories", {}).get("frontend", [])
            + ai_result.get("categories", {}).get("backend", [])
            + ai_result.get("categories", {}).get("ai_ml", [])
        ))[:20] if ai_result.get("categories") else [t for t, _ in sorted(lang_totals.items(), key=lambda x: -x[1])][:20],
        "categories": categories,
        "experience_level": experience_level,
        "top_skills": top_skills,
        "total_repos": total_repos,
        "total_stars_received": total_stars,
    }


def _build_fingerprint_regex(
    repos: List[Dict[str, Any]],
    languages_map: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    """Regex-based fallback skill fingerprint builder."""
    lang_totals: Dict[str, int] = {}
    topic_counts: Dict[str, int] = {}
    total_stars = 0

    for repo in repos:
        if repo.get("fork"):
            continue
        lang = repo.get("language")
        if lang:
            lang_lower = lang.lower()
            lang_totals[lang_lower] = lang_totals.get(lang_lower, 0) + 1
        for topic in repo.get("topics", []) or []:
            topic_lower = topic.lower()
            topic_counts[topic_lower] = topic_counts.get(topic_lower, 0) + 1
        total_stars += repo.get("stargazers_count", 0)

    if languages_map:
        for repo_langs in languages_map.values():
            for lang, bytes_count in repo_langs.items():
                lang_lower = lang.lower()
                lang_totals[lang_lower] = lang_totals.get(lang_lower, 0) + max(1, bytes_count // 10000)

    total_lang_weight = sum(lang_totals.values()) or 1
    languages_normalized = {
        lang: round(count / total_lang_weight, 3)
        for lang, count in sorted(lang_totals.items(), key=lambda x: -x[1])
    }

    categories: Dict[str, List[str]] = {}
    all_skills = set(lang_totals.keys()) | set(topic_counts.keys())
    for category, keywords in SKILL_CATEGORIES.items():
        matched = [s for s in all_skills if any(kw in s for kw in keywords)]
        if matched:
            categories[category] = list(set(matched))[:10]

    all_skill_scores = {**lang_totals, **topic_counts}
    top_skills = [s for s, _ in sorted(all_skill_scores.items(), key=lambda x: -x[1])][:10]

    total_repos = len([r for r in repos if not r.get("fork")])
    if total_repos < 5:
        experience_level = "beginner"
    elif total_repos < 20:
        experience_level = "intermediate"
    else:
        experience_level = "advanced"

    return {
        "languages": languages_normalized,
        "topics": list(topic_counts.keys())[:20],
        "categories": categories,
        "experience_level": experience_level,
        "top_skills": top_skills,
        "total_repos": total_repos,
        "total_stars_received": total_stars,
    }


def _skill_fingerprint_to_vector_hash(fingerprint: Dict[str, Any]) -> List[float]:
    """Hash-based fallback for skill fingerprint vectorization."""
    vector = np.zeros(SKILL_VECTOR_DIMS, dtype=np.float32)
    languages = fingerprint.get("languages", {})
    topics = fingerprint.get("topics", [])
    categories = fingerprint.get("categories", {})

    for lang, score in languages.items():
        idx = _stable_hash(lang, 64)
        vector[idx] = max(vector[idx], float(score))
    for topic in topics:
        idx = 64 + _stable_hash(topic, 32)
        vector[idx] = min(vector[idx] + 0.1, 1.0)
    category_list = list(SKILL_CATEGORIES.keys())
    for i, cat in enumerate(category_list):
        if cat in categories:
            idx = 96 + (i % 32)
            vector[idx] = min(len(categories[cat]) / 5.0, 1.0)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


def _issue_text_to_vector_hash(title: str, body: str, labels: List[str]) -> List[float]:
    """Hash-based fallback for issue text vectorization."""
    combined_text = f"{title} {body} {' '.join(labels)}".lower()
    vector = np.zeros(SKILL_VECTOR_DIMS, dtype=np.float32)
    all_langs = [
        "python", "javascript", "typescript", "java", "go", "rust",
        "ruby", "php", "swift", "kotlin", "c++", "c#", "scala", "r",
        "react", "vue", "angular", "django", "flask", "fastapi",
        "express", "spring", "rails", "laravel", "nodejs",
    ]
    for lang in all_langs:
        if lang in combined_text:
            idx = _stable_hash(lang, 64)
            vector[idx] = max(vector[idx], 0.8)
    for topic_kw in ["frontend", "backend", "api", "database", "ui", "ux",
                     "test", "bug", "feature", "documentation", "performance",
                     "security", "docker", "kubernetes", "ci", "deployment"]:
        if topic_kw in combined_text:
            idx = 64 + _stable_hash(topic_kw, 32)
            vector[idx] = min(vector[idx] + 0.15, 1.0)
    for i, (cat, keywords) in enumerate(SKILL_CATEGORIES.items()):
        matches = sum(1 for kw in keywords if kw in combined_text)
        if matches > 0:
            idx = 96 + (i % 32)
            vector[idx] = min(matches / 3.0, 1.0)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


async def skill_fingerprint_to_vector(fingerprint: Dict[str, Any]) -> List[float]:
    """
    Convert a skill fingerprint dict to a fixed-size 128-dim vector
    for pgvector similarity search.

    Uses Jina AI embedding when available, falls back to hash-based vector.
    """
    if ai_service.EMBEDDINGS_ENABLED:
        summary_parts = []
        languages = fingerprint.get("languages", {})
        if languages:
            top_langs = sorted(languages.items(), key=lambda x: -x[1])[:5]
            summary_parts.append("Languages: " + ", ".join(f"{l}({w})" for l, w in top_langs))
        top_skills = fingerprint.get("top_skills", [])
        if top_skills:
            summary_parts.append("Skills: " + ", ".join(top_skills[:10]))
        experience = fingerprint.get("experience_level", "")
        if experience:
            summary_parts.append(f"Experience: {experience}")
        categories = fingerprint.get("categories", {})
        if categories:
            summary_parts.append("Categories: " + ", ".join(categories.keys()))

        if summary_parts:
            embed_text = ". ".join(summary_parts)
            vector = await ai_service.generate_embedding(embed_text)
            if vector is not None:
                return vector

    return _skill_fingerprint_to_vector_hash(fingerprint)


async def issue_text_to_vector(title: str, body: str, labels: List[str]) -> List[float]:
    """
    Convert issue text to a skill vector for matching.

    Uses Jina AI embedding when available, falls back to hash-based vector.
    """
    if ai_service.EMBEDDINGS_ENABLED:
        embed_text = f"{title}\n{body}\nLabels: {', '.join(labels)}"[:2000]
        if embed_text.strip():
            vector = await ai_service.generate_embedding(embed_text)
            if vector is not None:
                return vector

    return _issue_text_to_vector_hash(title, body, labels)


def _compute_complexity(title: str, body: str, labels: List[str]) -> float:
    combined = f"{title} {body} {' '.join(labels)}".lower()

    simple_indicators = [
        "beginner", "easy", "simple", "starter", "first", "good first",
        "good-first", "low hanging", "trivial", "documentation", "typo",
        "help wanted", "up-for-grabs", "junior", "entry-level",
        "quick fix", "small", "minor",
    ]
    complex_indicators = [
        "complex", "advanced", "difficult", "expert", "hard", "challenging",
        "deep", "major", "core", "architecture", "performance", "security",
        "refactor", "complicated", "intricate",
    ]

    simple_count = sum(1 for w in simple_indicators if w in combined)
    complex_count = sum(1 for w in complex_indicators if w in combined)

    net = complex_count - simple_count
    if net > 2:
        return 0.8
    if net < -1:
        return 0.2

    word_count = len(combined.split())
    if word_count > 300:
        return 0.65
    if word_count < 30:
        return 0.35

    return 0.5


async def extract_required_skills(title: str, body: str, labels: List[str]) -> Dict[str, Any]:
    """
    Extract required skills from issue text.
    Uses AI (Groq) when available, falls back to regex.
    """
    if ai_service.AI_ENABLED:
        try:
            ai_result = await ai_service.analyze_issue_with_ai(title, body, labels)
        except Exception as e:
            logger.debug("AI issue analysis failed, falling back to regex: %s", e)
            ai_result = None
        if ai_result:
            categories: Dict[str, List[str]] = {}
            cat_skills = ai_result.get("categories", {})
            if isinstance(cat_skills, dict):
                categories = {
                    cat: skills[:5]
                    for cat, skills in cat_skills.items()
                    if isinstance(skills, list)
                }
            complexity = ai_result.get("complexity", 0.5)
            if isinstance(complexity, (int, float)):
                complexity = max(0.0, min(1.0, float(complexity)))
            else:
                complexity = _compute_complexity(title, body, labels)

            return {
                "skills": ai_result.get("skills", [])[:15],
                "categories": categories,
                "complexity": complexity,
                "labels": labels,
                "effort": ai_result.get("effort_estimate", "medium"),
                "issue_type": ai_result.get("issue_type", "other"),
            }

    combined = f"{title} {body} {' '.join(labels)}".lower()
    detected: Dict[str, List[str]] = {}
    for category, keywords in SKILL_CATEGORIES.items():
        found = [kw for kw in keywords if kw in combined]
        if found:
            detected[category] = found[:5]

    complexity = _compute_complexity(title, body, labels)

    return {
        "skills": [kw for category in detected.values() for kw in category][:15],
        "categories": detected,
        "complexity": complexity,
        "labels": labels,
    }


async def build_user_skills(github_username: str) -> Dict[str, Any]:
    """Full pipeline: fetch GitHub data → build skill fingerprint."""
    repos = await fetch_user_repos(github_username)
    fingerprint = await build_skill_fingerprint(repos)
    return fingerprint
