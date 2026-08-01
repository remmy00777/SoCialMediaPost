#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
need docker "Install Docker Desktop."
compose ps
URL="$(portal_url | sed 's#/portal/$#/api/health/readiness#')"
printf '\n'; curl -fsS "$URL" | python3 -m json.tool || { log "Readiness endpoint unavailable: $URL"; exit 1; }
