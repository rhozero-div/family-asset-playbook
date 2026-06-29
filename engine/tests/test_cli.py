"""CLI 端到端测试。"""
import io
import sys
import unittest
from unittest import mock
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.cli import _resolve_terminal_start_year, main  # noqa: E402

SAMPLE_YAML = ROOT / "samples" / "client-profile.example.yaml"


class TestCLIMain(unittest.TestCase):
    def test_terminal_start_year_falls_back_to_current_year_when_no_future_events(self):
        profile = SimpleNamespace(current_year=2026, events=())
        self.assertEqual(_resolve_terminal_start_year(profile), 2026)

    def test_terminal_start_year_uses_last_future_event(self):
        events = (
            SimpleNamespace(timing_year=2020),
            SimpleNamespace(timing_year=2029),
            SimpleNamespace(timing_year=2035),
        )
        profile = SimpleNamespace(current_year=2026, events=events)
        self.assertEqual(_resolve_terminal_start_year(profile), 2035)

    def test_main_with_sample_yaml_prints_markdown_to_stdout(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    "--profile",
                    str(SAMPLE_YAML),
                    "--current-year",
                    "2026",
                ]
            )
        self.assertEqual(code, 0)
        output = out.getvalue()
        self.assertIn("# 王先生 家庭资产配置剧本", output)
        self.assertIn("A. 客户情况概览", output)
        self.assertIn("B. 资产推演", output)
        self.assertIn("C. 资产配置执行方案", output)
        self.assertIn("不构成投资建议", output)

    def test_main_still_renders_without_qmc_dependency(self):
        out = io.StringIO()
        with redirect_stdout(out):
            with mock.patch("engine.cli.project_yearly_with_returns", side_effect=ModuleNotFoundError("No module named 'qmc'")):
                code = main(
                    [
                        "--profile",
                        str(SAMPLE_YAML),
                        "--current-year",
                        "2026",
                    ]
                )
        self.assertEqual(code, 0)
        output = out.getvalue()
        self.assertIn("# 王先生 家庭资产配置剧本", output)

    def test_main_missing_required_arg_returns_nonzero(self):
        """缺 --profile 时,argparse 直接 sys.exit(2)。main 不会返回值。"""
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertNotEqual(cm.exception.code, 0)

    def test_main_nonexistent_file_returns_error_code(self):
        code = main(["--profile", "/nonexistent_file.yaml", "--current-year", "2026"])
        # 期望退出码 2(ProfileLoadError 文件不存在)
        self.assertEqual(code, 2)
