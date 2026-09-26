#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-default}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"
HOME_DIR="$(require_hermes_profile "$PROFILE")"
TARGET="$HOME_DIR/plugins/$PLUGIN_ID"

# Stop behavior before deleting code. All commands are idempotent by design.
if [[ -d "$TARGET" ]]; then
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.mode off --force >/dev/null 2>&1 || true
  HERMES_HOME="$HOME_DIR" hermes plugins disable "$PLUGIN_ID" >/dev/null 2>&1 || true
  HERMES_HOME="$HOME_DIR" hermes plugins remove "$PLUGIN_ID" >/dev/null 2>&1 || true
fi

rm -rf "$TARGET"
# Defensive cleanup in case the install was a manually copied development build.
HERMES_HOME="$HOME_DIR" hermes config unset plugins.entries.local-system-one-hermes >/dev/null 2>&1 || true
while IFS= read -r state_dir; do
  [[ -n "$state_dir" ]] && rm -rf "$state_dir"
done < <(plugin_state_dirs "$HOME_DIR")

echo "Removed $PLUGIN_ID from profile '$PROFILE'."
echo "Plugin code, plugin settings, and Local System One plugin state were removed."
echo "Hermes itself and other plugins were not modified."