import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import forgefetch


class ForgeFetchTests(unittest.TestCase):
    def test_parse_os_release_quotes_and_spaces(self):
        result = forgefetch.parse_os_release('NAME="MX Linux"\nID=mx\nID_LIKE="debian"')
        self.assertEqual(result["NAME"], "MX Linux")
        self.assertEqual(result["ID"], "mx")
        self.assertEqual(result["ID_LIKE"], "debian")

    def test_parse_os_release_invalid_quote_fallback(self):
        result = forgefetch.parse_os_release('PRETTY_NAME="Broken Linux')
        self.assertEqual(result["PRETTY_NAME"], "Broken Linux")

    def test_parse_meminfo(self):
        result = forgefetch.parse_meminfo("MemTotal: 1024 kB\nMemAvailable: 512 kB\nSwapTotal: 0 kB")
        self.assertEqual(result["MemTotal"], 1024 * 1024)
        self.assertEqual(result["MemAvailable"], 512 * 1024)

    def test_human_bytes(self):
        self.assertEqual(forgefetch.human_bytes(0), "0 B")
        self.assertEqual(forgefetch.human_bytes(1024), "1.0 KiB")
        self.assertEqual(forgefetch.human_bytes(None), "Unknown")

    def test_uptime_format(self):
        with patch.object(forgefetch, "read_text", return_value="90061.0 0.0"):
            self.assertEqual(forgefetch.read_uptime(), "1d 1h 1m")

    def test_load_average_format(self):
        with patch.object(forgefetch, "read_text", return_value="0.12 0.34 0.56 1/100 123"):
            self.assertEqual(forgefetch.read_load_average(), "0.12 / 0.34 / 0.56 (1/5/15m)")

    def test_load_average_invalid(self):
        with patch.object(forgefetch, "read_text", return_value="not available"):
            self.assertEqual(forgefetch.read_load_average(), "Unavailable")

    def test_process_count(self):
        class FakeEntry:
            def __init__(self, name):
                self.name = name
        with patch.object(Path, "iterdir", return_value=[FakeEntry("1"), FakeEntry("abc"), FakeEntry("22")]):
            self.assertEqual(forgefetch.read_process_count(), "2")

    def test_boot_mode(self):
        with patch.object(Path, "is_dir", return_value=True):
            self.assertEqual(forgefetch.read_boot_mode(), "UEFI")
        with patch.object(Path, "is_dir", return_value=False):
            self.assertEqual(forgefetch.read_boot_mode(), "Legacy BIOS")

    def test_distro_wordmark_mx(self):
        word, subtitle = forgefetch.distro_wordmark({"ID": "mx", "PRETTY_NAME": "MX Linux"})
        self.assertEqual(word, "MX")
        self.assertEqual(subtitle, "MX Linux")

    def test_big_text_dimensions(self):
        lines = forgefetch.big_text("FORGE")
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(len(line) == len(lines[0]) for line in lines))

    def test_big_text_sanitizes_input(self):
        lines = forgefetch.big_text("abdu forge!?")
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(len(line) == len(lines[0]) for line in lines))

    def test_custom_config_logo(self):
        logo, subtitle = forgefetch.get_logo({"logo_mode": "custom", "custom_text": "ABDU", "subtitle": "My system"})
        self.assertEqual(len(logo), 5)
        self.assertEqual(subtitle, "My system")

    def test_config_validation(self):
        valid = forgefetch.validate_config({"logo_mode": "custom", "custom_text": "forge!fetch", "accent": "blue"})
        self.assertEqual(valid["custom_text"], "FORGEFETC")
        self.assertIsNone(forgefetch.validate_config({"logo_mode": "bad", "accent": "blue"}))

    def test_config_round_trip_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "config.json"
            with patch.object(forgefetch, "CONFIG_DIR", root), patch.object(forgefetch, "CONFIG_FILE", config_file):
                config = {"config_version": 1, "logo_mode": "custom", "custom_text": "ABDU", "subtitle": "Personal mark", "accent": "blue"}
                forgefetch.save_config(config)
                self.assertEqual(forgefetch.load_config(), config)
                self.assertEqual(config_file.stat().st_mode & 0o777, 0o600)

    def test_json_report_shape(self):
        text = forgefetch.to_json([("SYSTEM", [("OS", "MX Linux")])])
        parsed = json.loads(text)
        self.assertEqual(parsed["application"], "ForgeFetch")
        self.assertEqual(parsed["data"]["system"]["OS"], "MX Linux")
        self.assertIn("generated_at", parsed)

    def test_markdown_report_escapes_pipes_and_privacy_note(self):
        text = forgefetch.to_markdown([("SYSTEM", [("OS", "MX | Linux")])])
        self.assertIn("MX \\| Linux", text)
        self.assertIn("# ForgeFetch system report", text)
        self.assertIn("local IP addresses", text)

    def test_render_has_logo_before_characteristics(self):
        config = {"logo_mode": "custom", "custom_text": "FORGE", "subtitle": "test", "accent": "teal"}
        groups = [("SYSTEM", [("OS", "Test Linux")])]
        output = forgefetch.render_terminal(config, groups, plain=True, width=80)
        self.assertLess(output.index("SYSTEM"), output.index("OS"))
        self.assertIn("READ-ONLY", output)
        self.assertIn("╭", output)
        self.assertIn("╯", output)

    def test_render_narrow_terminal_does_not_force_wide_frame(self):
        output = forgefetch.render_terminal(forgefetch.default_config(), [], plain=True, width=40)
        self.assertIn("FORGEFETCH", output)
        self.assertNotIn("╭", output)

    def test_parser_has_expected_options(self):
        parser = forgefetch.build_parser()
        options = {action.dest for action in parser._actions}
        self.assertTrue({"setup", "json", "report", "plain", "no_network", "watch"}.issubset(options))

    def test_mx_uses_builtin_art(self):
        with patch.object(forgefetch, "parse_os_release", return_value={"ID": "mx", "PRETTY_NAME": "MX Linux 25.3"}):
            logo, subtitle = forgefetch.get_logo({"logo_mode": "distro"})
        self.assertIn("MX LINUX", logo[-1])
        self.assertEqual(subtitle, "MX Linux 25.3")

    def test_unknown_distro_falls_back_to_wordmark(self):
        with patch.object(forgefetch, "parse_os_release", return_value={"ID": "unknownos", "PRETTY_NAME": "Unknown OS"}):
            logo, subtitle = forgefetch.get_logo({"logo_mode": "distro"})
        self.assertEqual(len(logo), 5)
        self.assertEqual(subtitle, "Unknown OS")

    def test_network_reader_handles_missing_ip_tool(self):
        with patch.object(forgefetch, "safe_run", return_value=""), patch.object(forgefetch, "read_default_interface", return_value="Unknown"), patch.object(Path, "glob", return_value=[]):
            interfaces, addresses = forgefetch.read_network()
        self.assertEqual(interfaces, "Not detected")
        self.assertEqual(addresses, "Unavailable")

    def test_safe_run_handles_missing_command(self):
        self.assertEqual(forgefetch.safe_run(["/definitely/not/a/command"]), "")

    def test_clip_text(self):
        self.assertEqual(forgefetch.clip_text("abcdefgh", 5), "abcd…")
        self.assertEqual(forgefetch.visible_width("abc"), 3)

    def test_version_is_1_3_0(self):
        self.assertEqual(forgefetch.VERSION, "1.3.0")


if __name__ == "__main__":
    unittest.main()
