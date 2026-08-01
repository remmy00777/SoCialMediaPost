# Quick Start

1. Install and start Docker Desktop for macOS.
2. Run `cp .env.example .env`.
3. Replace `ADMIN_PASSWORD`, or allow `make install` to create the other local secrets.
4. Run `make install`.
5. Open `http://127.0.0.1:8765/portal/`.
6. Select **Initialize first-use account** once.
7. Sign in, complete the Brand Profile, and run the demonstration workflow.
8. Review files under `storage/Ready to Post for TikTok`, `storage/Ready to Post for Instagram`, and `storage/Ready to Post for YouTube`.

Use `make status`, `make doctor`, and `make logs` for diagnostics. Automatic publishing is off by default.
