import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
AI_ENABLED = settings.AI_ENABLED and bool(settings.GROQ_API_KEY)
EMBEDDINGS_ENABLED = settings.EMBEDDINGS_ENABLED and bool(settings.JINA_API_KEY)

# Cache settings for AI results
AI_CACHE_PREFIX = "ai:"
AI_CACHE_TTL = 3600  # 1 hour default
AI_CACHE_TTL_QUERY = 86400  # 24 hours for query parsing (deterministic)
AI_CACHE_TTL_SKILLS = 86400  # 24 hours for skill analysis
AI_CACHE_TTL_EMBEDDING = 86400  # 24 hours for embeddings (deterministic)

# In-flight request deduplication: maps cache_key -> asyncio.Task
_in_flight: Dict[str, "asyncio.Task"] = {}

SYSTEM_PROMPTS = {
    "skill_analysis": """You are a senior open-source maintainer analyzing a developer's GitHub profile.
Given their repository data, produce ONLY a JSON object with:
{
  "languages": {"language_name": weight_0to1},
  "top_skills": ["skill1", "skill2", ...],
  "categories": {"frontend": [...], "backend": [...], ...},
  "experience_level": "beginner|intermediate|advanced",
  "summary": "1-sentence description of their expertise"
}

Rules:
- Weight languages by frequency and depth of use
- Top skills should include specific frameworks, tools, and domains
- Categories should map to: frontend, backend, database, devops, ai_ml, mobile, systems
- Experience level: <5 repos = beginner, 5-15 = intermediate, >15 = advanced
- Be generous with skill detection — if a repo uses python + fastapi, list both""",

    "issue_analysis": """You are analyzing a GitHub issue to extract required skills.
Given the issue title, body, and labels, produce ONLY a JSON object with:
{
  "skills": ["skill1", "skill2", ...],
  "categories": {"category": ["skill", ...]},
  "complexity": 0.0-1.0,
  "effort_estimate": "small|medium|large",
  "issue_type": "bug|feature|documentation|refactor|test|other"
}

Rules:
- Extract specific technologies, frameworks, and domains mentioned
- Complexity: 0.0-0.35=beginner, 0.35-0.65=intermediate, 0.65-1.0=advanced
- Estimate effort based on issue scope and discussion
- Categories same as: frontend, backend, database, devops, ai_ml, mobile, systems""",

    "match_explanation": """You are explaining why a GitHub issue matches a developer's skills.
Given the developer's skill profile and the issue requirements, produce ONLY a JSON object with:
{
  "explanation": "1-2 sentence explanation",
  "confidence": 0.0-1.0,
  "key_match": "the single best skill match"
}

Rules:
- Be specific: mention actual skills, not generic statements
- Confidence based on how well skills overlap
- Keep explanation concise and actionable""",

    "query_parsing": """You are parsing a developer's natural language search for open-source issues.
Given their query, produce ONLY a JSON object with:
{
  "languages": ["lang1", "lang2"],
  "difficulty": "beginner|intermediate|advanced|null",
  "labels": ["label1"],
  "keywords": ["keyword1", "keyword2", ...],
  "categories": ["category1"],
  "expanded_query": "optimized GitHub search query string"
}

Rules:
- Detect ANY programming languages mentioned
- Map: easy/beginner/starter/simple = beginner, medium/intermediate = intermediate, hard/advanced/expert = advanced
- Detect labels like: bug, feature, documentation, test, help wanted, good first issue
- Extract meaningful keywords excluding stop words
- Categories: frontend, backend, database, devops, ai_ml, mobile, systems
- expanded_query: create a search-friendly version""",
}

SYSTEM_PROMPTS["vector_text"] = """You generate a dense semantic description of a developer's skills or an issue's requirements.
Produce ONLY a JSON object with:
{
  "text": "A short paragraph describing the technical profile (max 100 words)"
}

Focus on: programming languages, frameworks, domains, experience level, and key technologies.
This text will be used for semantic matching, so make it informative and precise."""


def _groq_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }


