"""缺口分析与投资建议。

基于推演结果,对有缺口的节点给出建议:
- 所需收益率是否可行
- 对应哪种骨架倾向
- 不可行时建议调整什么
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.projection import NodeProjection


# 各风险档位对应的可期待收益率上限(年化)
_RETURN_CAPS = {
    "conservative": 0.045,   # 固收为主,上限 4.5%
    "balanced": 0.08,        # 平衡配置,上限 8%
    "aggressive": 0.12,      # 进取配置,上限 12%
}


@dataclass(frozen=True)
class NodeAdvice:
    """单个节点的投资建议。"""

    event_id: str
    description: str
    year: int
    gap_or_surplus: float
    required_return: float | None
    # 建议
    feasibility: str          # "surplus" / "no_investment_needed" / "conservative" / "balanced" / "aggressive" / "infeasible"
    recommendation: str       # 人类可读建议
    needs_goal_adjustment: bool


def analyze_gaps(
    projections: tuple[NodeProjection, ...],
    risk_preference: str = "balanced",
) -> tuple[NodeAdvice, ...]:
    """对每个推演节点生成投资建议。"""
    results = []
    for proj in projections:
        if proj.gap_or_surplus >= 0:
            # 盈余
            results.append(NodeAdvice(
                event_id=proj.event_id,
                description=proj.description,
                year=proj.year,
                gap_or_surplus=proj.gap_or_surplus,
                required_return=None,
                feasibility="surplus",
                recommendation=f"该节点有盈余 ¥{proj.gap_or_surplus:,.0f},盈余部分可按风险偏好投资。",
                needs_goal_adjustment=False,
            ))
            continue

        if proj.required_return is None or proj.required_return <= 0:
            results.append(NodeAdvice(
                event_id=proj.event_id,
                description=proj.description,
                year=proj.year,
                gap_or_surplus=proj.gap_or_surplus,
                required_return=proj.required_return,
                feasibility="no_investment_needed",
                recommendation="不需要投资收益即可覆盖,但存在时序缺口,建议提前储备。",
                needs_goal_adjustment=False,
            ))
            continue

        req = proj.required_return
        # 判断可行性
        if req <= _RETURN_CAPS["conservative"]:
            feas = "conservative"
            rec = f"缺口 ¥{abs(proj.gap_or_surplus):,.0f},需年化 {req*100:.1f}% 即可补足。保守型配置(固收为主)即可实现。"
        elif req <= _RETURN_CAPS["balanced"]:
            feas = "balanced"
            rec = f"缺口 ¥{abs(proj.gap_or_surplus):,.0f},需年化 {req*100:.1f}%。需要平衡型配置(固收+权益)才能覆盖。"
        elif req <= _RETURN_CAPS["aggressive"]:
            feas = "aggressive"
            rec = f"缺口 ¥{abs(proj.gap_or_surplus):,.0f},需年化 {req*100:.1f}%。需要进取型配置(权益为主),回撤风险较大。"
        else:
            feas = "infeasible"
            rec = (
                f"缺口 ¥{abs(proj.gap_or_surplus):,.0f},需年化 {req*100:.1f}%,"
                f"超出合理预期上限({_RETURN_CAPS['aggressive']*100:.0f}%)。"
                f"建议调整目标:降低该事件预算、推迟时间、或增加收入来源。"
            )

        results.append(NodeAdvice(
            event_id=proj.event_id,
            description=proj.description,
            year=proj.year,
            gap_or_surplus=proj.gap_or_surplus,
            required_return=req,
            feasibility=feas,
            recommendation=rec,
            needs_goal_adjustment=(feas == "infeasible"),
        ))

    return tuple(results)
