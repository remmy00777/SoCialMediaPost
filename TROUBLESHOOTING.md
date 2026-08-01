# Troubleshooting

## Portal does not load

Run `make status`, then `make logs`. Confirm Docker Desktop is running and port 8765 is not occupied.

## Readiness is degraded

The readiness endpoint reports database, storage, FFmpeg, and adapter health separately. A missing live credential may make one adapter unavailable without stopping other platforms.

## No trends appear

Confirm the relevant official source is configured. In demo mode, run **Run Demo Workflow**. TikTok and Instagram broad discovery are intentionally unavailable without an approved source.

## Publication is blocked

Inspect missing permissions, app-review status, account eligibility, media validation, rights, originality, policy, quota, disclosure, user enablement, and the global pause state.

## Token refresh fails

Reconnect the account. Confirm redirect URI equality, client-secret correctness, refresh scope, clock accuracy, and provider app status.

## FFmpeg render fails

Run `docker compose exec api ffmpeg -version`, inspect free disk space, and remove incomplete files from `storage/temporary`. Ready folders use atomic finalization and should not contain partial media.
