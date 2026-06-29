"""逐成员未来收入现金流测试。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.profile_loader import load_profile  # noqa: E402
from engine.projection import project_yearly  # noqa: E402


class TestFutureIncomeProjection(unittest.TestCase):
    def test_future_income_starts_when_member_reaches_start_age(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 张先生\n"
                "      age: 40\n"
                "      role: primary_breadwinner\n"
                "      annual_income: 600000\n"
                "      monthly_expense: 10000\n"
                "      retirement_age: 60\n"
                "    - name: 张小朋友\n"
                "      age: 15\n"
                "      role: dependent\n"
                "      retirement_age: 60\n"
                "      income_start_age: 22\n"
                "      income_start_annual: 120000\n"
                "events: []\n"
                "income:\n"
                "  household_extra_monthly_expense: 3000\n"
                "assets:\n"
                "  financial:\n"
                "    total_value: 0\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            snapshots = project_yearly(profile)
            before = next(s for s in snapshots if s.year == 2032)
            after = next(s for s in snapshots if s.year == 2033)
            self.assertEqual(before.cash_inflow, 600000)
            self.assertEqual(before.cash_outflow, 156000)
            self.assertEqual(after.cash_inflow, 720000)
            self.assertEqual(after.cash_outflow, 156000)
        finally:
            Path(path).unlink()

    def test_project_yearly_respects_measurement_end_year(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 张先生\n"
                "      age: 40\n"
                "      role: primary_breadwinner\n"
                "      annual_income: 600000\n"
                "      monthly_expense: 10000\n"
                "      retirement_age: 60\n"
                "events:\n"
                "  - id: e1\n"
                "    type: housing\n"
                "    description: 换房\n"
                "    timing_year: 2028\n"
                "    estimated_amount: 500000\n"
                "assumptions:\n"
                "  projection:\n"
                "    measurement_end_year: 2029\n"
                "assets:\n"
                "  financial:\n"
                "    total_value: 0\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            snapshots = project_yearly(profile)
            self.assertEqual(snapshots[0].year, 2026)
            self.assertEqual(snapshots[-1].year, 2029)
        finally:
            Path(path).unlink()
