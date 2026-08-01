# TikTok Setup

## Account connection and publishing

- Register an application in TikTok for Developers.
- Add Login Kit and the Content Posting API.
- Register `http://127.0.0.1:8765/api/accounts/tiktok/callback`.
- Request approved user-information and publishing scopes, including `video.publish` only when needed.
- Add `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` to `.env`.

All unaudited Direct Post clients are restricted to private viewing. Public posting requires TikTok audit approval. The portal therefore keeps public automatic publishing ineligible until the account, app audit, scope, test upload, disclosure, and user-enable gates pass.

## Trend data

Broad TikTok public-data discovery is not assumed. Research Tools are available only to approved qualifying noncommercial researchers. Commercial use should use an approved licensed provider, authorized owned-account data, monitored inputs permitted by the API, or manual URL import. No scraper is included.

Research snapshots can lag live video statistics, so the adapter records retrieval time, source, confidence, and missing metrics.

Official documentation:

- https://developers.tiktok.com/products/research-api/
- https://developers.tiktok.com/doc/content-posting-api-get-started/
- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
