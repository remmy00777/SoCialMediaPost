#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
log(){ printf '[SoCialMediaPost] %s\n' "$*"; }
need(){ command -v "$1" >/dev/null 2>&1 || { log "Missing $1. $2"; exit 1; }; }
compose(){ docker compose "$@"; }
portal_url(){ local port; port="$(grep -E '^PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2 || true)"; echo "http://127.0.0.1:${port:-8765}/portal/"; }
