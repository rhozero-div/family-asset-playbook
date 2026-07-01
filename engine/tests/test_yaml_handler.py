"""web.yaml_handler 单元测试。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from web import yaml_handler  # noqa: E402


class TestYamlHandlerCodeResolution(unittest.TestCase):
    def test_resolve_code_prefers_explicit_client_code_even_if_name_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_dir = Path(tmpdir)
            (profiles_dir / "clients.json").write_text(
                json.dumps(
                    {
                        "000001": {
                            "name": "王先生",
                            "yaml_file": "000001.yaml",
                            "tags": ["", ""],
                            "notes": "",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            sample_yaml = Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8")
            code = yaml_handler._resolve_code(sample_yaml, "991001", profiles_dir)  # noqa: SLF001
            self.assertEqual(code, "991001")

    def test_ensure_code_is_available_rejects_taken_code_with_other_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "clients.json").write_text(
                json.dumps(
                    {
                        "123456": {
                            "name": "其他客户",
                            "yaml_file": "123456.yaml",
                            "tags": ["", ""],
                            "notes": "",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            sample_yaml = Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8")
            with mock.patch.object(yaml_handler, "PROJECT_ROOT", root):
                ok, code, error = yaml_handler.ensure_code_is_available(sample_yaml, "123456")
            self.assertFalse(ok)
            self.assertEqual(code, "")
            self.assertIn("123456", error)
