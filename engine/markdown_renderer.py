"""Markdown 渲染器。

按新的输出逻辑:
  A. 客户情况概览(初始状态 + 人生节点时间线)
  B. 资产推演(不含投资收益,每个节点的缺口/盈余)
  C. 缺口分析与投资建议
  D. 资产配置骨架(基于缺口分析的针对性建议)
  E. 风险边界与声明
"""
from __future__ import annotations

from datetime import datetime, timezone

from engine.allocator import AllocationPlan, BucketAllocation, InsuranceAnalysis
from engine.gap_advisor import NodeAdvice
from engine.period_divider import Period
from engine.profile_loader import ClientProfile
from engine.projection import (NodeProjection, TerminalStep, YearlyReturnSnapshot,
                                YearlySnapshot, BucketProjectionResult)



_DRAWDOWN_CAPS = {
    "conservative": "15%",
    "balanced": "25%",
    "aggressive": "40%",
}


def _fmt(x: float) -> str:
    """格式化金额。"""
    return f"¥{x:,.0f}"


def _format_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _regular_net_by_year(
    profile: ClientProfile,
    yearly_snapshots: tuple[YearlySnapshot, ...],
) -> list[tuple[int, float]]:
    """返回每年不含重大事件支出的常规净现金流。"""
    event_totals: dict[int, float] = {}
    for evt in profile.events:
        if evt.timing_year >= profile.current_year:
            event_totals[evt.timing_year] = event_totals.get(evt.timing_year, 0.0) + float(evt.estimated_amount or 0)

    result: list[tuple[int, float]] = []
    for snap in yearly_snapshots:
        event_total = event_totals.get(snap.year, 0.0)
        regular_outflow = snap.cash_outflow - event_total
        result.append((snap.year, snap.cash_inflow - regular_outflow))
    return result


def _future_cashflow_summary(
    profile: ClientProfile,
    yearly_snapshots: tuple[YearlySnapshot, ...],
) -> dict[str, object] | None:
    """提炼剧本展示所需的未来现金流摘要。"""
    if not yearly_snapshots:
        return None

    regular = _regular_net_by_year(profile, yearly_snapshots)
    if not regular:
        return None

    horizon_end = min(profile.measurement_end_year, regular[-1][0])
    window = [(year, net) for year, net in regular if year <= horizon_end]
    if not window:
        window = regular

    values = [net for _, net in window]
    avg_net = sum(values) / len(values)
    min_year, min_net = min(window, key=lambda item: item[1])
    max_year, max_net = max(window, key=lambda item: item[1])
    negative_years = [year for year, net in window if net < 0]
    return {
        "start_year": window[0][0],
        "end_year": window[-1][0],
        "avg_net": avg_net,
        "min_year": min_year,
        "min_net": min_net,
        "max_year": max_year,
        "max_net": max_net,
        "negative_years": negative_years,
    }


def _chart_end_year(profile: ClientProfile) -> int:
    """统一返回剧本图表展示截止年份。"""
    return max(profile.measurement_end_year, profile.current_year)


def _member_retirement_rollup(profile: ClientProfile) -> dict[str, object]:
    """按成员口径汇总退休收入、退休支出与退休医疗首年自付。"""
    income_items: list[tuple[str, float]] = []
    expense_items: list[tuple[str, float]] = []
    healthcare_items: list[tuple[str, float]] = []

    for member in profile.members:
        retirement_income = (member.retirement_pension + member.retirement_annuity)
        if retirement_income > 0:
            income_items.append((member.name, retirement_income))

        retirement_expense = member.monthly_expense * member.retirement_expense_coeff
        if retirement_expense > 0:
            expense_items.append((member.name, retirement_expense))

        if member.healthcare_starting_annual > 0:
            healthcare_items.append(
                (
                    member.name,
                    member.healthcare_starting_annual * (1 - member.reimbursement_rate),
                )
            )

    return {
        "monthly_income_total": sum(value for _, value in income_items),
        "monthly_expense_total": sum(value for _, value in expense_items),
        "first_year_healthcare_selfpay_total": sum(value for _, value in healthcare_items),
        "income_items": income_items,
        "expense_items": expense_items,
        "healthcare_items": healthcare_items,
    }


def _dependent_count(profile: ClientProfile) -> int:
    return sum(1 for member in profile.members if member.role in {"dependent", "dependent_elder"})


def _retirement_monthly_gap(
    profile: ClientProfile,
    retirement_rollup: dict[str, object],
) -> float:
    retirement_income = retirement_rollup["monthly_income_total"] or (
        profile.retirement_monthly_pension + profile.retirement_monthly_annuity
    )
    retirement_expense = retirement_rollup["monthly_expense_total"] or profile.retirement_monthly_expense
    return float(retirement_expense) - float(retirement_income)


def _next_future_event(profile: ClientProfile):
    future_events = [evt for evt in profile.events if evt.timing_year >= profile.current_year]
    return min(future_events, key=lambda evt: evt.timing_year) if future_events else None


def _next_bucket_gap(plan: AllocationPlan) -> BucketAllocation | None:
    for bucket in plan.node_buckets:
        if bucket.amount > bucket.initial_balance:
            return bucket
    return None


def _nearest_negative_projection(projections: tuple[NodeProjection, ...]) -> NodeProjection | None:
    negatives = [projection for projection in projections if projection.gap_or_surplus < 0]
    return min(negatives, key=lambda projection: projection.year) if negatives else None


def _append_unique(lines: list[str], line: str, *, max_items: int | None = None) -> None:
    if line in lines:
        return
    if max_items is not None and len(lines) >= max_items:
        return
    lines.append(line)


def _summary_state_lines(
    profile: ClientProfile,
    plan: AllocationPlan,
    projections: tuple[NodeProjection, ...],
    future_cf: dict[str, object] | None,
    retirement_gap: float,
) -> list[str]:
    lines: list[str] = []
    monthly_surplus = plan.monthly_surplus
    next_event = _next_future_event(profile)
    next_shortfall = _nearest_negative_projection(projections)
    emergency_funded = plan.total_investable >= plan.emergency.amount
    retirement_years_left = (profile.primary_breadwinner_birth_year + profile.primary_breadwinner_retirement_age) - profile.current_year

    if monthly_surplus < 0:
        _append_unique(
            lines,
            f"- 当前阶段属于**现金流修复优先**：月度净现金流约 {_fmt(monthly_surplus)}，"
            "在现金流转正之前，不适合把重点放在长期增值安排上。",
        )
    elif next_shortfall is not None:
        _append_unique(
            lines,
            f"- 当前阶段属于**目标取舍与预算重排优先**：按现有假设，最早会在 {next_shortfall.year} 年的"
            f"{next_shortfall.description} 出现约 {_fmt(abs(next_shortfall.gap_or_surplus))} 缺口，"
            "说明仅靠现有预算顺序还不够。",
        )
    elif next_event is not None and next_event.timing_year - profile.current_year <= 3:
        _append_unique(
            lines,
            f"- 当前阶段属于**近期节点保障优先**：最近的明确节点是 {next_event.description}"
            f"（{next_event.timing_year} 年），距离现在仅 {next_event.timing_year - profile.current_year} 年，"
            "这笔钱的可兑现性比收益弹性更重要。",
        )
    elif retirement_gap > 0 and retirement_years_left <= 10:
        _append_unique(
            lines,
            f"- 当前阶段属于**退休准备前置**：按当前口径，退休后月度缺口约 {_fmt(retirement_gap)}，"
            "而主要收入者已进入退休前 10 年窗口，后续新增积累需要兼顾退休后的现金流承接。",
        )
    elif plan.surplus and plan.surplus.initial_balance > 0:
        _append_unique(
            lines,
            f"- 当前阶段已进入**分层后可持续增值**：在满足应急层与已识别节点后，仍有"
            f" {_fmt(plan.surplus.initial_balance)} 初始富余资金可单独按长期资金管理。",
        )
    else:
        _append_unique(
            lines,
            "- 当前阶段属于**中期积累推进**：现有节点可覆盖，但后续仍需要按事件顺序持续把年度结余沉淀到对应账户中。",
        )

    if emergency_funded:
        _append_unique(
            lines,
            f"- 按当前金融资产规模，应急层目标 {_fmt(plan.emergency.amount)} 可以被单独划出，"
            "短期波动不应挤占这部分流动性缓冲。",
        )
    else:
        _append_unique(
            lines,
            f"- 按当前金融资产规模，应急层目标 {_fmt(plan.emergency.amount)} 仍无法被完整划出，"
            "说明家庭缓冲垫偏薄，任何新增压力都会更快传导到长期资金安排。",
        )

    if future_cf and future_cf["negative_years"]:
        neg_years = "、".join(str(year) for year in future_cf["negative_years"][:3])
        _append_unique(
            lines,
            f"- 常规现金流并不是一条平滑直线：按当前测算，{neg_years} 年等阶段会转负，"
            "这意味着预算管理需要前置，而不能等到事件临近再处理。",
        )

    return lines


