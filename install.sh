#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ForgeFetch requires Python 3.10 or newer." >&2
  exit 1
fi
python3 - "$ROOT/forgefetch.py" <<'PY'
import ast, pathlib, sys
source = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
ast.parse(source)
PY

mkdir -p "$BIN_DIR" "$APP_DIR"
install -m 0755 "$ROOT/forgefetch.py" "$BIN_DIR/forgefetch"
cat > "$APP_DIR/forgefetch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ForgeFetch
Comment=Customizable local Linux system summary
Exec=${BIN_DIR}/forgefetch
Terminal=true
Categories=System;Utility;
EOF
chmod 0644 "$APP_DIR/forgefetch.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "ForgeFetch 1.3.0 installed."
echo "Command: ${BIN_DIR}/forgefetch"
echo "Preferences are kept in ~/.config/forgefetch."
if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  echo "Add ${BIN_DIR} to PATH if the command is not found."
  echo 'For Bash: echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
fi
