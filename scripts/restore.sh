#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
archive="${1:-}"; [[ -f "$archive" ]] || { log "Backup archive not found: $archive"; exit 1; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
tar -xzf "$archive" -C "$work"; dir="$(find "$work" -mindepth 1 -maxdepth 1 -type d | head -1)"
( cd "$dir" && shasum -a 256 -c SHA256SUMS )
compose stop api worker beat
compose exec -T postgres dropdb -U socialmediapost --if-exists socialmediapost
compose exec -T postgres createdb -U socialmediapost socialmediapost
compose exec -T postgres pg_restore -U socialmediapost -d socialmediapost --clean --if-exists < "$dir/database.dump"
tar -xzf "$dir/storage.tar.gz" -C "$ROOT"
compose start api worker beat
log "Restore completed from $archive"
