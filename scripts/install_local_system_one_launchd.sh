#!/bin/zsh
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
label="ai.localsystemone.service"
uid="$(id -u)"
launch_agents="$HOME/Library/LaunchAgents"
logs="$HOME/Library/Logs/LocalSystemOne"
plist="$launch_agents/$label.plist"
python="$repo/.venv/bin/python"
[[ -x "$python" ]] || python="$(command -v python3)"
helper="$repo/scripts/local_system_one_launchd_credentials.py"

mkdir -p "$launch_agents" "$logs"
"$python" "$helper" prepare "$repo" "$plist" "$logs"
if ! plutil -lint "$plist"; then
  "$python" "$helper" remove "$repo" "$plist" "$logs"
  echo "LaunchAgent installation failed; its new credential was removed." >&2
  exit 1
fi
if ! launchctl bootstrap "gui/$uid" "$plist"; then
  if ! launchctl print "gui/$uid" >/dev/null 2>&1; then
    echo "LaunchAgent state is unknown; its configuration and credential were retained." >&2
    exit 1
  fi
  if launchctl print "gui/$uid/$label" >/dev/null 2>&1; then
    launchctl bootout "gui/$uid" "$plist" || exit 1
  fi
  "$python" "$helper" remove "$repo" "$plist" "$logs"
  echo "LaunchAgent installation failed; its new credential was removed." >&2
  exit 1
fi

echo "Installed $label with a private, dedicated Runtime credential."
echo "MCP profile: launchd"
echo "Plist: $plist"
echo "Logs: $logs"
