#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
"$ROOT/scripts/backup.sh"
git pull --ff-only
compose build --pull api worker beat
compose run --rm api alembic upgrade head
compose up -d postgres redis api worker beat
log "Update completed."
