"""阶段划分。

按事件时间线切分客户生命周期为 P0/P1/... 阶段。
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.profile_loader import Event


@dataclass(frozen=True)
class Period:
    """一个规划期。"""

    index: int
    label: str
    start_year: int
    end_year: int
    boundary_event: Event | None
    years_to_boundary: int


_HORIZON_YEARS = 10


def divide_periods(
    *, current_year: int, events: tuple[Event, ...], terminal_year: int | None = None
) -> tuple[Period, ...]:
    """按事件时间线划分阶段。

    Args:
        current_year: 当前年份
        events: 事件列表(应已按 timing_year 升序)
        terminal_year: 可选的正式终点年份。提供时优先使用；缺失时保留 +10 年兼容回退。

    Returns:
        元组 of Period
    """
    future_events = tuple(e for e in events if e.timing_year >= current_year)
    resolved_terminal_year = terminal_year if terminal_year is not None else current_year + _HORIZON_YEARS

    if not future_events:
        return (
            Period(
                index=0,
                label="P0",
                start_year=current_year,
                end_year=resolved_terminal_year,
                boundary_event=None,
                years_to_boundary=max(0, resolved_terminal_year - current_year),
            ),
        )

    periods: list[Period] = []

    # P0: current → events[0].timing_year
    first = future_events[0]
    periods.append(
        Period(
            index=0,
            label="P0",
            start_year=current_year,
            end_year=first.timing_year,
            boundary_event=first,
            years_to_boundary=first.timing_year - current_year,
        )
    )

    # P1..Pn-1: events[i] → events[i+1]
    for i in range(len(future_events) - 1):
        cur = future_events[i]
        nxt = future_events[i + 1]
        periods.append(
            Period(
                index=i + 1,
                label=f"P{i + 1}",
                start_year=cur.timing_year,
                end_year=nxt.timing_year,
                boundary_event=nxt,
                years_to_boundary=nxt.timing_year - cur.timing_year,
            )
        )

    # Pn: last event → terminal_year / fallback horizon
    last = future_events[-1]
    last_end_year = terminal_year if terminal_year is not None else last.timing_year + _HORIZON_YEARS
    periods.append(
        Period(
            index=len(future_events),
            label=f"P{len(future_events)}",
            start_year=last.timing_year,
            end_year=last_end_year,
            boundary_event=None,
            years_to_boundary=max(0, last_end_year - last.timing_year),
        )
    )

    return tuple(periods)
