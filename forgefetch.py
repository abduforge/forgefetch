#!/usr/bin/env python3
"""ForgeFetch - a small, privacy-conscious system information tool."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.4.0"
APP_NAME = "ForgeFetch"
SECTIONS = ("system", "cpu", "memory", "storage", "graphics", "sensors", "network", "security")
ACCENTS = ("cyan", "green", "blue", "magenta", "yellow", "white")
ANSI = {
    "cyan": "36", "green": "32", "blue": "34", "magenta": "35",
    "yellow": "33", "white": "37",
}


def read_text(path: str | Path, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, UnicodeError):
        return default


def parse_os_release(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def parse_meminfo(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^(MemTotal|MemAvailable|MemFree|SwapTotal|SwapFree):\s+(\d+)", line)
        if match:
            values[match.group(1)] = int(match.group(2)) * 1024
    if "MemAvailable" not in values:
        values["MemAvailable"] = values.get("MemFree", 0)
    return values


def human_bytes(value: int | float | None) -> str:
    if value is None:
        return "Not available"
    amount = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"


def read_cpu_model() -> str:
    text = read_text("/proc/cpuinfo")
    lines = text.splitlines()
    # Prefer descriptive model fields. On some systems, "processor" is only
    # a numeric core index (for example, "processor : 0"), not a model name.
    for prefix in ("model name", "hardware", "cpu model"):
        for line in lines:
            if line.lower().startswith(prefix) and ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    return value
    for line in lines:
        if line.lower().startswith("processor") and ":" in line:
            value = line.split(":", 1)[1].strip()
            if value and not value.isdigit():
                return value
    return platform.processor() or "Not available"


def read_cpu_frequency_mhz() -> float | None:
    candidates = [
        Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"),
        Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"),
    ]
    for path in candidates:
        raw = read_text(path)
        if raw.isdigit():
            return round(int(raw) / 1000, 1)
    text = read_text("/proc/cpuinfo")
    match = re.search(r"^cpu MHz\s*:\s*([0-9.]+)", text, re.MULTILINE)
    return round(float(match.group(1)), 1) if match else None


def read_temperature_c() -> float | None:
    readings: list[float] = []
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        raw = read_text(path)
        if raw.lstrip("-").isdigit():
            val = int(raw) / 1000
            if -10 <= val <= 150:
                readings.append(val)
    for path in Path("/sys/class/hwmon").glob("hwmon*/temp*_input"):
        raw = read_text(path)
        if raw.lstrip("-").isdigit():
            val = int(raw) / 1000
            if -10 <= val <= 150:
                readings.append(val)
    return round(max(readings), 1) if readings else None


def read_battery() -> dict[str, Any] | None:
    for base in Path("/sys/class/power_supply").glob("BAT*"):
        capacity = read_text(base / "capacity")
        status = read_text(base / "status", "Unknown")
        data: dict[str, Any] = {"status": status}
        if capacity.isdigit():
            data["capacity_percent"] = int(capacity)
        cycle_count = read_text(base / "cycle_count")
        if cycle_count.isdigit():
            data["cycle_count"] = int(cycle_count)
        return data
    return None


def read_gpu() -> list[str]:
    cards: list[str] = []
    vendor_names = {"0x8086": "Intel", "0x10de": "NVIDIA", "0x1002": "AMD", "0x1022": "AMD"}
    for card in sorted(p for p in Path("/sys/class/drm").glob("card[0-9]*") if re.fullmatch(r"card\d+", p.name)):
        device = card / "device"
        vendor = read_text(device / "vendor")
        device_id = read_text(device / "device")
        if vendor or device_id:
            name = vendor_names.get(vendor.lower(), vendor or "GPU")
            cards.append(f"{name} ({device_id})" if device_id else name)
    return cards


def read_network() -> dict[str, Any]:
    interfaces: list[str] = []
    try:
        interfaces = sorted(p.name for p in Path("/sys/class/net").iterdir() if p.name != "lo")
    except OSError:
        pass
    addresses: list[str] = []
    ip = shutil.which("ip")
    if ip:
        try:
            result = subprocess.run([ip, "-o", "addr", "show"], capture_output=True, text=True, timeout=2, check=False)
            for line in result.stdout.splitlines():
                match = re.match(r"\d+:\s+([^ ]+)\s+inet6?\s+([^/ ]+)", line)
                if match and match.group(1) != "lo":
                    item = f"{match.group(1)}: {match.group(2)}"
                    if item not in addresses:
                        addresses.append(item)
        except (OSError, subprocess.SubprocessError):
            pass
    return {"status": "Local-only data", "interfaces": interfaces, "local_addresses": sorted(addresses)}


def read_secure_boot() -> str:
    paths = list(Path("/sys/firmware/efi/efivars").glob("SecureBoot-*"))
    for path in paths:
        try:
            data = path.read_bytes()
            if len(data) >= 5:
                return "Enabled" if data[4] == 1 else "Disabled"
        except OSError:
            continue
    if not Path("/sys/firmware/efi").exists():
        return "Not available (Legacy BIOS or no EFI access)"
    return "Unknown"


def command_status(command: str, arguments: list[str] | None = None) -> str:
    executable = shutil.which(command)
    if not executable:
        return "Not installed"
    if arguments:
        try:
            result = subprocess.run([executable, *arguments], capture_output=True, text=True, timeout=3, check=False)
            output = (result.stdout + "\n" + result.stderr).strip().lower()
            if "active" in output and "inactive" not in output:
                return "Active"
            if "inactive" in output:
                return "Inactive"
        except (OSError, subprocess.SubprocessError):
            pass
    return "Installed; state not checked"


def collect_system(no_network: bool = False) -> dict[str, Any]:
    os_info = parse_os_release(read_text("/etc/os-release"))
    mem = parse_meminfo(read_text("/proc/meminfo"))
    try:
        load = [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        load = []
    try:
        disk = shutil.disk_usage("/")
        disk_data = {"total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free,
                     "used_percent": round((disk.used / disk.total) * 100, 1) if disk.total else None}
    except OSError:
        disk_data = {"total_bytes": None, "used_bytes": None, "free_bytes": None, "used_percent": None}
    try:
        uptime_seconds = float(read_text("/proc/uptime").split()[0])
        uptime = f"{int(uptime_seconds // 86400)}d {int((uptime_seconds % 86400) // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
    except (ValueError, IndexError):
        uptime = "Not available"
    try:
        processes = sum(1 for p in Path("/proc").iterdir() if p.name.isdigit())
    except OSError:
        processes = None

    memory_total = mem.get("MemTotal")
    memory_available = mem.get("MemAvailable")
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    memory_data = {
        "total_bytes": memory_total,
        "available_bytes": memory_available,
        "used_percent": round((1 - memory_available / memory_total) * 100, 1) if memory_total and memory_available is not None else None,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": max(0, swap_total - swap_free),
        "swap_used_percent": round((1 - swap_free / swap_total) * 100, 1) if swap_total else 0.0,
    }
    battery = read_battery()
    network = {"status": "Hidden by --no-network", "interfaces": [], "local_addresses": []} if no_network else read_network()
    distro = os_info.get("PRETTY_NAME") or os_info.get("NAME") or platform.system()
    return {
        "app": APP_NAME,
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "system": {
            "os": distro,
            "hostname": platform.node() or "Not available",
            "kernel": platform.release(),
            "architecture": platform.machine() or "Not available",
            "uptime": uptime,
            "boot_mode": "UEFI" if Path("/sys/firmware/efi").exists() else "Legacy BIOS / unknown",
        },
        "cpu": {
            "model": read_cpu_model(),
            "logical_cores": os.cpu_count(),
            "frequency_mhz": read_cpu_frequency_mhz(),
            "governor": read_text("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "Not available"),
            "load_average": load,
            "process_count": processes,
        },
        "memory": memory_data,
        "storage": {"root_filesystem": disk_data},
        "graphics": {"gpus": read_gpu()},
        "sensors": {"max_temperature_c": read_temperature_c(), "battery": battery},
        "network": network,
        "security": {
            "secure_boot": read_secure_boot(),
            "ufw": command_status("ufw", ["status"]),
            "ssh_server_binary": "Installed" if shutil.which("sshd") else "Not installed",
        },
    }


def health_checks(data: dict[str, Any]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    temp = data.get("sensors", {}).get("max_temperature_c")
    if temp is None:
        checks.append({"status": "INFO", "item": "CPU/system temperature", "message": "No readable temperature sensor was found."})
    elif temp >= 85:
        checks.append({"status": "WARN", "item": "CPU/system temperature", "message": f"Reported maximum is {temp:.1f} °C; check cooling and airflow."})
    else:
        checks.append({"status": "OK", "item": "CPU/system temperature", "message": f"Reported maximum is {temp:.1f} °C."})

    memory = data.get("memory", {})
    mem_pct = memory.get("used_percent")
    if mem_pct is None:
        checks.append({"status": "INFO", "item": "Memory", "message": "Memory usage could not be calculated."})
    elif mem_pct >= 90:
        checks.append({"status": "WARN", "item": "Memory", "message": f"Memory usage is {mem_pct:.1f}%; close unused applications if the system feels slow."})
    else:
        checks.append({"status": "OK", "item": "Memory", "message": f"Memory usage is {mem_pct:.1f}%."})

    disk_pct = data.get("storage", {}).get("root_filesystem", {}).get("used_percent")
    if disk_pct is None:
        checks.append({"status": "INFO", "item": "Root filesystem", "message": "Disk usage could not be checked."})
    elif disk_pct >= 90:
        checks.append({"status": "WARN", "item": "Root filesystem", "message": f"Root filesystem is {disk_pct:.1f}% full; review large files before it fills up."})
    else:
        checks.append({"status": "OK", "item": "Root filesystem", "message": f"Root filesystem is {disk_pct:.1f}% full."})

    swap_pct = memory.get("swap_used_percent")
    if swap_pct is not None and swap_pct >= 90:
        checks.append({"status": "WARN", "item": "Swap", "message": f"Swap usage is {swap_pct:.1f}%; check whether memory pressure is persistent."})
    elif memory.get("swap_total_bytes", 0) == 0:
        checks.append({"status": "INFO", "item": "Swap", "message": "No swap space is configured."})
    else:
        checks.append({"status": "OK", "item": "Swap", "message": f"Swap usage is {swap_pct or 0:.1f}%."})
    return checks


def parse_sections(values: list[str] | None) -> list[str]:
    if not values:
        return list(SECTIONS)
    selected: list[str] = []
    for value in values:
        for item in value.split(","):
            name = item.strip().lower()
            if name == "all":
                return list(SECTIONS)
            if name not in SECTIONS:
                raise ValueError(f"Unknown section '{name}'. Available: {', '.join(SECTIONS)}")
            if name not in selected:
                selected.append(name)
    return selected


def format_value(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, list):
        return ", ".join(str(x) for x in value) if value else "None detected"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {format_value(v)}" for k, v in value.items())
    return str(value)


def display_rows(data: dict[str, Any], sections: list[str]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    groups: dict[str, list[tuple[str, str]]] = {
        "system": [("OS", data["system"]["os"]), ("Hostname", data["system"]["hostname"]),
                   ("Kernel", data["system"]["kernel"]), ("Architecture", data["system"]["architecture"]),
                   ("Uptime", data["system"]["uptime"]), ("Boot mode", data["system"]["boot_mode"])],
        "cpu": [("Processor", data["cpu"]["model"]), ("Logical cores", data["cpu"]["logical_cores"]),
                ("Frequency", f"{data['cpu']['frequency_mhz']} MHz" if data["cpu"]["frequency_mhz"] is not None else None),
                ("Governor", data["cpu"]["governor"]), ("Load average", data["cpu"]["load_average"]),
                ("Processes", data["cpu"]["process_count"])],
        "memory": [("RAM total", human_bytes(data["memory"]["total_bytes"])),
                   ("RAM available", human_bytes(data["memory"]["available_bytes"])),
                   ("RAM used", f"{data['memory']['used_percent']}%" if data["memory"]["used_percent"] is not None else None),
                   ("Swap used", f"{human_bytes(data['memory']['swap_used_bytes'])} / {human_bytes(data['memory']['swap_total_bytes'])}")],
        "storage": [("Root disk", f"{human_bytes(data['storage']['root_filesystem']['free_bytes'])} free / {human_bytes(data['storage']['root_filesystem']['total_bytes'])} ({data['storage']['root_filesystem']['used_percent']}% used)" if data["storage"]["root_filesystem"]["total_bytes"] else "Not available")],
        "graphics": [("GPU", data["graphics"]["gpus"])],
        "sensors": [("Max temperature", f"{data['sensors']['max_temperature_c']} °C" if data["sensors"]["max_temperature_c"] is not None else None),
                    ("Battery", data["sensors"]["battery"] or "No battery detected")],
        "network": ([(["Data visibility", data["network"]["status"]])] if data["network"].get("status") else []) +
                   [("Interfaces", data["network"].get("interfaces", [])), ("Local addresses", data["network"].get("local_addresses", []))],
        "security": [("Secure Boot", data["security"]["secure_boot"]), ("UFW", data["security"]["ufw"]),
                     ("SSH server binary", data["security"]["ssh_server_binary"])],
    }
    for section in sections:
        rows.extend(groups[section])
    return rows


def colorize(text: str, accent: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[1;{ANSI.get(accent, ANSI['cyan'])}m{text}\033[0m"


def render_terminal(data: dict[str, Any], brand: str, accent: str, sections: list[str], plain: bool, checks: bool = False) -> str:
    width = shutil.get_terminal_size((80, 24)).columns
    use_color = sys.stdout.isatty() and not plain
    rows = display_rows(data, sections)
    heading = f"{brand}  |  SYSTEM SNAPSHOT"
    if width < 48:
        lines = [heading, "=" * min(width, len(heading))]
        for key, value in rows:
            lines.append(f"{key}: {format_value(value)}")
    else:
        inner = min(72, width - 8)
        title = f" {brand} "
        subtitle = " SYSTEM SNAPSHOT "
        lines = ["╭" + "─" * (inner + 2) + "╮", "│" + title.center(inner + 2) + "│",
                 "│" + subtitle.center(inner + 2) + "│", "╰" + "─" * (inner + 2) + "╯"]
        current = None
        group_titles = {"system": "SYSTEM", "cpu": "PROCESSOR", "memory": "MEMORY", "storage": "STORAGE",
                        "graphics": "GRAPHICS", "sensors": "SENSORS", "network": "NETWORK", "security": "SECURITY"}
        for section in sections:
            lines.append("")
            lines.append(f"  ┌─ {group_titles[section]} " + "─" * max(0, inner - len(group_titles[section]) - 3) + "┐")
            section_rows = display_rows(data, [section])
            for key, value in section_rows:
                value_text = format_value(value)
                label = f"{key:<18} : "
                available = max(8, inner - len(label) - 2)
                if len(value_text) > available:
                    value_text = value_text[:max(1, available - 1)] + "…"
                lines.append(f"  │ {label}{value_text:<{available}} │")
            lines.append("  └" + "─" * (inner + 1) + "┘")
    if checks:
        lines.append("")
        lines.append("Health check")
        for item in health_checks(data):
            lines.append(f"[{item['status']}] {item['item']}: {item['message']}")
    if use_color:
        colored: list[str] = []
        for line in lines:
            if line.startswith(("╭", "╰", "  ┌", "  └", "Health check")):
                colored.append(colorize(line, accent, True))
            elif line.startswith("[WARN]"):
                colored.append(colorize(line, "yellow", True))
            else:
                colored.append(line)
        lines = colored
    return "\n".join(lines)


def markdown_report(data: dict[str, Any], sections: list[str], checks: bool = False) -> str:
    lines = [f"# {APP_NAME} {VERSION} report", "", f"- Generated: {data['generated_at']}",
             "- Privacy: local system information only; no remote address lookup is performed.", ""]
    for section in sections:
        lines.extend([f"## {section.title()}", "", "| Field | Value |", "|---|---|"])
        for key, value in display_rows(data, [section]):
            lines.append(f"| {key} | {format_value(value).replace('|', '\\|')} |")
        lines.append("")
    if checks:
        lines.extend(["## Health check", "", "| Status | Check | Result |", "|---|---|---|"])
        for item in health_checks(data):
            safe_msg = item["message"].replace("|", "\\|")
            lines.append(f"| {item['status']} | {item['item']} | {safe_msg} |")
    lines.extend(["", "*ForgeFetch performs read-only local checks. Health thresholds are simple indicators, not a complete hardware diagnosis.*", ""])
    return "\n".join(lines)


def load_config(path: Path) -> dict[str, str]:
    defaults = {"brand_name": APP_NAME, "accent": "cyan"}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            brand = parsed.get("brand_name", defaults["brand_name"])
            accent = parsed.get("accent", defaults["accent"])
            if isinstance(brand, str) and 1 <= len(brand.strip()) <= 32:
                defaults["brand_name"] = brand.strip()
            if isinstance(accent, str) and accent.lower() in ACCENTS:
                defaults["accent"] = accent.lower()
    except (OSError, json.JSONDecodeError, UnicodeError):
        pass
    return defaults


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forgefetch",
        description="A lightweight, privacy-conscious system information tool.",
        epilog="Examples: forgefetch --check | forgefetch --section cpu,memory | forgefetch --report report.md",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    parser.add_argument("--watch", nargs="?", const=2.0, type=float, metavar="SECONDS", help="refresh live view (default: 2 seconds)")
    parser.add_argument("--no-network", action="store_true", help="hide interfaces and local IP addresses")
    parser.add_argument("--no-color", "--plain", dest="plain", action="store_true", help="disable terminal colors")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--report", nargs="?", const="forgefetch-report.md", metavar="FILE", help="write a Markdown report (default: forgefetch-report.md)")
    parser.add_argument("--check", action="store_true", help="run simple read-only health checks")
    parser.add_argument("--section", action="append", metavar="NAME", help="show one or more sections; repeat or use comma-separated names")
    parser.add_argument("--list-sections", action="store_true", help="list available sections")
    parser.add_argument("--brand", help="override the display name for this run")
    parser.add_argument("--accent", choices=ACCENTS, help="override the terminal accent color")
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/forgefetch/config.json", help="use a custom config file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_sections:
        print("Available sections: " + ", ".join(SECTIONS))
        return 0
    if args.watch is not None:
        if not 0.5 <= args.watch <= 60:
            parser.error("--watch interval must be between 0.5 and 60 seconds")
        if not sys.stdout.isatty():
            parser.error("--watch requires an interactive terminal")
        if args.json or args.report:
            parser.error("--watch cannot be combined with --json or --report")
    if args.json and args.report:
        parser.error("--json and --report cannot be combined")
    try:
        sections = parse_sections(args.section)
    except ValueError as exc:
        parser.error(str(exc))
    config = load_config(args.config)
    brand = args.brand.strip()[:32] if args.brand and args.brand.strip() else config["brand_name"]
    accent = args.accent or config["accent"]

    def render_once() -> None:
        data = collect_system(no_network=args.no_network)
        if args.check:
            data["health_checks"] = health_checks(data)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        elif args.report:
            target = Path(args.report).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(markdown_report(data, sections, args.check), encoding="utf-8")
            print(f"Report saved: {target}")
        else:
            print(render_terminal(data, brand, accent, sections, args.plain, args.check))

    if args.watch is not None:
        try:
            while True:
                if sys.stdout.isatty():
                    print("\033[2J\033[H", end="")
                render_once()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nForgeFetch stopped.")
        return 0
    render_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
