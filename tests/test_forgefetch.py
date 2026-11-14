import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import forgefetch as ff


class ParsingTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(ff.VERSION, "1.4.0")

    def test_parse_os_release(self):
        result = ff.parse_os_release('NAME="Test Linux"\nID=test\n# comment\nBROKEN')
        self.assertEqual(result["NAME"], "Test Linux")
        self.assertEqual(result["ID"], "test")
        self.assertNotIn("BROKEN", result)

    def test_parse_meminfo(self):
        result = ff.parse_meminfo("MemTotal: 1000 kB\nMemAvailable: 250 kB\nSwapTotal: 200 kB\nSwapFree: 50 kB")
        self.assertEqual(result["MemTotal"], 1_024_000)
        self.assertEqual(result["MemAvailable"], 256_000)
        self.assertEqual(result["SwapTotal"], 204_800)
        self.assertEqual(result["SwapFree"], 51_200)

    def test_meminfo_falls_back_to_memfree(self):
        result = ff.parse_meminfo("MemTotal: 100 kB\nMemFree: 20 kB")
        self.assertEqual(result["MemAvailable"], result["MemFree"])

    def test_human_bytes(self):
        self.assertEqual(ff.human_bytes(512), "512 B")
        self.assertEqual(ff.human_bytes(1024), "1.0 KiB")
        self.assertEqual(ff.human_bytes(None), "Not available")

    def test_sections_default_to_all(self):
        self.assertEqual(ff.parse_sections(None), list(ff.SECTIONS))

    def test_sections_parse_comma_and_repeat(self):
        self.assertEqual(ff.parse_sections(["cpu,memory", "storage"]), ["cpu", "memory", "storage"])

    def test_sections_all_keyword(self):
        self.assertEqual(ff.parse_sections(["all"]), list(ff.SECTIONS))

    def test_unknown_section_rejected(self):
        with self.assertRaises(ValueError):
            ff.parse_sections(["networking"])

    def test_format_value(self):
        self.assertEqual(ff.format_value(["a", "b"]), "a, b")
        self.assertEqual(ff.format_value([]), "None detected")
        self.assertEqual(ff.format_value(None), "Not available")

    def test_cpu_model_does_not_use_numeric_processor_index(self):
        with mock.patch.object(ff, "read_text", return_value="processor : 0\nmodel name : Example CPU 123"):
            self.assertEqual(ff.read_cpu_model(), "Example CPU 123")

    def test_cpu_model_falls_back_when_no_model_field_exists(self):
        with mock.patch.object(ff, "read_text", return_value="processor : 0"), mock.patch.object(ff.platform, "processor", return_value=""):
            self.assertEqual(ff.read_cpu_model(), "Not available")


class HealthCheckTests(unittest.TestCase):
    def make_data(self, temperature=40, memory=50, disk=40, swap=10):
        return {
            "sensors": {"max_temperature_c": temperature},
            "memory": {"used_percent": memory, "swap_used_percent": swap, "swap_total_bytes": 100},
            "storage": {"root_filesystem": {"used_percent": disk}},
        }

    def test_normal_metrics_are_ok(self):
        statuses = {row["item"]: row["status"] for row in ff.health_checks(self.make_data())}
        self.assertEqual(statuses["Memory"], "OK")
        self.assertEqual(statuses["Root filesystem"], "OK")

    def test_high_temperature_warns(self):
        rows = ff.health_checks(self.make_data(temperature=91))
        self.assertEqual(rows[0]["status"], "WARN")

    def test_high_memory_and_disk_warn(self):
        rows = ff.health_checks(self.make_data(memory=95, disk=96, swap=95))
        statuses = {row["item"]: row["status"] for row in rows}
        self.assertEqual(statuses["Memory"], "WARN")
        self.assertEqual(statuses["Root filesystem"], "WARN")
        self.assertEqual(statuses["Swap"], "WARN")

    def test_missing_sensor_is_informational(self):
        rows = ff.health_checks(self.make_data(temperature=None))
        self.assertEqual(rows[0]["status"], "INFO")


