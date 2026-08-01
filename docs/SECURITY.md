# Security Controls

- Localhost binding and no host exposure for PostgreSQL or Redis
- Local account authentication with scrypt password hashing
- HMAC-signed, HTTP-only, SameSite strict session cookies
- CSRF token required for mutating requests
- Content Security Policy, clickjacking denial, MIME sniffing prevention, and restrictive permissions policy
- Typed request validation and SQLAlchemy parameterization
- Encrypted OAuth credentials and secret redaction
- Safe filenames, path containment, atomic files, MIME and media probing
- Source content treated as untrusted data, not instructions
- Request timeouts, API rate limiting, quota state, retries, idempotency, and audit records
- Global pause and controlled automatic-publishing eligibility gates
- Dependency manifest and generated CycloneDX SBOM

A malware-scanning provider interface is represented as an integration boundary. No scanner signature database is bundled. Configure an approved scanner before accepting arbitrary third-party uploads outside manual trusted use.
