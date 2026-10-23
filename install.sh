#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SOURCE="$SCRIPT_DIR/setup-plausible"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
SKILL_DESTINATION="$CODEX_ROOT/skills/setup-plausible"
BIN_DESTINATION="$HOME/.local/bin"
PLAUSIBLE_ORIGIN=""

usage() {
  echo "Usage: ./install.sh [--plausible-url https://plausible.example.com]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plausible-url)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      PLAUSIBLE_ORIGIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

for REQUIRED_COMMAND in python3 security expect; do
  if ! command -v "$REQUIRED_COMMAND" >/dev/null 2>&1; then
    echo "Required command is unavailable: $REQUIRED_COMMAND" >&2
    exit 1
  fi
done

mkdir -p "$SKILL_DESTINATION" "$BIN_DESTINATION"
rsync -a "$SKILL_SOURCE/" "$SKILL_DESTINATION/"
install -m 755 "$SKILL_SOURCE/scripts/plausible-setup" "$BIN_DESTINATION/plausible-setup"
install -m 755 "$SKILL_SOURCE/scripts/plausible-keychain-store" "$BIN_DESTINATION/plausible-keychain-store"

install -m 755 "$SKILL_SOURCE/scripts/plausible" "$BIN_DESTINATION/plausible"

echo "Installed CLI in $BIN_DESTINATION/plausible"
echo "Installed Codex skill in $SKILL_DESTINATION"
echo "Installed CLI in $BIN_DESTINATION/plausible-setup"

if [[ -n "$PLAUSIBLE_ORIGIN" ]]; then
  "$BIN_DESTINATION/plausible-setup" configure --plausible-url "$PLAUSIBLE_ORIGIN"
else
  echo "Next: plausible-setup configure --plausible-url https://plausible.example.com"
fi

case ":$PATH:" in
  *":$BIN_DESTINATION:"*) ;;
  *) echo "Add $BIN_DESTINATION to PATH before running plausible-setup." ;;
esac
