#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM_URL="https://github.com/mizorewww/laya-coreml.git"
UPSTREAM_COMMIT="4619e0483f07adf39068532e85b42ec2347edb83"
SOURCE="${LOCAL_SYSTEM_ONE_SOURCE:-laya-typed-decisions}"
LENGTH="${LOCAL_SYSTEM_ONE_ANE_LENGTH:-512}"
CHECKOUT="${LOCAL_SYSTEM_ONE_LAYA_COREML_CHECKOUT:-$ROOT/artifacts/upstream/laya-coreml-${UPSTREAM_COMMIT:0:12}}"
OUTPUT="${LOCAL_SYSTEM_ONE_ANE_BUILD_OUTPUT:-$ROOT/artifacts/models/typed421-body${LENGTH}-fp16}"
ITERATIONS="${LOCAL_SYSTEM_ONE_ANE_BUILD_ITERATIONS:-30}"
SKIP_PREDICT="${LOCAL_SYSTEM_ONE_ANE_SKIP_PREDICT:-1}"
PREPARE_ONLY=0

if [[ "${1:-}" == "--prepare-only" ]]; then
  PREPARE_ONLY=1
elif [[ -n "${1:-}" ]]; then
  echo "usage: $0 [--prepare-only]" >&2
  exit 2
fi

for command in git uv; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "$command is required." >&2
    exit 1
  }
done

if [[ ! "$LENGTH" =~ ^[0-9]+$ ]] || (( LENGTH < 16 )); then
  echo "LOCAL_SYSTEM_ONE_ANE_LENGTH must be an integer >= 16." >&2
  exit 2
fi

mkdir -p "$(dirname "$CHECKOUT")" "$(dirname "$OUTPUT")"

fresh_checkout=0
if [[ ! -d "$CHECKOUT/.git" ]]; then
  [[ ! -e "$CHECKOUT" ]] || {
    echo "checkout path exists but is not a Git repository: $CHECKOUT" >&2
    exit 1
  }
  git clone --filter=blob:none --no-checkout "$UPSTREAM_URL" "$CHECKOUT"
  fresh_checkout=1
fi

origin="$(git -C "$CHECKOUT" remote get-url origin)"
case "$origin" in
  "$UPSTREAM_URL"|https://github.com/mizorewww/laya-coreml) ;;
  *)
    echo "unexpected laya-coreml origin: $origin" >&2
    exit 1
    ;;
esac

if (( ! fresh_checkout )) && [[ -n "$(git -C "$CHECKOUT" status --porcelain)" ]]; then
  echo "refusing to modify dirty upstream checkout: $CHECKOUT" >&2
  exit 1
fi

if ! git -C "$CHECKOUT" cat-file -e "$UPSTREAM_COMMIT^{commit}" 2>/dev/null; then
  git -C "$CHECKOUT" fetch --depth=1 origin "$UPSTREAM_COMMIT"
fi
git -C "$CHECKOUT" checkout --detach --quiet "$UPSTREAM_COMMIT"

actual="$(git -C "$CHECKOUT" rev-parse HEAD)"
[[ "$actual" == "$UPSTREAM_COMMIT" ]] || {
  echo "upstream revision mismatch: $actual" >&2
  exit 1
}

if [[ -n "$(git -C "$CHECKOUT" status --porcelain)" ]]; then
  echo "upstream checkout is dirty after pinning: $CHECKOUT" >&2
  exit 1
fi

probe=(uv run --frozen --extra convert python -m experiments.ane_engineering.probe)

if (( PREPARE_ONLY )); then
  (
    cd "$CHECKOUT"
    "${probe[@]}" --help >/dev/null
  )
  echo "Prepared pinned laya-coreml checkout: $CHECKOUT"
  echo "Revision: $UPSTREAM_COMMIT"
  echo "Source alias: $SOURCE"
  echo "Planned output: $OUTPUT"
  exit 0
fi

[[ ! -e "$OUTPUT" ]] || {
  echo "refusing to overwrite ANE output: $OUTPUT" >&2
  exit 1
}

args=(
  --source "$SOURCE"
  --kind body
  --length "$LENGTH"
  --compute-units cpu_ne
  --output "$OUTPUT"
  --iterations "$ITERATIONS"
)
if [[ "$SKIP_PREDICT" == "1" ]]; then
  args+=(--skip-predict)
fi

echo "Building Typed Decisions 421M fixed ANE body"
echo "  upstream: $UPSTREAM_COMMIT"
echo "  source:   $SOURCE"
echo "  length:   $LENGTH"
echo "  output:   $OUTPUT"

(
  cd "$CHECKOUT"
  "${probe[@]}" "${args[@]}"
)

echo "ANE package ready: $OUTPUT/model.mlpackage"
echo "Manifest: $OUTPUT/manifest.json"
