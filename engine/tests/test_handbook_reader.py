"""handbook_reader 单元测试。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.handbook_reader import (  # noqa: E402
    Assumptions,
    HandbookReadError,
    read_assumptions,
)

HANDBOOK_DIR = ROOT / "handbook"
ASSUMPTIONS_MD = HANDBOOK_DIR / "03-asset-assumptions.md"


class TestReadAssumptions(unittest.TestCase):
    """read_assumptions() 的核心行为。"""

    def test_returns_assumptions_instance(self):
        a = read_assumptions(ASSUMPTIONS_MD)
        self.assertIsInstance(a, Assumptions)

    def test_fixed_income_return_is_float(self):
        a = read_assumptions(ASSUMPTIONS_MD)
        self.assertIsInstance(a.fixed_income_return, float)
        self.assertGreater(a.fixed_income_return, 0)

    def test_all_four_asset_classes_present(self):
        a = read_assumptions(ASSUMPTIONS_MD)
        for attr in (
            "fixed_income_return",
            "equity_return",
            "insurance_return",
            "alternatives_return",
        ):
            self.assertTrue(hasattr(a, attr))
            self.assertIsInstance(getattr(a, attr), float)
            self.assertGreater(getattr(a, attr), 0)

    def test_volatility_attributes_present(self):
        a = read_assumptions(ASSUMPTIONS_MD)
        for attr in (
            "fixed_income_volatility",
            "equity_volatility",
            "insurance_volatility",
            "alternatives_volatility",
        ):
            self.assertTrue(hasattr(a, attr))

    def test_parses_real_values_from_handbook(self):
        """从 handbook/03 实际值解析 — 固收 2%, 权益 7%。"""
        a = read_assumptions(ASSUMPTIONS_MD)
        self.assertAlmostEqual(a.fixed_income_return, 0.02, places=3)
        self.assertAlmostEqual(a.equity_return, 0.07, places=3)

    def test_parser_actually_reads_handbook_not_just_fallback(self):
        """回归测试:parser 必须真的从手册读,而非总回退到 fallback。"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(
                "# Test\n\n"
                "## 1. intro\n\n"
                "### 3.1 4 大类\n\n"
                "| 大类 | 预期年化收益率 | 年化波动率 | 数据源 |\n"
                "|---|---|---|---|\n"
                "| 固收 | **3.0%** | **2%** | test |\n"
                "| 权益 | **8%** | **20%** | test |\n"
                "| 保险 | **4%** | **1.5%** | test |\n"
                "| 另类 | **7%** | **18%** | test |\n"
            )
            path = f.name
        try:
            a = read_assumptions(path)
            # 关键断言:必须是手册改后的值,不能是 fallback
            self.assertAlmostEqual(a.fixed_income_return, 0.030, places=3,
                                   msg="Parser 没真读手册(返回 fallback),或 §3.1 章节提取失败")
            self.assertAlmostEqual(a.equity_return, 0.08, places=3,
                                   msg="Parser 没真读手册(返回 fallback),或 §3.1 章节提取失败")
        finally:
            Path(path).unlink()


class TestErrorHandling(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(HandbookReadError):
            read_assumptions(HANDBOOK_DIR / "does_not_exist.md")

    def test_empty_file_uses_fallback(self):
        """空文件或无匹配表格时使用 fallback 默认值,不报错。"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# 空文件\n\n无表格。\n")
            path = f.name
        try:
            a = read_assumptions(path)
            self.assertIsInstance(a, Assumptions)
        finally:
            Path(path).unlink()
