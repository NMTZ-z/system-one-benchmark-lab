#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-}"
if [[ -z "$PROFILE" ]]; then
  echo "Usage: $0 <hermes-profile>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/integrations/hermes/local-system-one-hermes"
HOME_DIR="$HOME/.hermes/profiles/$PROFILE"
TARGET="$HOME_DIR/plugins/local-system-one-hermes"

if [[ ! -d "$HOME_DIR" ]]; then
  echo "Hermes profile not found: $PROFILE" >&2
  exit 1
fi

mkdir -p "$HOME_DIR/plugins"
rm -rf "$TARGET"
cp -R "$SOURCE" "$TARGET"

# Safe-by-default installation: enabled plugin, behavior mode OFF.
HERMES_HOME="$HOME_DIR" hermes config set   plugins.entries.local-system-one-hermes.settings.mode off --force >/dev/null
HERMES_HOME="$HOME_DIR" hermes config set   plugins.entries.local-system-one-hermes.settings.service_url   http://127.0.0.1:8787 --force >/dev/null
HERMES_HOME="$HOME_DIR" hermes config set   plugins.entries.local-system-one-hermes.settings.timeout_ms 500 --force >/dev/null

HERMES_HOME="$HOME_DIR" hermes plugins enable   local-system-one-hermes --no-allow-tool-override >/dev/null

echo "Installed local-system-one-hermes into profile '$PROFILE' in OFF mode."
echo "Enable observation with:"
echo "  $ROOT/scripts/set_hermes_system_one_mode.sh $PROFILE shadow"
