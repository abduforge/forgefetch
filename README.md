# ForgeFetch

**A customizable Linux system summary with a centered wordmark.**

ForgeFetch is a lightweight, dependency-free terminal tool inspired by the system-summary style of Fastfetch. Its visual layout is intentionally different: a built-in distribution ASCII mark or personal large-letter wordmark is centered at the top, followed by system characteristics in a vertical list, framed by ornamental corners.

## Features

- First-run choice: auto-detected distribution wordmark or your own large text wordmark.
- Six accent colors: teal, blue, purple, amber, red, and white.
- Persistent preferences stored in `~/.config/forgefetch/config.json`.
- Centered 5-row block lettering, with a subtitle in custom mode.
- Sequential sections for system, hardware, resources, and session details.
- Local JSON output and Markdown report export.
- Python standard library only; no third-party Python packages.
- Read-only: it does not change system settings or scan other devices.

## Requirements

- Linux
- Python 3.10 or newer
- A terminal with UTF-8 support for the decorative frame (plain output is also available)

## Quick install

```bash
unzip forgefetch-1.0.0.zip -d forgefetch-1.0.0
cd forgefetch-1.0.0
chmod +x install.sh
./install.sh
```

Ensure `~/.local/bin` is in your `PATH`, then run:

```bash
forgefetch
```

The first launch asks you to choose a logo source:

1. Distribution mark — ForgeFetch detects supported distributions (MX Linux, Debian, Ubuntu, Arch, Fedora, Linux Mint) and displays a built-in terminal mark; other distributions receive an automatically generated wordmark.
2. Your own wordmark — enter up to nine Latin letters, digits, dots, underscores, or hyphens, plus a short subtitle.

Then choose an accent color. Preferences are saved for future launches.

## Commands

```bash
forgefetch              # Display the terminal system summary
forgefetch --setup      # Reconfigure logo and accent
forgefetch --plain      # Disable ANSI colors
forgefetch --json       # Print a JSON snapshot
forgefetch --report ~/forgefetch-report.md
forgefetch --version
```

## Layout

```text
╭────────────── ◇ FORGEFETCH 1.0.0 ◇ ──────────────╮
│                                                  │
│                    [WORDMARK]                    │
│                  Distribution name               │
│                                                  │
│  ◆ SYSTEM                                         │
│    OS               MX Linux                      │
│    Kernel           ...                           │
│    Architecture     ...                           │
│                                                  │
│  ◆ HARDWARE                                       │
│    CPU              ...                           │
│    Logical cores    ...                           │
│                                                  │
╰──────────── ✦ ABDUFORGE · LOCAL SYSTEM SNAPSHOT ✦╯
```

Custom wordmarks are rendered in large 5x5 block lettering. Distribution mode uses built-in terminal marks where available. System characteristics are always displayed below the logo, never in a side-by-side logo/details layout.

## Configuration

Preferences are stored locally at:

```text
~/.config/forgefetch/config.json
```

Run `forgefetch --setup` to change the wordmark or accent. The configuration file is private to your user account.

## Development and tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile forgefetch.py
```

## Uninstall

```bash
./uninstall.sh
```

The uninstaller keeps your preferences. Remove them separately only if desired:

```bash
rm -r ~/.config/forgefetch
```

## Scope and privacy

ForgeFetch reads local operating-system files and common environment variables to display a basic snapshot. It does not perform port scans, network discovery, privilege escalation, or configuration changes. Hardware values may be unavailable on some systems.

## License

MIT. See [LICENSE](LICENSE).
