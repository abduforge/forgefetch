#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR="${FORGEFETCH_INSTALL_DIR:-$HOME/.local/bin}"
mkdir -p "$INSTALL_DIR"
install -m 755 "$SCRIPT_DIR/forgefetch.py" "$INSTALL_DIR/forgefetch"
printf 'ForgeFetch installed to %s/forgefetch\n' "$INSTALL_DIR"
case ":${PATH:-}:" in
  *":$INSTALL_DIR:"*) ;;
  *) printf 'Note: add %s to your PATH if the command is not found.\n' "$INSTALL_DIR" ;;
esac
