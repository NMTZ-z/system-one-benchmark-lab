#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-default}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=hermes_system_one_common.sh
source "$ROOT/scripts/hermes_system_one_common.sh"

SOURCE="$ROOT/integrations/hermes/local-system-one-hermes"
HOME_DIR="$(require_hermes_profile "$PROFILE")"
PLUGINS_DIR="$HOME_DIR/plugins"
TARGET="$PLUGINS_DIR/$PLUGIN_ID"
FIRST_INSTALL=true
PLUGIN_VERSION="$(awk '/^version:/ {print $2; exit}' "$SOURCE/plugin.yaml")"

hermes plugins validate "$SOURCE" >/dev/null
mkdir -p "$PLUGINS_DIR"

if [[ -e "$TARGET" ]]; then
  FIRST_INSTALL=false
  if [[ ! -f "$TARGET/plugin.yaml" ]] || ! grep -Eq '^name:[[:space:]]+local-system-one-hermes[[:space:]]*$' "$TARGET/plugin.yaml"; then
    echo "Refusing to overwrite non-matching plugin directory: $TARGET" >&2
    exit 1
  fi
fi

STAGE="$(mktemp -d "$PLUGINS_DIR/.local-system-one-hermes.install.XXXXXX")"
BACKUP=""
cleanup() {
  rm -rf "$STAGE" 2>/dev/null || true
  if [[ -n "$BACKUP" && -d "$BACKUP" ]]; then
    rm -rf "$BACKUP" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Copy only the publishable runtime package. Never ship local bytecode/cache.
cp "$SOURCE/__init__.py" "$SOURCE/plugin.yaml" "$STAGE/"
[[ -f "$SOURCE/README.md" ]] && cp "$SOURCE/README.md" "$STAGE/"

if [[ "$FIRST_INSTALL" == false ]]; then
  BACKUP="$PLUGINS_DIR/.local-system-one-hermes.backup.$$"
  mv "$TARGET" "$BACKUP"
fi

if ! mv "$STAGE" "$TARGET"; then
  if [[ -n "$BACKUP" && -d "$BACKUP" ]]; then
    mv "$BACKUP" "$TARGET"
    BACKUP=""
  fi
  exit 1
fi

# Validate the exact installed bytes before changing activation/config.
if ! HERMES_HOME="$HOME_DIR" hermes plugins validate "$TARGET" >/dev/null; then
  rm -rf "$TARGET"
  if [[ -n "$BACKUP" && -d "$BACKUP" ]]; then
    mv "$BACKUP" "$TARGET"
    BACKUP=""
  fi
  echo "Installed plugin failed Hermes validation; previous version restored." >&2
  exit 1
fi

if [[ "$FIRST_INSTALL" == true ]]; then
  # First install is explicit and inert. Manifest defaults cover every other setting.
  HERMES_HOME="$HOME_DIR" hermes config unset \
    plugins.entries.local-system-one-hermes.settings.mode >/dev/null 2>&1 || true
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.canary_acknowledged false --force >/dev/null
  HERMES_HOME="$HOME_DIR" hermes plugins enable \
    local-system-one-hermes --no-allow-tool-override >/dev/null
  echo "Installed $PLUGIN_ID v$PLUGIN_VERSION into '$PROFILE' in OFF mode."
else
  # Preserve the user's existing enabled/disabled state and all settings on upgrades.
  echo "Updated $PLUGIN_ID in '$PROFILE'; existing settings and activation state preserved."
fi

if ! curl -fsS --max-time 2 http://127.0.0.1:8787/health >/dev/null 2>&1; then
  echo "Note: Local System One is currently unreachable at http://127.0.0.1:8787." >&2
  echo "The plugin remains safe: OFF does nothing, and Shadow/Canary fail open." >&2
fi

echo "Status: $ROOT/scripts/hermes_system_one_status.sh $PROFILE"
echo "Shadow: $ROOT/scripts/set_hermes_system_one_mode.sh $PROFILE shadow"
