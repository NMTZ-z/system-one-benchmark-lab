#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v local-system-one >/dev/null 2>&1; then
  exec local-system-one status --profile "${1:-default}"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m local_system_one status --profile "${1:-default}"
