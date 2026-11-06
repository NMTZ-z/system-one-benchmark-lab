#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="local-system-one-hermes"
HERMES_ROOT="${LOCAL_SYSTEM_ONE_HERMES_ROOT:-$HOME/.hermes}"

resolve_hermes_profile_home() {
  local profile="${1:-default}"
  if [[ ! "$profile" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]]; then
    echo "Invalid profile name: use letters, digits, '-' or '_'." >&2
    return 1
  fi
  if [[ -L "$HERMES_ROOT/profiles" ]]; then
    echo "Refusing a symbolic-link profiles directory." >&2
    return 1
  fi
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
  if [[ ! -d "$home_dir" || -L "$home_dir" ]]; then
    echo "Hermes profile not found: $profile ($home_dir)" >&2
    return 1
  fi
  printf '%s\n' "$home_dir"
}

hermes_profile_setting() {
  local home_dir="$1" key="$2" value
  if ! value="$(HERMES_HOME="$home_dir" hermes config get "plugins.entries.$PLUGIN_ID.settings.$key" 2>/dev/null)"; then
    if ! value="$(HERMES_HOME="$home_dir" hermes config get "plugins.entries.$PLUGIN_ID.config.$key" 2>/dev/null)"; then
      return 0
    fi
  fi
  printf '%s' "$value"
}

plugin_state_dirs() {
  local home_dir="$1"
  local base="$home_dir/plugin-data"
  [[ -d "$base" ]] || return 0
  local suffix
  suffix="$(python3 -c 'import hashlib; print(hashlib.sha256(b"local-system-one-hermes").hexdigest()[:8])')"
  [[ -d "$base/agent-plugin-local-system-one-hermes-$suffix" && ! -L "$base/agent-plugin-local-system-one-hermes-$suffix" ]] && printf '%s\n' "$base/agent-plugin-local-system-one-hermes-$suffix"
  return 0
}
