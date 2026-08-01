#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
fail=0
patterns='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,})'
if grep -RIE --exclude-dir=.git --exclude-dir=node_modules --exclude='*.db*' "$patterns" .; then echo 'Potential committed secret detected'; fail=1; else echo '✓ No high-confidence secret signatures detected'; fi
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  compose run --rm api python -m pip check || fail=1
else echo 'ℹ Container dependency audit skipped because Docker is unavailable.'; fi
python3 -m compileall -q backend/app || fail=1
exit "$fail"
