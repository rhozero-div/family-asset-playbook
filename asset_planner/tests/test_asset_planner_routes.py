"""资产规划网页路由测试。"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from asset_planner import routes  # noqa: E402


class TestAssetPlannerRoutes(unittest.TestCase):
    @staticmethod
    def _request(path: str, method: str = "GET") -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
            }
        )

    def test_home_page_renders(self):
        response = asyncio.run(routes.asset_planner_home(self._request("/asset-planner")))
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("资产规划原型", body)

    def test_report_renders_core_sections(self):
        response = asyncio.run(
            routes.asset_planner_analyze(
                self._request("/asset-planner/analyze", "POST"),
                yaml_content=Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8"),
                yaml_file=None,
                current_year=2026,
                client_code="000001",
            )
        )
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("家庭快照", body)
        self.assertIn("重大节点覆盖检查", body)
        self.assertIn("资金分层", body)
        self.assertIn("打开保险规划", body)
        self.assertIn("生成剧本", body)


if __name__ == "__main__":
    unittest.main()
