#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
need docker "Install Docker Desktop for macOS, start it, then rerun make install."
docker info >/dev/null 2>&1 || { log "Docker Desktop is not running."; exit 1; }
if [[ ! -f .env ]]; then cp .env.example .env; fi
python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.env')
s=p.read_text()
s=s.replace('SESSION_SECRET=replace-with-at-least-32-random-characters','SESSION_SECRET='+secrets.token_urlsafe(48))
s=s.replace('POSTGRES_PASSWORD=change-this-local-password','POSTGRES_PASSWORD='+secrets.token_urlsafe(30)) if 'POSTGRES_PASSWORD=' in s else s+'\nPOSTGRES_PASSWORD='+secrets.token_urlsafe(30)+'\n'
p.write_text(s)
PY
mkdir -p storage/logs "$HOME/Library/LaunchAgents"
chmod 700 storage storage/.secrets 2>/dev/null || true
compose build api worker beat
compose run --rm api alembic upgrade head
if [[ "${1:-}" != "--no-start" ]]; then compose up -d postgres redis api worker beat; fi
PLIST="$HOME/Library/LaunchAgents/com.rcegai.socialmediapost.plist"
sed "s|__PROJECT_ROOT__|$ROOT|g" launchd/com.rcegai.socialmediapost.plist > "$PLIST"
launchctl bootout "gui/$(id -u)/com.rcegai.socialmediapost" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.rcegai.socialmediapost"
log "Installed. Portal: $(portal_url)"
log "Initialize the local account from the portal, then replace ADMIN_PASSWORD in .env."
