"""三骨架生成器。

为单个规划期生成 conservative / balanced / aggressive 三个代表性骨架。
权重区间与角色描述参照 handbook/04-pareto-generation.md §3.2。
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.handbook_reader import Assumptions


@dataclass(frozen=True)
class AssetWeight:
    """单一大类的权重区间(单位:百分比,如 30.0 表示 30%)。"""

    asset_class: str
    weight_low: float
    weight_high: float
    return_pct: float
    volatility: float


@dataclass(frozen=True)
class Skeleton:
    """一个代表性骨架。"""

    name: str
    weights: tuple[AssetWeight, ...]
    role: str


_TEMPLATES = [
    {
        "name": "保守型",
        "weights": {
            "fixed_income": (50.0, 60.0),
            "equity": (10.0, 20.0),
            "insurance": (15.0, 20.0),
            "alternatives": (5.0, 10.0),
        },
        "role": "流动性优先,牺牲长期增长",
    },
    {
        "name": "平衡型",
        "weights": {
            "fixed_income": (30.0, 45.0),
            "equity": (25.0, 40.0),
            "insurance": (10.0, 20.0),
            "alternatives": (5.0, 15.0),
        },
        "role": "风险调整后最优",
    },
    {
        "name": "进取型",
        "weights": {
            "fixed_income": (15.0, 25.0),
            "equity": (50.0, 65.0),
            "insurance": (5.0, 10.0),
            "alternatives": (10.0, 20.0),
        },
        "role": "长期增长优先,承受较大回撤",
    },
]


def _make_weight(
    asset_class: str,
    weight_range: tuple[float, float],
    assumptions: Assumptions,
) -> AssetWeight:
    ret = getattr(assumptions, f"{asset_class}_return")
    vol = getattr(assumptions, f"{asset_class}_volatility")
    return AssetWeight(
        asset_class=asset_class,
        weight_low=weight_range[0],
        weight_high=weight_range[1],
        return_pct=ret,
        volatility=vol,
    )


def generate_skeletons(
    *,
    assumptions: Assumptions,
    risk_preference: str = "balanced",
) -> tuple[Skeleton, ...]:
    """生成三骨架。

    当前始终返回 handbook 约定的保守 / 平衡 / 进取三组区间模板。
    `risk_preference` 作为兼容参数保留,供调用方自行决定优先阅读顺序。
    """
    del risk_preference

    skels = []
    for tpl in _TEMPLATES:
        weights = tuple(
            _make_weight(ac, w, assumptions)
            for ac, w in sorted(tpl["weights"].items())
        )
        skels.append(
            Skeleton(
                name=tpl["name"],
                weights=weights,
                role=tpl["role"],
            )
        )
    return tuple(skels)
