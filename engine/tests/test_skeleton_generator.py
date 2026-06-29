"""skeleton_generator 单元测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.handbook_reader import read_assumptions  # noqa: E402
from engine.skeleton_generator import (  # noqa: E402
    AssetWeight,
    Skeleton,
    generate_skeletons,
)

HANDBOOK_DIR = ROOT / "handbook"
ASSUMPTIONS_PATH = HANDBOOK_DIR / "03-asset-assumptions.md"


class TestGenerateSkeletons(unittest.TestCase):
    """generate_skeletons() 的核心行为。"""

    def setUp(self):
        self.assumptions = read_assumptions(ASSUMPTIONS_PATH)

    def test_returns_three_skeletons(self):
        skels = generate_skeletons(assumptions=self.assumptions)
        self.assertEqual(len(skels), 3)

    def test_skeleton_names(self):
        skels = generate_skeletons(assumptions=self.assumptions)
        names = [s.name for s in skels]
        self.assertEqual(names, ["保守型", "平衡型", "进取型"])

    def test_each_skeleton_has_four_asset_weights(self):
        skels = generate_skeletons(assumptions=self.assumptions)
        for s in skels:
            self.assertEqual(len(s.weights), 4)

    def test_weights_sum_to_100(self):
        """每个骨架的可行总权重区间应覆盖 100。"""
        skels = generate_skeletons(assumptions=self.assumptions)
        for s in skels:
            total_low = sum(w.weight_low for w in s.weights)
            total_high = sum(w.weight_high for w in s.weights)
            self.assertLessEqual(total_low, 100.0, msg=f"{s.name} low 权重和 = {total_low}")
            self.assertGreaterEqual(total_high, 100.0, msg=f"{s.name} high 权重和 = {total_high}")

    def test_conservative_has_more_fixed_income_than_aggressive(self):
        skels = generate_skeletons(assumptions=self.assumptions)
        cons = next(s for s in skels if s.name == "保守型")
        aggr = next(s for s in skels if s.name == "进取型")
        cons_fi = next(
            w.weight_low for w in cons.weights if w.asset_class == "fixed_income"
        )
        aggr_fi = next(
            w.weight_low for w in aggr.weights if w.asset_class == "fixed_income"
        )
        self.assertGreater(cons_fi, aggr_fi)

    def test_each_weight_has_return(self):
        """每个 AssetWeight 的 return 来自 handbook/03(单值)。"""
        skels = generate_skeletons(assumptions=self.assumptions)
        fi = next(
            w
            for s in skels
            for w in s.weights
            if w.asset_class == "fixed_income"
        )
        self.assertAlmostEqual(fi.return_pct, 0.02, places=3)
