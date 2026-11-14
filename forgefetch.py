#!/usr/bin/env python3
"""ForgeFetch: a customizable, local-first Linux system summary."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "ForgeFetch"
VERSION = "1.3.0"
CONFIG_DIR = Path.home() / ".config" / "forgefetch"
CONFIG_FILE = CONFIG_DIR / "config.json"

COLORS = {
    "teal": "\033[38;5;80m",
    "blue": "\033[38;5;75m",
    "purple": "\033[38;5;141m",
    "amber": "\033[38;5;179m",
    "red": "\033[38;5;203m",
    "white": "\033[38;5;252m",
    "muted": "\033[38;5;245m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}

# Compact 5x5 lettering. Deliberately dependency-free and terminal friendly.
FONT = {
    "A": ("01110", "10001", "11111", "10001", "10001"),
    "B": ("11110", "10001", "11110", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "11110", "10000", "11111"),
    "F": ("11111", "10000", "11110", "10000", "10000"),
    "G": ("01111", "10000", "10111", "10001", "01111"),
    "H": ("10001", "10001", "11111", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "11100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001"),
    "O": ("01110", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "11110", "10000", "10000"),
    "Q": ("01110", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "11110", "10010", "10001"),
    "S": ("01111", "10000", "01110", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10101", "11011", "10001"),
    "X": ("10001", "01010", "00100", "01010", "10001"),
    "Y": ("10001", "01010", "00100", "00100", "00100"),
    "Z": ("11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10011", "10101", "11001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00010", "00100", "11111"),
    "3": ("11110", "00001", "00110", "00001", "11110"),
    "4": ("10010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "11110"),
    "6": ("01110", "10000", "11110", "10001", "01110"),
    "7": ("11111", "00010", "00100", "01000", "01000"),
    "8": ("01110", "10001", "01110", "10001", "01110"),
    "9": ("01110", "10001", "01111", "00001", "01110"),
    "-": ("00000", "00000", "11111", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00110", "00110"),
    "_": ("00000", "00000", "00000", "00000", "11111"),
}

DISTRO_MARKS = {
    "mx": ("MX", "MX LINUX"),
    "debian": ("DEBIAN", "DEBIAN GNU/LINUX"),
    "ubuntu": ("UBUNTU", "UBUNTU"),
    "linuxmint": ("MINT", "LINUX MINT"),
    "fedora": ("FEDORA", "FEDORA LINUX"),
    "arch": ("ARCH", "ARCH LINUX"),
    "manjaro": ("MANJARO", "MANJARO LINUX"),
    "opensuse": ("OPENSUSE", "OPENSUSE"),
    "pop": ("POP-OS", "POP!_OS"),
}

# Original text-art interpretations, not copied vendor logos.
DISTRO_ARTS = {
    "mx": (
        "       .--------.",
        "   .---|   MX   |---.",
        "   |   |        |   |",
        "   '---|________|---'",
        "        MX LINUX",
    ),
    "debian": (
        "       .----.",
        "    .-'      '-.",
        "   (   DEBIAN   )",
        "    '-.______.-'",
    ),
    "ubuntu": (
        "      .------.",
        "   .-' UBUNTU '-.",
        "  (   o      o   )",
        "   '-.________.-'",
    ),
    "arch": (
        "        /\\",
        "       /  \\",
        "      / /\\ \\",
        "     /_/  \\_\\",
        "       ARCH",
    ),
    "fedora": (
        "      ______",
        "     |  ____|",
        "     | |___",
        "     |  ___|",
        "     |_|",
        "     FEDORA",
    ),
    "linuxmint": (
        "     .--------.",
        "     |  LINUX |",
        "     |   MINT |",
        "     '--------'",
    ),
}


def read_text(path: str | Path, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return default


def parse_os_release(text: str | None = None) -> dict[str, str]:
    raw = text if text is not None else read_text("/etc/os-release")
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parsed = shlex.split(value, comments=False, posix=True)
            result[key.strip()] = parsed[0] if parsed else ""
        except ValueError:
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def parse_meminfo(text: str | None = None) -> dict[str, int]:
    raw = text if text is not None else read_text("/proc/meminfo")
    values: dict[str, int] = {}
    for line in raw.splitlines():
        match = re.match(r"^(\w+):\s+(\d+)\s+kB", line)
        if match:
            values[match.group(1)] = int(match.group(2)) * 1024
    return values


def human_bytes(value: int | float | None) -> str:
    if value is None:
        return "Unknown"
    amount = float(max(0, value))
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{int(amount)} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return "Unknown"


def safe_run(command: list[str], timeout: float = 1.5) -> str:
    """Run a fixed local read-only command; never invoke a shell."""
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read_cpu_model() -> str:
    cpuinfo = read_text("/proc/cpuinfo")
    for line in cpuinfo.splitlines():
        if line.lower().startswith(("model name", "hardware", "processor")) and ":" in line:
            value = line.split(":", 1)[1].strip()
            if value and not value.isdigit():
                return value
    return platform.processor() or "Unknown CPU"


def read_cpu_frequency() -> str:
    values: list[int] = []
    for path in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            values.append(int(path.read_text().strip()))
        except (OSError, ValueError):
            continue
    if values:
        return f"{sum(values) / len(values) / 1000:.0f} MHz avg"
    return "Unavailable"


def read_uptime() -> str:
    raw = read_text("/proc/uptime")
    try:
        seconds = int(float(raw.split()[0]))
    except (ValueError, IndexError):
        return "Unknown"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def read_load_average() -> str:
    """Return the 1/5/15 minute load average without spawning a process."""
    raw = read_text("/proc/loadavg")
    fields = raw.split()
    if len(fields) < 3:
        return "Unavailable"
    try:
        values = [float(item) for item in fields[:3]]
    except ValueError:
        return "Unavailable"
    return " / ".join(f"{value:.2f}" for value in values) + " (1/5/15m)"


def read_process_count() -> str:
    """Count visible numeric /proc entries."""
    try:
        count = sum(1 for item in Path("/proc").iterdir() if item.name.isdigit())
    except OSError:
        return "Unavailable"
    return str(count)


def read_boot_mode() -> str:
    return "UEFI" if Path("/sys/firmware/efi").is_dir() else "Legacy BIOS"


def read_cpu_governor() -> str:
    governors: list[str] = []
    for path in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value and value not in governors:
            governors.append(value)
    return ", ".join(governors) if governors else "Unavailable"


def read_temperature() -> str:
    # Prefer a CPU-labelled thermal zone; fall back to the first sane zone.
    candidates = list(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    fallback = "Unavailable"
    for candidate in candidates:
        try:
            celsius = int(candidate.read_text().strip()) / 1000
        except (OSError, ValueError):
            continue
        if not -10 <= celsius <= 150:
            continue
        zone_type = read_text(candidate.parent / "type").lower()
        value = f"{celsius:.0f} °C"
        if any(token in zone_type for token in ("cpu", "x86_pkg", "package")):
            return value
        if fallback == "Unavailable":
            fallback = value
    if fallback != "Unavailable":
        return fallback
    # Many systems expose temperatures through hwmon instead of thermal zones.
    for candidate in Path("/sys/class/hwmon").glob("hwmon*/temp*_input"):
        label = read_text(candidate.with_name(candidate.name.replace("_input", "_label"))).lower()
        try:
            celsius = int(candidate.read_text().strip()) / 1000
        except (OSError, ValueError):
            continue
        if -10 <= celsius <= 150 and (not label or any(x in label for x in ("package", "cpu", "core"))):
            return f"{celsius:.0f} °C"
    return "Unavailable"


def read_gpu() -> str:
    drm = Path("/sys/class/drm")
    vendor_names = {"0x8086": "Intel", "0x1002": "AMD", "0x10de": "NVIDIA"}
    for device_path in sorted(drm.glob("card[0-9]*/device")):
        vendor = read_text(device_path / "vendor").lower()
        device = read_text(device_path / "device").lower()
        if vendor:
            name = vendor_names.get(vendor, "GPU")
            return f"{name} ({vendor.removeprefix('0x')}:{device.removeprefix('0x') or 'unknown'})"
    return "Not detected"


def read_battery() -> str:
    for battery in Path("/sys/class/power_supply").glob("*",):
        if read_text(battery / "type").lower() != "battery":
            continue
        capacity = read_text(battery / "capacity")
        status = read_text(battery / "status")
        if capacity.isdigit():
            suffix = f" · {status}" if status else ""
            return f"{capacity}%{suffix}"
    return "Not detected"


def read_default_interface() -> str:
    routes = read_text("/proc/net/route")
    for line in routes.splitlines()[1:]:
        fields = line.split()
        if len(fields) > 3 and fields[1] == "00000000":
            try:
                if int(fields[3], 16) & 1:
                    return fields[0]
            except ValueError:
                continue
    return "Unknown"


def read_network() -> tuple[str, str]:
    interfaces: list[str] = []
    for interface in sorted(Path("/sys/class/net").glob("*")):
        if interface.name == "lo":
            continue
        state = read_text(interface / "operstate", "unknown")
        interfaces.append(f"{interface.name} ({state})")
    interface_text = ", ".join(interfaces) if interfaces else "Not detected"

    addresses: list[str] = []
    ip_output = safe_run(["ip", "-o", "-4", "addr", "show", "scope", "global"])
    for line in ip_output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[2] == "inet":
            addresses.append(fields[3].split("/", 1)[0])
    if not addresses:
        ip_output = safe_run(["ip", "-o", "-6", "addr", "show", "scope", "global"])
        for line in ip_output.splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[2] == "inet6":
                addresses.append(fields[3].split("/", 1)[0])
    default_iface = read_default_interface()
    address_text = ", ".join(addresses) if addresses else "Unavailable"
    if default_iface != "Unknown":
        address_text = f"{default_iface}: {address_text}"
    return interface_text, address_text


def read_secure_boot() -> str:
    efivars = Path("/sys/firmware/efi/efivars")
    if not efivars.is_dir():
        return "Not available (legacy boot)"
    for variable in efivars.glob("SecureBoot-*"):
        try:
            data = variable.read_bytes()
            if len(data) >= 5:
                return "Enabled" if data[4] == 1 else "Disabled"
        except OSError:
            return "Permission restricted"
    return "Unavailable"


def command_available(name: str) -> str:
    return "Available" if shutil.which(name) else "Not installed"


def get_info(include_network: bool = True) -> list[tuple[str, list[tuple[str, str]]]]:
    osr = parse_os_release()
    os_name = osr.get("PRETTY_NAME") or osr.get("NAME") or "Linux"
    mem = parse_meminfo()
    mem_total = mem.get("MemTotal")
    mem_available = mem.get("MemAvailable")
    mem_used = max(0, mem_total - mem_available) if mem_total and mem_available is not None else None
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    try:
        disk = shutil.disk_usage("/")
        disk_value = (
            f"{human_bytes(disk.used)} used / {human_bytes(disk.total)} "
            f"({disk.used / disk.total * 100:.0f}%)"
            if disk.total else "Unknown"
        )
    except OSError:
        disk_value = "Unavailable"

    session = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "Unknown"
    session_type = os.environ.get("XDG_SESSION_TYPE", "Unknown")
    shell = Path(os.environ.get("SHELL", "")).name or "Unknown"
    terminal = os.environ.get("TERM_PROGRAM") or os.environ.get("TERM", "Unknown")
    if include_network:
        interfaces, addresses = read_network()
    else:
        interfaces, addresses = "Hidden by --no-network", "Hidden by --no-network"

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        ("SYSTEM", [
            ("OS", os_name),
            ("Hostname", socket.gethostname() or "Unknown"),
            ("Kernel", platform.release()),
            ("Architecture", platform.machine()),
            ("Uptime", read_uptime()),
            ("Boot mode", read_boot_mode()),
            ("Load average", read_load_average()),
            ("Processes", read_process_count()),
        ]),
        ("HARDWARE", [
            ("CPU", read_cpu_model()),
            ("Logical cores", str(os.cpu_count() or "Unknown")),
            ("CPU frequency", read_cpu_frequency()),
            ("CPU governor", read_cpu_governor()),
            ("Graphics", read_gpu()),
            ("Temperature", read_temperature()),
            ("Battery", read_battery()),
        ]),
        ("RESOURCES", [
            ("Memory", f"{human_bytes(mem_used)} used / {human_bytes(mem_total)} ({mem_used / mem_total * 100:.0f}%)" if mem_used is not None and mem_total else "Unknown"),
            ("Available RAM", human_bytes(mem_available)),
            ("Swap", f"{human_bytes(swap_total - swap_free)} used / {human_bytes(swap_total)}"),
            ("Root disk", disk_value),
        ]),
        ("SESSION & NETWORK", [
            ("Desktop", session),
            ("Session type", session_type),
            ("Shell", shell),
            ("Terminal", terminal),
            ("Interfaces", interfaces),
            ("Local addresses", addresses),
        ]),
        ("SECURITY", [
            ("Secure Boot", read_secure_boot()),
            ("UFW command", command_available("ufw")),
            ("SSH server", command_available("sshd")),
        ]),
    ]
    return groups


def distro_wordmark(osr: dict[str, str]) -> tuple[str, str]:
    ident = osr.get("ID", "").lower().replace("-", "")
    pretty = osr.get("PRETTY_NAME", osr.get("NAME", "LINUX"))
    like = [item.lower().replace("-", "") for item in osr.get("ID_LIKE", "").split()]
    for candidate in [ident] + like:
        for key, mark in DISTRO_MARKS.items():
            if candidate == key or candidate.startswith(key):
                return mark[0], pretty
    lowered = pretty.lower()
    for key, mark in DISTRO_MARKS.items():
        if key in lowered:
            return mark[0], pretty
    clean = re.sub(r"[^A-Za-z0-9 ._-]", "", ident or "LINUX").upper()
    return (clean[:9] or "LINUX"), pretty


def big_text(text: str) -> list[str]:
    cleaned = re.sub(r"[^A-Z0-9._-]", "", str(text).upper())[:9]
    cleaned = cleaned or "FORGE"
    glyphs = [FONT.get(char, FONT["-"]) for char in cleaned]
    return [
        " ".join("".join("█" if pixel == "1" else " " for pixel in glyph[row]) for glyph in glyphs)
        for row in range(5)
    ]


def default_config() -> dict[str, Any]:
    return {
        "config_version": 1,
        "logo_mode": "distro",
        "custom_text": "FORGE",
        "subtitle": "A personal Linux snapshot",
        "accent": "teal",
    }


def validate_config(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    defaults = default_config()
    logo_mode = value.get("logo_mode", defaults["logo_mode"])
    accent = value.get("accent", defaults["accent"])
    if logo_mode not in ("distro", "custom") or accent not in ("teal", "blue", "purple", "amber", "red", "white"):
        return None
    custom = re.sub(r"[^A-Za-z0-9._-]", "", str(value.get("custom_text", "FORGE")).upper())[:9] or "FORGE"
    subtitle = re.sub(r"[\x00-\x1f\x7f]", "", str(value.get("subtitle", "")))[:56]
    return {
        "config_version": 1,
        "logo_mode": logo_mode,
        "custom_text": custom,
        "subtitle": subtitle,
        "accent": accent,
    }


def load_config() -> dict[str, Any] | None:
    try:
        value = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return validate_config(value)


def save_config(config: dict[str, Any]) -> None:
    validated = validate_config(config)
    if validated is None:
        raise ValueError("Invalid ForgeFetch configuration")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass
    temp = CONFIG_FILE.with_suffix(f".tmp-{os.getpid()}")
    try:
        temp.write_text(json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(CONFIG_FILE)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def setup_config() -> dict[str, Any]:
    print("\nForgeFetch · First-run setup")
    print("Choose the logo style:")
    print("  1) Distribution mark (auto-detect Linux distribution)")
    print("  2) My own wordmark (large custom letters)")
    choice = input("Selection [1]: ").strip() or "1"
    mode = "custom" if choice == "2" else "distro"
    custom = "FORGE"
    subtitle = "A personal Linux snapshot"
    if mode == "custom":
        raw = input("Your wordmark, up to 9 Latin letters/numbers [FORGE]: ").strip() or "FORGE"
        custom = re.sub(r"[^A-Za-z0-9._-]", "", raw.upper())[:9] or "FORGE"
        raw_subtitle = input("Short subtitle [A personal Linux snapshot]: ").strip()
        subtitle = re.sub(r"[\x00-\x1f\x7f]", "", raw_subtitle)[:56] or subtitle
    print("\nChoose an accent:")
    options = [("1", "teal"), ("2", "blue"), ("3", "purple"), ("4", "amber"), ("5", "red"), ("6", "white")]
    for number, name in options:
        print(f"  {number}) {name.title()}")
    selected = input("Accent [1]: ").strip() or "1"
    accent = dict(options).get(selected, "teal")
    config = {"config_version": 1, "logo_mode": mode, "custom_text": custom, "subtitle": subtitle, "accent": accent}
    save_config(config)
    print(f"\nSaved preferences to {CONFIG_FILE}\n")
    return config


def get_logo(config: dict[str, Any]) -> tuple[list[str], str]:
    if config.get("logo_mode") == "custom":
        return big_text(str(config.get("custom_text", "FORGE"))), str(config.get("subtitle", ""))
    osr = parse_os_release()
    ident = osr.get("ID", "").lower().replace("-", "")
    pretty = osr.get("PRETTY_NAME", osr.get("NAME", "Linux"))
    aliases = {"linuxmint": "linuxmint", "pop_os": "pop"}
    ident = aliases.get(ident, ident)
    if ident in DISTRO_ARTS:
        return list(DISTRO_ARTS[ident]), pretty
    mark, subtitle = distro_wordmark(osr)
    return big_text(mark), subtitle


def color_enabled(plain: bool) -> bool:
    return not plain and sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def visible_width(text: str) -> int:
    clean = re.sub(r"\033\[[0-?]*[ -/]*[@-~]", "", text)
    width = 0
    for char in clean:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def clip_text(text: str, maximum: int) -> str:
    if maximum <= 0:
        return ""
    out: list[str] = []
    used = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if used + char_width > maximum:
            return "".join(out[:-1]) + "…" if out else "…"
        out.append(char)
        used += char_width
    return "".join(out)


def render_terminal(
    config: dict[str, Any],
    groups: list[tuple[str, list[tuple[str, str]]]],
    plain: bool = False,
    width: int | None = None,
) -> str:
    use_color = color_enabled(plain)
    accent = COLORS.get(str(config.get("accent", "teal")), COLORS["teal"]) if use_color else ""
    muted = COLORS["muted"] if use_color else ""
    bold = COLORS["bold"] if use_color else ""
    reset = COLORS["reset"] if use_color else ""
    terminal_width = width or shutil.get_terminal_size((80, 24)).columns
    terminal_width = max(30, min(terminal_width, 100))
    framed = terminal_width >= 56
    frame_width = terminal_width if framed else terminal_width
    inner = frame_width - 4 if framed else frame_width

    def fit(text: str, limit: int) -> str:
        if visible_width(text) <= limit:
            return text
        return clip_text(text, limit)

    def row(content: str = "", align: str = "left", style: str = "") -> str:
        content = fit(content, inner - (2 if align == "left" else 0))
        used = visible_width(content)
        if align == "center":
            left_pad = max(0, (inner - used) // 2)
            body = " " * left_pad + content + " " * max(0, inner - used - left_pad)
        else:
            body = "  " + content + " " * max(0, inner - used - 2)
        if not framed:
            return f"{style}{body}{reset}"
        return f"{accent}│{reset} {style}{body}{reset} {accent}│{reset}"

    if framed:
        top_label = f"◇ {APP_NAME.upper()} {VERSION} ◇"
        bottom_label = "ABDUFORGE · LOCAL SYSTEM SNAPSHOT"
        def border(label: str, left: str, right: str) -> str:
            available = max(0, frame_width - visible_width(label) - 2)
            left_count = available // 2
            return f"{accent}{left}{'─' * left_count}{label}{'─' * (available - left_count)}{right}{reset}"
        output = [border(top_label, "╭", "╮"), row()]
    else:
        output = [f"{bold}{accent}{APP_NAME.upper()} {VERSION}{reset}", ""]

    logo, subtitle = get_logo(config)
    for logo_line in logo:
        output.append(row(logo_line, "center", accent + bold))
    if subtitle:
        output.append(row(subtitle, "center", muted))
    output.append(row())

    for group_name, items in groups:
        output.append(row(f"◆  {group_name}", "left", accent + bold))
        for label, value in items:
            label_width = min(17, max(11, inner // 3))
            available_value = max(8, inner - label_width - 5)
            value = fit(value, available_value)
            output.append(row(f"{label:<{label_width}} : {value}", "left", muted))
        output.append(row("·" * min(24, max(3, inner - 5)), "left", muted))

    output.append(row("READ-ONLY  ·  NO NETWORK SCANNING  ·  NO SYSTEM CHANGES", "center", muted))
    if framed:
        output.append(border(bottom_label, "╰", "╯"))
    return "\n".join(output)


def to_json(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    payload = {
        "application": APP_NAME,
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": {name.lower().replace(" & ", "_").replace(" ", "_"): dict(items) for name, items in groups},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_markdown(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    lines = [f"# {APP_NAME} system report", "", f"Version: {VERSION}", f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}", ""]
    for name, items in groups:
        lines += [f"## {name.title()}", "", "| Property | Value |", "|:--|:--|"]
        for key, value in items:
            escaped = value.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {key} | {escaped} |")
        lines.append("")
    lines += ["---", "Generated locally by ForgeFetch. No network scanning was performed.", ""]
    lines += ["**Privacy note:** this report may contain your hostname and local IP addresses. Review it before sharing.", ""]
    return "\n".join(lines)


def write_report(path: str, groups: list[tuple[str, list[tuple[str, str]]]]) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_markdown(groups), encoding="utf-8")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A customizable, local-first Linux system summary.")
    parser.add_argument("--setup", action="store_true", help="Choose logo style and accent again")
    parser.add_argument("--json", action="store_true", help="Print a structured JSON snapshot")
    parser.add_argument("--report", metavar="FILE", help="Write a Markdown report to FILE")
    parser.add_argument("--plain", "--no-color", dest="plain", action="store_true", help="Disable terminal colors")
    parser.add_argument("--no-network", action="store_true", help="Hide network interfaces and local IP addresses")
    parser.add_argument("--watch", nargs="?", const=2.0, type=float, metavar="SECONDS", help="Refresh the terminal snapshot continuously (default: 2 seconds)")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.watch is not None and (args.json or args.report):
        print("ForgeFetch: --watch cannot be combined with --json or --report.", file=sys.stderr)
        return 2
    if args.watch is not None and (args.watch <= 0 or args.watch > 60):
        print("ForgeFetch: watch interval must be greater than 0 and no more than 60 seconds.", file=sys.stderr)
        return 2
    if args.watch is not None and not sys.stdout.isatty():
        print("ForgeFetch: --watch requires an interactive terminal.", file=sys.stderr)
        return 2

    if args.setup:
        if not sys.stdin.isatty():
            print("ForgeFetch setup requires an interactive terminal.", file=sys.stderr)
            return 2
        config = setup_config()
    else:
        config = load_config()
        if config is None:
            if sys.stdin.isatty():
                config = setup_config()
            else:
                config = default_config()

    if args.watch is not None:
        try:
            while True:
                groups = get_info(include_network=not args.no_network)
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write(render_terminal(config, groups, plain=args.plain))
                sys.stdout.write(f"\nRefreshing every {args.watch:g}s · Press Ctrl+C to exit.\n")
                sys.stdout.flush()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            sys.stdout.write("\nForgeFetch watch stopped.\n")
            return 130

    groups = get_info(include_network=not args.no_network)
    if args.json:
        print(to_json(groups))
        return 0
    if args.report:
        try:
            target = write_report(args.report, groups)
        except OSError as exc:
            print(f"ForgeFetch: cannot write report: {exc}", file=sys.stderr)
            return 1
        print(f"ForgeFetch report saved: {target}")
        return 0
    print(render_terminal(config, groups, plain=args.plain))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nForgeFetch: cancelled.", file=sys.stderr)
        raise SystemExit(130)
