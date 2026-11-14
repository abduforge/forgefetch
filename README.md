# ForgeFetch 1.4.0

A lightweight, read-only system information tool for Linux. ForgeFetch uses Python's standard library and does not need root privileges or third-party packages.

> “Every system tells a story. Learn to read it.”

## What's new in 1.4.0

- `--check`: simple local health indicators for temperature, memory, root filesystem and swap.
- `--section`: display only selected groups (`system`, `cpu`, `memory`, `storage`, `graphics`, `sensors`, `network`, `security`).
- Root filesystem capacity is included in the normal system view.
- `--report [FILE]`: export a Markdown system report.
- Better report formatting and more defensive handling of missing system files and commands.
- Existing 1.3.0 features remain: live refresh, JSON output, network privacy switch, custom brand/accent, and no-color mode.

Health checks are informational heuristics, not a full hardware or security audit. ForgeFetch does not make changes to system settings.

## Requirements

- Linux
- Python 3.10 or newer
- No third-party Python modules

## Run without installing

```bash
python3 forgefetch.py
python3 forgefetch.py --check
python3 forgefetch.py --section cpu,memory
python3 forgefetch.py --json --no-network
python3 forgefetch.py --report system-report.md
```

## Install for the current user

```bash
chmod +x install.sh
./install.sh
```

The installer places `forgefetch` in `~/.local/bin`. Make sure that directory is on your `PATH`.

```bash
forgefetch --version
forgefetch --watch
```

To uninstall the executable:

```bash
./uninstall.sh
```

Your configuration file is kept at `~/.config/forgefetch/config.json` and is not removed by the uninstall script.

## Options

| Option | Description |
|---|---|
| `--version` | Print the version |
| `--watch [SECONDS]` | Refresh the display continuously; default interval is 2 seconds |
| `--check` | Show read-only health indicators |
| `--section NAME[,NAME]` | Select display groups; can be repeated |
| `--list-sections` | List available display groups |
| `--json` | Print JSON data |
| `--report [FILE]` | Write a Markdown report; default file is `forgefetch-report.md` |
| `--no-network` | Hide network interfaces and local IP addresses |
| `--no-color`, `--plain` | Disable terminal colors |
| `--brand TEXT` | Override the display name for one run |
| `--accent COLOR` | Choose `cyan`, `green`, `blue`, `magenta`, `yellow`, or `white` |
| `--config FILE` | Read settings from a custom JSON config file |

Examples:

```bash
forgefetch --section system,cpu,storage
forgefetch --check --no-network
forgefetch --json --section cpu,memory,storage
forgefetch --report ~/Documents/forgefetch-report.md --check
forgefetch --brand AbduForge --accent green
```

## Configuration

ForgeFetch reads optional settings from `~/.config/forgefetch/config.json`:

```json
{
  "brand_name": "ForgeFetch",
  "accent": "cyan"
}
```

Unknown values are ignored. You can also use `--brand` and `--accent` for a one-time override.

## Privacy

ForgeFetch runs locally. It does not contact a remote service, upload telemetry, or resolve your public IP address. Its normal output can include your hostname and local network addresses. Use `--no-network` to hide interface names and local IP addresses. Review any report before sharing it publicly because it may contain device-identifying information.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile forgefetch.py
```

## License

Keep the license already selected for the ForgeFetch GitHub repository. This source bundle does not replace or change that license file.
