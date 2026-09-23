#!/bin/zsh
set -euo pipefail

service="${TYPESAFE_KEYCHAIN_SERVICE:-typesafe-systemone}"
account="${TYPESAFE_KEYCHAIN_ACCOUNT:-$USER}"

echo "Store the TypeSafe API key in macOS Keychain."
echo "Service: $service"
echo "Account: $account"
echo "The key will be entered by the macOS security CLI and will not be echoed."
security add-generic-password \
  -U \
  -a "$account" \
  -s "$service" \
  -l "TypeSafe SystemOne API" \
  -w

echo "TypeSafe API key stored in Keychain."
