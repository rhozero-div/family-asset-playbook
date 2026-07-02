"""问卷回填工作流测试。"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from web import routes  # noqa: E402


class TestQuestionnaireReview(unittest.TestCase):
    @staticmethod
    def _request(path: str) -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
            }
        )

    def test_questionnaire_review_refills_form_from_yaml(self):
        yaml_text = Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8")
        response = asyncio.run(
            routes.questionnaire_review(
                self._request("/questionnaire/review"),
                yaml_content=yaml_text,
                current_year=2026,
                client_code="000001",
                lang="zh",
            )
        )
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("客户问卷", body)
        self.assertIn("window.__clientCode = &#34;000001&#34;", body)
        self.assertIn("sample-data", body)


if __name__ == "__main__":
    unittest.main()
