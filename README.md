# IssueCompass

**Match open-source contributors to issues they can actually solve.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

---

## The Problem

Developers want to contribute to open source but face a discovery gap:

- **Contributors** browse GitHub aimlessly, wasting hours finding issues matching their skill set
- **Maintainers** tag issues as "good first issue" but attract contributors without the right skills
- **Existing tools** (GitHub Explore, goodfirstissue.dev) are generic lists — zero personalization, zero intelligence

## The Solution

IssueCompass analyzes your **actual GitHub activity** to build a personal skill fingerprint, then uses **pgvector semantic similarity search** to match you with open issues across thousands of repositories that align with your demonstrated abilities.

```
GitHub Login  →  Fetch repos & activity  →  Build skill vector  →  Semantic match  →  Personalized feed
```

## Testing

```bash
# Backend tests
cd backend && source venv/bin/activate
pytest -v

# Frontend lint + type check
cd frontend
npm run lint
npx tsc --noEmit
```

---

## Roadmap

- Email digest of new matched issues
- Maintainer dashboard with analytics and promoted placement
- Browser extension (GitHub sidebar integration)
- CLI tool for terminal-based matching
- Slack/Discord bot for issue notifications
- AI-powered skill extraction via LLM
- Contribution streak tracking and gamification

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines. All contributions welcome — features, bug fixes, tests, docs.

---

## License

[MIT](LICENSE) — Copyright (c) 2026 Paul Bryton Raj
