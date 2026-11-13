#!/usr/bin/env python3
"""ForgeFetch: a small, local-first Linux system summary for the terminal."""
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
from pathlib import Path
from typing import Any

APP_NAME = "ForgeFetch"
VERSION = "1.0.0"
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

# Compact 5x5 glyphs. This keeps ForgeFetch dependency-free and sharp in terminals.
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
    "linux mint": ("MINT", "LINUX MINT"),
    "fedora": ("FEDORA", "FEDORA LINUX"),
    "arch": ("ARCH", "ARCH LINUX"),
    "manjaro": ("MANJARO", "MANJARO LINUX"),
    "opensuse": ("OPENSUSE", "OPENSUSE"),
    "pop!_os": ("POP OS", "POP!_OS"),
}

# Small built-in distribution marks. They are intentionally original terminal
# interpretations, not copies of vendor artwork or logos.
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
        "        /",
        "       /  /",
        "      /  /  /",
        "     /______/",
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
    "linux mint": (
        "     .--------.",
        "     |  LINUX |",
        "     |   MINT |",
        "     '--------'",
    ),
}


def read_text(path: str | Path, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, PermissionError):
        return default


def parse_os_release(text: str | None = None) -> dict[str, str]:
    raw = text if text is not None else read_text("/etc/os-release")
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        result[key.strip()] = value
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
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return "Unknown"


def read_cpu_model() -> str:
    cpuinfo = read_text("/proc/cpuinfo")
    for line in cpuinfo.splitlines():
        if line.lower().startswith(("model name", "hardware", "processor")) and ":" in line:
            value = line.split(":", 1)[1].strip()
            if value and not value.isdigit():
                return value
    return platform.processor() or "Unknown CPU"


def read_uptime() -> str:
    raw = read_text("/proc/uptime")
    try:
        seconds = int(float(raw.split()[0]))
    except (ValueError, IndexError):
        return "Unknown"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def read_temperature() -> str:
    candidates = list(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    for candidate in candidates:
        raw = read_text(candidate)
        try:
            celsius = int(raw) / 1000
        except ValueError:
            continue
        if -10 <= celsius <= 150:
            return f"{celsius:.0f} °C"
    return "Unavailable"


def read_gpu() -> str:
    drm = Path("/sys/class/drm")
    for card in sorted(drm.glob("card[0-9]*/device")):
        vendor = read_text(card / "vendor")
        device = read_text(card / "device")
        if vendor and device:
            names = {"0x8086": "Intel graphics", "0x1002": "AMD graphics", "0x10de": "NVIDIA graphics"}
            return f"{names.get(vendor.lower(), 'GPU')} ({vendor}:{device})"
    return "Not detected"


def get_info() -> list[tuple[str, list[tuple[str, str]]]]:
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
        disk_value = f"{human_bytes(disk.used)} used / {human_bytes(disk.total)} ({disk.used / disk.total * 100:.0f}%)" if disk.total else "Unknown"
    except OSError:
        disk_value = "Unavailable"

    session = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "Unknown"
    window_manager = os.environ.get("XDG_SESSION_TYPE", "Unknown")
    shell = Path(os.environ.get("SHELL", "")).name or "Unknown"
    terminal = os.environ.get("TERM_PROGRAM") or os.environ.get("TERM", "Unknown")

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        ("SYSTEM", [
            ("OS", os_name),
            ("Host", socket.gethostname() or "Unknown"),
            ("Kernel", platform.release()),
            ("Architecture", platform.machine()),
            ("Uptime", read_uptime()),
        ]),
        ("HARDWARE", [
            ("CPU", read_cpu_model()),
            ("Logical cores", str(os.cpu_count() or "Unknown")),
            ("Graphics", read_gpu()),
            ("Temperature", read_temperature()),
        ]),
        ("RESOURCES", [
            ("Memory", f"{human_bytes(mem_used)} used / {human_bytes(mem_total)} ({mem_used / mem_total * 100:.0f}%)" if mem_used is not None and mem_total else "Unknown"),
            ("Available RAM", human_bytes(mem_available)),
            ("Swap", f"{human_bytes(swap_total - swap_free)} used / {human_bytes(swap_total)}"),
            ("Root disk", disk_value),
        ]),
        ("SESSION", [
            ("Desktop", session),
            ("Session type", window_manager),
            ("Shell", shell),
            ("Terminal", terminal),
        ]),
    ]
    return groups


def distro_wordmark(osr: dict[str, str]) -> tuple[str, str]:
    ident = osr.get("ID", "").lower()
    pretty = osr.get("PRETTY_NAME", osr.get("NAME", "LINUX"))
    like = osr.get("ID_LIKE", "").lower().split()
    candidates = [ident] + like
    for candidate in candidates:
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
    text = text.upper()[:9]
    if not text:
        text = "FORGE"
    glyphs = [FONT.get(char, FONT["-"]) for char in text]
    return [" ".join("".join("█" if pixel == "1" else " " for pixel in glyph[row]) for glyph in glyphs) for row in range(5)]


def load_config() -> dict[str, Any] | None:
    try:
        value = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return None
        return value
    except (OSError, json.JSONDecodeError):
        return None


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass
    temp = CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(CONFIG_FILE)


