# macOS Installation

## Requirements

- macOS on Apple Silicon or Intel
- Docker Desktop
- Xcode Command Line Tools
- Internet access for image and dependency downloads
- At least 15 GB free disk space for the initial stack and media workspace

## Install

```bash
xcode-select --install
cp .env.example .env
make doctor
make install
```

The installer builds the API, worker, and scheduler images, runs database migrations, starts the stack, and installs `~/Library/LaunchAgents/com.rcegai.socialmediapost.plist`.

The LaunchAgent executes `scripts/start.sh` after login. The script waits for Docker, starts one Compose project, and relies on durable database records and idempotency keys to prevent duplicate completed jobs.

## Apple Silicon

All selected base images publish arm64 variants. FFmpeg is installed from the Debian image repository inside the API and worker containers.

## Intel Macs

The same Compose file selects amd64 image variants automatically.

## Remove

```bash
./scripts/uninstall.sh
```

Data is preserved. Use `./scripts/uninstall.sh --purge` only after a verified backup.
