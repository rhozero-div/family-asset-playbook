"""profile_loader 的单元测试。

遵循 TDD:先写测试,后写实现。
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.profile_loader import (  # noqa: E402
    ClientProfile,
    Event,
    ProfileLoadError,
    load_profile,
)

SAMPLES_DIR = ROOT / "samples"
SAMPLE_YAML = SAMPLES_DIR / "client-profile.example.yaml"


class TestLoadProfile(unittest.TestCase):
    """load_profile() 的核心行为。"""

    def test_load_sample_yaml_succeeds(self):
        """解析仓库内置的示例档案应成功。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertIsInstance(profile, ClientProfile)

    def test_sample_profile_has_expected_fields(self):
        """示例档案应有正确的版本与字段。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertEqual(profile.profile_version, "0.1")
        self.assertEqual(profile.schema_version, "handbook-v0.1")

    def test_sample_profile_family_name_is_primary_breadwinner(self):
        """family_name 应派生自 primary_breadwinner。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertEqual(profile.family_name, "王先生")

    def test_sample_profile_has_six_events(self):
        """示例档案应解析出 6 个事件(含子女成家)。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertEqual(len(profile.events), 6)

    def test_sample_profile_risk_preference(self):
        """risk_preference 应来自 advisor_assessment。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertEqual(profile.risk_preference, "balanced")

    def test_sample_profile_insurance_fields(self):
        """保险字段应正确解析。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertEqual(profile.insurance_critical_illness_cov, 500000)
        self.assertEqual(profile.insurance_term_life_cov, 0)

    def test_sample_profile_total_assets(self):
        """total_financial_assets 应等于 financial.total_value,不含储蓄险。"""
        profile = load_profile(SAMPLE_YAML)
        self.assertEqual(profile.total_financial_assets, 1500000)

    def test_liquidity_reserve_months_defaults_to_six(self):
        """未显式填写流动性月数时,默认按 6 个月处理。"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 王先生\n"
                "      age: 38\n"
                "      role: primary_breadwinner\n"
                "events: []\n"
                "assets: {}\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            self.assertEqual(profile.liquidity_reserve_months, 6.0)
        finally:
            Path(path).unlink()

    def test_loads_future_income_and_household_extra_expense(self):
        """成员未来收入参数与家庭整体额外支出应被解析。"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 李先生\n"
                "      age: 40\n"
                "      role: primary_breadwinner\n"
                "      annual_income: 600000\n"
                "      retirement_age: 60\n"
                "    - name: 李小朋友\n"
                "      age: 15\n"
                "      role: dependent\n"
                "      retirement_age: 60\n"
                "      income_start_age: 22\n"
                "      income_start_annual: 120000\n"
                "events: []\n"
                "income:\n"
                "  household_extra_monthly_expense: 3000\n"
                "assets: {}\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            self.assertEqual(profile.members[1].income_start_age, 22)
            self.assertEqual(profile.members[1].income_start_annual, 120000)
            self.assertEqual(profile.monthly_living_expense, 3000)
        finally:
            Path(path).unlink()

    def test_measurement_end_year_defaults_to_current_year_plus_thirty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 王先生\n"
                "      age: 38\n"
                "      role: primary_breadwinner\n"
                "events: []\n"
                "assets: {}\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            self.assertEqual(profile.measurement_end_year, 2056)
        finally:
            Path(path).unlink()

    def test_measurement_end_year_reads_from_projection_assumptions(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 王先生\n"
                "      age: 38\n"
                "      role: primary_breadwinner\n"
                "events:\n"
                "  - id: e1\n"
                "    type: housing\n"
                "    description: 买房\n"
                "    timing_year: 2032\n"
                "    estimated_amount: 1000000\n"
                "assumptions:\n"
                "  projection:\n"
                "    measurement_end_year: 2040\n"
                "assets: {}\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            self.assertEqual(profile.measurement_end_year, 2040)
        finally:
            Path(path).unlink()


class TestEventParsing(unittest.TestCase):
    """Event 字段解析。"""

    def test_events_have_required_fields(self):
        profile = load_profile(SAMPLE_YAML)
        for event in profile.events:
            self.assertIsInstance(event, Event)
            self.assertTrue(event.id)
            self.assertTrue(event.type)
            self.assertEqual(event.timing_year, int(event.timing_year))
            self.assertTrue(event.certainty)

    def test_events_default_certainty_when_missing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 王先生\n"
                "      age: 38\n"
                "      role: primary_breadwinner\n"
                "events:\n"
                "  - id: e1\n"
                "    type: housing\n"
                "    description: 买房\n"
                "    timing_year: 2029\n"
                "    estimated_amount: 1000000\n"
                "assets: {}\n"
            )
            path = f.name
        try:
            profile = load_profile(path, current_year=2026)
            self.assertEqual(profile.events[0].certainty, "medium")
        finally:
            Path(path).unlink()

    def test_events_sorted_by_timing_year(self):
        """事件应按 timing_year 升序。"""
        profile = load_profile(SAMPLE_YAML)
        years = [e.timing_year for e in profile.events]
        self.assertEqual(years, sorted(years))


class TestErrorHandling(unittest.TestCase):
    """错误处理。"""

    def test_missing_file_raises(self):
        with self.assertRaises(ProfileLoadError):
            load_profile(SAMPLES_DIR / "does_not_exist.yaml")

    def test_missing_required_field_raises(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("profile_version: '0.1'\n")  # 缺 schema_version
            path = f.name
        try:
            with self.assertRaises(ProfileLoadError):
                load_profile(path)
        finally:
            Path(path).unlink()
