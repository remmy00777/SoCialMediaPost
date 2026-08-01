# Data Dictionary

The SQLAlchemy model in `backend/app/models.py` is the source of truth. Main entities include:

- `users`: local authenticated operators
- `brand_profiles`: audience, voice, topics, languages, countries, approval
- `platform_accounts`: account identity, permissions, token health, eligibility, quotas
- `oauth_credentials`: encrypted access and refresh tokens
- `trend_sources`: official, licensed, manual, or demonstration source and limitations
- `source_videos`: normalized source observations and preserved raw response
- `source_metrics`: timestamped views, likes, comments, shares, saves, velocity inputs
- `trend_candidates`, `trend_scores`, `trend_analyses`: ranking, confidence, and interpretation
- `content_concepts`: selected and rejected scored concepts
- `content_packages`, `platform_variants`, `generated_assets`: generated deliverables
- `originality_checks`, `policy_checks`: blocking gate evidence
- `approval_records`, `publication_jobs`, `platform_posts`: review and publishing lifecycle
- `post_metric_snapshots`, `account_metric_snapshots`: official analytics observations
- `schedules`, `workflow_runs`, `task_runs`: durable orchestration state
- `provider_configurations`, `prompt_versions`: replaceable providers and versioning
- `experiments`, `experiment_assignments`, `experiment_results`: controlled optimization
- `audit_events`, `notifications`, `error_events`: operations and accountability
