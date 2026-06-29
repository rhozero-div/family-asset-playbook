"""projection 内部辅助逻辑测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.projection import _build_strategies, _compute_bucket_rv, _return_strategy_for  # noqa: E402


class TestBuildStrategies(unittest.TestCase):
    def test_accepts_dict_weight_shape_from_handbook_schema(self):
        strategies = _build_strategies(
            {
                "phases": [
                    {
                        "max_years": 3,
                        "weights": {
                            "fixed_income": 0.8,
                            "equity": 0.1,
                            "insurance": 0.05,
                            "alternatives": 0.05,
                        },
                    }
                ]
            },
            risk_preference="balanced",
        )
        self.assertEqual(strategies, [(0, 3, (80.0, 10.0, 5.0, 5.0))])

    def test_return_strategy_weights_are_treated_as_percentages(self):
        weights = _return_strategy_for(2)
        annual_return, annual_vol = _compute_bucket_rv(
            weights,
            0.02, 0.02,
            0.07, 0.30,
            0.02, 0.00,
            0.05, 0.30,
            0.3, 0.0, -0.3,
            0.0, 0.0, 0.0,
        )
        self.assertLess(annual_return, 0.10)
        self.assertLess(annual_vol, 0.10)

    def test_accepts_percent_weight_shape_without_rescaling(self):
        strategies = _build_strategies(
            {
                "phases": [
                    {
                        "max_years": 3,
                        "weights": {
                            "fixed_income": 80,
                            "equity": 10,
                            "insurance": 5,
                            "alternatives": 5,
                        },
                    }
                ]
            },
            risk_preference="balanced",
        )
        self.assertEqual(strategies, [(0, 3, (80.0, 10.0, 5.0, 5.0))])
