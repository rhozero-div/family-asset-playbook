"""资金分块分配引擎。

把可投资资产按用途和时间切成多个层次,每层独立给投资策略。
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.handbook_reader import Assumptions
from engine.profile_loader import ClientProfile
from engine.projection import NodeProjection


@dataclass(frozen=True)
class BucketAllocation:
    """单个资金块的配置建议。"""

    name: str           # "应急储备" / "近期-购房" / "中期-教育" ...
    amount: float       # 该块资金量(元)
    event_id: str | None  # 关联事件
    years_from_now: int | None  # 距今年数,应急/富余为 None
    time_label: str     # "应急" / "近期(≤3年)" / "中期(3-7年)" / "远期(7-10年)" / "超远期(>10年)" / "富余"
    funding_source: str
    # 投资策略(单值)
    fi_weight: float
    eq_weight: float
    ins_weight: float
    alt_weight: float
    expected_return_pct: float
    rationale: str
    # bucket 追踪字段 (用于 MC 推演)
    initial_balance: float = 0.0          # 初始存量资金划拨(从 cash_for_nodes 一次性划拨部分)
    monthly_contribution: float = 0.0     # 月供(从 monthly_surplus 累积; 应急/富余/一次性CI = 0)
    withdrawal_year: int | None = None     # 提取年份(节点事件发生年,余额归 0); None 表示不提取
    has_target: bool = True               # 是否具有明确目标 (富余资金 = False)


@dataclass(frozen=True)
class InsuranceAnalysis:
    """保险保障分析。"""

    # 定期寿险
    term_life_existing: float
    term_life_recommended: float
    term_life_gap: float
    # 重疾险
    ci_existing: float
    ci_recommended: float
    ci_gap: float
    # 医疗险
    medical_covered: bool
    # 保费负担
    total_annual_premium: float
    monthly_premium: float
    monthly_income: float
    premium_burden_pct: float   # 保费占月收入比


@dataclass(frozen=True)
class AllocationPlan:
    """完整分配方案。"""

    monthly_income: float
    monthly_expense: float   # 含保费
    monthly_surplus: float
    total_investable: float
    emergency: BucketAllocation
    ci_reserve: BucketAllocation | None
    node_buckets: tuple[BucketAllocation, ...]
    surplus: BucketAllocation | None
    insurance: InsuranceAnalysis
    warnings: tuple[str, ...]


# ── 时间分层 → 策略映射 ──────────────────────

# (距今年数下限, 上限, 标签, 固收%, 权益%, 保险%, 另类%)
_TIME_STRATEGIES = [
    (0, 3,   "近期(≤3年)",
     87.5, 5.0, 2.5, 5.0,
     "距事件不足3年,不能承受波动,固收为主确保本金安全"),
    (3, 7,   "中期(3-7年)",
     57.0, 29.0, 7.0, 7.0,
     "3-7年窗口,可适度配置权益增厚收益,以固收为底"),
    (7, 10,  "远期(7-10年)",
     38.0, 43.0, 9.0, 10.0,
     "7年以上可承受更大波动,权益过半,追求增长"),
    (10, 999, "超远期(>10年)",
     22.0, 56.0, 7.0, 15.0,
     "十年以上视野,进取配置,权益为主"),
]


def _normalize_phase_weights(values: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """兼容 0-1 小数权重与 0-100 百分数权重，统一转换为百分数。"""
    if max(values) <= 1.0:
        return tuple(v * 100.0 for v in values)
    return values


def _phase_strategies(profile: ClientProfile) -> list[tuple[int, int, tuple[float, float, float, float]]]:
    """返回节点 bucket 使用的阶段权重。

    优先读取 `profile.assumptions.phases[].weights`，以与 handbook 的顾问可配置口径保持一致。
    缺失或格式异常时回退到当前默认模板。
    """
    assumptions = profile.assumptions if isinstance(profile.assumptions, dict) else None
    phases = assumptions.get("phases") if assumptions else None
    if not isinstance(phases, list) or not phases:
        return [(lo, hi, (fi, eq, ins, alt)) for lo, hi, _, fi, eq, ins, alt, _ in _TIME_STRATEGIES]

    result: list[tuple[int, int, tuple[float, float, float, float]]] = []
    prev = 0
    for phase in phases:
        if not isinstance(phase, dict):
            return [(lo, hi, (fi, eq, ins, alt)) for lo, hi, _, fi, eq, ins, alt, _ in _TIME_STRATEGIES]
        max_years = phase.get("max_years")
        weights = phase.get("weights")
        if not isinstance(max_years, (int, float)):
            return [(lo, hi, (fi, eq, ins, alt)) for lo, hi, _, fi, eq, ins, alt, _ in _TIME_STRATEGIES]
        if isinstance(weights, dict):
            try:
                parsed = _normalize_phase_weights((
                    float(weights["fixed_income"]),
                    float(weights["equity"]),
                    float(weights["insurance"]),
                    float(weights["alternatives"]),
                ))
            except (KeyError, TypeError, ValueError):
                return [(lo, hi, (fi, eq, ins, alt)) for lo, hi, _, fi, eq, ins, alt, _ in _TIME_STRATEGIES]
        elif isinstance(weights, (list, tuple)) and len(weights) == 4:
            try:
                parsed = _normalize_phase_weights(tuple(float(v) for v in weights))
            except (TypeError, ValueError):
                return [(lo, hi, (fi, eq, ins, alt)) for lo, hi, _, fi, eq, ins, alt, _ in _TIME_STRATEGIES]
        else:
            return [(lo, hi, (fi, eq, ins, alt)) for lo, hi, _, fi, eq, ins, alt, _ in _TIME_STRATEGIES]
        result.append((prev, int(max_years), parsed))
        prev = int(max_years)
    return result


def _strategy_for(years: int, profile: ClientProfile):
    phase_weights = _phase_strategies(profile)
    phase_map: dict[tuple[int, int], tuple[float, float, float, float]] = {
        (lo, hi): weights for lo, hi, weights in phase_weights
    }
    for lo, hi, label, fi, eq, ins, alt, rationale in _TIME_STRATEGIES:
        if years > lo and years <= hi:
            weights = phase_map.get((lo, hi), (fi, eq, ins, alt))
            return label, *weights, rationale
    last_weights = phase_weights[-1][2] if phase_weights else (22.0, 56.0, 7.0, 15.0)
    return "超远期(>10年)", *last_weights, "长期进取"


# ── 主分配逻辑 ────────────────────────────────

def allocate(
    profile: ClientProfile,
    projections: tuple[NodeProjection, ...],
    assumptions: Assumptions,
) -> AllocationPlan:
    monthly_income = profile.total_annual_income / 12.0
    monthly_premium = profile.insurance_total_annual_premium / 12.0
    monthly_expense = (profile.monthly_living_expense
                       + profile.monthly_liabilities
                       + monthly_premium)
    monthly_surplus = monthly_income - monthly_expense

    warnings: list[str] = []
    if monthly_surplus < 0:
        warnings.append("月度结余为负,现金流不可持续,请检查支出或收入")

    # 1. 应急储备
    emergency_months = profile.liquidity_reserve_months if profile.liquidity_reserve_months > 0 else 6.0
    emergency_amount = monthly_expense * emergency_months
    emergency = BucketAllocation(
        name="应急储备",
        amount=emergency_amount,
        event_id=None,
        years_from_now=None,
        time_label="应急",
        funding_source=f"当前资产(覆盖{emergency_months:g}个月支出)",
        fi_weight=100.0,
        eq_weight=0.0,
        ins_weight=0.0,
        alt_weight=0.0,
        expected_return_pct=assumptions.fixed_income_return,
        rationale="货币基金/短期固收,随时可取,不计收益,仅保流动性",
        initial_balance=emergency_amount,
        monthly_contribution=0.0,
        withdrawal_year=None,
    )

    total_investable = profile.total_financial_assets
    remaining_cash = total_investable - emergency_amount
    if remaining_cash < 0:
        warnings.append(
            f"可投资资产({total_investable:,.0f})不足以覆盖{emergency_months:g}个月应急储备"
            f"({emergency_amount:,.0f}),缺口 {abs(remaining_cash):,.0f} 元"
        )
        remaining_cash = 0.0

    # 2. 按时间顺序分配节点
    node_buckets: list[BucketAllocation] = []
    cash_for_nodes = remaining_cash
    accumulated_surplus = 0.0
    prev_balance_after = profile.total_financial_assets
    linked_savings_remaining = {
        idx: float(s.get("amount", 0))
        for idx, s in enumerate(profile.savings)
        if float(s.get("amount", 0)) > 0
    }

    for proj in projections:
        event_cost = proj.event_cost
        if event_cost <= 0:
            prev_balance_after = proj.balance_after
            continue

        # 累积: 直接沿用 projection 的逐年年末净现金流结果
        accumulated_surplus += proj.accumulated_savings - prev_balance_after

        label, fi, eq, ins, alt, rationale = _strategy_for(proj.years_from_now, profile)

        # 储蓄险指定到心理账户时,直接并入该账户初始余额
        savings_linked = 0.0
        for idx, s in enumerate(profile.savings):
            linked = str(s.get("linked_account", "")).strip()
            if idx not in linked_savings_remaining or linked_savings_remaining[idx] <= 0:
                continue
            if not linked:
                continue
            if linked in {proj.event_id, proj.description}:
                savings_linked += linked_savings_remaining[idx]
                linked_savings_remaining[idx] = 0.0

        effective_cost = max(0.0, event_cost - savings_linked)

        if effective_cost <= 0:
            from_cash = 0.0
            from_surplus = 0.0
            fund_src = f"储蓄险 ¥{savings_linked:,.0f}"
        elif effective_cost <= accumulated_surplus:
            from_cash = 0.0
            from_surplus = effective_cost
            accumulated_surplus -= from_surplus
            if savings_linked > 0:
                fund_src = f"储蓄险 ¥{savings_linked:,.0f} + " + _fund_desc(0, effective_cost)
            else:
                fund_src = _fund_desc(0, effective_cost)
        else:
            gap = effective_cost - accumulated_surplus
            from_cash = min(cash_for_nodes, gap)
            from_surplus = accumulated_surplus
            cash_for_nodes -= from_cash
            accumulated_surplus = 0.0
            if gap > from_cash:
                shortfall = gap - from_cash
                fund_src = (_fund_desc(from_cash, from_surplus)
                            + (f" + 储蓄险 ¥{savings_linked:,.0f}" if savings_linked > 0 else "")
                            + f", 缺口 ¥{shortfall:,.0f}")
                warnings.append(
                    f"{proj.description}({proj.year}年) 缺口 ¥{shortfall:,.0f},"
                    f"需调整目标或增加收入"
                )
            else:
                fund_src = _fund_desc(from_cash, from_surplus) + (f" + 储蓄险 ¥{savings_linked:,.0f}" if savings_linked > 0 else "")

        bucket = BucketAllocation(
            name=f"{label.split('(')[0]}-{proj.description}",
            amount=event_cost,
            event_id=proj.event_id,
            years_from_now=proj.years_from_now,
            time_label=label,
            funding_source=fund_src,
            fi_weight=fi,
            eq_weight=eq,
            ins_weight=ins,
            alt_weight=alt,
            expected_return_pct=(
                fi / 100 * assumptions.fixed_income_return
                + eq / 100 * assumptions.equity_return
                + ins / 100 * assumptions.insurance_return
                + alt / 100 * assumptions.alternatives_return
            ),
            rationale=rationale,
            initial_balance=from_cash + savings_linked,
            # monthly_contribution 由推演层按时间优先顺序统一分发 (cash conservation);
            # 这里固定为 0,避免"所有节点 bucket 同时拿月供"的虚高.
            monthly_contribution=0.0,
            withdrawal_year=proj.year,
        )
        node_buckets.append(bucket)
        prev_balance_after = proj.balance_after

    # 3. 重疾保障 (仅用于保险分析, 不再创建储备 bucket)
    ci_bucket = None

    # 4. 富余资金
    unassigned_savings = 0.0
    for idx, s in enumerate(profile.savings):
        if idx not in linked_savings_remaining:
            continue
        linked = str(s.get("linked_account", "")).strip()
        if linked not in {"", "富余资金"}:
            warnings.append(f"储蓄险 linked_account={linked} 未匹配到有效心理账户，已并入富余资金")
        unassigned_savings += linked_savings_remaining[idx]

    remaining_total = cash_for_nodes + accumulated_surplus + unassigned_savings
    # 查找退休年份,用于 surplus 的 withdrawal_year (动态调权)
    retire_year = None
    for evt in profile.events:
        if evt.type == "retirement":
            retire_year = evt.timing_year
            break
    if remaining_total > 0:
        surplus_bucket = BucketAllocation(
            name="富余资金",
            amount=remaining_total,
            event_id=None,
            years_from_now=(retire_year - profile.current_year) if retire_year else None,
            time_label="富余",
            funding_source="扣除应急和所有节点后的剩余",
            fi_weight=17.5,
            eq_weight=62.5,
            ins_weight=5.0,
            alt_weight=15.0,
            expected_return_pct=(
                17.5 / 100 * assumptions.fixed_income_return
                + 62.5 / 100 * assumptions.equity_return
                + 5.0 / 100 * assumptions.insurance_return
                + 15.0 / 100 * assumptions.alternatives_return
            ),
            rationale="无特定用途,可承担更高风险,权益为主,追求长期增长",
            initial_balance=cash_for_nodes + unassigned_savings,
            monthly_contribution=0.0,
            withdrawal_year=retire_year,  # 以退休时点调权,退休后转保守
            has_target=False,
        )
    else:
        surplus_bucket = None

    # 4. 保险分析
    ins = InsuranceAnalysis(
        term_life_existing=profile.insurance_term_life_cov,
        term_life_recommended=0.0,
        term_life_gap=0.0,
        ci_existing=profile.insurance_critical_illness_cov,
        ci_recommended=0.0,
        ci_gap=0.0,
        medical_covered=profile.insurance_medical_covered,
        total_annual_premium=profile.insurance_total_annual_premium,
        monthly_premium=monthly_premium,
        monthly_income=monthly_income,
        premium_burden_pct=(monthly_premium / monthly_income * 100
                            if monthly_income > 0 else 0.0),
    )

    return AllocationPlan(
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        monthly_surplus=monthly_surplus,
        total_investable=total_investable,
        emergency=emergency,
        ci_reserve=ci_bucket,
        node_buckets=tuple(node_buckets),
        surplus=surplus_bucket,
        insurance=ins,
        warnings=tuple(warnings),
    )


def _fund_desc(from_cash: float, from_surplus: float) -> str:
    parts = []
    if from_cash > 0:
        parts.append(f"存量 ¥{from_cash:,.0f}")
    if from_surplus > 0:
        parts.append(f"年结余累计 ¥{from_surplus:,.0f}")
    return " + ".join(parts) if parts else "—"