def _summary_action_lines(
    profile: ClientProfile,
    plan: AllocationPlan,
    projections: tuple[NodeProjection, ...],
    future_cf: dict[str, object] | None,
    retirement_gap: float,
) -> list[str]:
    lines: list[str] = []
    monthly_surplus = plan.monthly_surplus
    next_event = _next_future_event(profile)
    next_bucket = _next_bucket_gap(plan)
    next_shortfall = _nearest_negative_projection(projections)
    dependent_count = _dependent_count(profile)
    debt_burden_pct = (profile.monthly_liabilities / plan.monthly_income * 100) if plan.monthly_income > 0 else 0.0

    if monthly_surplus < 0:
        _append_unique(
            lines,
            f"- **先修复现金流本身**：把月度净现金流至少修回到非负。当前约为 {_fmt(monthly_surplus)}，"
            "如果这一步不先完成，后续任何节点资金计划都会被动被打断。",
            max_items=3,
        )

    if plan.total_investable < plan.emergency.amount:
        _append_unique(
            lines,
            f"- **先补足应急缓冲**：按当前口径应急层目标为 {_fmt(plan.emergency.amount)}。"
            "在这部分没有独立站稳之前，不建议把全部金融资产都暴露在长期波动里。",
            max_items=3,
        )

    if next_shortfall is not None:
        _append_unique(
            lines,
            f"- **优先重排最近会出缺口的目标**：先围绕 {next_shortfall.description}（{next_shortfall.year} 年）"
            f"消化约 {_fmt(abs(next_shortfall.gap_or_surplus))} 的缺口，再考虑其他远期目标是否按原计划推进。",
            max_items=3,
        )
    elif next_event is not None and next_event.timing_year - profile.current_year <= 3:
        _append_unique(
            lines,
            f"- **把最近节点资金单独锁定**：{next_event.description}（{next_event.timing_year} 年）属于近端用途，"
            "在这笔钱达标前，应以可用性和低波动为先，而不是追求更高收益。",
            max_items=3,
        )

    if next_bucket is not None and next_bucket.years_from_now is not None and next_bucket.years_from_now > 0:
        annual_gap = max(next_bucket.amount - next_bucket.initial_balance, 0.0) / (next_bucket.years_from_now + 1)
        _append_unique(
            lines,
            f"- **按年度进度补最近未达标账户**：当前最先需要继续积累的是 {next_bucket.name}，"
            f"剩余目标约 {_fmt(max(next_bucket.amount - next_bucket.initial_balance, 0.0))}，"
            f"可按每年约 {_fmt(annual_gap)} 的节奏检查是否跟上进度。",
            max_items=3,
        )

    if plan.surplus and plan.surplus.initial_balance > 0 and len(lines) < 3:
        _append_unique(
            lines,
            f"- **把长钱与近钱分开**：当前已有 {_fmt(plan.surplus.initial_balance)} 初始富余资金，"
            "这部分可以单独视作长期账户管理，不要与近 3 年内要动用的节点资金混在一起。",
            max_items=3,
        )

    if retirement_gap > 0 and len(lines) < 3:
        _append_unique(
            lines,
            f"- **提前为退休后的现金流断层做准备**：按当前口径退休后月度缺口约 {_fmt(retirement_gap)}，"
            "后续新增积累不应只盯子女或购房节点，也要预留退休后的承接空间。",
            max_items=3,
        )

    if (
        plan.insurance.term_life_existing <= 0
        and (dependent_count > 0 or profile.total_outstanding_debt > 0 or debt_burden_pct >= 20)
        and len(lines) < 3
    ):
        _append_unique(
            lines,
            "- **单独复核责任型保障结构**：当前档案未体现有效定寿，而家庭仍有负债或抚养责任，"
            "这类风险不应默认由投资账户去被动承接。",
            max_items=3,
        )

    if not lines:
        _append_unique(
            lines,
            "- **继续按既定分层推进**：现阶段没有看到需要立刻推翻原计划的硬约束，重点是按账户顺序持续执行并定期回看。",
            max_items=3,
        )

    return lines[:3]


def _summary_metric_lines(
    profile: ClientProfile,
    plan: AllocationPlan,
    future_cf: dict[str, object] | None,
    retirement_gap: float,
) -> list[str]:
    lines: list[str] = []
    next_bucket = _next_bucket_gap(plan)
    next_event = _next_future_event(profile)
    debt_burden_pct = (profile.monthly_liabilities / plan.monthly_income * 100) if plan.monthly_income > 0 else 0.0

    _append_unique(
        lines,
        f"- **月度净结余**：重点关注是否持续低于当前基线 {_fmt(plan.monthly_surplus)}。"
        "这是一切节点资金计划能否按时推进的总开关。",
        max_items=5,
    )
    _append_unique(
        lines,
        f"- **应急层是否仍独立保留**：当前应急目标为 {_fmt(plan.emergency.amount)}。"
        "如果这部分被挪作他用，后续所有长期安排都会更脆弱。",
        max_items=5,
    )

    if next_bucket is not None and next_bucket.years_from_now is not None and next_bucket.years_from_now > 0:
        annual_gap = max(next_bucket.amount - next_bucket.initial_balance, 0.0) / (next_bucket.years_from_now + 1)
        _append_unique(
            lines,
            f"- **最近未达标目标账户进度**：优先看 {next_bucket.name} 是否至少按每年约 {_fmt(annual_gap)} 的节奏推进，"
            "不要只看总资产涨跌。",
            max_items=5,
        )
    elif next_event is not None:
        _append_unique(
            lines,
            f"- **最近重大节点的可兑现性**：持续检查 {next_event.description}（{next_event.timing_year} 年）对应资金"
            "是否仍保持独立和可动用。",
            max_items=5,
        )

    if future_cf:
        _append_unique(
            lines,
            f"- **最紧年份的常规净现金流**：当前测算里最紧的是 {future_cf['min_year']} 年，"
            f"常规净现金流约 {_fmt(future_cf['min_net'])}。如果现实偏离这里，剧本需要更早调整。",
            max_items=5,
        )

    if debt_burden_pct > 0:
        _append_unique(
            lines,
            f"- **负债月供占收入比**：当前约 {debt_burden_pct:.1f}%。"
            "如果月供上升或收入下降，这个比例会直接压缩节点资金的可执行空间。",
            max_items=5,
        )

    if retirement_gap > 0 and len(lines) < 5:
        _append_unique(
            lines,
            f"- **退休后月度缺口**：当前口径约 {_fmt(retirement_gap)}。"
            "若未来养老金、支出或退休年份发生变化，这一项需要优先回看。",
            max_items=5,
        )

    if plan.surplus and len(lines) < 5:
        _append_unique(
            lines,
            "- **富余资金是否被提前挪用**：这部分本应用于长期增值，若频繁回流去补近端目标，说明原预算顺序需要重排。",
            max_items=5,
        )

    return lines[:5]


