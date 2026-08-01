# Testing

## Backend

```bash
cd backend
PYTHONPATH=. pytest
ruff check app tests
mypy app
```

The suite covers scoring, normalization, deduplication, originality, policy gates, security helpers, platform contracts, storage safety, media rendering, media probing, API authentication and CSRF, reports, backup, and a full demo workflow with three valid platform videos.

## Frontend

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

## Acceptance

```bash
make doctor
make test
make audit
make sbom
make start
make demo
make backup
make restore FILE=storage/backups/<archive>.tar.gz
```

Live platform contract tests require dedicated test applications and must never publish publicly during CI.
