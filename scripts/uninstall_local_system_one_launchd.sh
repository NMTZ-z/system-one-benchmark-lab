#!/bin/zsh
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
label="ai.localsystemone.service"
uid="$(id -u)"
plist="$HOME/Library/LaunchAgents/$label.plist"
logs="$HOME/Library/Logs/LocalSystemOne"
python="$repo/.venv/bin/python"
[[ -x "$python" ]] || python="$(command -v python3)"
helper="$repo/scripts/local_system_one_launchd_credentials.py"

"$python" "$helper" verify "$repo" "$plist" "$logs"
if ! launchctl bootout "gui/$uid" "$plist"; then
  if ! launchctl print "gui/$uid" >/dev/null 2>&1 || launchctl print "gui/$uid/$label" >/dev/null 2>&1; then
    echo "LaunchAgent state is unknown or still running; its credential was retained." >&2
    exit 1
  fi
fi
"$python" "$helper" remove "$repo" "$plist" "$logs"
echo "Uninstalled $label and removed its owned Runtime credential."
