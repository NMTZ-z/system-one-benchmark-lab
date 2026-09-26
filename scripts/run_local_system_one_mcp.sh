#!/bin/zsh
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
service_url="${LOCAL_SYSTEM_ONE_URL:-http://127.0.0.1:8787}"

if [[ -x /opt/homebrew/bin/uv ]]; then
  uv_bin=/opt/homebrew/bin/uv
elif command -v uv >/dev/null 2>&1; then
  uv_bin="$(command -v uv)"
else
  echo "uv is required to run the optional MCP integration." >&2
  exit 1
fi

export LOCAL_SYSTEM_ONE_URL="$service_url"
cd "$repo"
exec "$uv_bin" run --with 'mcp>=2,<3' python -m local_system_one.mcp_server