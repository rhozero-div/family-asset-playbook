"""保险保费进入主剧本现金流的测试。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.profile_loader import load_profile  # noqa: E402
from engine.projection import _annual_net_for_year  # noqa: E402


class TestProjectionInsurancePremiums(unittest.TestCase):
    def test_annual_net_deducts_existing_insurance_premiums(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 王先生\n"
                "      age: 38\n"
                "      role: primary_breadwinner\n"
                "      annual_income: 120000\n"
                "      monthly_expense: 5000\n"
                "      term_life_premium: 1200\n"
                "      critical_illness_premium: 2400\n"
                "      medical_covered: true\n"
                "      medical_premium: 1800\n"
                "      hci_premium: 3600\n"
                "      other_insurance_premium: 600\n"
                "events: []\n"
                "assets:\n"
                "  financial:\n"
                "    savings:\n"
                "      - amount: 200000\n"
                "        premium: 3000\n"
                "        pay_years: 5\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            annual_net = _annual_net_for_year(profile, 2026, 2026)
            self.assertEqual(annual_net, 120000 - 5000 * 12 - 12600)
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