def _groq_base() -> str:
    return settings.GROQ_API_BASE


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def _call_groq(
    system_prompt: str,
    user_prompt: str,
    temp: float = 0.1,
    max_tokens: int = 1024,
) -> str:
    if not AI_ENABLED:
        raise RuntimeError("AI is disabled — set GROQ_API_KEY and AI_ENABLED=true")

    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_groq_base()}/chat/completions",
            headers=_groq_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        usage = data.get("usage", {})
        if usage:
            logger.info(
                "Groq call: %s tokens used (prompt=%d, completion=%d)",
                settings.GROQ_MODEL,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            rate_remaining = resp.headers.get("x-ratelimit-remaining")
            if rate_remaining is not None and int(rate_remaining) < 10:
                logger.warning(
                    "Groq rate limit low: %s remaining (resets %s)",
                    rate_remaining,
                    resp.headers.get("x-ratelimit-reset", "unknown"),
                )

        return content


async def _parse_json_response(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse AI response as JSON: %s", raw[:200])
        return {}


def _cache_key(prefix: str, *parts: str) -> str:
    return f"{AI_CACHE_PREFIX}{prefix}:" + ":".join(parts)


async def _cached_ai_call(
    cache_key: str,
    ttl: int,
    coro_factory,
) -> Optional[Any]:
    """Deduplicated, cached AI call.

    1. Check cache (Redis)
    2. Check in-flight requests (deduplicate concurrent identical calls)
    3. Execute, cache result, return
    """
    result = await cache_get(cache_key)
    if result is not None:
        logger.debug("AI cache HIT: %s", cache_key)
        return result

    existing = _in_flight.get(cache_key)
    if existing is not None:
        logger.debug("AI dedup: waiting for in-flight request: %s", cache_key)
        try:
            return await existing
        except Exception:
            pass

    task = asyncio.create_task(coro_factory())
    _in_flight[cache_key] = task
    try:
        result = await task
        if result is not None:
            await cache_set(cache_key, result, ttl=ttl)
        return result
    finally:
        _in_flight.pop(cache_key, None)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
)
async def _call_jina_embed(text: str) -> Optional[List[float]]:
    """Call Jina AI embedding API, returns a vector or None on failure."""
    if not EMBEDDINGS_ENABLED:
        return None

    payload = {
        "model": settings.JINA_EMBED_MODEL,
        "input": [text],
        "dimensions": settings.JINA_EMBED_DIMS,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.JINA_API_BASE}/embeddings",
            headers={
                "Authorization": f"Bearer {settings.JINA_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]

        usage = data.get("usage", {})
        if usage:
            logger.debug("Jina embed: %s tokens used", usage.get("total_tokens", 0))

        return embedding


def _jina_enabled() -> bool:
    return EMBEDDINGS_ENABLED


async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate an embedding vector for the given text using Jina AI.

    Falls back to None if Jina is unavailable — callers should use hash-based
    vectors as a fallback.
    """
    if not EMBEDDINGS_ENABLED or not text.strip():
        return None

    cache_key = _cache_key("emb", hashlib.md5(text.strip().lower().encode()).hexdigest()[:16])

    result = await cache_get(cache_key)
    if result is not None:
        return result

    try:
        vector = await _call_jina_embed(text)
        if vector is not None:
            await cache_set(cache_key, vector, ttl=AI_CACHE_TTL_EMBEDDING)
        return vector
    except Exception as e:
        logger.debug("Jina embed failed, caller should fall back: %s", e)
        return None


async def analyze_skills_with_ai(repos: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Use Groq LLM to extract a rich skill fingerprint from repo data."""
    if not AI_ENABLED:
        return None

    repo_summaries = []
    for repo in repos[:20]:
        if repo.get("fork"):
            continue
        repo_summaries.append({
            "name": repo.get("full_name", repo.get("name", "")),
            "lang": repo.get("language"),
            "desc": (repo.get("description") or "")[:200],
            "topics": repo.get("topics", [])[:5],
            "stars": repo.get("stargazers_count", 0),
        })

    if not repo_summaries:
        return None

    cache_key = _cache_key("skills", hashlib.md5(json.dumps(repo_summaries, sort_keys=True).encode()).hexdigest()[:16])

    async def _execute():
        user_prompt = json.dumps({"repositories": repo_summaries}, indent=2)
        raw = await _call_groq(SYSTEM_PROMPTS["skill_analysis"], user_prompt, temp=0.2)
        result = await _parse_json_response(raw)
        if result and "languages" in result:
            return result
        return None

    return await _cached_ai_call(cache_key, AI_CACHE_TTL_SKILLS, _execute)


async def analyze_issue_with_ai(title: str, body: str, labels: List[str]) -> Optional[Dict[str, Any]]:
    """Use Groq LLM to extract required skills from an issue."""
    if not AI_ENABLED:
        return None

    cache_key = _cache_key("issue", hashlib.md5(f"{title[:500]}|{(body or '')[:2000]}|{labels}".encode()).hexdigest()[:16])

    async def _execute():
        user_prompt = json.dumps({
            "title": title[:500],
            "body": (body or "")[:2000],
            "labels": labels,
        }, indent=2)
        raw = await _call_groq(SYSTEM_PROMPTS["issue_analysis"], user_prompt, temp=0.2)
        result = await _parse_json_response(raw)
        if result and "skills" in result:
            return result
        return None

    return await _cached_ai_call(cache_key, AI_CACHE_TTL, _execute)


async def generate_match_explanation(
    user_skills: Dict[str, Any],
    issue_skills: Dict[str, Any],
    match_score: float,
) -> Optional[str]:
    """Use Groq LLM to generate a human-quality match explanation."""
    if not AI_ENABLED:
        return None

    cache_key = _cache_key(
        "explain",
        hashlib.md5(
            json.dumps({
                "us": {k: user_skills.get(k) for k in ["top_skills", "experience_level"]},
                "is": {k: issue_skills.get(k) for k in ["skills", "complexity"]},
                "s": round(match_score, 2),
            }, sort_keys=True).encode()
        ).hexdigest()[:16],
    )

    async def _execute():
        user_prompt = json.dumps({
            "developer_skills": {
                "top_skills": user_skills.get("top_skills", [])[:10],
                "languages": list(user_skills.get("languages", {}).keys())[:10],
                "experience": user_skills.get("experience_level", "unknown"),
                "categories": list(user_skills.get("categories", {}).keys()),
            },
            "issue_requirements": {
                "skills": issue_skills.get("skills", []) if isinstance(issue_skills.get("skills"), list) else [],
                "categories": list(issue_skills.get("categories", {}).keys()) if isinstance(issue_skills.get("categories"), dict) else [],
                "complexity": issue_skills.get("complexity", 0.5),
            },
            "current_match_score": match_score,
        }, indent=2)
        raw = await _call_groq(SYSTEM_PROMPTS["match_explanation"], user_prompt, temp=0.3, max_tokens=256)
        result = await _parse_json_response(raw)
        return result.get("explanation") if result else None

    return await _cached_ai_call(cache_key, AI_CACHE_TTL, _execute)


async def parse_query_with_ai(query: str) -> Optional[Dict[str, Any]]:
    """Use Groq LLM to parse a natural language search query into structured intent."""
    if not AI_ENABLED:
        return None

    cache_key = _cache_key("query", hashlib.md5(query.strip().lower().encode()).hexdigest()[:16])

    async def _execute():
        raw = await _call_groq(SYSTEM_PROMPTS["query_parsing"], query, temp=0.1)
        result = await _parse_json_response(raw)
        if result and "keywords" in result:
            return result
        return None

    return await _cached_ai_call(cache_key, AI_CACHE_TTL_QUERY, _execute)


async def generate_vector_text(
    fingerprint: Dict[str, Any],
) -> Optional[str]:
    """Generate a dense semantic description for vector embedding."""
    if not AI_ENABLED:
        return None

    user_prompt = json.dumps({
        "languages": fingerprint.get("languages", {}),
        "top_skills": fingerprint.get("top_skills", []),
        "categories": fingerprint.get("categories", {}),
        "experience_level": fingerprint.get("experience_level", "unknown"),
    }, indent=2)

    try:
        raw = await _call_groq(SYSTEM_PROMPTS["vector_text"], user_prompt, temp=0.2, max_tokens=256)
        result = await _parse_json_response(raw)
        return result.get("text") if result else None
    except Exception as e:
        logger.warning("AI vector text generation failed: %s", e)
        return None
