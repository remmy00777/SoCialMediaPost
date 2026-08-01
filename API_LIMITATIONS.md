# Current API Limitations

Verified on July 30, 2026. Platform behavior can change, so recheck official documentation before each release.

## YouTube

- `videos.list` supports `chart=mostPopular`, region, and category. The current official implementation guide describes the chart as including trending music, movies, and gaming videos.
- It must not be labeled as the historical general YouTube Trending page.
- Search, uploads, analytics, captions, and channel statistics use separate endpoints, permissions, and quotas.
- Some metrics requested by the product specification, such as saves, are not generally exposed for arbitrary public videos.

## TikTok

- Research Tools require an approved qualifying noncommercial research project. A normal developer account is insufficient.
- Research video data can lag, with new videos taking time to enter search and statistics updating after the live values.
- Commercial creators and businesses are not eligible for Research Tools merely because they have a developer account.
- Content Posting API requires approved scopes and user authorization.
- Unaudited Direct Post clients are restricted to private visibility. Public posting requires audit approval.
- Posting, creator, and rate caps vary and must be read from current provider responses rather than hard-coded.

## Instagram

- Publishing and insights require an eligible professional account and approved Meta permissions.
- Personal accounts are not treated as supported publishing targets by this application.
- Owned-media insights do not represent platform-wide trend discovery.
- Hashtag, creator, and public-content access varies by API product, account type, review status, region, and current Meta policy.

## Application behavior

Unsupported fields are stored as null with a reason code. The system does not estimate official metrics unless the output is explicitly labeled as an estimate. No unauthorized scraper or authentication bypass is implemented.

## Rights-managed source clips

- The application does not download or copy a third party's viral video from a platform URL.
- Full source-clip playback is available only for a file uploaded by the user with recorded ownership, license, public-domain status, or explicit permission.
- A user declaration is an operational safeguard, not independent legal verification. The user remains responsible for confirming that the license covers editing, voiceover, publication, territories, platforms, and commercial use.
- The local `espeak-ng` voice is a functional fallback. Configure an approved higher-quality TTS provider for polished production narration.
