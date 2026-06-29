"""allocator 内部阶段权重逻辑测试。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.allocator import _strategy_for  # noqa: E402


class TestAllocatorStrategies(unittest.TestCase):
    def test_strategy_reads_decimal_phase_weights_from_profile_assumptions(self):
        profile = SimpleNamespace(
            assumptions={
                "phases": [
                    {
                        "max_years": 3,
                        "weights": {
                            "fixed_income": 0.8,
                            "equity": 0.1,
                            "insurance": 0.05,
                            "alternatives": 0.05,
                        },
                    },
                    {
                        "max_years": 7,
                        "weights": {
                            "fixed_income": 0.6,
                            "equity": 0.25,
                            "insurance": 0.1,
                            "alternatives": 0.05,
                        },
                    },
                ]
            }
        )

        label, fi, eq, ins, alt, _ = _strategy_for(2, profile)
        self.assertEqual(label, "近期(≤3年)")
        self.assertEqual((fi, eq, ins, alt), (80.0, 10.0, 5.0, 5.0))

    def test_strategy_accepts_percent_phase_weights_without_rescaling(self):
        profile = SimpleNamespace(
            assumptions={
                "phases": [
                    {
                        "max_years": 3,
                        "weights": [80, 10, 5, 5],
                    }
                ]
            }
        )

        _, fi, eq, ins, alt, _ = _strategy_for(2, profile)
        self.assertEqual((fi, eq, ins, alt), (80.0, 10.0, 5.0, 5.0))

