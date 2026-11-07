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
OWNERSHIP="$ROOT/scripts/hermes_system_one_ownership.py"

HERMES_HOME="$HOME_DIR" hermes plugins validate "$SOURCE" >/dev/null
if [[ -L "$PLUGINS_DIR" || -L "$TARGET" ]]; then
  echo "Refusing a symbolic-link plugin directory." >&2
  exit 1
fi
mkdir -p "$PLUGINS_DIR"

if [[ -e "$TARGET" ]]; then
  FIRST_INSTALL=false
  python3 "$OWNERSHIP" verify "$TARGET"
  OLD_VERSION="$(awk '/^version:/ {print $2; exit}' "$TARGET/plugin.yaml")"
  [[ "$OLD_VERSION" =~ ^[A-Za-z0-9.+_-]+$ ]] || OLD_VERSION="UNKNOWN"
  echo "Upgrade in profile '$PROFILE': $OLD_VERSION -> $PLUGIN_VERSION"
  for key in mode search_gate_enabled model_tier_gate_enabled notification_gate_enabled completion_gate_enabled retry_escalation_gate_enabled completion_loop_probe_enabled; do
    value="$(hermes_profile_setting "$HOME_DIR" "$key")"
    if [[ -z "$value" ]]; then
      value="$(awk -v key="$key" '$0 == "  " key ":" {found=1; next} found && /^  [A-Za-z_]/ {exit} found && /^    default:/ {print $2; exit}' "$TARGET/plugin.yaml" | tr -d '"')"
    fi
    case "$value" in off|shadow|canary|true|false|True|False) ;; *) value="UNKNOWN";; esac
    printf '  %s: %s\n' "$key" "$value"
  done
  echo "Existing activation and explicit settings will be preserved."
fi

STAGE="$(mktemp -d "$PLUGINS_DIR/.local-system-one-hermes.install.XXXXXX")"
BACKUP=""
COMMITTED=false
CONFIG_STARTED=false
cleanup() {
  local result=$?
  if [[ -n "$BACKUP" && -d "$BACKUP" ]]; then
    if [[ "$COMMITTED" == true ]]; then
      python3 "$OWNERSHIP" remove "$BACKUP" || { echo "Backup remains at $BACKUP" >&2; result=1; }
    else
      if [[ -d "$TARGET" ]] && ! python3 "$OWNERSHIP" remove "$TARGET"; then
        echo "Rollback needs manual attention; previous plugin remains at $BACKUP" >&2
        result=1
      elif ! mv "$BACKUP" "$TARGET"; then
        echo "Rollback needs manual attention; previous plugin remains at $BACKUP" >&2
        result=1
      fi
    fi
  elif [[ "$COMMITTED" != true && "$FIRST_INSTALL" == true && -d "$TARGET" ]]; then
    python3 "$OWNERSHIP" remove "$TARGET" || echo "Partial installation remains at $TARGET" >&2
  fi
  if [[ "$COMMITTED" != true && "$FIRST_INSTALL" == true && "$CONFIG_STARTED" == true ]]; then
    echo "Profile configuration or control state may remain; inspect prior settings before running local-system-one uninstall --profile $PROFILE." >&2
  fi
  if [[ -d "$STAGE" ]]; then
    rm -f "$STAGE/__init__.py" "$STAGE/plugin.yaml" "$STAGE/README.md" "$STAGE/.local-system-one-install.json"
    rmdir "$STAGE" 2>/dev/null || echo "Staging directory remains at $STAGE" >&2
  fi
  return "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Copy only the publishable runtime package. Never ship local bytecode/cache.
cp "$SOURCE/__init__.py" "$SOURCE/plugin.yaml" "$STAGE/"
[[ -f "$SOURCE/README.md" ]] && cp "$SOURCE/README.md" "$STAGE/"
python3 "$OWNERSHIP" mark "$STAGE"

if [[ "$FIRST_INSTALL" == false ]]; then
  BACKUP="$(mktemp -d "$PLUGINS_DIR/.local-system-one-hermes.backup.XXXXXX")"
  rmdir "$BACKUP"
  mv "$TARGET" "$BACKUP"
fi

if ! mv "$STAGE" "$TARGET"; then
  exit 1
fi

# Validate the exact installed bytes before changing activation/config.
if ! HERMES_HOME="$HOME_DIR" hermes plugins validate "$TARGET" >/dev/null; then
  echo "Installed plugin failed Hermes validation; attempting rollback." >&2
  exit 1
fi

if [[ "$FIRST_INSTALL" == true ]]; then
  CONFIG_STARTED=true
  python3 "$SOURCE/__init__.py" "$HOME_DIR" off
  # First install is explicit and inert. Manifest defaults cover every other setting.
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.mode false --force >/dev/null
  HERMES_HOME="$HOME_DIR" hermes config set \
    plugins.entries.local-system-one-hermes.settings.canary_acknowledged false --force >/dev/null
  HERMES_HOME="$HOME_DIR" hermes plugins enable \
    local-system-one-hermes --no-allow-tool-override >/dev/null
  echo "Installed $PLUGIN_ID v$PLUGIN_VERSION into '$PROFILE' in OFF mode."
else
  # Preserve the user's existing enabled/disabled state and all settings on upgrades.
  echo "Updated $PLUGIN_ID in '$PROFILE'; existing settings and activation state preserved."
  echo "Reload Hermes to use the updated plugin; older loaded versions remain UNKNOWN."
fi
COMMITTED=true

echo "Status: $ROOT/scripts/hermes_system_one_status.sh $PROFILE"
echo "Shadow: $ROOT/scripts/set_hermes_system_one_mode.sh $PROFILE shadow"