class OutputTests(unittest.TestCase):
    def sample_data(self):
        return {
            "app": ff.APP_NAME, "version": ff.VERSION, "generated_at": "2026-11-14T00:00:00+00:00",
            "system": {"os": "Test OS", "hostname": "testbox", "kernel": "6.1", "architecture": "x86_64", "uptime": "1d 2h", "boot_mode": "UEFI"},
            "cpu": {"model": "Test CPU", "logical_cores": 4, "frequency_mhz": 1200.0, "governor": "powersave", "load_average": [0.1, 0.2, 0.3], "process_count": 50},
            "memory": {"total_bytes": 1024, "available_bytes": 512, "used_percent": 50.0, "swap_total_bytes": 0, "swap_used_bytes": 0, "swap_used_percent": 0.0},
            "storage": {"root_filesystem": {"total_bytes": 1024, "used_bytes": 512, "free_bytes": 512, "used_percent": 50.0}},
            "graphics": {"gpus": ["Intel (0x1234)"]}, "sensors": {"max_temperature_c": 40.0, "battery": None},
            "network": {"interfaces": [], "local_addresses": []},
            "security": {"secure_boot": "Unknown", "ufw": "Not installed", "ssh_server_binary": "Not installed"},
        }

    def test_rows_filter_to_selected_section(self):
        rows = ff.display_rows(self.sample_data(), ["cpu"])
        self.assertTrue(rows)
        self.assertEqual(rows[0][0], "Processor")
        self.assertFalse(any(key == "Hostname" for key, _ in rows))

    def test_markdown_report_contains_selected_section(self):
        report = ff.markdown_report(self.sample_data(), ["cpu"])
        self.assertIn("## Cpu", report)
        self.assertIn("Test CPU", report)
        self.assertNotIn("## Network", report)

    def test_markdown_escapes_table_delimiter(self):
        data = self.sample_data()
        data["system"]["hostname"] = "host|name"
        report = ff.markdown_report(data, ["system"])
        self.assertIn("host\\|name", report)

    def test_load_config_accepts_valid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"brand_name": "My Forge", "accent": "green"}), encoding="utf-8")
            self.assertEqual(ff.load_config(path), {"brand_name": "My Forge", "accent": "green"})

    def test_load_config_ignores_invalid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"brand_name": "x" * 80, "accent": "orange"}), encoding="utf-8")
            self.assertEqual(ff.load_config(path), {"brand_name": ff.APP_NAME, "accent": "cyan"})


class CliTests(unittest.TestCase):
    def test_version_option(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as ctx:
            ff.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("ForgeFetch 1.4.0", output.getvalue())

    def test_list_sections(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ff.main(["--list-sections"]), 0)
        self.assertIn("storage", output.getvalue())

    def test_json_no_network(self):
        data = self.sample_data_for_cli()
        data["network"] = {"status": "Hidden by --no-network", "interfaces": [], "local_addresses": []}
        output = io.StringIO()
        with mock.patch.object(ff, "collect_system", return_value=data):
            with contextlib.redirect_stdout(output):
                self.assertEqual(ff.main(["--json", "--no-network"]), 0)
        parsed = json.loads(output.getvalue())
        self.assertEqual(parsed["network"]["status"], "Hidden by --no-network")

    def test_report_export(self):
        data = self.sample_data_for_cli()
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.md"
            output = io.StringIO()
            with mock.patch.object(ff, "collect_system", return_value=data):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(ff.main(["--report", str(report), "--section", "cpu"]), 0)
            self.assertTrue(report.exists())
            self.assertIn("Test CPU", report.read_text(encoding="utf-8"))

    def test_json_and_report_are_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            ff.main(["--json", "--report"])
        self.assertEqual(ctx.exception.code, 2)

    def test_sample_data_factory(self):
        self.assertEqual(self.sample_data_for_cli()["version"], ff.VERSION)

    def test_watch_rejects_out_of_range_interval(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            ff.main(["--watch", "61"])
        self.assertEqual(ctx.exception.code, 2)

    def test_check_flag_includes_health_checks_in_json(self):
        data = self.sample_data_for_cli()
        output = io.StringIO()
        with mock.patch.object(ff, "collect_system", return_value=data):
            with contextlib.redirect_stdout(output):
                self.assertEqual(ff.main(["--json", "--check"]), 0)
        parsed = json.loads(output.getvalue())
        self.assertTrue(parsed["health_checks"])

    @staticmethod
    def sample_data_for_cli():
        return OutputTests().sample_data()


if __name__ == "__main__":
    unittest.main()
