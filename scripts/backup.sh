#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
need docker "Start the Docker stack before backup."
ts="$(date -u +%Y%m%dT%H%M%SZ)"; out="storage/backups/socialmediapost-$ts"; mkdir -p "$out"
compose exec -T postgres pg_dump -U socialmediapost -d socialmediapost -Fc > "$out/database.dump"
tar -czf "$out/storage.tar.gz" --exclude='storage/backups' storage
cp .env.example "$out/env.schema.example"
( cd "$out" && shasum -a 256 database.dump storage.tar.gz env.schema.example > SHA256SUMS )
tar -czf "$out.tar.gz" -C "$(dirname "$out")" "$(basename "$out")"
rm -rf "$out"
chmod 600 "$out.tar.gz"
log "Backup created: $out.tar.gz"
