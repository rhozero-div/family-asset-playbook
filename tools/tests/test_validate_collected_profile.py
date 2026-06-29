"""validate_collected_profile 的单元测试。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "validate_collected_profile.py"
SAMPLE = ROOT / "samples" / "client-profile.example.yaml"


class TestValidateCollectedProfile(unittest.TestCase):
    def test_sample_yaml_passes(self):
        """仓库内置的示例档案应通过校验。"""
        result = subprocess.run(
            [sys.executable, str(TOOL), str(SAMPLE)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("OK", result.stdout)

    def test_missing_file_returns_error(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "/nonexistent.yaml"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)

    def test_missing_required_field_returns_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("profile_version: '0.1'\n")  # 缺 schema_version
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, str(TOOL), path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("schema_version", result.stderr)
        finally:
            Path(path).unlink()

    def test_bad_enum_value_returns_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members: []\n"
                "events:\n"
                "  - id: e1\n"
                "    type: invalid_type\n"
                "    description: x\n"
                "    timing_year: 2029\n"
                "    certainty: high\n"
            )
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, str(TOOL), path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid_type", result.stderr)
        finally:
            Path(path).unlink()

    def test_minimal_top_level_schema_passes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members: []\n"
                "events: []\n"
            )
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, str(TOOL), path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
        finally:
            Path(path).unlink()

    def test_legacy_objectives_do_not_fail_validation(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members: []\n"
                "events: []\n"
                "objectives:\n"
                "  target_annual_return: 'legacy-string'\n"
                "  investment_horizon: 'legacy-string'\n"
                "  max_drawdown_tolerance: 'legacy-string'\n"
            )
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, str(TOOL), path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
        finally:
            Path(path).unlink()