def setup_config() -> dict[str, Any]:
    print("\nForgeFetch · First-run setup")
    print("Choose the logo style:")
    print("  1) Distribution wordmark (auto-detect Linux distribution)")
    print("  2) My own wordmark (large custom letters)")
    choice = input("Selection [1]: ").strip() or "1"
    mode = "custom" if choice == "2" else "distro"
    custom = "FORGE"
    subtitle = "A personal Linux snapshot"
    if mode == "custom":
        raw = input("Your wordmark, up to 9 Latin letters/numbers [FORGE]: ").strip()
        custom = re.sub(r"[^A-Za-z0-9._-]", "", raw.upper())[:9] or "FORGE"
        subtitle = re.sub(r"[\x00-\x1f\x7f]", "", input("Short subtitle [A personal Linux snapshot]: ").strip())[:56] or subtitle
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
        word = str(config.get("custom_text", "FORGE"))
        subtitle = str(config.get("subtitle", ""))
        return big_text(word), subtitle

    osr = parse_os_release()
    ident = osr.get("ID", "").lower()
    like = osr.get("ID_LIKE", "").lower().split()
    pretty = osr.get("PRETTY_NAME", osr.get("NAME", "Linux"))
    candidates = [ident] + like
    for candidate in candidates:
        if candidate in DISTRO_ARTS:
            return list(DISTRO_ARTS[candidate]), pretty
    word, subtitle = distro_wordmark(osr)
    return big_text(word), subtitle


def color_enabled(plain: bool) -> bool:
    return not plain and sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def render_terminal(config: dict[str, Any], groups: list[tuple[str, list[tuple[str, str]]]], plain: bool = False, width: int | None = None) -> str:
    use_color = color_enabled(plain)
    accent = COLORS.get(str(config.get("accent", "teal")), COLORS["teal"]) if use_color else ""
    muted = COLORS["muted"] if use_color else ""
    bold = COLORS["bold"] if use_color else ""
    reset = COLORS["reset"] if use_color else ""
    width = width or shutil.get_terminal_size((80, 24)).columns
    width = max(52, min(width, 96))
    inner = width - 4

    def box(content: str = "", align: str = "left", color: str = "") -> str:
        clean_len = len(content)
        if clean_len > inner:
            content = content[: max(0, inner - 1)] + "…"
            clean_len = len(content)
        if align == "center":
            left = (inner - clean_len) // 2
            padded = " " * left + content + " " * (inner - clean_len - left)
        else:
            padded = "  " + content + " " * max(0, inner - clean_len - 2)
        return f"{accent}│{reset} {color}{padded}{reset} {accent}│{reset}"

    top_label = f"◇ {APP_NAME.upper()} {VERSION} ◇"
    left_corner, right_corner = "╭─✦", "✦─╮"
    remaining = max(0, width - len(top_label) - len(left_corner) - len(right_corner))
    top = f"{accent}{left_corner}{reset}{muted}{'─' * (remaining // 2)}{reset}{bold}{accent}{top_label}{reset}{muted}{'─' * (remaining - remaining // 2)}{reset}{accent}{right_corner}{reset}"
    bottom_label = "ABDUFORGE · LOCAL SYSTEM SNAPSHOT"
    bottom_left, bottom_right = "╰─❖", "❖─╯"
    remaining_bottom = max(0, width - len(bottom_label) - len(bottom_left) - len(bottom_right))
    bottom = f"{accent}{bottom_left}{reset}{muted}{'─' * (remaining_bottom // 2)}{reset}{accent}{bottom_label}{reset}{muted}{'─' * (remaining_bottom - remaining_bottom // 2)}{reset}{accent}{bottom_right}{reset}"

    output = [top, box(),]
    logo, subtitle = get_logo(config)
    for row in logo:
        output.append(box(row, "center", accent + bold))
    output.append(box(subtitle[:inner], "center", muted))
    output.append(box())

    for group_name, items in groups:
        heading = f"◆  {group_name}"
        output.append(box(heading, "left", accent + bold))
        for label, value in items:
            # Keep values readable in narrow terminals.
            prefix = f"{label:<16}"
            max_value = max(8, inner - len(prefix) - 3)
            if len(value) > max_value:
                value = value[: max_value - 1] + "…"
            line = prefix + " : " + value
            output.append(box(line, "left", muted))
        output.append(box("·" * min(24, inner - 4), "left", muted))
    output.append(box("READ-ONLY  ·  NO NETWORK SCANNING  ·  NO SYSTEM CHANGES", "center", muted))
    output.append(bottom)
    return "\n".join(output)


def to_json(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    return json.dumps({name.lower(): dict(items) for name, items in groups}, ensure_ascii=False, indent=2)


def to_markdown(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    lines = [f"# {APP_NAME} system report", "", f"Version: {VERSION}", ""]
    for name, items in groups:
        lines += [f"## {name.title()}", "", "| Property | Value |", "|:--|:--|"]
        lines += [f"| {key} | {value.replace('|', '\\|')} |" for key, value in items]
        lines.append("")
    lines += ["---", "Generated locally by ForgeFetch. No network scanning was performed."]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A customizable Linux system summary with a centered wordmark.")
    parser.add_argument("--setup", action="store_true", help="Choose logo style and accent again")
    parser.add_argument("--json", action="store_true", help="Print system information as JSON")
    parser.add_argument("--report", metavar="FILE", help="Write a Markdown report to FILE")
    parser.add_argument("--plain", action="store_true", help="Disable terminal colors")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = setup_config() if args.setup else load_config()
    if config is None:
        if sys.stdin.isatty():
            config = setup_config()
        else:
            config = {"config_version": 1, "logo_mode": "distro", "custom_text": "FORGE", "subtitle": "A personal Linux snapshot", "accent": "teal"}
    groups = get_info()
    if args.json:
        print(to_json(groups))
        return 0
    if args.report:
        target = Path(args.report).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_markdown(groups), encoding="utf-8")
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
