# OpenIssue

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

OpenIssue analyzes your **actual GitHub activity** to build a personal skill fingerprint, then uses **pgvector semantic similarity search** to match you with open issues across thousands of repositories that align with your demonstrated abilities.

```
GitHub Login  →  Fetch repos & activity  →  Build skill vector  →  Semantic match  →  Personalized feed
```

---

## Deploy to Google Cloud Run

Two separate Cloud Run services — frontend (Next.js) and backend (FastAPI) — deploy independently.

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud` CLI)
- A Google Cloud project with billing enabled
- [Artifact Registry](https://cloud.google.com/artifact-registry) API enabled
- [Cloud Run](https://cloud.google.com/run) API enabled
- A [Supabase](https://supabase.com) project (PostgreSQL + pgvector)
- A [GitHub OAuth App](https://github.com/settings/applications/new)

### 1. Set secrets in Secret Manager

```bash
gcloud secrets create GITHUB_CLIENT_ID --data-file=<(echo -n "your_client_id")
gcloud secrets create GITHUB_CLIENT_SECRET --data-file=<(echo -n "your_client_secret")
```

### 2. Deploy with Cloud Build

Create a Cloud Build trigger pointing to your repo, or run manually:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=\
_DATABASE_URL="postgresql://postgres:pass@db.xxx.supabase.co:6543/postgres",\
_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')",\
_GITHUB_TOKEN="ghp_your_token",\
_FRONTEND_URL="https://openissue-frontend-xxxxx-uc.a.run.app",\
_NEXT_PUBLIC_API_URL="https://openissue-backend-xxxxx-uc.a.run.app",\
_NEXTAUTH_URL="https://openissue-frontend-xxxxx-uc.a.run.app",\
_NEXTAUTH_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

### 3. Update GitHub OAuth callback

Set the callback URL in your GitHub OAuth App to:
```
https://openissue-frontend-xxxxx-uc.a.run.app/api/auth/callback/github
```

### 4. Enable pgvector in Supabase

In your Supabase dashboard → Database → Extensions → enable `vector`.

---

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
