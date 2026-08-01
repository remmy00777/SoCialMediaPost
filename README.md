# SoCialMediaPost Studio

SoCialMediaPost Studio is a local-first social-media intelligence, original-content production, review, publishing-control, analytics, and experimentation system. It binds to localhost by default, stores generated media in user-visible folders, encrypts OAuth credentials, and uses only official APIs, licensed providers, user-authorized data, or manual imports.

## Architecture selected

The default runtime is a modular monolith:

- FastAPI and SQLAlchemy for the API and business logic
- PostgreSQL for durable records
- Redis plus Celery for persistent work queues and schedules
- FFmpeg and ffprobe for local video production and validation
- A dependency-free responsive portal served by FastAPI
- An optional Next.js 16 portal under the `nextjs` Docker Compose profile
- Docker Compose for repeatable macOS operation
- launchd for login startup and crash restart

This avoids unnecessary microservices while isolating platform adapters, AI providers, media providers, policy gates, analytics, and optimization behind typed interfaces.

## Implemented capability summary

- Transparent trend scoring, confidence, missing-signal reporting, and deduplication
- Official YouTube `mostPopular` chart adapter, keyword/channel support foundations, and manual import
- TikTok OAuth, Research API, owned-media, and Content Posting API adapter paths with eligibility gates
- Instagram professional-account OAuth, owned-media, insights, and publishing adapter paths with account-type gates
- Demo mode with synthetic fixtures, three platform adaptations, valid H.264/AAC videos, captions, thumbnails, reports, and sample analytics
- Manual Export, Review and Approve, and gated Controlled Automatic Publishing data models and controls
- Originality, policy, rights, quality, media-validation, budget, idempotency, and global-pause gates
- OAuth token encryption through macOS Keychain where available, with a permission-restricted local fallback
- CSV and PDF reports, audit events, notifications, experiments, backups, health checks, and a complete storage tree

Live publication remains disabled until credentials, scopes, platform approval, account eligibility, a successful private test upload, brand approval, explicit user enablement, limits, and emergency-stop validation are present.

## Quick start on macOS

```bash
cp .env.example .env
make install
open http://127.0.0.1:8765/portal/
```

Initialize the first-use account in the portal, then sign in using `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`. Replace the default password before connecting accounts.

## Demonstration without Docker

When the Python dependencies are already available:

```bash
cd backend
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765/portal/`, initialize the account, and select **Run Demo Workflow**.

## Repository map

```text
backend/                 FastAPI API, data models, adapters, workflows, tests
frontend/                Optional Next.js portal source and Playwright tests
fixtures/                Isolated demonstration data
launchd/                 macOS LaunchAgent template
scripts/                 Install, start, doctor, backup, restore, update, scan
security/                Generated software bill of materials
storage/                 Persistent data and ready-to-post folders
docs/                    Architecture, security, platform, and operations guides
docker-compose.yml       Default local stack
Makefile                 Operator commands
```

## Critical limitations

- The YouTube `mostPopular` chart is not a replacement for the historical general Trending page. Current official documentation describes it as including trending music, movies, and gaming videos.
- TikTok Research Tools require approval and are limited to qualifying noncommercial research. Research snapshots can lag live metrics.
- TikTok unaudited Content Posting API clients are restricted to private visibility, and public posting requires audit approval.
- Instagram publishing and insights require an eligible professional account and approved Meta permissions. Owned-account insights are not platform-wide trend discovery.
- Live credentials, app-review decisions, changing quotas, and real publication were not exercised in this build environment.

See `docs/API_LIMITATIONS.md` and each platform setup guide before enabling live access.
