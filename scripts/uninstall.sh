#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
PLIST="$HOME/Library/LaunchAgents/com.rcegai.socialmediapost.plist"
launchctl bootout "gui/$(id -u)/com.rcegai.socialmediapost" >/dev/null 2>&1 || true
rm -f "$PLIST"
if command -v docker >/dev/null 2>&1; then compose down --remove-orphans; fi
if [[ "${1:-}" == "--purge" ]]; then
  read -r -p "Delete PostgreSQL and Redis volumes plus managed storage? Type DELETE: " confirm
  [[ "$confirm" == "DELETE" ]] || exit 1
  compose down -v --remove-orphans || true
  rm -rf storage
fi
log "Application services and LaunchAgent removed. Data was preserved unless --purge was used."
