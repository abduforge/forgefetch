# ForgeFetch 1.4.0

ForgeFetch 1.4.0 adds a read-only health overview, selective output sections, root filesystem usage, and Markdown report export.

## Highlights

- `forgefetch --check` — quick indicators for temperature, memory, disk capacity and swap.
- `forgefetch --section cpu,memory` — show only selected system sections.
- `forgefetch --list-sections` — list available sections.
- `forgefetch --report report.md` — save a Markdown report.
- `forgefetch --json --no-network` — machine-readable report with local network details hidden.

The health checks use simple thresholds and are not a full hardware diagnostic or security audit. All checks are local and read-only.

## Verification

- Python syntax check: passed.
- Unit tests: 29 passed.
- JSON output validation: passed.
- `--no-network` privacy validation: passed.
- Install/uninstall smoke test: passed.
