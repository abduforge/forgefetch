# Changelog

## 1.3.0 — System intelligence and live view

- Expanded the system snapshot with CPU governor, load average, visible process count, and firmware boot mode.
- Added `--watch [SECONDS]` for a continuously refreshed terminal view, with interval validation and graceful Ctrl+C exit.
- Added `--no-network` to hide network interface names and local IP addresses from terminal, JSON, and Markdown output.
- Added `--no-color` as an alias for `--plain`.
- Includes the hardware, battery, network, Secure Boot, responsive layout, and safer configuration improvements prepared during development after 1.0.0.
- Remains local-first, read-only, dependency-free, and compatible with existing logo preferences.

## 1.0.0 — First release

- First-run logo selection: distribution mark or custom wordmark.
- Large centered 5×5 ASCII lettering above the system characteristics.
- Vertical system-information layout with decorative corner framing.
- Six accent colors and persistent local preferences.
- System, hardware, resources, and session information.
- JSON and Markdown report output.
- Install and uninstall scripts.
- Automated unit tests.
