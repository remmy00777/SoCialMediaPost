# Instagram Setup

## Eligibility

Instagram publishing and insights require an eligible professional account, typically Business or Creator, connected through a Meta application with approved permissions. Personal consumer accounts are not treated as eligible publishing accounts by this integration.

## Configuration

- Create a Meta application and add the Instagram API products appropriate to the account connection flow.
- Register `http://127.0.0.1:8765/api/accounts/instagram/callback`.
- Request only the scopes needed for profile access, owned-media insights, and publishing.
- Complete Meta app review and business verification when required.
- Add `META_APP_ID`, `META_APP_SECRET`, and the current supported `META_GRAPH_VERSION` to `.env`.

## Discovery limitation

Owned-account insights and manually imported Reel references are not described as platform-wide trend discovery. The active source and this limitation are shown in the portal. A licensed trend provider may be configured separately when its terms allow the intended use.

Official documentation entry points:

- https://developers.facebook.com/docs/instagram-platform/
- https://developers.facebook.com/docs/instagram-platform/content-publishing/
- https://developers.facebook.com/docs/instagram-platform/insights/
