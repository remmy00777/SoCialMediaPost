# Configuration

Configuration is read through Pydantic Settings from `.env` and validated at startup. Unknown keys are ignored, but invalid host binding, short session secrets, malformed types, or unsupported modes stop startup.

## Important groups

- Runtime: `ENVIRONMENT`, `HOST`, `PORT`, `TIMEZONE`, `DEMO_MODE`
- Authentication: `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SESSION_SECRET`, cookie settings
- Persistence: `DATABASE_URL`, `REDIS_URL`, `STORAGE_ROOT`, encryption settings
- Scheduling: `TREND_DISCOVERY_CRON`, `CONTENT_WORKFLOW_CRON`, timezone, per-platform limits
- Providers: LLM, speech, image, video, stock, music, moderation, embeddings
- OAuth: YouTube, TikTok, and Meta application values
- Analytics: intervals at 1, 6, 24, 72, 168, and 720 hours by default
- Budgets: daily, monthly, hard limit, warning threshold, local-only mode
- Operations: logging, notifications, backups, global pause, feature flags

Run `make doctor` after every material `.env` change.
