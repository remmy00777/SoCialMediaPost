# YouTube Setup

## Required Google configuration

- Create a Google Cloud project.
- Enable YouTube Data API v3 and, when analytics are needed, the YouTube Analytics API.
- Create an OAuth web application.
- Register `http://127.0.0.1:8765/api/accounts/youtube/callback`.
- Configure the OAuth consent screen and request only necessary scopes.
- Add `YOUTUBE_API_KEY`, `YOUTUBE_CLIENT_ID`, and `YOUTUBE_CLIENT_SECRET` to `.env`.

## Discovery

The adapter uses `videos.list` with `chart=mostPopular`, region, category, statistics, and content details. It labels this source as the official YouTube most-popular chart, not the former general Trending page. Search and monitored-channel requests should be budgeted separately because quota costs differ.

## Publishing

YouTube upload requires user OAuth and appropriate upload scope. The integration validates title, privacy, audience setting, media format, and idempotency before creating an upload job. Real credentials and quota were not validated in the build environment.

Official documentation:

- https://developers.google.com/youtube/v3/docs/videos/list
- https://developers.google.com/youtube/v3/docs/videos/insert
- https://developers.google.com/youtube/analytics
