#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
mkdir -p "$BIN_DIR" "$APP_DIR"
install -m 0755 "$ROOT/forgefetch.py" "$BIN_DIR/forgefetch"
cat > "$APP_DIR/forgefetch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ForgeFetch
Comment=Customizable Linux system summary
Exec=${BIN_DIR}/forgefetch
Terminal=true
Categories=System;Utility;
EOF
chmod 0644 "$APP_DIR/forgefetch.desktop"
if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  echo "Note: add ${BIN_DIR} to PATH if 'forgefetch' is not found."
  echo 'For Bash: echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
fi
echo "ForgeFetch 1.0.0 installed."
echo "Command: ${BIN_DIR}/forgefetch"
echo "Launch: forgefetch"
echo "Customize: forgefetch --setup"
