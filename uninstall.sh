#!/usr/bin/env sh
set -eu
INSTALL_DIR="${FORGEFETCH_INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$INSTALL_DIR/forgefetch"
if [ -f "$TARGET" ]; then
  rm -- "$TARGET"
  printf 'Removed %s\n' "$TARGET"
else
  printf 'ForgeFetch executable not found at %s\n' "$TARGET"
fi
printf 'Configuration and reports were left untouched.\n'
