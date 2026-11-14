# ForgeFetch

**A customizable, local-first Linux system summary with a centered ASCII wordmark.**

ForgeFetch displays a readable snapshot of a Linux machine in the terminal. Pick a built-in distribution mark or create your own large wordmark, then inspect system and hardware details, export reports, or watch values refresh live.

## What's new in 1.3.0

- `--watch [SECONDS]`: refresh the display continuously (2 seconds by default; press `Ctrl+C` to stop).
- `--no-network`: hide network interface names and local IP addresses in terminal and report output.
- `--no-color`: alias for `--plain`.
- Additional system facts: boot mode, load average, visible process count, and CPU frequency governor when the kernel exposes them.
- The application remains dependency-free and uses only Python's standard library.

## Requirements

- Linux
- Python 3.10 or newer
- UTF-8 terminal recommended
- Optional: `iproute2` (`ip` command) for local IP address display

## Install

Download and extract the release archive, then run:

```bash
unzip forgefetch-1.3.0.zip
cd forgefetch-1.3.0
chmod +x install.sh
./install.sh
```

The installer places the command in `~/.local/bin/forgefetch` and creates a desktop launcher in `~/.local/share/applications/`. Ensure `~/.local/bin` is in your `PATH`.

Run:

```bash
forgefetch
```

## First-run setup

Choose one of two logo styles:

1. **Distribution mark** — detect common distributions such as MX Linux, Debian, Ubuntu, Arch, Fedora, and Linux Mint.
2. **Custom wordmark** — render up to nine Latin letters, digits, dots, underscores, or hyphens in large 5×5 block lettering, with a subtitle.

Then choose an accent color. Preferences are saved locally in `~/.config/forgefetch/config.json`.

Change preferences later:

```bash
forgefetch --setup
```

## Commands

```bash
forgefetch                         # Display a terminal system summary
forgefetch --setup                  # Reconfigure logo and accent
forgefetch --watch                  # Refresh the snapshot every 2 seconds
forgefetch --watch 5                # Refresh every 5 seconds
forgefetch --no-network             # Hide interfaces and local IP addresses
forgefetch --plain                  # Disable ANSI colors
forgefetch --no-color               # Same as --plain
forgefetch --json                   # Print a structured JSON snapshot
forgefetch --no-network --json      # JSON without local network details
forgefetch --report ~/system.md     # Write a Markdown report
forgefetch --no-network --report ~/system.md
forgefetch --version                # Print version
```

`--watch` requires an interactive terminal and cannot be combined with `--json` or `--report`. Refresh intervals must be greater than 0 and no more than 60 seconds.

## Example layout

```text
╭────────────── ◇ FORGEFETCH 1.3.0 ◇ ──────────────╮
│                                                  │
│                    [WORDMARK]                    │
│                  MX Linux 25.3                   │
│                                                  │
│  ◆ SYSTEM                                         │
│    OS               MX Linux 25.3                 │
│    Hostname         workstation                   │
│    Kernel           6.x                           │
│    Boot mode        UEFI                          │
│    Load average     0.12 / 0.18 / 0.20             │
│                                                  │
│  ◆ HARDWARE                                       │
│    CPU              Intel Celeron ...             │
│    Logical cores    2                             │
│    Graphics         Intel ...                      │
│                                                  │
╰────────── ABDUFORGE · LOCAL SYSTEM SNAPSHOT ─────╯
```

The logo is always above the system characteristics; there is no side-by-side logo/details layout.

## Privacy and scope

ForgeFetch is read-only. It reads common local Linux system files and may call the local `ip` command to display addresses assigned to this machine. It does **not** scan other hosts, probe ports, change firewall settings, elevate privileges, or modify system configuration.

Use `--no-network` when preparing a screenshot or report that should not include interface names or private/local IP addresses. Reports may still contain your hostname and other machine details; review them before sharing or committing them to a public repository.

Some hardware details may show `Unavailable` when the kernel or hardware does not expose them to the current user.

## Development and tests

```bash
python3 -m py_compile forgefetch.py
python3 -m unittest discover -s tests -v
```

## Uninstall

```bash
./uninstall.sh
```

The uninstaller keeps preferences unless `--purge` is passed:

```bash
./uninstall.sh --purge
```

## License

MIT. See [LICENSE](LICENSE).
