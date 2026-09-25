#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"

PROFILE=""
MODE=""
ACK=false

if [[ "${1:-}" =~ ^(off|shadow|canary)$ ]]; then
  PROFILE="default"
  MODE="$1"
  [[ "${2:-}" == "--ack-canary" ]] && ACK=true
else
  PROFILE="${1:-default}"
  MODE="${2:-}"
  [[ "${3:-}" == "--ack-canary" ]] && ACK=true
fi

if [[ -z "$MODE" ]]; then
  echo "Usage: $0 [profile] <off|shadow|canary> [--ack-canary]" >&2
  exit 2
fi

case "$MODE" in
  off|shadow) ;;
  canary)
    if [[ "$ACK" != true ]]; then
      echo "Refusing Canary without explicit acknowledgement." >&2
      echo "Re-run with: $0 $PROFILE canary --ack-canary" >&2
      exit 2
    fi
    ;;
  *)
    echo "Unsupported mode '$MODE'. Allowed: off, shadow, canary." >&2
    exit 2
    ;;
esac

HOME_DIR="$(require_hermes_profile "$PROFILE")"
if [[ ! -d "$HOME_DIR/plugins/$PLUGIN_ID" ]]; then
  echo "$PLUGIN_ID is not installed in profile '$PROFILE'." >&2
  exit 1
fi

if [[ "$MODE" == "canary" ]]; then
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.canary_acknowledged true --force >/dev/null
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.mode canary --force >/dev/null
elif [[ "$MODE" == "shadow" ]]; then
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.mode shadow --force >/dev/null
else
  # Hermes YAML-coerces bare `off` to boolean false. Unset uses the plugin's
  # declared/default string `off` without dirtying config.yaml with the wrong type.
  HERMES_HOME="$HOME_DIR" hermes config unset \
    plugins.entries.local-system-one-hermes.settings.mode >/dev/null 2>&1 || true
fi

if [[ "$MODE" != "canary" ]]; then
  # Leaving Canary revokes acknowledgement so a future Canary requires another explicit action.
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.canary_acknowledged false --force >/dev/null
fi

echo "$PLUGIN_ID mode for '$PROFILE': $MODE"
if [[ "$MODE" == "canary" ]]; then
  echo "Canary acknowledgement: enabled for this profile"
fi
