"""保险规划网页路由测试。"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from insurance_planner import routes  # noqa: E402


class TestInsurancePlannerRoutes(unittest.TestCase):
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
        response = asyncio.run(routes.insurance_planner_home(self._request("/insurance-planner")))
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("保险规划原型", body)

    def test_sample_wang_prefills_yaml(self):
        response = asyncio.run(routes.insurance_planner_sample_wang(self._request("/insurance-planner/sample-wang")))
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("王先生示例", body)
        self.assertIn("profile_version", body)

    def test_report_renders_target_section_and_chart_canvases(self):
        response = asyncio.run(
            routes.insurance_planner_analyze(
                self._request("/insurance-planner/analyze", "POST"),
                yaml_content=Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8"),
                yaml_file=None,
                current_year=2026,
                manual_premium_cap_annual=12000,
                auto_budget_ratio_pct=6,
                term_multiplier_with_dependents=8.0,
                term_multiplier_without_dependents=4.0,
                ci_income_multiple=3.5,
                ci_expense_years=5.0,
                child_ci_target=300000.0,
                elder_ci_target=300000.0,
                include_hci_upgrade="true",
            )
        )
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("客户目标参数", body)
        self.assertIn("gap-chart-0", body)
        self.assertIn("gap-premium-chart-0", body)
        self.assertIn("core-coverage-chart-0", body)
        self.assertIn("balanced-coverage-chart-0", body)
        self.assertIn("current_premium_by_product", body)
        self.assertIn("plan_a_premium_by_product", body)
        self.assertIn("plan_b_premium_by_product", body)
        self.assertIn("打开资产规划", body)
        self.assertIn("生成剧本", body)

    def test_optional_numeric_fields_accept_empty_strings(self):
        response = asyncio.run(
            routes.insurance_planner_analyze(
                self._request("/insurance-planner/analyze", "POST"),
                yaml_content=Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8"),
                yaml_file=None,
                current_year=2026,
                manual_premium_cap_annual="",
                auto_budget_ratio_pct="",
                term_multiplier_with_dependents=7.0,
                term_multiplier_without_dependents=4.0,
                ci_income_multiple=3.0,
                ci_expense_years=5.0,
                child_ci_target=300000.0,
                elder_ci_target=300000.0,
                include_hci_upgrade="true",
            )
        )
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("家庭快照", body)

    def test_recommendation_page_renders_plan_forms(self):
        response = asyncio.run(
            routes.insurance_recommendation(
                self._request("/insurance-planner/recommendation", "POST"),
                yaml_content=Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8"),
                yaml_file=None,
                current_year=2026,
                client_code="000001",
                focus_plan="core",
                lang="zh",
            )
        )
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("保险配置回填页", body)
        self.assertIn("方案 A：优先补足核心保障", body)
        self.assertIn("plan_a_0_term_cov", body)
        self.assertIn("用方案 A配置重新测算生成剧本", body)

    def test_recalculate_generates_playbook_with_overlay_yaml(self):
        class _FormRequest(Request):
            async def form(self):
                return {
                    "yaml_content": Path(ROOT / "profiles" / "sample-wang.yaml").read_text(encoding="utf-8"),
                    "current_year": "2026",
                    "client_code": "000001",
                    "lang": "zh",
                    "scenario_key": "core",
                    "plan_a_0_term_cov": "100000",
                    "plan_a_0_term_premium": "0",
                    "plan_a_0_term_pay_years": "10",
                }

        response = asyncio.run(routes.insurance_recalculate(_FormRequest(self._request("/insurance-planner/recalculate", "POST").scope)))
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("家庭资产配置剧本", body)
        self.assertIn("编辑问卷", body)


if __name__ == "__main__":
    unittest.main()