def _summary_insurance_lines(
    profile: ClientProfile,
    plan: AllocationPlan,
    projections: tuple[NodeProjection, ...],
    retirement_gap: float,
) -> list[str]:
    lines: list[str] = []
    dependent_count = _dependent_count(profile)
    next_shortfall = _nearest_negative_projection(projections)
    key_earner_count = sum(
        1 for member in profile.members
        if member.annual_income > 0 or member.income_start_annual > 0 or member.role == "primary_breadwinner"
    )
    has_responsibility = (
        dependent_count > 0
        or profile.total_outstanding_debt > 0
        or any((evt.estimated_amount or 0) > 0 for evt in profile.events if evt.timing_year >= profile.current_year)
    )
    medical_gap = not plan.insurance.medical_covered
    ci_gap = plan.insurance.ci_existing <= 0 and key_earner_count > 0
    life_gap = plan.insurance.term_life_existing <= 0 and has_responsibility and key_earner_count > 0
    premium_pressure = (
        plan.insurance.premium_burden_pct >= 10
        or plan.monthly_surplus <= 0
        or next_shortfall is not None
    )

    if medical_gap or ci_gap or life_gap:
        missing_items: list[str] = []
        if medical_gap:
            missing_items.append("医疗保障")
        if ci_gap:
            missing_items.append("重疾保障")
        if life_gap:
            missing_items.append("定期寿险")
        missing_text = "、".join(missing_items)
        if premium_pressure:
            _append_unique(
                lines,
                f"- 当前保障更值得先补的是**{missing_text}**，但不建议一次性全面铺开。"
                "更合适的做法是先围绕关键收入成员补基础保障，再控制新增保费，避免挤压近期重大节点和日常现金流。",
                max_items=2,
            )
        else:
            _append_unique(
                lines,
                f"- 当前保障存在明显结构缺口，建议优先复核关键收入成员的**{missing_text}**是否齐全。"
                "顺序上先补基础保障，再考虑长期锁定型保险安排会更稳妥。",
                max_items=2,
            )
    elif plan.insurance.premium_burden_pct >= 10:
        _append_unique(
            lines,
            f"- 现有基础保障已有一定覆盖，但当前保费负担约占月收入的 {plan.insurance.premium_burden_pct:.1f}%。"
            "现阶段更重要的是确认保费压力是否能长期承受，而不是继续叠加新的长期保单。",
            max_items=2,
        )
    elif retirement_gap > 0 and profile.insurance_medical_covered:
        _append_unique(
            lines,
            "- 现有保障结构没有看到明显短板，后续重点可放在定期回看退休后的医疗与自付压力是否仍在可承受范围内，"
            "而不必急着做复杂加保。",
            max_items=2,
        )
    else:
        _append_unique(
            lines,
            "- 当前保障更适合做定期复核，而不是明显加码。重点是确认关键收入成员的医疗、重疾和寿险责任"
            "能否覆盖家庭责任期，而不是把保障配置做得过于复杂。",
            max_items=2,
        )

    return lines[:2]


def _summary_recalc_lines(
    profile: ClientProfile,
    plan: AllocationPlan,
    future_cf: dict[str, object] | None,
    retirement_gap: float,
) -> list[str]:
    lines: list[str] = []
    income_change = max(plan.monthly_income * 0.2, 1.0)
    expense_change = max(plan.monthly_expense * 0.15, 1.0)

    _append_unique(
        lines,
        f"- 家庭收入若出现明显变化，特别是年收入下降约 20% 以上"
        f"（折合月收入变动约 {_fmt(income_change)} 量级）时，建议重算。",
        max_items=5,
    )
    _append_unique(
        lines,
        "- 新增、提前、取消或放大任何重大支出节点时，建议重算；这会直接改变资金分层顺序。",
        max_items=5,
    )
    _append_unique(
        lines,
        f"- 常规支出或负债月供若明显抬升，特别是月度总支出变化约 15% 以上"
        f"（约 {_fmt(expense_change)} 量级）时，建议重算。",
        max_items=5,
    )
    if retirement_gap > 0 or _next_future_event(profile) is not None:
        _append_unique(
            lines,
            "- 退休年份、子女教育路径、购房安排等人生节点发生变化时，建议重算；这类变化通常比市场波动更能改变剧本结论。",
            max_items=5,
        )
    if future_cf and future_cf["negative_years"]:
        _append_unique(
            lines,
            "- 若现实中已经出现长期动用应急层、提前挪用富余资金、或连续几年净结余低于预期，也应视作重算信号。",
            max_items=5,
        )
    else:
        _append_unique(
            lines,
            "- 若金融资产出现大额进出、或家庭保障结构发生明显变化，也应回到问卷重算一次，避免沿用旧假设。",
            max_items=5,
        )
    return lines[:5]


def _headline_conclusion_lines(
    profile: ClientProfile,
    plan: AllocationPlan,
    projections: tuple[NodeProjection, ...],
    bucket_result: BucketProjectionResult | None,
) -> list[str]:
    lines: list[str] = []
    negative_nodes = [projection for projection in projections if projection.gap_or_surplus < 0]
    future_nodes = [projection for projection in projections if projection.year >= profile.current_year]

    if future_nodes and not negative_nodes:
        last_node = max(future_nodes, key=lambda projection: projection.year)
        lines.append(
            f"- **重大节点覆盖结论**：按当前测算，已录入的重大支出节点整体可满足；"
            f"截至 {last_node.year} 年，最后一个节点 {last_node.description} 之后仍保留约 {_fmt(last_node.balance_after)} 结余。"
        )
    elif negative_nodes:
        first_shortfall = min(negative_nodes, key=lambda projection: projection.year)
        lines.append(
            f"- **重大节点覆盖结论**：按当前测算，并非所有重大支出节点都能满足；"
            f"最早的缺口会出现在 {first_shortfall.year} 年的 {first_shortfall.description}，"
            f"缺口约 {_fmt(abs(first_shortfall.gap_or_surplus))}。"
        )
    else:
        lines.append("- **重大节点覆盖结论**：当前档案未录入需要单独测算的大额节点，现阶段可先把重点放在持续积累与定期回看上。")

    if bucket_result is not None and plan.surplus is not None:
        stats = bucket_result.annualized_return_for_bucket("富余资金")
        if stats is not None:
            lines.append(
                f"- **富余资金长期收益结论**：如果把富余资金账户从 {stats.start_year} 年持有到 {stats.end_year} 年，"
                f"更居中的结果大致相当于每年增长 {_format_pct(stats.p50)}；"
                f"若结果偏保守，长期下来大约可能落在每年 {_format_pct(stats.p10)} 到 {_format_pct(stats.p25)} 左右，"
                f"若结果偏顺利，则大致可能在每年 {_format_pct(stats.p75)} 到 {_format_pct(stats.p90)} 左右。"
            )
        else:
            lines.append("- **富余资金长期收益结论**：这笔长期资金的收益区间暂时还未算出，需等收益推演可用后再补充。")
    else:
        lines.append("- **富余资金长期收益结论**：当前没有单独划出的富余资金账户，所以现阶段不单独讨论这部分长期资金的增长表现。")

    return lines


# ── A. 客户情况概览 ────────────────────────────────────

def _render_metadata(profile: ClientProfile) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    semver = profile.schema_version.replace("handbook-v", "")
    return (
        f"# {profile.family_name} 家庭资产配置剧本\n\n"
        f"**生成时间:** {timestamp} | "
        f"**方法论版本:** handbook-v{semver} | "
        f"**风险偏好:** {profile.risk_preference}\n\n"
        f"> 本剧本用于家庭资产规划沟通，不构成投资建议。所有数值基于方法论假设，实际配置仍需结合专业人士意见。\n\n"
    )


