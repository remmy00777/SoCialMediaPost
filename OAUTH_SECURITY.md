# OAuth Security

- OAuth state values are random, short-lived, and verified on callback.
- Access and refresh tokens are encrypted before database storage.
- The encryption key is read from macOS Keychain when available. A fallback file is created with mode `0600` under `storage/.secrets`.
- Platform passwords are never requested or stored.
- Refresh tokens are server-side only and excluded from API serialization, logs, reports, and frontend bundles.
- Scopes are least privilege and displayed as granted or missing.
- Disconnect revokes local credentials and attempts provider revocation when the provider supports it.
- Redirect URIs are fixed localhost values by default.
- Reauthorization is required after failed refresh, revocation, or a material scope change.

Do not synchronize `storage/.secrets`, `.env`, database dumps, or OAuth records through an unencrypted consumer cloud folder.
