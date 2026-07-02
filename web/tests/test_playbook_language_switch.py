"""剧本页语言切换与存储路径回归测试。"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from web import routes  # noqa: E402


class TestPlaybookLanguageSwitch(unittest.TestCase):
    def setUp(self):
        self.original_save_and_generate = routes.save_yaml_and_generate
        self.original_storage_enabled = routes.server_storage_enabled
        self.original_storage_dir = routes.storage_dir

    def tearDown(self):
        routes.save_yaml_and_generate = self.original_save_and_generate
        routes.server_storage_enabled = self.original_storage_enabled
        routes.storage_dir = self.original_storage_dir

    @staticmethod
    def _request(path: str, query: str = "") -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": query.encode("utf-8"),
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
            }
        )

    def test_playbook_view_uses_storage_dir_and_supports_english_switch(self):
        routes.server_storage_enabled = lambda: True
        routes.save_yaml_and_generate = lambda yaml_text, current_year, client_code="", lang="zh": (
            True,
            "# Family Asset Playbook\n\n## Executive Summary\n\nSummary." if lang == "en"
            else "# 家庭资产配置剧本\n\n## 综合建议摘要\n\n这里是摘要。",
            "",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            routes.storage_dir = lambda: tmp_path
            (tmp_path / "000001.yaml").write_text(
                "family:\n"
                "  members:\n"
                "    - name: 王先生\n"
                "      role: primary_breadwinner\n",
                encoding="utf-8",
            )

            response = asyncio.run(
                routes.playbook_view(
                    self._request("/playbook/000001", "lang=en"),
                    "000001",
                )
            )

        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Family Asset Playbook", body)
        self.assertIn("?lang=zh", body)
        self.assertIn("?lang=en", body)
        self.assertNotIn('action="/asset-planner/analyze"', body)
        self.assertNotIn('action="/insurance-planner/analyze"', body)

    def test_generate_uses_storage_dir_when_code_missing(self):
        routes.server_storage_enabled = lambda: True
        routes.save_yaml_and_generate = lambda yaml_text, current_year, client_code="", lang="zh": (
            True,
            "# 家庭资产配置剧本\n\n## 综合建议摘要\n\n这里是摘要。",
            "",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            routes.storage_dir = lambda: tmp_path
            (tmp_path / "clients.json").write_text("{}", encoding="utf-8")

            response = asyncio.run(
                routes.questionnaire_generate(
                    Request(
                        {
                            "type": "http",
                            "http_version": "1.1",
                            "method": "POST",
                            "scheme": "http",
                            "path": "/questionnaire/generate",
                            "raw_path": b"/questionnaire/generate",
                            "query_string": b"",
                            "headers": [],
                            "client": ("testclient", 50000),
                            "server": ("testserver", 80),
                        }
                    ),
                    yaml_content=(
                        "family:\n"
                        "  members:\n"
                        "    - name: 王先生\n"
                        "      role: primary_breadwinner\n"
                    ),
                    yaml_file=None,
                    current_year=2026,
                    client_code="",
                    lang="zh",
                )
            )

        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("客户 000001", body)
        self.assertNotIn('action="/asset-planner/analyze"', body)


if __name__ == "__main__":
    unittest.main()
