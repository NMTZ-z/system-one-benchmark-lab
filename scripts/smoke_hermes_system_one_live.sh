#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-systemoneeval}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"

case "$PROFILE" in
  systemoneeval|*test*|*eval*) ;;
  *)
    if [[ "${LOCAL_SYSTEM_ONE_ALLOW_PRODUCTION_SMOKE:-0}" != "1" ]]; then
      echo "Refusing live smoke against non-evaluation profile '$PROFILE'." >&2
      echo "Use an eval/test profile, or set LOCAL_SYSTEM_ONE_ALLOW_PRODUCTION_SMOKE=1 explicitly." >&2
      exit 2
    fi
    ;;
esac

HOME_DIR="$(require_hermes_profile "$PROFILE")"
TARGET="$HOME_DIR/plugins/$PLUGIN_ID"
[[ -d "$TARGET" ]] || { echo "$PLUGIN_ID is not installed in '$PROFILE'." >&2; exit 1; }

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes executable not found in PATH." >&2
  exit 1
fi

STATE_DIR="$(plugin_state_dirs "$HOME_DIR" | head -1 || true)"
STATE_FILE="${STATE_DIR:+$STATE_DIR/state.json}"
[[ -n "$STATE_FILE" && -f "$STATE_FILE" ]] || {
  echo "plugin runtime state not found; start one Hermes turn in '$PROFILE' first." >&2
  exit 1
}

get_config() {
  HERMES_HOME="$HOME_DIR" hermes config get "$1" 2>/dev/null
}

capture_config() {
  local key="$1"
  local value
  if value="$(get_config "$key")"; then
    printf 'set\t%s\n' "$value"
  else
    printf 'unset\t\n'
  fi
}

MODE_KEY="plugins.entries.local-system-one-hermes.settings.mode"
ACK_KEY="plugins.entries.local-system-one-hermes.settings.canary_acknowledged"
URL_KEY="plugins.entries.local-system-one-hermes.settings.service_url"

MODE_ORIG="$(capture_config "$MODE_KEY")"
ACK_ORIG="$(capture_config "$ACK_KEY")"
URL_ORIG="$(capture_config "$URL_KEY")"

restore_key() {
  local key="$1" captured="$2"
  local state value
  state="${captured%%$'\t'*}"
  value="${captured#*$'\t'}"
  if [[ "$state" == "set" ]]; then
    if [[ "$key" == "$MODE_KEY" && "$value" == "off" ]]; then
      HERMES_HOME="$HOME_DIR" hermes config unset "$key" >/dev/null 2>&1 || true
    else
      HERMES_HOME="$HOME_DIR" hermes config set "$key" "$value" --force >/dev/null
    fi
  else
    HERMES_HOME="$HOME_DIR" hermes config unset "$key" >/dev/null 2>&1 || true
  fi
}

restore() {
  restore_key "$URL_KEY" "$URL_ORIG"
  restore_key "$ACK_KEY" "$ACK_ORIG"
  restore_key "$MODE_KEY" "$MODE_ORIG"
}
trap restore EXIT

shadow_count() {
  python3 - "$STATE_FILE" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1], encoding="utf-8")).get("shadow_history", [])))
PY
}

echo "Hermes/System One live smoke: profile=$PROFILE"

"$ROOT/scripts/set_hermes_system_one_mode.sh" "$PROFILE" off >/dev/null
before="$(shadow_count)"
hermes -p "$PROFILE" -z "只回复 OFF_OK" >/dev/null
after="$(shadow_count)"
[[ "$before" == "$after" ]] || {
  echo "FAIL: OFF mode called Local System One ($before -> $after)." >&2
  exit 1
}
echo "PASS off: no System One call"

"$ROOT/scripts/set_hermes_system_one_mode.sh" "$PROFILE" shadow >/dev/null
hermes -p "$PROFILE" -z "把这句话改写得更简洁：今天下午三点我们需要召开一次项目会议。" >/dev/null
python3 - "$STATE_FILE" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
e=d.get("last_shadow") or {}
assert e.get("ok") is True, e
assert (d.get("status") or {}).get("mode") == "shadow", d.get("status")
n=d.get("last_notification_shadow") or {}
assert n.get("ok") is True, n
assert int(n.get("event_chars", 0)) > 0, n
assert (n.get("notification") or {}).get("delivery") in {"silent", "digest", "notify_now"}, n
PY
echo "PASS shadow: Search/Model Tier observed; Notification Shadow observed; no mutation"

"$ROOT/scripts/set_hermes_system_one_mode.sh" "$PROFILE" canary --ack-canary >/dev/null
hermes -p "$PROFILE" -z "把“今天下午三点我们需要召开一次项目会议”改写得更简洁。" >/dev/null
canary_ts="$(python3 - "$STATE_FILE" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
e=d.get("last_canary") or {}
assert e.get("changed") is True, e
removed=set(e.get("removed_tools") or [])
assert {"web_search", "web_extract"} <= removed, e
print(e.get("ts"))
PY
)"
echo "PASS canary: deterministic web tools filtered"

HERMES_HOME="$HOME_DIR" hermes config set "$URL_KEY" http://127.0.0.1:9 --force >/dev/null
hermes -p "$PROFILE" -z "把“测试失败开放机制”改写得更自然。" >/dev/null
python3 - "$STATE_FILE" "$canary_ts" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
previous=float(sys.argv[2])
shadow=d.get("last_shadow") or {}
assert shadow.get("ok") is False, shadow
assert shadow.get("error"), shadow
canary=d.get("last_canary") or {}
assert float(canary.get("ts", 0)) == previous, (previous, canary)
PY
echo "PASS fail-open: Runtime failure preserved Hermes request"

restore
trap - EXIT
echo "PASS restored original plugin settings"