def _render_section_a(profile: ClientProfile) -> str:
    monthly_income = profile.total_annual_income / 12.0
    monthly_premium = profile.insurance_total_annual_premium / 12.0
    monthly_expense = profile.monthly_living_expense + profile.monthly_liabilities + monthly_premium
    monthly_surplus = monthly_income - monthly_expense
    net_worth = (profile.total_real_estate_value + profile.total_financial_assets
                 - profile.total_outstanding_debt)

    parts = ["---\n\n## A. 客户情况概览\n\n"]

    # A1. 初始状态
    parts.append("### A1. 初始资产与收支状态\n\n")
    parts.append("| 项目 | 金额 |\n|---|---|\n")
    parts.append(f"| 房产估值 | {_fmt(profile.total_real_estate_value)} |\n")
    parts.append(f"| 金融资产(境内+海外) | {_fmt(profile.total_financial_assets)} |\n")
    parts.append(f"| 负债余额 | {_fmt(profile.total_outstanding_debt)} |\n")
    parts.append(f"| **家庭净资产** | **{_fmt(net_worth)}** |\n\n")

    parts.append("| 项目 | 月度金额 |\n|---|---|\n")
    parts.append(f"| 家庭月收入(税前) | {_fmt(monthly_income)} |\n")
    if profile.monthly_living_expense > 0:
        parts.append(f"| 常规支出(含家庭额外) | {_fmt(profile.monthly_living_expense)} |\n")
    if profile.monthly_liabilities > 0:
        parts.append(f"| 贷款月供 | {_fmt(profile.monthly_liabilities)} |\n")
    if monthly_premium > 0:
        parts.append(f"| 保险保费(月均) | {_fmt(monthly_premium)} |\n")
    parts.append(f"| **月度结余** | **{_fmt(monthly_surplus)}** |\n")
    if monthly_surplus < 0:
        parts.append("\n> **警告:** 月度支出超过收入,现金流为负。\n")
    parts.append("\n")

    # 退休后收支
    retirement_rollup = _member_retirement_rollup(profile)
    has_retirement = (
        retirement_rollup["monthly_income_total"] > 0
        or retirement_rollup["monthly_expense_total"] > 0
        or retirement_rollup["first_year_healthcare_selfpay_total"] > 0
        or profile.retirement_monthly_pension > 0
        or profile.retirement_monthly_annuity > 0
        or profile.retirement_monthly_expense > 0
    )
    if has_retirement:
        ret_income = retirement_rollup["monthly_income_total"] or (profile.retirement_monthly_pension + profile.retirement_monthly_annuity)
        ret_expense = retirement_rollup["monthly_expense_total"] or profile.retirement_monthly_expense
        parts.append("**退休后预期**\n\n")
        parts.append("| 项目 | 金额/参数 | 说明 |\n")
        parts.append("|---|---|---|\n")
        if ret_income > 0:
            income_items = retirement_rollup["income_items"]
            income_desc = "；".join(f"{name} {_fmt(value)}" for name, value in income_items[:4]) if income_items else (
                f"养老金 {_fmt(profile.retirement_monthly_pension)} + 年金 {_fmt(profile.retirement_monthly_annuity)}"
            )
            parts.append(
                f"| 退休月收入 | {_fmt(ret_income)} | "
                f"{income_desc} |\n"
            )
        if ret_expense > 0:
            expense_items = retirement_rollup["expense_items"]
            expense_desc = "；".join(f"{name} {_fmt(value)}" for name, value in expense_items[:4]) if expense_items else "退休后月度生活支出口径"
            parts.append(f"| 退休月支出 | {_fmt(ret_expense)} | {expense_desc} |\n")
        hc = retirement_rollup["first_year_healthcare_selfpay_total"] or profile.healthcare_starting_annual
        if hc > 0:
            growth_desc = "—"
            growth_rates = [m.healthcare_growth_rate for m in profile.members if m.healthcare_starting_annual > 0]
            annual_caps = [m.healthcare_annual_cap for m in profile.members if m.healthcare_starting_annual > 0 and m.healthcare_annual_cap > 0]
            display_growth = max(growth_rates) if growth_rates else profile.healthcare_growth_rate
            if display_growth > 0:
                pct = round(display_growth * 100, 1)
                growth_desc = f"年复利增长 {pct}%"
            cap_desc = _fmt(sum(annual_caps)) if annual_caps else "—"
            gross_hc = sum(m.healthcare_starting_annual for m in profile.members if m.healthcare_starting_annual > 0) or profile.healthcare_starting_annual
            parts.append(f"| 退休首年医疗年支出(毛额) | {_fmt(gross_hc)} | {growth_desc}；年度封顶 {cap_desc} |\n")
            healthcare_items = retirement_rollup["healthcare_items"]
            hc_desc = "；".join(f"{name} {_fmt(value)}" for name, value in healthcare_items[:4]) if healthcare_items else "按退休首年医疗支出测算"
            parts.append(
                f"| 退休首年医疗自付 | {_fmt(hc)} | {hc_desc} |\n"
            )
        parts.append("\n")

    # 负债还清时间
    if profile.monthly_liabilities > 0 and profile.remaining_liability_end_year > profile.current_year:
        parts.append(f"**贷款还清:** {profile.remaining_liability_end_year} 年"
                     f"(剩余 {profile.remaining_liability_end_year - profile.current_year} 年)\n\n")

    target_liquidity_months = profile.liquidity_reserve_months if profile.liquidity_reserve_months > 0 else 6.0
    parts.append(f"**流动性储备:** 当前 {profile.liquidity_reserve_months:.0f} 个月(目标 {target_liquidity_months:.0f} 个月)\n\n")

    # A2. 人生节点时间线
    parts.append("### A2. 人生阶段节点\n\n")
    parts.append("| 年份 | 距今 | 事件 | 预计金额 |\n")
    parts.append("|---|---|---|---|\n")
    for evt in profile.events:
        if evt.timing_year < profile.current_year:
            continue
        years = evt.timing_year - profile.current_year
        amount = _fmt(evt.estimated_amount) if evt.estimated_amount else "—"
        parts.append(
            f"| {evt.timing_year} | {years}年 | {evt.description} | {amount} |\n"
        )
    parts.append("\n")

    return "".join(parts)


def _render_section_a3(
    profile: ClientProfile,
    plan: AllocationPlan,
    projections: tuple[NodeProjection, ...],
    yearly_snapshots: tuple[YearlySnapshot, ...] = (),
    bucket_result: BucketProjectionResult | None = None,
) -> str:
    future_cf = _future_cashflow_summary(profile, yearly_snapshots)
    retirement_rollup = _member_retirement_rollup(profile)
    retirement_gap = _retirement_monthly_gap(profile, retirement_rollup)
    headline_lines = _headline_conclusion_lines(profile, plan, projections, bucket_result)
    state_lines = _summary_state_lines(profile, plan, projections, future_cf, retirement_gap)
    action_lines = _summary_action_lines(profile, plan, projections, future_cf, retirement_gap)
    insurance_lines = _summary_insurance_lines(profile, plan, projections, retirement_gap)
    metric_lines = _summary_metric_lines(profile, plan, future_cf, retirement_gap)
    recalc_lines = _summary_recalc_lines(profile, plan, future_cf, retirement_gap)

    parts = ["---\n\n## 综合建议摘要\n\n"]
    for line in headline_lines:
        parts.append(f"{line}\n")
    parts.append("\n")

    parts.append("**1. 现阶段的整体判断**\n\n")
    for line in state_lines:
        parts.append(f"{line}\n")
    parts.append("\n")

    parts.append("**2. 现在最值得优先做的 3 件事**\n\n")
    for line in action_lines:
        parts.append(f"{line}\n")
    parts.append("\n")

    parts.append("**3. 保障配置建议**\n\n")
    for line in insurance_lines:
        parts.append(f"{line}\n")
    parts.append("\n")

    parts.append("**4. 后续需要持续关注的几个信号**\n\n")
    for line in metric_lines:
        parts.append(f"{line}\n")
    parts.append("\n")

    parts.append("**5. 出现哪些变化时，建议尽快重算**\n\n")
    for line in recalc_lines:
        parts.append(f"{line}\n")
    parts.append("\n")

    return "".join(parts)


