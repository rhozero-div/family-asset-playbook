"""不确定性收窄。

按 handbook/04-pareto-generation.md §6 的区间收窄规则,
对三骨架的权重区间做阶段性缩窄。
"""
from __future__ import annotations

from dataclasses import replace

from engine.skeleton_generator import AssetWeight, Skeleton


def _multiplier(years_to_event: int) -> float:
    if years_to_event >= 10:
        return 1.0
    if years_to_event >= 5:
        return 0.75
    if years_to_event >= 2:
        return 0.50
    return 0.25


def _narrow_weight(weight: AssetWeight, multiplier: float) -> AssetWeight:
    midpoint = (weight.weight_low + weight.weight_high) / 2.0
    half_width = (weight.weight_high - weight.weight_low) / 2.0
    new_half_width = max(half_width * multiplier, 5.0)
    return replace(
        weight,
        weight_low=round(midpoint - new_half_width, 4),
        weight_high=round(midpoint + new_half_width, 4),
    )


def narrow_skeleton(skeleton: Skeleton, *, years_to_event: int) -> Skeleton:
    """按 years_to_event 缩窄骨架区间。"""
    mult = _multiplier(years_to_event)
    return replace(
        skeleton,
        weights=tuple(_narrow_weight(w, mult) for w in skeleton.weights),
    )
