#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
need docker "Install and start Docker Desktop."
for _ in {1..60}; do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info >/dev/null 2>&1 || { log "Docker did not become ready."; exit 1; }
compose up -d postgres redis api worker beat
for _ in {1..60}; do curl -fsS "$(portal_url | sed 's#/portal/$#/api/health/readiness#')" >/dev/null 2>&1 && { log "Running at $(portal_url)"; exit 0; }; sleep 2; done
compose ps
exit 1
