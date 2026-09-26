#!/bin/zsh
set -euo pipefail

label="ai.localsystemone.service"
uid="$(id -u)"
url="${LOCAL_SYSTEM_ONE_URL:-http://127.0.0.1:8787}"

echo "== launchd =="
if launchctl print "gui/$uid/$label" >/dev/null 2>&1; then
  echo "loaded: $label"
else
  echo "not loaded: $label"
fi

echo
echo "== health =="
if curl -fsS --max-time 3 "$url/health"; then
  echo
else
  echo "service unavailable at $url" >&2
  exit 1
fi