# ── B. 资产推演 ────────────────────────────────────

def _render_section_b(
    profile: ClientProfile,
    projections: tuple[NodeProjection, ...],
    yearly: tuple[YearlySnapshot, ...] = (),
    return_snapshots: tuple[YearlyReturnSnapshot, ...] = (),
    bucket_result: BucketProjectionResult | None = None,
) -> str:
    future_cf = _future_cashflow_summary(profile, yearly)

    parts = [
        "---\n\n## B. 资产推演\n\n"
        f"> 本段推演主要回答“未来重大节点能否按时覆盖”。"
        f"这里以初始金融资产 {_fmt(profile.total_financial_assets)} 和逐年净现金流序列为基础，"
        "统一按年末口径累计，并暂不计入投资收益。\n\n"
    ]
    if future_cf:
        parts.append(
            f"> 按当前档案，{future_cf['start_year']}-{future_cf['end_year']} 年常规净现金流"
            f"年均约 {_fmt(future_cf['avg_net'])}，并会随成员起薪、退休切换与退休后支出口径动态变化。\n\n"
        )

    chart_end_year = _chart_end_year(profile)
    yearly = tuple(s for s in yearly if s.year <= chart_end_year)
    return_snapshots_truncated = tuple(s for s in return_snapshots if s.year <= chart_end_year)

    # 时序图
    if yearly:
        labels = [str(s.year) for s in yearly]
        inflow = [s.cash_inflow for s in yearly]
        outflow = [-s.cash_outflow for s in yearly]
        balance = [round(s.asset_balance) for s in yearly]
        import json

        # 事件索引
        events_by_yr: dict[int, list[tuple[float, str]]] = {}
        for evt in profile.events:
            if evt.timing_year >= profile.current_year:
                events_by_yr.setdefault(evt.timing_year, []).append(
                    (float(evt.estimated_amount or 0), evt.description)
                )

        # 阶段图所需数据: obstacles / 不含事件的正规年支出 / 阶段内累计现金流
        obstacle_amounts: list[float] = []
        regular_outflow: list[float] = []
        phase_cash_flow: list[float] = []
        running_phase = 0.0
        for s in yearly:
            evts = events_by_yr.get(s.year, [])
            total_obstacle = sum(e[0] for e in evts)
            obstacle_amounts.append(total_obstacle)
            reg_out = s.cash_outflow - total_obstacle
            regular_outflow.append(reg_out)
            running_phase += s.cash_inflow - reg_out
            phase_cash_flow.append(running_phase)
            if total_obstacle > 0:
                running_phase = 0.0

        chart_data = json.dumps({
            "labels": labels,
            "inflow": inflow,
            "outflow": outflow,
            "balance": balance,
        })
        phase_chart_data = json.dumps({
            "labels": labels,
            "balance": balance,
            "phaseCashFlow": phase_cash_flow,
            "obstacles": obstacle_amounts,
        })
        # 含投资收益的总资产图: 优先使用 bucket 级推演汇总,避免与 C5/C6 口径不一致
        total_stats_truncated = tuple(
            s for s in (bucket_result.total_stats if bucket_result else ())
            if s.year <= chart_end_year
        )
        if total_stats_truncated:
            ret_labels = [str(s.year) for s in total_stats_truncated]
            total_returns_p50_by_year: dict[int, float] = {}
            if bucket_result is not None:
                for item in bucket_result.breakdowns:
                    if item.year <= chart_end_year:
                        total_returns_p50_by_year[item.year] = (
                            total_returns_p50_by_year.get(item.year, 0.0) + item.returns_p50
                        )
            negative_return_years = [
                str(year)
                for year, total_return in sorted(total_returns_p50_by_year.items())
                if total_return < 0
            ]
            note = (
                "> 这张图展示的是家庭总资产路径。总资产上升，可能同时来自当年结余和投资结果；"
                "其中某些年份，投资结果本身也可能为负。\n\n"
            )
            if negative_return_years:
                note += (
                    f"> 按居中情景口径，投资结果为负的年份包括："
                    f"{'、'.join(negative_return_years)}。\n\n"
                )
            cashflow_with_return_data = json.dumps({
                "labels": ret_labels,
                "inflow": inflow,
                "outflow": outflow,
                "p10": [s.p10 for s in total_stats_truncated],
                "p25": [s.p25 for s in total_stats_truncated],
                "p50": [s.p50 for s in total_stats_truncated],
                "p75": [s.p75 for s in total_stats_truncated],
                "p90": [s.p90 for s in total_stats_truncated],
                "balance": balance,
            })
            parts.append(
                '<div class="chart-section">\n'
                f'  <h3>家庭总资产路径（含现金流与投资结果，展示至 {chart_end_year} 年）</h3>\n'
                '  <div class="chart-container">\n'
                '    <canvas id="cashflowWithReturnChart"></canvas>\n'
                '  </div>\n'
                '</div>\n'
                f'{note}'
                f'<script id="cashflow-with-return-data" type="application/json">{cashflow_with_return_data}</script>\n\n'
            )
        elif return_snapshots_truncated:
            ret_labels = [str(s.year) for s in return_snapshots_truncated]
            cashflow_with_return_data = json.dumps({
                "labels": ret_labels,
                "inflow": inflow,
                "outflow": outflow,
                "p10": [s.p10 for s in return_snapshots_truncated],
                "p25": [s.p25 for s in return_snapshots_truncated],
                "p50": [s.p50 for s in return_snapshots_truncated],
                "p75": [s.p75 for s in return_snapshots_truncated],
                "p90": [s.p90 for s in return_snapshots_truncated],
            })
            parts.append(
                '<div class="chart-section">\n'
                f'  <h3>家庭总资产路径（含现金流与投资结果，展示至 {chart_end_year} 年）</h3>\n'
                '  <div class="chart-container">\n'
                '    <canvas id="cashflowWithReturnChart"></canvas>\n'
                '  </div>\n'
                '</div>\n'
                '> 这张图展示的是家庭总资产路径。总资产上升，可能同时来自当年结余和投资结果；其中某些年份，投资结果本身也可能为负。\n\n'
                f'<script id="cashflow-with-return-data" type="application/json">{cashflow_with_return_data}</script>\n\n'
            )

    parts.append("### 事件节点推演\n\n")
    parts.append("| 节点 | 年份 | 距今 | 到达时累积资产 | 所需支出 | 支出后余额 | 状态 |\n")
    parts.append("|---|---|---|---|---|---|---|\n")
    for proj in projections:
        status = f"**盈余 {_fmt(proj.gap_or_surplus)}**" if proj.gap_or_surplus >= 0 else f"**缺口 {_fmt(abs(proj.gap_or_surplus))}**"
        parts.append(
            f"| {proj.description} | {proj.year} | {proj.years_from_now}年 "
            f"| {_fmt(proj.accumulated_savings)} | {_fmt(proj.event_cost)} "
            f"| {_fmt(proj.balance_after)} | {status} |\n"
        )
    parts.append("\n")

    return "".join(parts)


# ── C. 资金分配方案 ────────────────────────────────────

def _iter_buckets_with_initial(plan: AllocationPlan):
    """遍历所有 bucket (包括 initial_balance=0 的富余资金)。"""
    for b in _iter_all_buckets(plan):
        yield b


