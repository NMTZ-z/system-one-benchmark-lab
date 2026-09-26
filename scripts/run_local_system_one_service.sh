#!/bin/zsh
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
python="$repo/.venv/bin/python"
legacy_source="$repo/models/typed-decisions-source"
legacy_ane="$repo/experiments/phase4a/typed421-body512-fp16/model.mlpackage"
public_ane="$repo/artifacts/models/typed421-body512-fp16/model.mlpackage"

if [[ -n "${LOCAL_SYSTEM_ONE_SOURCE:-}" ]]; then
  source_model="$LOCAL_SYSTEM_ONE_SOURCE"
elif [[ -d "$legacy_source" ]]; then
  source_model="$legacy_source"
else
  source_model="laya-typed-decisions"
fi

if [[ -n "${LOCAL_SYSTEM_ONE_ANE_PACKAGE:-}" ]]; then
  ane_package="$LOCAL_SYSTEM_ONE_ANE_PACKAGE"
elif [[ -d "$legacy_ane" ]]; then
  ane_package="$legacy_ane"
else
  ane_package="$public_ane"
fi

host="${LOCAL_SYSTEM_ONE_HOST:-127.0.0.1}"
port="${LOCAL_SYSTEM_ONE_PORT:-8787}"

if [[ ! -x "$python" ]]; then
  echo "missing Python runtime: $python" >&2
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