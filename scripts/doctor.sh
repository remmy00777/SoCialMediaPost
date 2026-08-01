#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
fail=0
check(){ if command -v "$1" >/dev/null 2>&1; then printf '✓ %-18s %s\n' "$1" "$(command -v "$1")"; else printf '✗ %-18s %s\n' "$1" "$2"; fail=1; fi; }
check docker "Install Docker Desktop"
check curl "Install Xcode Command Line Tools"
check python3 "Install Python 3.12 or later"
check openssl "Install Xcode Command Line Tools"
check security "macOS Keychain command unavailable"
[[ -f .env ]] || { echo '✗ .env              Run cp .env.example .env'; fail=1; }
[[ -x scripts/start.sh ]] || { echo '✗ scripts           Run chmod +x scripts/*.sh'; fail=1; }
if command -v docker >/dev/null 2>&1; then docker info >/dev/null 2>&1 || { echo '✗ Docker Desktop     Start Docker Desktop'; fail=1; }; fi
if [[ -f .env ]]; then
  python3 - <<'PY' || fail=1
from pathlib import Path
required=['SESSION_SECRET','ADMIN_PASSWORD','POSTGRES_PASSWORD']
values={}
for line in Path('.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1); values[k]=v
for key in required:
    value=values.get(key,'')
    if not value: raise SystemExit(f'✗ {key} is missing')
if len(values.get('SESSION_SECRET',''))<32: raise SystemExit('✗ SESSION_SECRET must contain at least 32 characters')
print('✓ Environment configuration is structurally valid')
PY
fi
if command -v ffmpeg >/dev/null 2>&1; then ffmpeg -version | head -1; else echo 'ℹ FFmpeg is provided inside the application container.'; fi
exit "$fail"
