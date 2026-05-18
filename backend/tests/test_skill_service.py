from app.services.skill_service import (
    _stable_hash,
    build_skill_fingerprint,
    extract_required_skills,
    issue_text_to_vector,
    skill_fingerprint_to_vector,
)


def test_stable_hash_deterministic():
    val1 = _stable_hash("python", 64)
    val2 = _stable_hash("python", 64)
    assert val1 == val2
    assert 0 <= val1 < 64


def test_stable_hash_different_inputs_different_buckets():
    val_a = _stable_hash("python", 64)
    val_b = _stable_hash("javascript", 64)
    assert val_a != val_b


async def test_build_skill_fingerprint_basic():
    repos = [
        {
            "name": "repo1",
            "language": "Python",
            "topics": ["web", "api"],
            "stargazers_count": 10,
            "fork": False,
        },
        {
            "name": "repo2",
            "language": "JavaScript",
            "topics": ["frontend", "react"],
            "stargazers_count": 5,
            "fork": False,
        },
    ]
    fp = await build_skill_fingerprint(repos)
    assert fp["total_repos"] == 2
    assert "python" in fp["languages"]
    assert "javascript" in fp["languages"]
    assert fp["total_stars_received"] == 15
    assert fp["experience_level"] == "beginner"


async def test_build_skill_fingerprint_skips_forks():
    repos = [
        {"name": "own", "language": "Python", "fork": False},
        {"name": "forked", "language": "Java", "fork": True},
    ]
    fp = await build_skill_fingerprint(repos)
    assert fp["total_repos"] == 1
    assert "java" not in fp["languages"]


async def test_skill_fingerprint_to_vector_output_shape():
    fp = {
        "languages": {"python": 0.5, "javascript": 0.3},
        "topics": ["web", "api"],
        "categories": {"backend": ["python"], "frontend": ["javascript"]},
        "experience_level": "beginner",
        "top_skills": ["python", "javascript"],
        "total_repos": 2,
        "total_stars_received": 0,
    }
    vec = await skill_fingerprint_to_vector(fp)
    assert len(vec) == 128
    assert all(isinstance(v, float) for v in vec)
    import numpy as np
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 0.01


async def test_issue_text_to_vector_output_shape():
    vec = await issue_text_to_vector("Add Python support", "We need to support python 3.11", ["enhancement"])
    assert len(vec) == 128
    import numpy as np
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 0.01 or norm == 0


async def test_extract_required_skills():
    skills = await extract_required_skills("Add Python API endpoints with detailed discussion", "Use FastAPI and PostgreSQL for data processing. This is a standard feature that requires typical implementation work across multiple modules with testing and documentation. We should implement it using the usual patterns found in similar projects.", ["backend", "enhancement"])
    assert "backend" in skills["categories"]
    assert skills["complexity"] == 0.5


async def test_extract_required_skills_beginner():
    skills = await extract_required_skills("Easy beginner issue", "Simple starter task", ["good first issue"])
    assert skills["complexity"] == 0.2


async def test_extract_required_skills_advanced():
    skills = await extract_required_skills("Complex advanced feature", "Expert level implementation", ["enhancement"])
    assert skills["complexity"] == 0.8
