#!/bin/zsh
set -euo pipefail

label="ai.localsystemone.service"
uid="$(id -u)"
url="${LOCAL_SYSTEM_ONE_URL:-http://127.0.0.1:8787}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
python="$repo/.venv/bin/python"
[[ -x "$python" ]] || python="$(command -v python3)"

echo "== launchd =="
if launchctl print "gui/$uid/$label" >/dev/null 2>&1; then
  echo "loaded: $label"
else
  echo "not loaded: $label"
fi

echo
echo "== health =="
if PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}" "$python" - "$url" <<'PY'
import json
import os
import sys
from local_system_one.client import LocalSystemOneClient
from local_system_one.security import access_token_path

token = os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN")
path = os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE") or (None if token else access_token_path())
try:
    print(json.dumps(LocalSystemOneClient(sys.argv[1], auth_token=token, auth_token_file=path, timeout=3).health()))
except (RuntimeError, ValueError):
    raise SystemExit(1) from None
PY
then
  echo
else
  echo "service unavailable at $url" >&2
  exit 1
fi
