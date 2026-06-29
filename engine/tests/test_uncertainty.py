"""uncertainty 单元测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.handbook_reader import read_assumptions  # noqa: E402
from engine.skeleton_generator import generate_skeletons  # noqa: E402
from engine.uncertainty import narrow_skeleton  # noqa: E402

ASSUMPTIONS_PATH = ROOT / "handbook" / "03-asset-assumptions.md"


class TestNarrowSkeleton(unittest.TestCase):
    def setUp(self):
        assumptions = read_assumptions(ASSUMPTIONS_PATH)
        self.skel = generate_skeletons(assumptions=assumptions)[1]

    def test_no_narrowing_at_ten_years_or_more(self):
        after = narrow_skeleton(self.skel, years_to_event=10)
        for before_weight, after_weight in zip(self.skel.weights, after.weights):
            self.assertAlmostEqual(before_weight.weight_low, after_weight.weight_low)
            self.assertAlmostEqual(before_weight.weight_high, after_weight.weight_high)

    def test_narrowing_at_seven_years(self):
        after = narrow_skeleton(self.skel, years_to_event=7)
        for before_weight, after_weight in zip(self.skel.weights, after.weights):
            midpoint = (before_weight.weight_low + before_weight.weight_high) / 2.0
            half_width = (before_weight.weight_high - before_weight.weight_low) / 2.0
            expected_half = max(half_width * 0.75, 5.0)
            self.assertAlmostEqual(after_weight.weight_low, midpoint - expected_half, places=4)
            self.assertAlmostEqual(after_weight.weight_high, midpoint + expected_half, places=4)

    def test_narrowing_at_three_years(self):
        after = narrow_skeleton(self.skel, years_to_event=3)
        for before_weight, after_weight in zip(self.skel.weights, after.weights):
            midpoint = (before_weight.weight_low + before_weight.weight_high) / 2.0
            half_width = (before_weight.weight_high - before_weight.weight_low) / 2.0
            expected_half = max(half_width * 0.50, 5.0)
            self.assertAlmostEqual(after_weight.weight_low, midpoint - expected_half, places=4)
            self.assertAlmostEqual(after_weight.weight_high, midpoint + expected_half, places=4)

    def test_minimum_bandwidth_kept_when_very_near(self):
        after = narrow_skeleton(self.skel, years_to_event=1)
        for after_weight in after.weights:
            half_width = (after_weight.weight_high - after_weight.weight_low) / 2.0
            self.assertGreaterEqual(half_width, 5.0)

    def test_narrow_is_pure(self):
        """narrow_skeleton 不修改入参。"""
        before_weights = tuple(self.skel.weights)
        _ = narrow_skeleton(self.skel, years_to_event=1)
        self.assertEqual(before_weights, self.skel.weights)
