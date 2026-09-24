#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-}"
MODE="${2:-}"

if [[ -z "$PROFILE" || -z "$MODE" ]]; then
  echo "Usage: $0 <hermes-profile> <off|shadow>" >&2
  exit 2
fi

case "$MODE" in
  off|shadow) ;;
  *)
    echo "Refusing unsupported mode '$MODE'. v0.1 only allows off or shadow." >&2
    exit 2
    ;;
esac

HOME_DIR="$HOME/.hermes/profiles/$PROFILE"
if [[ ! -d "$HOME_DIR" ]]; then
  echo "Hermes profile not found: $PROFILE" >&2
  exit 1
fi

HERMES_HOME="$HOME_DIR" hermes config set   plugins.entries.local-system-one-hermes.settings.mode "$MODE" --force >/dev/null

echo "local-system-one-hermes mode for '$PROFILE': $MODE"