def _stage_symbol(years_left: int | None) -> str:
    """根据剩余年限返回阶段符号。"""
    if years_left is None or years_left <= 0:
        return "—"
    if years_left <= 3:
        return "★"
    if years_left <= 7:
        return "●"
    if years_left <= 10:
        return "■"
    return "▲"


def _stage_label(years_left: int | None) -> str:
    if years_left is None or years_left <= 0:
        return "到期"
    if years_left <= 3:
        return "近期"
    if years_left <= 7:
        return "中期"
    if years_left <= 10:
        return "远期"
    return "超远期"


def _stage_color(years_left: int | None) -> str:
    if years_left is None or years_left <= 0:
        return "#9ca3af"
    if years_left <= 3:
        return "#22c55e"
    if years_left <= 7:
        return "#eab308"
    if years_left <= 10:
        return "#f97316"
    return "#dc2626"


def _stage_badge(symbol: str, label: str, years_left: int | None) -> str:
    color = _stage_color(years_left)
    return f'<span style="color:{color};font-weight:700">{symbol}</span> {label}'


def _stage_legend_html(*, include_expired_note: bool = False) -> str:
    legend = (
        '<span class="stage-legend">'
        '<span class="stage-chip stage-chip-near">★</span>=近期(≤3年) '
        '<span class="stage-chip stage-chip-mid">●</span>=中期(3-7年) '
        '<span class="stage-chip stage-chip-long">■</span>=远期(7-10年) '
        '<span class="stage-chip stage-chip-ultra">▲</span>=超远期(>10年)'
        '</span>'
    )
    if include_expired_note:
        legend += " 无符号=已到期。"
    return legend


def _iter_all_buckets(plan: AllocationPlan):
    yield plan.emergency
    if plan.ci_reserve:
        yield plan.ci_reserve
    yield from plan.node_buckets
    if plan.surplus:
        yield plan.surplus


def _bucket_purpose(b: BucketAllocation) -> str:
    """返回 bucket 的中文用途描述。"""
    if b.name == "应急储备":
        return "流动性保障"
    if b.name == "富余资金":
        return "长期灵活投资"
    if b.withdrawal_year:
        return f"对应 {b.withdrawal_year} 年目标支出"
    return b.name


def _render_section_c(
    plan: AllocationPlan,
    current_year: int = 2026,
    profile: ClientProfile | None = None,
    yearly_snapshots: tuple[YearlySnapshot, ...] = (),
) -> str:
    parts = ["---\n\n## C. 资产配置执行方案\n\n"]

    total = sum(b.initial_balance for b in _iter_buckets_with_initial(plan))
    monthly = plan.monthly_surplus
    future_cf = _future_cashflow_summary(profile, yearly_snapshots) if profile else None

    # ── C1. 初始存量资金配置 ──
    parts.append("### C1. 初始存量资金分配（立即执行）\n\n")

    if total <= 0:
        parts.append("> 无可投资金融资产，跳过本节。\n\n")
    else:
        parts.append(
            f"你现有的 **{_fmt(total)}** 金融资产，可先按下表完成一次初始分层；核心目的是先把不同用途的资金分别放到合适的位置。\n\n"
        )

        parts.append("| 资金层 | 用途 | 一次性划拨 | 占存量比 | 投资阶段 |\n")
        parts.append("|---|---|---|---|---|\n")

        for b in _iter_buckets_with_initial(plan):
            if b.initial_balance <= 0 and b.name != "富余资金":
                continue  # 跳过无存量的节点
            pct_str = f"{b.initial_balance/total*100:.1f}%" if b.initial_balance > 0 else "0.0%"
            # 确定投资阶段
            if b.name == "应急储备":
                sym, label = "★", "近期"
                years_left = 1
            elif b.name.startswith("重疾准备金"):
                sym, label = "★", "近期"
                years_left = 1
            elif b.name == "富余资金":
                years_left = (b.withdrawal_year - current_year) if b.withdrawal_year else 15
                sym = _stage_symbol(years_left)
                label = _stage_label(years_left)
            else:
                years_left = (b.withdrawal_year - current_year) if b.withdrawal_year else None
                sym = _stage_symbol(years_left)
                label = _stage_label(years_left)
            stage_html = _stage_badge(sym, label, years_left)
            parts.append(
                f"| {b.name} | {_bucket_purpose(b)} "
                f"| {_fmt(b.initial_balance)} | {pct_str} "
                f"| {stage_html} |\n"
            )
        parts.append(
            f"| **合计** | — | **{_fmt(total)}** | **100%** | — |\n"
        )
        parts.append("\n")

        parts.append("**操作指引**\n\n")
        parts.append("- 清点现有持仓，按上表目标完成首次分层配置\n")
        parts.append(f"- 投资阶段图例：{_stage_legend_html()}\n\n")

    # ── C2. 年度净结余分配 ──
    parts.append("### C2. 年度净结余分配（动态口径，按年预算，按月执行）\n\n")

    if monthly <= 0 and not future_cf:
        parts.append("> 当前缺少可用于分配的净结余信息。\n\n")
    else:
        ci_monthly = plan.ci_reserve.monthly_contribution if plan.ci_reserve else 0

        if monthly <= 0:
            parts.append(
                "你当前截面的月度结余并不宽松，但未来年度预算仍应以逐年净现金流序列来判断，"
                "而不是只看当前一个时点。\n\n"
            )
        else:
            parts.append(
                f"你当前每月约有 **{_fmt(monthly)}** 净结余，"
                f"对应当前年度起点预算约 **{_fmt(monthly * 12)}**。"
                "但后续执行不应把它视作固定值，下表反映的是年度优先顺序，日常执行时再按月持续投入。\n\n"
            )
        if future_cf:
            parts.append(
                f"> 参考逐年快照：{future_cf['start_year']}-{future_cf['end_year']} 年常规净现金流"
                f"年均约 {_fmt(future_cf['avg_net'])}，区间大致在 {_fmt(future_cf['min_net'])}"
                f"（{future_cf['min_year']}年）到 {_fmt(future_cf['max_net'])}（{future_cf['max_year']}年）之间。\n\n"
            )

        parts.append("| 顺序 | 资金去向 | 月度执行口径 | 需累计资金 | 说明 |\n")
        parts.append("|---|---|---|---|---|\n")

        seq = 1

        # 应急储备补足
        em_shortfall = plan.emergency.amount - plan.emergency.initial_balance
        if em_shortfall > 0:
            parts.append(
                f"| {seq} | 应急储备补足 | 灵活\\* | {_fmt(em_shortfall)} "
                f"| 低于目标时优先补足 |\n"
            )
            seq += 1

        # 节点 bucket（按时间序，跳过已由存量覆盖的）
        for b in plan.node_buckets:
            need = b.amount - b.initial_balance
            if need <= 0:
                continue
            label = "用于对应年度规划事项"
            yr_note = f"（{b.withdrawal_year}年使用）" if b.withdrawal_year else ""
            parts.append(
                f"| {seq} | {b.name} | 动态† | {_fmt(need)} "
                f"| {label}{yr_note} |\n"
            )
            seq += 1

        # CI 自留（方案B/D）
        if ci_monthly > 0:
            parts.append(
                f"| {seq} | 重疾自留储备 | {_fmt(ci_monthly)}/月‡ "
                f"| {_fmt(plan.ci_reserve.amount)} "
                f"| 分期储备固定月供 |\n"
            )
            seq += 1

        # 富余资金
        if plan.surplus:
            parts.append(
                f"| {seq} | 富余资金 | 剩余全部 | — | 所有目标达标后自动转入 |\n"
            )

        parts.append("\n")
        parts.append("**分配规则**\n\n")
        parts.append("- \\* 灵活：应急储备未达标时，优先从年度预算中补足；执行上可以按月逐步补齐\n")
        parts.append("- † 动态：年度净结余按事件时间顺序逐层满足；执行时可按月持续投入，前一层达标后再转向下一层\n")
        if ci_monthly > 0:
            parts.append("- ‡ 固定：重疾自留月供优先于其他节点资金安排\n")
        parts.append("\n")

    # 注意事项（保留原样）
    if plan.warnings:
        parts.append("> **注意事项:**\n")
        for w in plan.warnings:
            parts.append(f"> - {w}\n")
        parts.append("\n")

    return "".join(parts)


