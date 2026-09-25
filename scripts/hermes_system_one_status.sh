#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-default}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"
HOME_DIR="$(require_hermes_profile "$PROFILE")"
TARGET="$HOME_DIR/plugins/$PLUGIN_ID"

echo "== profile =="
echo "name: $PROFILE"
echo "home: $HOME_DIR"

echo
echo "== plugin =="
if [[ -d "$TARGET" ]]; then
  HERMES_HOME="$HOME_DIR" hermes plugins show "$PLUGIN_ID" 2>/dev/null || true
else
  echo "not installed"
fi

echo
echo "== configured settings =="
for key in mode service_url timeout_ms search_gate_enabled model_tier_gate_enabled canary_acknowledged canary_web_filter_enabled canary_reasoning_downgrade_enabled; do
  value="$(HERMES_HOME="$HOME_DIR" hermes config get "plugins.entries.local-system-one-hermes.settings.$key" 2>/dev/null || true)"
  [[ -n "$value" ]] || value="(manifest default)"
  printf '%-38s %s\n' "$key:" "$value"
done

echo
echo "== effective runtime status =="
STATE_DIR="$(plugin_state_dirs "$HOME_DIR" | head -1 || true)"
STATE_FILE=""
[[ -n "$STATE_DIR" ]] && STATE_FILE="$STATE_DIR/state.json"
if [[ -n "$STATE_FILE" && -f "$STATE_FILE" ]]; then
  python3 - "$STATE_FILE" <<'PY'
import json, sys
p=sys.argv[1]
try:
    status=json.load(open(p)).get("status")
except Exception:
    status=None
if isinstance(status, dict):
    keep=("version","requested_mode","mode","profile","service_url","timeout_ms","search_gate_enabled","model_tier_gate_enabled","canary_acknowledged","canary_web_filter_enabled","canary_reasoning_downgrade_enabled")
    print(json.dumps({k:status.get(k) for k in keep if k in status},ensure_ascii=False,indent=2))
else:
    print("no runtime status yet (start a new Hermes session after changing settings)")
PY
else
  echo "no runtime status yet"
fi

SERVICE_URL="$(HERMES_HOME="$HOME_DIR" hermes config get plugins.entries.local-system-one-hermes.settings.service_url 2>/dev/null || true)"
[[ -n "$SERVICE_URL" ]] || SERVICE_URL="http://127.0.0.1:8787"
echo
echo "== Local System One =="
curl -fsS --max-time 2 "$SERVICE_URL/health" || echo "unreachable: $SERVICE_URL"
echo
