#!/usr/bin/env bash
set -euo pipefail
PURGE="${1:-}"
rm -f "${HOME}/.local/bin/forgefetch"
rm -f "${HOME}/.local/share/applications/forgefetch.desktop"
if [[ "$PURGE" == "--purge" ]]; then
  rm -rf "${HOME}/.config/forgefetch"
  echo "ForgeFetch removed, including local preferences."
else
  echo "ForgeFetch launcher removed. Preferences in ~/.config/forgefetch were kept."
  echo "To remove preferences too: ./uninstall.sh --purge"
fi
