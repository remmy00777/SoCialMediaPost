# Architecture

## Shape

The system is a local modular monolith with three process roles: API, asynchronous worker, and persistent scheduler. PostgreSQL and Redis provide durable state. All roles share the managed storage root.

## Major layers

1. **Portal and API**: local authentication, CSRF-protected writes, account status, trends, content review, schedules, analytics, experiments, security, reports, and backups.
2. **Platform access**: normalized adapters for YouTube, TikTok, and Instagram. Raw responses remain available for audit.
3. **Discovery**: official or licensed sources, manual imports, metric normalization, deduplication, transparent scoring, and confidence penalties.
4. **Analysis and strategy**: factual observations stay separate from model interpretations, assumptions, confidence, and missing information.
5. **Generation**: provider-independent interfaces, local template fallback, platform adaptation, FFmpeg rendering, subtitles, thumbnails, and packages.
6. **Gates**: policy, rights, originality, duplicate, budget, media, account, quota, schedule, and disclosure validation.
7. **Publishing**: idempotent jobs and platform status polling. No cross-platform batch is failed by a single item.
8. **Learning**: normalized metrics, experiment registry, multi-objective evaluation, and rollback-ready configuration versions.

## Data flow

```text
Official source or manual import
  -> raw response and normalized SourceVideo
  -> metric snapshot
  -> candidate and transparent score
  -> structured analysis
  -> multiple concepts and scored selection
  -> originality and policy checks
  -> TikTok, Instagram, and YouTube adaptations
  -> FFmpeg render and media validation
  -> draft, review, or ready-to-post queue
  -> gated publication job
  -> post and account metric snapshots
  -> versioned experiment result
```

## Failure isolation

Every workflow has child task records. Item failures are stored without terminating the batch. Adapter health, quotas, retries with jitter, circuit behavior, and dead-letter states are represented separately by platform and item.
