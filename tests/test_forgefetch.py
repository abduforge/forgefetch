import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import forgefetch


class ForgeFetchTests(unittest.TestCase):
    def test_parse_os_release(self):
        result = forgefetch.parse_os_release('NAME="MX Linux"\nID=mx\nID_LIKE="debian"')
        self.assertEqual(result["NAME"], "MX Linux")
        self.assertEqual(result["ID"], "mx")

    def test_parse_meminfo(self):
        result = forgefetch.parse_meminfo("MemTotal: 1024 kB\nMemAvailable: 512 kB\nSwapTotal: 0 kB")
        self.assertEqual(result["MemTotal"], 1024 * 1024)
        self.assertEqual(result["MemAvailable"], 512 * 1024)

    def test_human_bytes(self):
        self.assertEqual(forgefetch.human_bytes(0), "0 B")
        self.assertEqual(forgefetch.human_bytes(1024), "1.0 KiB")

    def test_uptime_format_from_mock(self):
        # Exercise formatting logic through a known /proc-like string by patching read_text.
        original = forgefetch.read_text
        try:
            forgefetch.read_text = lambda path, default="": "90061.0 0.0" if str(path) == "/proc/uptime" else default
            self.assertEqual(forgefetch.read_uptime(), "1d 1h 1m")
        finally:
            forgefetch.read_text = original

    def test_distro_wordmark_mx(self):
        word, subtitle = forgefetch.distro_wordmark({"ID": "mx", "PRETTY_NAME": "MX Linux"})
        self.assertEqual(word, "MX")
        self.assertEqual(subtitle, "MX Linux")

    def test_big_text_dimensions(self):
        lines = forgefetch.big_text("FORGE")
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(len(line) == len(lines[0]) for line in lines))

    def test_custom_config_logo(self):
        logo, subtitle = forgefetch.get_logo({"logo_mode": "custom", "custom_text": "ABDU", "subtitle": "My system"})
        self.assertEqual(len(logo), 5)
        self.assertEqual(subtitle, "My system")

    def test_json_report(self):
        text = forgefetch.to_json([("SYSTEM", [("OS", "MX Linux")])])
        parsed = json.loads(text)
        self.assertEqual(parsed["system"]["OS"], "MX Linux")

    def test_markdown_report(self):
        text = forgefetch.to_markdown([("SYSTEM", [("OS", "MX | Linux")])])
        self.assertIn("MX \\| Linux", text)
        self.assertIn("# ForgeFetch system report", text)

    def test_render_has_logo_before_characteristics(self):
        config = {"logo_mode": "custom", "custom_text": "FORGE", "subtitle": "test", "accent": "teal"}
        groups = [("SYSTEM", [("OS", "Test Linux")])]
        output = forgefetch.render_terminal(config, groups, plain=True, width=80)
        self.assertLess(output.index("SYSTEM"), output.index("OS"))
        self.assertIn("READ-ONLY", output)
        self.assertIn("╭", output)
        self.assertIn("╯", output)

    def test_parser_version(self):
        parser = forgefetch.build_parser()
        options = {action.dest for action in parser._actions}
        self.assertIn("setup", options)
        self.assertIn("json", options)
        self.assertIn("report", options)


    def test_distro_mx_uses_builtin_art(self):
        with patch.object(forgefetch, "parse_os_release", return_value={"ID": "mx", "PRETTY_NAME": "MX Linux 25.3"}):
            logo, subtitle = forgefetch.get_logo({"logo_mode": "distro"})
        self.assertIn("MX LINUX", logo[-1])
        self.assertEqual(subtitle, "MX Linux 25.3")

    def test_unknown_distro_falls_back_to_wordmark(self):
        with patch.object(forgefetch, "parse_os_release", return_value={"ID": "unknownos", "PRETTY_NAME": "Unknown OS"}):
            logo, subtitle = forgefetch.get_logo({"logo_mode": "distro"})
        self.assertEqual(len(logo), 5)
        self.assertEqual(subtitle, "Unknown OS")

    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(forgefetch, "CONFIG_DIR", root), patch.object(forgefetch, "CONFIG_FILE", root / "config.json"):
                config = {"config_version": 1, "logo_mode": "custom", "custom_text": "ABDU", "subtitle": "Personal mark", "accent": "blue"}
                forgefetch.save_config(config)
                self.assertEqual(forgefetch.load_config(), config)

    def test_plain_output_has_no_ansi(self):
        config = {"logo_mode": "custom", "custom_text": "FORGE", "subtitle": "Snapshot", "accent": "teal"}
        output = forgefetch.render_terminal(config, [("SYSTEM", [("OS", "Linux")])], plain=True, width=80)
        self.assertNotIn("\033[", output)

    def test_empty_meminfo(self):
        self.assertEqual(forgefetch.parse_meminfo(""), {})


if __name__ == "__main__":
    unittest.main()