# ── C3. 心理账户余额（居中情景）─────────────────────

def _render_section_c3(
    bucket_result: BucketProjectionResult | None,
    plan: AllocationPlan,
    chart_end_year: int,
) -> str:
    """心理账户余额表: 每账户每年的居中情景余额。"""
    import json

    parts = []

    if bucket_result is None or not bucket_result.snapshots:
        return "".join(parts)

    account_order = ["应急储备"]
    account_order.extend(b.name for b in plan.node_buckets)
    if plan.surplus:
        account_order.append("富余资金")

    years = sorted({s.year for s in bucket_result.snapshots if s.year <= chart_end_year})
    if not years:
        return "".join(parts)

    parts.append("---\n\n### C3. 心理账户余额（居中情景）\n\n")
    parts.append(
        "下表展示各心理账户在每个年末的 <b>居中结果余额</b>，并已计入投资收益。"
        "“初始划拨”代表最开始的资金分层，后续各年展示的是每年年末滚动后的账户余额。\n\n"
    )

    bal_by_key: dict[tuple[str, int], float] = {}
    for s in bucket_result.snapshots:
        if s.year <= chart_end_year:
            bal_by_key[(s.bucket_name, s.year)] = s.p50

    header_cols = ["年份"] + account_order + ["**合计**"]
    parts.append("| " + " | ".join(header_cols) + " |\n")
    parts.append("|" + "---|" * len(header_cols) + "\n")

    init_row = ["**初始划拨**"]
    init_sum = 0.0
    for aname in account_order:
        if aname == "应急储备":
            val = plan.emergency.initial_balance
        elif aname == "富余资金":
            val = plan.surplus.initial_balance if plan.surplus else 0.0
        else:
            b = next((x for x in plan.node_buckets if x.name == aname), None)
            val = b.initial_balance if b else 0.0
        init_sum += val
        init_row.append(_fmt(val))
    init_row.append(f"**{_fmt(init_sum)}**")
    parts.append("| " + " | ".join(init_row) + " |\n")

    for yr in years:
        row = [f"**{yr}**"]
        yr_sum = 0.0
        for aname in account_order:
            val = bal_by_key.get((aname, yr), 0.0)
            yr_sum += val
            row.append(_fmt(val))
        row.append(f"**{_fmt(yr_sum)}**")
        parts.append("| " + " | ".join(row) + " |\n")
    parts.append("\n")

    return "".join(parts)


# ── C4. 余额阶段热力图 ─────────────────────────

def _render_stage_heatmap(
    bucket_result: BucketProjectionResult | None,
    plan: AllocationPlan,
    chart_end_year: int,
) -> str:
    """HTML 表格: 与 C3 同格式,但单元格为居中情景余额,字体+符号按阶段着色。"""
    import re

    parts = []

    if bucket_result is None or not bucket_result.snapshots:
        return "".join(parts)

    years = sorted({s.year for s in bucket_result.snapshots if s.year <= chart_end_year})
    account_order = ["应急储备"]
    if plan.ci_reserve:
        account_order.append(plan.ci_reserve.name)
    account_order.extend(b.name for b in plan.node_buckets)
    if plan.surplus:
        account_order.append("富余资金")

    bal_by_key: dict[tuple[str, int], float] = {}
    for s in bucket_result.snapshots:
        if s.year <= chart_end_year:
            bal_by_key[(s.bucket_name, s.year)] = s.p50

    STAGE_SPEC = [
        (0, 3,   "#22c55e", "★"),
        (3, 7,   "#eab308", "●"),
        (7, 10,  "#f97316", "■"),
        (10, 999, "#dc2626", "▲"),
    ]

    def _stage_info(years_left: int | None) -> tuple[str, str, str]:
        if years_left is None or years_left <= 0:
            return "#9ca3af", "", ""
        for lo, hi, color, shape in STAGE_SPEC:
            if lo < years_left <= hi:
                return color, shape, color
        return "#dc2626", "▲", "#dc2626"

    def _cell_info(aname: str, yr: int) -> tuple[str, str, str]:
        if aname == "应急储备":
            return "#000000", "★", "#22c55e"
        if aname == "富余资金":
            retire_yr = plan.surplus.withdrawal_year if plan.surplus else None
            left = (retire_yr - yr) if retire_yr else None
            if left is not None and left <= 0:
                return "#9ca3af", "", ""
            clr, shape, _ = _stage_info(left)
            return "#000000", shape, clr
        if aname.startswith("重疾准备金"):
            return "#000000", "★", "#22c55e"
        b = next((x for x in plan.node_buckets if x.name == aname), None)
        if not b:
            return "#9ca3af", "", ""
        left = (b.withdrawal_year - yr) if b.withdrawal_year else None
        if left is not None and left <= 0:
            return "#9ca3af", "", ""
        clr, shape, _ = _stage_info(left)
        return "#000000", shape, clr

    parts.append("---\n\n### C4. 心理账户余额（按阶段着色）\n\n")
    parts.append(
        "这张表和 C3 使用同一组数据，只是额外用颜色标出每笔资金所处阶段。"
        "单元格中的金额仍是 <b>居中结果余额</b>，左侧符号对应阶段："
        f" {_stage_legend_html(include_expired_note=True)}\n\n"
    )

    header_cols = ["年份"] + account_order + ["合计"]
    parts.append('<div class="stage-table-wrapper">\n<table class="stage-table">\n<thead>\n<tr>')
    for h in header_cols:
        parts.append(f'<th>{h}</th>')
    parts.append('</tr>\n</thead>\n<tbody>\n')

    for yr in years:
        row = [f'<td><b>{yr}</b></td>']
        yr_sum = 0.0
        for aname in account_order:
            bal = bal_by_key.get((aname, yr), 0.0)
            yr_sum += bal
            fclr, shape, sclr = _cell_info(aname, yr)
            if shape:
                cell = f'<td style="color:{fclr}"><span style="color:{sclr}">{shape}</span> {_fmt(bal)}</td>'
            else:
                cell = f'<td style="color:{fclr}">{_fmt(bal)}</td>'
            row.append(cell)
        row.append(f'<td><b>{_fmt(yr_sum)}</b></td>')
        parts.append('<tr>' + ''.join(row) + '</tr>\n')

    parts.append('</tbody>\n</table>\n</div>\n')
    return "".join(parts)


# ── C6. 各层余额与资金来源 ───────────────────────────

