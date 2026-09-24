#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-}"
if [[ -z "$PROFILE" ]]; then
  echo "Usage: $0 <hermes-profile>" >&2
  exit 2
fi

HOME_DIR="$HOME/.hermes/profiles/$PROFILE"
if [[ ! -d "$HOME_DIR" ]]; then
  echo "Hermes profile not found: $PROFILE" >&2
  exit 1
fi

echo "== plugin =="
HERMES_HOME="$HOME_DIR" hermes plugins show local-system-one-hermes 2>/dev/null || echo "not installed"

echo
echo "== mode =="
HERMES_HOME="$HOME_DIR" hermes config get   plugins.entries.local-system-one-hermes.settings.mode 2>/dev/null || echo "unset"

echo
echo "== Local System One =="
curl -fsS --max-time 2 http://127.0.0.1:8787/health || echo "unreachable"
echo
