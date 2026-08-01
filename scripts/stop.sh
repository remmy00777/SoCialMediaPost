#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
command -v docker >/dev/null 2>&1 && compose stop api worker beat redis postgres || true
log "Stopped."
