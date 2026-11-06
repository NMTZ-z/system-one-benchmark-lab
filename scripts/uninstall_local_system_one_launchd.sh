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
confirm_stopped=false
if [[ "${1:-}" == "--confirm-stopped" && $# == 1 ]]; then
  confirm_stopped=true
elif [[ $# != 0 ]]; then
  echo "Usage: $0 [--confirm-stopped]" >&2
  exit 2
fi

"$python" "$helper" verify "$repo" "$plist" "$logs"
if ! launchctl bootout "gui/$uid" "$plist"; then
  if launchctl print "gui/$uid/$label" >/dev/null 2>&1 || [[ "$confirm_stopped" != true ]]; then
    echo "LaunchAgent state is unknown or still running; its credential was retained. Verify it has stopped before using --confirm-stopped." >&2
    exit 1
  fi
fi
"$python" "$helper" remove "$repo" "$plist" "$logs"
echo "Uninstalled $label and removed its owned Runtime credential."
