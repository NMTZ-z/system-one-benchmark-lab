#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-default}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"
HOME_DIR="$(require_hermes_profile "$PROFILE")"
TARGET="$HOME_DIR/plugins/$PLUGIN_ID"
OWNERSHIP="$ROOT/scripts/hermes_system_one_ownership.py"
CONTROL="$ROOT/integrations/hermes/local-system-one-hermes/__init__.py"

if [[ -L "$HOME_DIR/plugins" || -L "$TARGET" ]]; then
  echo "Refusing a symbolic-link plugin directory." >&2
  exit 1
fi
if [[ -e "$TARGET" ]]; then python3 "$OWNERSHIP" verify "$TARGET"; fi
python3 "$CONTROL" "$HOME_DIR" off

if [[ -d "$TARGET" ]]; then
  MEMORY_PROVIDER="$(HERMES_HOME="$HOME_DIR" hermes config get memory.provider 2>/dev/null || true)"
  if [[ "$MEMORY_PROVIDER" == "$PLUGIN_ID" ]]; then
    echo "Removal would change the selected memory provider; resolve that setting first." >&2
    exit 1
  fi
  HERMES_HOME="$HOME_DIR" hermes plugins remove "$PLUGIN_ID" >/dev/null
  if [[ -d "$TARGET" ]]; then python3 "$OWNERSHIP" remove "$TARGET"; fi
fi
if HERMES_HOME="$HOME_DIR" hermes config get plugins.entries.local-system-one-hermes >/dev/null 2>&1; then
  HERMES_HOME="$HOME_DIR" hermes config unset plugins.entries.local-system-one-hermes >/dev/null
fi
python3 "$OWNERSHIP" remove-sessions "$HOME_DIR/plugin-data/local-system-one-hermes.sessions"
while IFS= read -r state_dir; do
  [[ -n "$state_dir" ]] || continue
  if [[ -L "$state_dir/state.json" || -L "$state_dir/.state.json.lock" ]]; then
    echo "State contains a symbolic link; remaining: $state_dir" >&2
    exit 1
  fi
  rm -f "$state_dir/state.json" "$state_dir/.state.json.lock"
  if ! rmdir "$state_dir" 2>/dev/null; then
    echo "Unrecognized state files remain at $state_dir" >&2
    exit 1
  fi
done < <(plugin_state_dirs "$HOME_DIR")
CONTROL_FILE="$HOME_DIR/plugin-data/local-system-one-hermes.control"
if [[ -L "$CONTROL_FILE" ]]; then echo "Control file is a symbolic link: $CONTROL_FILE" >&2; exit 1; fi
rm -f "$CONTROL_FILE"

echo "Removed owned $PLUGIN_ID files from profile '$PROFILE'."
echo "Older loaded plugin versions require a Hermes reload; their effective state is UNKNOWN."
echo "Check and stop any separately running Local System One Runtime."
