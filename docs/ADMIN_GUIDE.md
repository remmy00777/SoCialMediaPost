# Administrator Guide

- `make status`: show containers and API readiness.
- `make logs`: follow API, worker, and scheduler logs.
- `make doctor`: verify macOS prerequisites and configuration structure.
- `make backup`: create a PostgreSQL and storage backup with checksums.
- `make restore FILE=...`: verify and restore a backup.
- `make audit`: compile Python, scan high-confidence secret signatures, and run container package checks when Docker is available.
- `make sbom`: regenerate `security/sbom.cdx.json`.
- `make stop` and `make start`: controlled shutdown and startup.

The portal binds to localhost. Do not expose it through port forwarding, public reverse proxies, or remote tunnels without a separate threat review and transport security design.
