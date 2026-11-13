#!/usr/bin/env bash
set -euo pipefail
rm -f "${HOME}/.local/bin/forgefetch"
rm -f "${HOME}/.local/share/applications/forgefetch.desktop"
echo "ForgeFetch launcher removed. Your preferences in ~/.config/forgefetch were kept."
echo "To remove preferences too: rm -r ~/.config/forgefetch"
