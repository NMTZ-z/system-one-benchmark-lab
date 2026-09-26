#!/bin/zsh
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
label="ai.localsystemone.service"
uid="$(id -u)"
launch_agents="$HOME/Library/LaunchAgents"
logs="$HOME/Library/Logs/LocalSystemOne"
plist="$launch_agents/$label.plist"
runner="$repo/scripts/run_local_system_one_service.sh"

mkdir -p "$launch_agents" "$logs"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>$runner</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$repo</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$logs/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$logs/stderr.log</string>
</dict>
</plist>
EOF

plutil -lint "$plist"

launchctl bootout "gui/$uid" "$plist" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$plist"

echo "Installed $label"
echo "Plist: $plist"
echo "Logs: $logs"
echo "Health: http://127.0.0.1:8787/health"