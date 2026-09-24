#!/bin/zsh
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
python="$repo/.venv/bin/python"
source_model="${LOCAL_SYSTEM_ONE_SOURCE:-$repo/models/typed-decisions-source}"
ane_package="${LOCAL_SYSTEM_ONE_ANE_PACKAGE:-$repo/experiments/phase4a/typed421-body512-fp16/model.mlpackage}"
host="${LOCAL_SYSTEM_ONE_HOST:-127.0.0.1}"
port="${LOCAL_SYSTEM_ONE_PORT:-8787}"

if [[ ! -x "$python" ]]; then
  echo "missing Python runtime: $python" >&2
  exit 1
fi

if [[ ! -d "$source_model" ]]; then
  echo "missing source model: $source_model" >&2
  exit 1
fi

args=(
  -m local_system_one
  --source "$source_model"
  --host "$host"
  --port "$port"
)

if [[ -d "$ane_package" ]]; then
  args+=(--ane-package "$ane_package")
else
  echo "ANE package not found; starting MLX-only fallback mode." >&2
fi

cd "$repo"
exec "$python" "${args[@]}"
