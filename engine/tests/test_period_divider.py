"""period_divider 单元测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.period_divider import (  # noqa: E402
    Period,
    divide_periods,
)
from engine.profile_loader import Event, load_profile  # noqa: E402

SAMPLE_YAML = ROOT / "samples" / "client-profile.example.yaml"


def _make_event(id_: str, year: int):
    return Event(
        id=id_,
        type="other",
        description="",
        timing_year=year,
        estimated_amount=None,
        certainty="medium",
        expected_replacement_ratio=None,
        owner=None,
    )


class TestDividePeriods(unittest.TestCase):
    def test_no_events_returns_single_period(self):
        """无事件 → 单一 P0 覆盖 10 年。"""
        periods = divide_periods(current_year=2026, events=())
        self.assertEqual(len(periods), 1)
        p = periods[0]
        self.assertEqual(p.index, 0)
        self.assertEqual(p.label, "P0")
        self.assertEqual(p.start_year, 2026)
        self.assertEqual(p.end_year, 2036)

    def test_terminal_year_overrides_synthetic_horizon_when_no_events(self):
        periods = divide_periods(current_year=2026, events=(), terminal_year=2050)
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].end_year, 2050)

    def test_terminal_year_overrides_last_plus_ten_when_events_exist(self):
        events = (_make_event("e1", 2029),)
        periods = divide_periods(current_year=2026, events=events, terminal_year=2060)
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[-1].start_year, 2029)
        self.assertEqual(periods[-1].end_year, 2060)

    def test_one_event_yields_two_periods(self):
        """1 个事件 → P0 + P1。"""
        events = (_make_event("e1", 2029),)
        periods = divide_periods(current_year=2026, events=events)
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0].label, "P0")
        self.assertEqual(periods[0].end_year, 2029)
        self.assertEqual(periods[1].label, "P1")
        self.assertEqual(periods[1].start_year, 2029)

    def test_multiple_events_yield_n_plus_one_periods(self):
        """n 个事件 → n+1 个阶段。"""
        events = tuple(_make_event(f"e{i}", 2028 + i) for i in range(3))
        periods = divide_periods(current_year=2026, events=events)
        self.assertEqual(len(periods), 4)

    def test_events_in_past_are_filtered(self):
        """过去事件(timing_year < current_year)被过滤。"""
        events = (
            _make_event("past", 2020),
            _make_event("future", 2029),
        )
        periods = divide_periods(current_year=2026, events=events)
        self.assertEqual(len(periods), 2)

    def test_period_boundary_event_is_set(self):
        """每个阶段的 boundary_event 是该期末的事件(若有)。"""
        e1 = _make_event("e1", 2029)
        periods = divide_periods(current_year=2026, events=(e1,))
        self.assertEqual(periods[0].boundary_event.id, "e1")
        self.assertIsNone(periods[-1].boundary_event)

    def test_sample_profile_yields_seven_periods(self):
        """示例档案(6 个事件) → 7 个阶段(P0-P6)。"""
        profile = load_profile(SAMPLE_YAML)
        periods = divide_periods(current_year=2026, events=profile.events)
        self.assertEqual(len(periods), 7)
        labels = [p.label for p in periods]
        self.assertEqual(labels, ["P0", "P1", "P2", "P3", "P4", "P5", "P6"])

    def test_periods_cover_full_timeline_without_gaps(self):
        """各阶段首尾相连,无间隔无重叠。"""
        profile = load_profile(SAMPLE_YAML)
        periods = divide_periods(current_year=2026, events=profile.events)
        # P[i].end_year == P[i+1].start_year
        for i in range(len(periods) - 1):
            self.assertEqual(periods[i].end_year, periods[i + 1].start_year)
