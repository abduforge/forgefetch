# Changelog

## [1.4.0] - 2026-11-14

### Added
- Read-only `--check` indicators for temperature, memory, root filesystem and swap.
- Selective output with `--section` and `--list-sections`.
- Root filesystem capacity in the default view.
- Markdown report export with `--report [FILE]`.

### Improved
- More informative help text and examples.
- Defensive handling of absent or unreadable system data.
- Report and JSON output retain the `--no-network` privacy behavior.

### Preserved
- Live refresh with `--watch`.
- JSON output, custom brand/accent, and `--no-color` / `--plain`.
- CPU, memory, GPU, temperature, battery, boot mode and security availability data.

## [1.3.0]
- Live refresh, network privacy switch and additional hardware/system metrics.
