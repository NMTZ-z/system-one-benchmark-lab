#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="local-system-one-hermes"
HERMES_ROOT="${LOCAL_SYSTEM_ONE_HERMES_ROOT:-$HOME/.hermes}"

resolve_hermes_profile_home() {
  local profile="${1:-default}"
  if [[ "$profile" == "default" ]]; then
    printf '%s\n' "$HERMES_ROOT"
  else
    printf '%s\n' "$HERMES_ROOT/profiles/$profile"
  fi
}

require_hermes_profile() {
  local profile="${1:-default}"
  local home_dir
  home_dir="$(resolve_hermes_profile_home "$profile")"
  if [[ ! -d "$home_dir" ]]; then
    echo "Hermes profile not found: $profile ($home_dir)" >&2
    return 1
  fi
  printf '%s\n' "$home_dir"
}

plugin_state_dirs() {
  local home_dir="$1"
  local base="$home_dir/plugin-data"
  [[ -d "$base" ]] || return 0
  find "$base" -maxdepth 1 -type d -name 'agent-plugin-local-system-one-hermes-*' -print
}