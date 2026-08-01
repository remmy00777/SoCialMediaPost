# Platform Setup

Each platform requires its own developer application, redirect URI, approved scopes, and eligible account. Enter client values only in `.env`, never in the browser bundle or Git.

1. Complete the Brand Profile.
2. Register each developer app with the localhost redirect URI shown in `.env.example`.
3. Request only the least-privilege scopes listed in the platform-specific guide.
4. Complete required platform review or audit.
5. Add the client credentials to `.env` and restart.
6. Connect the account through the portal.
7. Inspect granted and missing permissions, token health, quota state, and eligibility.
8. Run **Test connection**.
9. Run a private or draft test upload where supported.
10. Keep automatic publishing disabled until all portal gates pass.

Never paste a platform password into this application.
