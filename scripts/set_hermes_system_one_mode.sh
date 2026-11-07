#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"

PROFILE=""
MODE=""
ACK=false
ALLOW_REMOTE=false

if [[ "${1:-}" =~ ^(off|shadow|canary)$ ]]; then
  PROFILE="default"
  MODE="$1"
  [[ "${2:-}" == "--ack-canary" ]] && ACK=true
  [[ "${2:-}" == "--allow-remote" ]] && ALLOW_REMOTE=true
else
  PROFILE="${1:-default}"
  MODE="${2:-}"
  [[ "${3:-}" == "--ack-canary" ]] && ACK=true
  [[ "${3:-}" == "--allow-remote" ]] && ALLOW_REMOTE=true
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

CONTROL="$ROOT/integrations/hermes/local-system-one-hermes/__init__.py"

if [[ "$MODE" == "off" ]]; then
  # Wait for fenced calls to finish before changing the saved configuration.
  python3 "$CONTROL" "$HOME_DIR" off
else
  SERVICE_URL="$(hermes_profile_setting "$HOME_DIR" service_url)"
  [[ -n "$SERVICE_URL" ]] || SERVICE_URL="http://127.0.0.1:8787"
  if ! LSO_CHECK_URL="$SERVICE_URL" LSO_ALLOW_REMOTE="$ALLOW_REMOTE" python3 - "$CONTROL" <<'PY'
import os, runpy, sys
check = runpy.run_path(sys.argv[1])["_sidecar_url_allowed"]
url = os.environ["LSO_CHECK_URL"]
allowed = os.environ["LSO_ALLOW_REMOTE"] == "true"
if not check(url, allowed):
    print("Invalid or unapproved sidecar. Remote HTTPS requires --allow-remote.", file=sys.stderr)
    raise SystemExit(1)
print("Sidecar:", url)
print("Non-local transmission:", "no" if check(url) else "YES (explicitly approved)")
PY
  then exit 1; fi
  echo "Data categories: bounded task, recent context and an opaque turn reference; optional gates may send response or failure context."
  echo "Enabled gates (explicit profile settings override defaults):"
  for item in search_gate_enabled:true model_tier_gate_enabled:false notification_gate_enabled:false completion_gate_enabled:false retry_escalation_gate_enabled:false completion_loop_probe_enabled:false; do
    key="${item%:*}"; default="${item#*:}"
    value="$(hermes_profile_setting "$HOME_DIR" "$key")"
    [[ -n "$value" ]] || value="$default"
    case "$value" in true|false|True|False) ;; *) echo "Invalid $key setting." >&2; exit 1;; esac
    printf '  %s: %s\n' "$key" "$value"
  done
  if [[ "$ALLOW_REMOTE" == true ]]; then
    HERMES_HOME="$HOME_DIR" hermes config set \
      plugins.entries.local-system-one-hermes.settings.allow_remote_sidecar true --force >/dev/null
  fi
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
  # The plugin maps false to OFF and masks any older legacy mode setting.
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.mode false --force >/dev/null
fi

if [[ "$MODE" != "canary" ]]; then
  # Leaving Canary revokes acknowledgement so a future Canary requires another explicit action.
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.canary_acknowledged false --force >/dev/null
fi

if [[ "$MODE" != "off" ]]; then
  python3 "$CONTROL" "$HOME_DIR" on
fi
echo "$PLUGIN_ID CONFIGURED mode for '$PROFILE': $MODE"
echo "EFFECTIVE: UNKNOWN until the selected Hermes session has reloaded and status is verified."
echo "OFF fences version 0.10 sessions; older loaded versions require a Hermes reload."
if [[ "$MODE" == "canary" ]]; then
  echo "Canary acknowledgement: enabled for this profile"
fi
