#!/bin/zsh
set -euo pipefail

label="ai.localsystemone.service"
uid="$(id -u)"
plist="$HOME/Library/LaunchAgents/$label.plist"

launchctl bootout "gui/$uid" "$plist" 2>/dev/null || true
rm -f "$plist"

echo "Uninstalled $label"