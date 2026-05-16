# Contributing to IssueCompass

First off — thank you for considering a contribution. IssueCompass is built for the open source community, and every contribution matters.

---

## Quick Start for Contributors

```bash
git clone https://github.com/yourusername/issuecompass.git
cd issuecompass
cp .env.example .env
# Fill in GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, NEXTAUTH_SECRET
docker-compose up --build
```

Frontend at `http://localhost:3000`, API docs at `http://localhost:8000/docs`.

---

## How to Contribute

### Reporting Bugs

Open an issue with the `bug` label. Include:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS and Node/Python versions

### Suggesting Features

Open an issue with the `enhancement` label. Describe the feature and why it benefits contributors.

### Submitting a Pull Request

1. Fork the repo and create a branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Test locally with Docker or manual setup
4. Commit with a clear message: `git commit -m "feat: add weekly digest emails"`
5. Push and open a PR against `main`

---

## Project Structure Reference

```
issuecompass/
├── frontend/src/
│   ├── app/          ← Next.js pages (App Router)
│   ├── components/   ← Reusable UI components
│   └── lib/          ← API client, types, utilities
├── backend/app/
│   ├── routes/       ← FastAPI route handlers
│   ├── services/     ← Business logic (GitHub, matching, skills)
│   ├── models/       ← SQLAlchemy database models
│   └── core/         ← Config, database connection
```

---

## Good First Issues

Look for issues tagged `good first issue` in this repo. Great starting points:
- Adding a new language filter
- Improving the skill extraction regex in `skill_service.py`
- Adding a new chart to the profile page
- Writing tests for the matching algorithm

---

## Code Style

**Frontend:** ESLint + Prettier defaults. Run `npm run lint` before committing.

**Backend:** Follow PEP 8. Keep route handlers thin — logic goes in `services/`.

---

## Questions?

Open a Discussion on GitHub or drop a comment in any issue.
