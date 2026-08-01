#!/usr/bin/env bash
set -Eeuo pipefail
"$(dirname "$0")/stop.sh"
"$(dirname "$0")/start.sh"