def _render_section_c6(
    bucket_result: BucketProjectionResult | None,
    plan: AllocationPlan,
    chart_end_year: int,
) -> str:
    """每 bucket 一张区间图: stacked bar + fan band + 中线。"""
    import json

    parts = []

    if bucket_result is None or not bucket_result.snapshots:
        return "".join(parts)

    current_year = bucket_result.snapshots[0].year

    # 收集每个 bucket 的 withdrawal_year + target (从 plan)
    bucket_info_map: dict[str, tuple[int | None, float, bool]] = {}
    for b in (plan.emergency, plan.ci_reserve) if plan.ci_reserve else (plan.emergency,):
        bucket_info_map[b.name] = (b.withdrawal_year, b.amount if b.has_target else 0.0, b.has_target)
    for b in plan.node_buckets:
        bucket_info_map[b.name] = (b.withdrawal_year, b.amount if b.has_target else 0.0, b.has_target)
    if plan.surplus:
        bucket_info_map[plan.surplus.name] = (
            plan.surplus.withdrawal_year,
            plan.surplus.amount if plan.surplus.has_target else 0.0,
            plan.surplus.has_target,
        )

    # 每 bucket 1 张图: stacked bar + fan band + p50 总线
    parts.append("### C6. 各层余额与资金来源\n\n")
    parts.append(
        "下图把每个资金层单独展开来看。"
        "每年柱状部分展示这笔钱在居中结果下由“上年滚存 / 当年现金投入 / 当年收益”三部分组成；"
        "浅色阴影表示从偏保守到偏乐观的大致结果范围，深色线表示居中结果。"
        "若该资金层有明确目标，会同时显示目标线；节点资金在对应年份年末支取后清零。\n\n"
    )
    parts.append('<div class="bucket-chart-grid">\n')

    for bname in bucket_result.bucket_names:
        bsnaps = [s for s in bucket_result.snapshots if s.bucket_name == bname and s.year <= chart_end_year]
        if not bsnaps:
            continue
        bbreakdowns = [
            b for b in bucket_result.breakdowns
            if b.bucket_name == bname and b.year <= chart_end_year
        ]
        if not bbreakdowns:
            continue
        # 用 bbreakdowns 的年份作 keys, bsnaps 同样年份对齐
        years_set = {b.year for b in bbreakdowns}
        bsnaps = [s for s in bsnaps if s.year in years_set]
        bsnaps.sort(key=lambda x: x.year)
        bbreakdowns.sort(key=lambda x: x.year)
        wy, target_amt, has_target = bucket_info_map.get(bname, (None, 0.0, False))
        # 保障分析已降级为结构缺失分析，不再展示目标保额或加保测算。
        ci_existing_cov = 0
        if bname.startswith("重疾准备金"):
            ci_existing_cov = plan.insurance.ci_existing or 0
        ci_offset = ci_existing_cov
        # canvas id 用 slug 化(bucket 名含中文 -> base64 hash 简化)
        slug = "b_" + str(abs(hash(bname)) % (10**8))
        chart_data = {
            "labels": [b.year for b in bbreakdowns],
            # bar: 资金来源
            "starting": [b.starting_p50 for b in bbreakdowns],
            "cash": [b.cash_p50 for b in bbreakdowns],
            "returns": [b.returns_p50 for b in bbreakdowns],
            # fan: 若为重疾相关 bucket，仅叠加已有保额，不再引入目标保额口径。
            "p10": [b.ending_p10 + ci_offset for b in bbreakdowns],
            "p25": [b.ending_p25 + ci_offset for b in bbreakdowns],
            "p50": [b.ending_p50 + ci_offset for b in bbreakdowns],
            "p75": [b.ending_p75 + ci_offset for b in bbreakdowns],
            "p90": [b.ending_p90 + ci_offset for b in bbreakdowns],
            "withdrawal_amount": [b.withdrawal for b in bbreakdowns],
            "withdrawal_year": wy,
            "target_amount": target_amt if has_target else None,
            "ci_existing_cov": ci_existing_cov,
        }
        parts.append(
            f'<div class="bucket-chart-cell">\n'
            f'  <h4>{bname}</h4>\n'
            f'  <div class="chart-container" style="height:220px;">\n'
            f'    <canvas id="bucketFanChart_{slug}"></canvas>\n'
            f'  </div>\n'
            f'</div>\n'
            f'<script id="bucket-fan-data-{slug}" type="application/json">{json.dumps(chart_data, ensure_ascii=False)}</script>\n'
        )

    parts.append('</div>\n\n')
    return "".join(parts)


# ── C5. 各层余额堆叠图（综合图） ─────────────────────

def _render_section_c5(
    bucket_result: BucketProjectionResult | None,
    plan: AllocationPlan,
    chart_end_year: int,
) -> str:
    """一张综合 stacked bar + fan band 图: 各层居中结果堆叠 + 总和区间。"""
    import json

    parts = []

    if bucket_result is None or not bucket_result.snapshots:
        return "".join(parts)

    parts.append("### C5. 各层余额时序堆叠\n\n")
    parts.append(
        "下图把所有资金层放在一张图里看。"
        "每个色块代表一个资金层在各年年末的居中结果余额；当对应事件在该年年末发生后，这一层会被支取并归零。"
        "外侧灰色区间表示总资产余额从偏保守到偏乐观的大致波动范围。\n\n"
    )

    all_years = sorted({s.year for s in bucket_result.snapshots})

    all_years = [y for y in all_years if y <= chart_end_year]

    # bucket 顺序: 应急 → 节点(按时间) → CI → 富余
    bucket_order = ["应急储备"]
    if plan.ci_reserve:
        bucket_order.append(plan.ci_reserve.name)
    bucket_order.extend(b.name for b in plan.node_buckets)
    if plan.surplus:
        bucket_order.append(plan.surplus.name)

    snap_by_key: dict[tuple[str, int], BucketYearlyStats] = {}
    for s in bucket_result.snapshots:
        snap_by_key[(s.bucket_name, s.year)] = s

    series: dict[str, list[float]] = {name: [] for name in bucket_order}
    labels: list[str] = []
    total_stats_by_year = {s.year: s for s in bucket_result.total_stats}
    total_p10: list[float] = []
    total_p25: list[float] = []
    total_p50: list[float] = []
    total_p75: list[float] = []
    total_p90: list[float] = []

    for yr in all_years:
        labels.append(str(yr))
        for bname in bucket_order:
            s = snap_by_key.get((bname, yr))
            val = s.p50 if s else 0.0
            series[bname].append(val)
        total_stats = total_stats_by_year.get(yr)
        if total_stats:
            total_p10.append(total_stats.p10)
            total_p25.append(total_stats.p25)
            total_p50.append(total_stats.p50)
            total_p75.append(total_stats.p75)
            total_p90.append(total_stats.p90)
        else:
            total_p10.append(0.0)
            total_p25.append(0.0)
            total_p50.append(0.0)
            total_p75.append(0.0)
            total_p90.append(0.0)

    chart_data = {
        "labels": labels,
        "total_p10": total_p10,
        "total_p25": total_p25,
        "total_p50": total_p50,
        "total_p75": total_p75,
        "total_p90": total_p90,
        "series": series,
    }

    parts.append(
        f'<div class="chart-section">\n'
        f'  <div class="chart-container" style="height:320px;">\n'
        f'    <canvas id="combinedStackedChart"></canvas>\n'
        f'  </div>\n'
        f'</div>\n'
        f'<script id="combined-stacked-data" type="application/json">{json.dumps(chart_data, ensure_ascii=False)}</script>\n'
    )

    return "".join(parts)


# ── 主入口 ────────────────────────────────────

def render_playbook(
    *,
    profile: ClientProfile,
    plan: AllocationPlan,
    risk_preference: str = "balanced",
    projections: tuple[NodeProjection, ...] = (),
    terminal_steps: tuple[TerminalStep, ...] = (),
    yearly_snapshots: tuple[YearlySnapshot, ...] = (),
    return_snapshots: tuple[YearlyReturnSnapshot, ...] = (),
    bucket_result: BucketProjectionResult | None = None,
) -> str:
    """渲染完整剧本 Markdown。"""
    chart_end_year = _chart_end_year(profile)
    parts = [
        _render_metadata(profile),
        _render_section_a3(profile, plan, projections, yearly_snapshots, bucket_result),
        _render_section_a(profile),
        _render_section_b(profile, projections, yearly_snapshots, return_snapshots, bucket_result),
        _render_section_c(plan, profile.current_year, profile, yearly_snapshots),
        _render_section_c3(bucket_result, plan, chart_end_year),
        _render_stage_heatmap(bucket_result, plan, chart_end_year),
        _render_section_c5(bucket_result, plan, chart_end_year),
        _render_section_c6(bucket_result, plan, chart_end_year),
    ]
    return "".join(parts)
