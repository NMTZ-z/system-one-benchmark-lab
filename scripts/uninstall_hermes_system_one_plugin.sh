#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-}"
if [[ -z "$PROFILE" ]]; then
  echo "Usage: $0 <hermes-profile>" >&2
  exit 2
fi

HOME_DIR="$HOME/.hermes/profiles/$PROFILE"
if [[ ! -d "$HOME_DIR" ]]; then
  echo "Hermes profile not found: $PROFILE" >&2
  exit 1
fi

# Disable first so runtime behavior stops before files/config are removed.
HERMES_HOME="$HOME_DIR" hermes plugins disable local-system-one-hermes >/dev/null 2>&1 || true
HERMES_HOME="$HOME_DIR" hermes plugins remove local-system-one-hermes >/dev/null 2>&1 || true

# Defensive cleanup for manually copied development installs.
rm -rf "$HOME_DIR/plugins/local-system-one-hermes"

echo "Removed local-system-one-hermes from profile '$PROFILE'."
echo "Hermes remains usable without Local System One."
