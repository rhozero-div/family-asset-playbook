"""资产推演引擎。

统一按年度、年末结算:
- 现金流按年汇总
- 重大事件按事件年份年末扣减
- 带收益推演按年为步长
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from engine.handbook_reader import Assumptions
from engine.profile_loader import ClientProfile, Event


@dataclass(frozen=True)
class YearlySnapshot:
    """逐年现金流与资产余额快照。"""

    year: int
    age: int
    cash_inflow: float       # 年收入(税前)
    cash_outflow: float      # 年支出(生活+负债+保费+事件)
    net_cashflow: float      # 净现金流(+盈余 / -缺口)
    asset_balance: float     # 年末资产余额(累积)


@dataclass(frozen=True)
class TerminalStep:
    """终老推演的单个 5 年步长。"""

    age: int
    year: int
    starting_wealth: float     # 该步起点剩余资产
    monthly_income: float      # 该阶段月收入
    monthly_expense: float     # 该阶段月支出
    ending_wealth: float       # 该步终点剩余资产
    cumulative_deficit: float  # 累计缺口(有缺口时)




@dataclass(frozen=True)
class NodeProjection:
    """单个节点的推演结果。"""

    event_id: str
    description: str
    year: int
    years_from_now: int
    certainty: str
    # 推演数值
    accumulated_savings: float   # 到达该节点时的累积结余(初始金融资产 + 年度结余逐年累积)
    event_cost: float            # 该节点所需支出
    balance_after: float         # 支出后余额 = accumulated - event_cost
    gap_or_surplus: float        # 正=盈余, 负=缺口
    # 缺口补足所需年化收益率(仅缺口时有意义)
    required_return: float | None


def _required_annual_return(
    initial: float,
    annual_addition: float,
    target: float,
    years: int,
) -> float | None:
    """计算把 initial + 年末追加资金 累积到 target 所需的年化收益率。

    用二分法求解,精度 0.1%。
    如果不投资就够(target <= 0),返回 None。
    如果需要超过 30% 年化才能达到,返回 30%(标记为不可行)。
    """
    if target <= 0:
        return None
    if years <= 0:
        return 0.30  # 没时间了

    def fv(r: float) -> float:
        """给定年化收益率 r,计算终值。"""
        if abs(r) < 1e-9:
            return initial + annual_addition * years
        fv_lump = initial * (1 + r) ** years
        fv_annuity = annual_addition * (((1 + r) ** years - 1) / r)
        return fv_lump + fv_annuity

    # 如果 0% 收益就够
    if fv(0.0) >= target:
        return 0.0

    # 二分法: 在 0% ~ 30% 之间找
    lo, hi = 0.0, 0.30
    for _ in range(50):
        mid = (lo + hi) / 2
        if fv(mid) >= target:
            hi = mid
        else:
            lo = mid

    return round(hi, 4)




def _premium_total_annual(profile: ClientProfile, current_year: int, yr: int) -> float:
    """所有成员保险费年总额 (逐人, 缴费期满后停扣).

    如果成员无逐人数据, 回退到旧聚合保费函数.
    """
    # 判断是否有逐人保费数据
    has_per_person = any(
        m.term_life_premium > 0 or m.critical_illness_premium > 0 or m.medical_premium > 0
        or m.hci_premium > 0 or m.other_insurance_premium > 0 or m.hci_coverage > 0
        for m in profile.members
    ) or any(item.get("premium", 0) > 0 for item in profile.savings)
    if has_per_person:
        total = 0.0
        for m in profile.members:
            yrs_since = yr - current_year
            if m.term_life_pay_years <= 0 or yrs_since < m.term_life_pay_years:
                total += m.term_life_premium
            if m.critical_illness_pay_years <= 0 or yrs_since < m.critical_illness_pay_years:
                total += m.critical_illness_premium
            if m.medical_pay_years <= 0 or yrs_since < m.medical_pay_years:
                total += m.medical_premium
            if m.hci_pay_years <= 0 or yrs_since < m.hci_pay_years:
                total += m.hci_premium
            if m.other_insurance_pay_years <= 0 or yrs_since < m.other_insurance_pay_years:
                total += m.other_insurance_premium
        for item in profile.savings:
            pay_years = int(item.get("pay_years", 0) or 0)
            premium = float(item.get("premium", 0) or 0)
            if pay_years <= 0 or yrs_since < pay_years:
                total += premium
        return total
    total = _ci_premium_annual(profile, current_year, yr) + _term_life_premium_annual(profile, current_year, yr)
    yrs_since = yr - current_year
    if profile.insurance_medical_pay_years <= 0 or yrs_since < profile.insurance_medical_pay_years:
        total += profile.insurance_medical_premium
    return total if total > 0 else profile.insurance_total_annual_premium


def _annual_cashflow_per_person(
    profile: ClientProfile, yr: int, current_year: int,
) -> tuple[float, float] | None:
    """逐人计算年度 (收入, 支出). 无逐人数据时返回 None."""
    annual_in = 0.0
    annual_out = 0.0
    has_data = False
    for m in profile.members:
        if (
            m.annual_income == 0
            and m.income_start_annual == 0
            and m.monthly_expense == 0
            and m.retirement_pension == 0
            and m.retirement_annuity == 0
        ):
            continue
        has_data = True
        age_in_year = m.age + (yr - current_year)
        if yr < m.retirement_year:
            if m.annual_income > 0:
                annual_in += m.annual_income
            elif (
                m.income_start_annual > 0
                and m.income_start_age > 0
                and age_in_year >= m.income_start_age
            ):
                annual_in += m.income_start_annual
            annual_out += m.monthly_expense * 12.0
        else:
            annual_in += (m.retirement_pension + m.retirement_annuity) * 12.0
            annual_out += m.monthly_expense * m.retirement_expense_coeff * 12.0
        # 医疗支出逐人 (退休后)
        if yr >= m.retirement_year and m.healthcare_starting_annual > 0:
            yr_since = yr - m.retirement_year
            annual_hc = m.healthcare_starting_annual * (1 + m.healthcare_growth_rate) ** yr_since
            if m.healthcare_annual_cap > 0:
                annual_hc = min(annual_hc, m.healthcare_annual_cap)
            annual_hc *= 1 - m.reimbursement_rate
            annual_out += annual_hc
        # 保费逐人 (已在 _premium_total_monthly 处理, 这里不计)
    if not has_data:
        return None
    annual_out += profile.household_extra_monthly_expense * 12.0
    # 负债家庭级
    if profile.monthly_liabilities > 0 and profile.remaining_liability_end_year > 0 and yr < profile.remaining_liability_end_year:
        annual_out += profile.monthly_liabilities * 12.0
    elif profile.monthly_liabilities > 0 and profile.remaining_liability_end_year <= 0:
        # 负债已还清 (end_year=0), 不计月供
        pass
    return annual_in, annual_out


def _ci_premium_annual(profile: ClientProfile, current_year: int, yr: int) -> float:
    if profile.insurance_critical_illness_pay_years <= 0:
        return profile.insurance_critical_illness_premium
    yr_since = yr - current_year
    if yr_since >= profile.insurance_critical_illness_pay_years:
        return 0.0
    return profile.insurance_critical_illness_premium


def _term_life_premium_annual(profile: ClientProfile, current_year: int, yr: int) -> float:
    """定期寿险年保费: 缴费期内返回年保费, 期满后返回 0.0."""
    if profile.insurance_term_life_pay_years <= 0:
        return profile.insurance_term_life_premium
    yr_since = yr - current_year
    if yr_since >= profile.insurance_term_life_pay_years:
        return 0.0
    return profile.insurance_term_life_premium


def _year_span_inclusive(from_year: int, to_year: int) -> range:
    """返回 [from_year, to_year] 的闭区间年度序列。"""
    if to_year < from_year:
        return range(0)
    return range(from_year, to_year + 1)


def _annual_net_for_year(profile: ClientProfile, yr: int, current_year: int) -> float:
    """计算某一年的家庭净现金流(不含重大事件支出)."""
    cf = _annual_cashflow_per_person(profile, yr, current_year)
    if cf is not None:
        annual_income, annual_expense_no_premium = cf
        annual_premium = _premium_total_annual(profile, current_year, yr)
        return annual_income - annual_expense_no_premium - annual_premium

    annual_income = profile.total_annual_income
    annual_premium = profile.insurance_total_annual_premium
    annual_expense = profile.monthly_living_expense * 12.0 + annual_premium
    if profile.remaining_liability_end_year <= 0 or yr < profile.remaining_liability_end_year:
        annual_expense += profile.monthly_liabilities * 12.0

    retire_yr = _retirement_year(profile)
    if yr >= retire_yr:
        annual_income = (profile.retirement_monthly_pension + profile.retirement_monthly_annuity) * 12.0
        if annual_income <= 0:
            annual_income = profile.total_annual_income * 0.6
        annual_expense = (profile.retirement_monthly_expense or profile.monthly_living_expense) * 12.0
        annual_expense += annual_premium
        if profile.remaining_liability_end_year <= 0 or yr < profile.remaining_liability_end_year:
            annual_expense += profile.monthly_liabilities * 12.0
        if profile.healthcare_starting_annual > 0:
            yr_since = yr - retire_yr
            annual_hc = profile.healthcare_starting_annual * (1 + profile.healthcare_growth_rate) ** yr_since
            if profile.healthcare_annual_cap > 0:
                annual_hc = min(annual_hc, profile.healthcare_annual_cap)
            annual_hc *= 1 - profile.healthcare_reimbursement_rate
            annual_expense += annual_hc
        annual_expense -= _ci_premium_annual(profile, current_year, yr)
        annual_expense -= _term_life_premium_annual(profile, current_year, yr)
    return annual_income - annual_expense


def project_to_nodes(profile: ClientProfile) -> tuple[NodeProjection, ...]:
    """对每个未来事件节点做资产推演。

    假设:
    - 初始可投资金融资产 = total_financial_assets
    - 家庭净现金流按年汇总,并在年末一次性计入
    - 重大事件在对应年份年末扣减
    """
    current_year = profile.current_year
    running_assets = profile.total_financial_assets
    last_event_year = current_year - 1

    results = []
    for evt in profile.events:
        if evt.timing_year < profile.current_year:
            continue

        years_from_now = evt.timing_year - profile.current_year

        # 累积: 上一事件之后到本事件当年的年度净现金流
        accumulated = running_assets
        accumulation_years = list(_year_span_inclusive(last_event_year + 1, evt.timing_year))
        for yr in accumulation_years:
            accumulated += _annual_net_for_year(profile, yr, current_year)

        event_cost = float(evt.estimated_amount or 0)
        balance_after = accumulated - event_cost
        gap_or_surplus = balance_after

        # 计算补足缺口所需收益率
        req_ret = None
        if gap_or_surplus < 0 and years_from_now > 0:
            years_total = len(accumulation_years)
            annual_addition = 0.0
            if years_total > 0:
                annual_addition = sum(
                    max(_annual_net_for_year(profile, yr, current_year), 0.0)
                    for yr in accumulation_years
                ) / years_total
            req_ret = _required_annual_return(
                initial=running_assets,
                annual_addition=annual_addition,
                target=event_cost,
                years=years_total,
            )

        results.append(NodeProjection(
            event_id=evt.id,
            description=evt.description,
            year=evt.year if hasattr(evt, 'year') else evt.timing_year,
            years_from_now=years_from_now,
            certainty=evt.certainty,
            accumulated_savings=accumulated,
            event_cost=event_cost,
            balance_after=balance_after,
            gap_or_surplus=gap_or_surplus,
            required_return=req_ret,
        ))

        # 更新 running state
        running_assets = balance_after
        last_event_year = evt.timing_year

    return tuple(results)


def project_to_terminal(
    profile: ClientProfile,
    starting_wealth: float,
    start_year: int,
) -> tuple[TerminalStep, ...]:
    """终老推演: 从 start_year 到主要收入者 100 岁, 5 年一步。

    start_year 之前的所有事件已处理,starting_wealth 是当时剩余资产。
    逐人退休后收支 + 医疗支出。
    """
    birth = profile.primary_breadwinner_birth_year
    end_year = birth + 100
    current_year = profile.current_year

    cf = _annual_cashflow_per_person(profile, start_year, current_year)
    if cf is not None:
        # 逐人: 所有成员已退休, 计算退休后收支
        ret_income, ret_total_out_no_premium = cf
        annual_premium = _premium_total_annual(profile, current_year, start_year)
        ret_total_out = ret_total_out_no_premium + annual_premium
    else:
        ret_income = (profile.retirement_monthly_pension + profile.retirement_monthly_annuity) * 12.0
        if ret_income <= 0:
            ret_income = profile.total_annual_income * 0.6
        ret_expense = profile.retirement_monthly_expense * 12.0
        if ret_expense <= 0:
            ret_expense = profile.monthly_living_expense * 12.0
        annual_premium = profile.insurance_total_annual_premium
        still_has_liabilities = (
            profile.remaining_liability_end_year <= 0
            or start_year < profile.remaining_liability_end_year
        )
        post_ret_liabilities = profile.monthly_liabilities * 12.0 if still_has_liabilities else 0.0
        ret_total_out = ret_expense + post_ret_liabilities + annual_premium

    steps: list[TerminalStep] = []
    wealth = starting_wealth
    yr = start_year
    using_per_person = cf is not None

    # 5 年步长, 80→85→90→95→100(最后一个步长可能不足 5 年)
    while yr < end_year:
        next_yr = min(yr + 5, end_year)
        years = next_yr - yr

        if using_per_person:
            cf_yr = _annual_cashflow_per_person(profile, yr, current_year)
            if cf_yr is not None:
                ret_inc, ret_out_no_prem = cf_yr
                prem = _premium_total_annual(profile, current_year, yr)
                total_out = ret_out_no_prem + prem
                annual_income_ = ret_inc
            else:
                annual_income_ = ret_income
                total_out = ret_total_out
        else:
            hc_annual = 0.0
            if profile.healthcare_starting_annual > 0:
                yr_since = yr - start_year
                annual_hc = profile.healthcare_starting_annual * (1 + profile.healthcare_growth_rate) ** yr_since
                if profile.healthcare_annual_cap > 0:
                    annual_hc = min(annual_hc, profile.healthcare_annual_cap)
                annual_hc *= 1 - profile.healthcare_reimbursement_rate
                hc_annual = annual_hc
            effective_total_out = ret_total_out - _ci_premium_annual(profile, profile.current_year, yr)
            total_out = effective_total_out + hc_annual
            annual_income_ = ret_income

        net_annual = annual_income_ - total_out
        delta = net_annual * years
        ending = wealth + delta
        steps.append(TerminalStep(
            age=yr - birth,
            year=yr,
            starting_wealth=wealth,
            monthly_income=annual_income_ / 12.0,
            monthly_expense=total_out / 12.0,
            ending_wealth=ending,
            cumulative_deficit=abs(ending) if ending < 0 else 0.0,
        ))
        wealth = ending
        yr = next_yr

    return tuple(steps)


# ── 带投资收益的推演 ─────────────────────────

# 距今年数 → (固收%, 权益%, 保险%, 另类%) 的锚点
# 三档风险偏好对应的阶段权重
_RISK_STRATEGIES = {
    "conservative": [
        (0, 3,   (90.0, 5.0,  2.5, 2.5)),
        (3, 7,   (70.0, 20.0, 5.0, 5.0)),
        (7, 10,  (50.0, 35.0, 7.5, 7.5)),
        (10, 999,(35.0, 50.0, 7.5, 7.5)),
    ],
    "balanced": [
        (0, 3,   (87.5,  5.0,  2.5,  5.0)),
        (3, 7,   (60.0, 30.0,  7.5,  7.5)),
        (7, 10,  (40.0, 45.0, 10.0, 10.0)),
        (10, 999,(22.5, 57.5,  7.5, 12.5)),
    ],
    "aggressive": [
        (0, 3,   (85.0,  8.0,  2.0,  5.0)),
        (3, 7,   (50.0, 40.0,  5.0,  5.0)),
        (7, 10,  (30.0, 55.0,  7.5,  7.5)),
        (10, 999,(15.0, 70.0,  7.5,  7.5)),
    ],
}

_RETURN_STRATEGIES = _RISK_STRATEGIES["balanced"]


def _build_strategies(profile_override: dict | None, risk_preference: str = "balanced") -> list:
    """从风险偏好选择阶段权重表,允许 profile.assumptions.phases 覆盖。

    YAML 格式:
      phases:
        - max_years: 3
          weights: [0.875, 0.05, 0.025, 0.05]
    """
    base = _RISK_STRATEGIES.get(risk_preference, _RISK_STRATEGIES["balanced"])
    if not profile_override:
        return base
    phases = profile_override.get("phases") if isinstance(profile_override, dict) else None
    if not isinstance(phases, list) or len(phases) == 0:
        return base

    def _normalize_weights(values: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        # handbook 示例采用 0-1 小数口径；运行时统一折算为百分数。
        if max(values) <= 1.0:
            return tuple(v * 100.0 for v in values)
        return values

    result = []
    prev = 0
    for p in phases:
        if not isinstance(p, dict):
            return _RETURN_STRATEGIES
        mx = p.get("max_years")
        w = p.get("weights")
        if not isinstance(mx, (int, float)):
            return _RETURN_STRATEGIES
        if isinstance(w, dict):
            try:
                ww = _normalize_weights((
                    float(w["fixed_income"]),
                    float(w["equity"]),
                    float(w["insurance"]),
                    float(w["alternatives"]),
                ))
            except (KeyError, TypeError, ValueError):
                return _RETURN_STRATEGIES
        elif isinstance(w, (list, tuple)) and len(w) == 4:
            ww = _normalize_weights(tuple(float(v) for v in w))
        else:
            return _RETURN_STRATEGIES
        result.append((prev, int(mx), ww))
        prev = int(mx)
    return result


def _return_strategy_for(years: int, strategies: list | None = None) -> tuple[float, float, float, float]:
    if strategies is None:
        strategies = _RETURN_STRATEGIES
    if years <= 0:
        return strategies[0][2]
    for lo, hi, w in strategies:
        if lo < years <= hi:
            return w
    return strategies[-1][2]


def _bucket_weights(bucket_name: str, years_to_withdrawal: int | None,
                    strategies: list | None = None) -> tuple[float, float, float, float]:
    """根据 bucket 名称和距今剩余年限, 返回 (固收, 权益, 保险, 另类) 权重 (合计 100).

    - 应急储备: 100% 固收
    - 富余资金: 进取 (17.5/62.5/5/15)
    - 重疾准备金 (含 CI 分期): 90% 固收
    - 节点 bucket: 距 withdrawal_year 年数映射到 _RETURN_STRATEGIES
    """
    if bucket_name == "应急储备":
        return (100.0, 0.0, 0.0, 0.0)
    if bucket_name == "富余资金":
        # 以退休时点调权: 退休前进取,退休后保守
        if years_to_withdrawal is None:
            return (17.5, 62.5, 5.0, 15.0)
        return _return_strategy_for(max(0, years_to_withdrawal), strategies)
    if bucket_name == "重疾准备金" or bucket_name.startswith("重疾准备金"):
        return (90.0, 2.5, 2.5, 5.0)
    # 节点 bucket: 距 withdrawal 年数 → 策略
    if years_to_withdrawal is None:
        return _return_strategy_for(20, strategies)
    return _return_strategy_for(max(0, years_to_withdrawal), strategies)


def _compute_bucket_rv(weights: tuple[float, float, float, float],
                       fi_r: float, fi_v: float,
                       eq_r: float, eq_v: float,
                       ins_r: float, ins_v: float,
                       alt_r: float, alt_v: float,
                       rho_fi_eq: float, rho_fi_ins: float, rho_fi_alt: float,
                       rho_eq_ins: float, rho_eq_alt: float, rho_ins_alt: float
                       ) -> tuple[float, float]:
    """给定 bucket 权重和大类参数, 计算该 bucket 的 (年化收益, 波动率)."""
    w_fi, w_eq, w_ins, w_alt = (w / 100.0 for w in weights)
    r = (w_fi * fi_r + w_eq * eq_r + w_ins * ins_r + w_alt * alt_r)
    v = math.sqrt(
        w_fi**2 * fi_v**2 + w_eq**2 * eq_v**2
        + w_ins**2 * ins_v**2 + w_alt**2 * alt_v**2
        + 2 * w_fi * w_eq * fi_v * eq_v * rho_fi_eq
        + 2 * w_fi * w_ins * fi_v * ins_v * rho_fi_ins
        + 2 * w_fi * w_alt * fi_v * alt_v * rho_fi_alt
        + 2 * w_eq * w_ins * eq_v * ins_v * rho_eq_ins
        + 2 * w_eq * w_alt * eq_v * alt_v * rho_eq_alt
        + 2 * w_ins * w_alt * ins_v * alt_v * rho_ins_alt
    )
    return r, v


@dataclass(frozen=True)
class YearlyReturnSnapshot:
    """逐年情景推演(含投资收益)。"""

    year: int
    age: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


@dataclass(frozen=True)
class PortfolioYearlyStats:
    """组合总资产逐年分位数。"""

    year: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


def _merge_assumptions(
    handbook: Assumptions,
    profile_override: dict | None,
) -> Assumptions:
    """将 YAML 档案中的 assumptions 覆盖合并到 handbook 默认值。"""
    if not profile_override:
        return handbook

    ac = profile_override.get("asset_classes", {}) if isinstance(profile_override, dict) else {}
    corr = profile_override.get("correlations", {}) if isinstance(profile_override, dict) else {}

    def _override_float(base: float, overrides: dict, key: str) -> float:
        val = overrides.get(key)
        if isinstance(val, (int, float)):
            return float(val)
        return base

    fi = ac.get("fixed_income", {})
    eq = ac.get("equity", {})
    ins = ac.get("insurance", {})
    alt = ac.get("alternatives", {})

    return Assumptions(
        fixed_income_return=_override_float(handbook.fixed_income_return, fi, "return_pct"),
        fixed_income_volatility=_override_float(handbook.fixed_income_volatility, fi, "volatility_pct"),
        equity_return=_override_float(handbook.equity_return, eq, "return_pct"),
        equity_volatility=_override_float(handbook.equity_volatility, eq, "volatility_pct"),
        insurance_return=_override_float(handbook.insurance_return, ins, "return_pct"),
        insurance_volatility=_override_float(handbook.insurance_volatility, ins, "volatility_pct"),
        alternatives_return=_override_float(handbook.alternatives_return, alt, "return_pct"),
        alternatives_volatility=_override_float(handbook.alternatives_volatility, alt, "volatility_pct"),
        correlation_fi_eq=_override_float(handbook.correlation_fi_eq, corr, "fi_eq"),
        correlation_fi_ins=_override_float(handbook.correlation_fi_ins, corr, "fi_ins"),
        correlation_fi_alt=_override_float(handbook.correlation_fi_alt, corr, "fi_alt"),
        correlation_eq_ins=_override_float(handbook.correlation_eq_ins, corr, "eq_ins"),
        correlation_eq_alt=_override_float(handbook.correlation_eq_alt, corr, "eq_alt"),
        correlation_ins_alt=_override_float(handbook.correlation_ins_alt, corr, "ins_alt"),
    )


def _net_annual_from_profile(profile: ClientProfile, yr: int, current_year: int) -> float:
    """计算给定年份的年净现金流(不含重大事件支出)."""
    return _annual_net_for_year(profile, yr, current_year)


def _projection_end_year(profile: ClientProfile) -> int:
    """统一返回逐年测算截止年份。"""
    last_event_year = max(
        (evt.timing_year for evt in profile.events if evt.timing_year >= profile.current_year),
        default=profile.current_year,
    )
    return max(profile.measurement_end_year, profile.current_year, last_event_year)


def project_yearly_with_returns(
    profile: ClientProfile,
    assumptions: Assumptions,
    n_sobol_points: int = 5000,
    seed: int = 42,
) -> tuple[YearlyReturnSnapshot, ...]:
    """逐年推演含投资收益的情景 —— Sobol MC + BB + AV。"""
    import numpy as np
    from qmc import generate_sobol_paths, percentiles_from_paths

    assumptions = _merge_assumptions(assumptions, profile.assumptions)
    strategies = _build_strategies(profile.assumptions, profile.risk_preference)
    retire_horizon = 2
    if profile.assumptions and isinstance(profile.assumptions, dict):
        proj = profile.assumptions.get("projection", {})
        if isinstance(proj, dict):
            retire_horizon = int(proj.get("post_retirement_horizon_years", retire_horizon))

    current_year = profile.current_year
    end_year = _projection_end_year(profile)
    birth = profile.primary_breadwinner_birth_year
    n_years = end_year - current_year + 1

    events_by_year: dict[int, float] = {}
    for evt in profile.events:
        if evt.timing_year >= current_year:
            events_by_year[evt.timing_year] = events_by_year.get(evt.timing_year, 0.0) + float(evt.estimated_amount or 0)

    sorted_events = sorted(
        [e for e in profile.events if e.timing_year >= current_year],
        key=lambda e: e.timing_year,
    )

    fi_r = assumptions.fixed_income_return
    fi_v = assumptions.fixed_income_volatility
    eq_r = assumptions.equity_return
    eq_v = assumptions.equity_volatility
    ins_r = assumptions.insurance_return
    ins_v = assumptions.insurance_volatility
    alt_r = assumptions.alternatives_return
    alt_v = assumptions.alternatives_volatility

    rho_fi_eq = assumptions.correlation_fi_eq
    rho_fi_ins = assumptions.correlation_fi_ins
    rho_fi_alt = assumptions.correlation_fi_alt
    rho_eq_ins = assumptions.correlation_eq_ins
    rho_eq_alt = assumptions.correlation_eq_alt
    rho_ins_alt = assumptions.correlation_ins_alt

    # 逐年预计算确定性数据(收益/波动/现金流)
    yearly_data = []
    retire_yr = _retirement_year(profile)
    for yr in range(current_year, end_year + 1):
        annual_net = _net_annual_from_profile(profile, yr, current_year)
        if yr >= retire_yr:
            years_to_next = retire_horizon
        else:
            next_evt_year = None
            for evt in sorted_events:
                if evt.timing_year > yr:
                    next_evt_year = evt.timing_year
                    break
            years_to_next = (next_evt_year - yr) if next_evt_year else 20

        weights = _return_strategy_for(years_to_next, strategies)
        r, v = _compute_bucket_rv(
            weights, fi_r, fi_v, eq_r, eq_v, ins_r, ins_v, alt_r, alt_v,
            rho_fi_eq, rho_fi_ins, rho_fi_alt, rho_eq_ins, rho_eq_alt, rho_ins_alt,
        )
        event_total = events_by_year.get(yr, 0.0)
        yearly_data.append((r, v, annual_net, event_total))

    # 生成 Sobol 创新
    mc = generate_sobol_paths(
        n_steps=n_years,
        n_sobol_points=n_sobol_points,
        seed=seed,
        use_brownian_bridge=True,
        use_antithetic=True,
    )

    # 向量化逐年推演: 先应用年度收益,再在年末计入净现金流并扣减事件
    balances = np.full(mc.n_paths, profile.total_financial_assets, dtype=np.float64)
    year_end_paths = np.zeros((mc.n_paths, n_years), dtype=np.float64)

    for yr_idx, (r, v, annual_net, event_total) in enumerate(yearly_data):
        z = mc.z[:, yr_idx]
        balances = balances * (1.0 + r + v * z) + annual_net - event_total
        year_end_paths[:, yr_idx] = balances

    pcts = percentiles_from_paths(year_end_paths, [10, 25, 50, 75, 90])

    snapshots = []
    for yr_idx, yr in enumerate(range(current_year, end_year + 1)):
        snapshots.append(YearlyReturnSnapshot(
            year=yr,
            age=yr - birth,
            p10=round(pcts[10][yr_idx]),
            p25=round(pcts[25][yr_idx]),
            p50=round(pcts[50][yr_idx]),
            p75=round(pcts[75][yr_idx]),
            p90=round(pcts[90][yr_idx]),
        ))
    return tuple(snapshots)


def _retirement_year(profile: ClientProfile) -> int:
    """从事件或最早退休成员推算家庭策略切换年份。"""
    for evt in profile.events:
        if evt.type == "retirement" and evt.timing_year >= profile.current_year:
            return evt.timing_year
    retire_yrs = [m.retirement_year for m in profile.members
                  if (m.annual_income > 0 or m.income_start_annual > 0) and m.retirement_year > profile.current_year]
    if retire_yrs:
        return min(retire_yrs)
    return profile.primary_breadwinner_birth_year + profile.primary_breadwinner_retirement_age


def project_yearly(profile: ClientProfile) -> tuple[YearlySnapshot, ...]:
    """逐年推演现金流与资产余额,从当前年至主要收入者 100 岁。

    不含投资收益,仅按收支差额累积。
    """
    current_year = profile.current_year
    end_year = _projection_end_year(profile)
    birth = profile.primary_breadwinner_birth_year

    # 事件表: 按年份索引
    events_by_year: dict[int, list[float]] = {}
    for evt in profile.events:
        if evt.timing_year >= current_year:
            events_by_year.setdefault(evt.timing_year, []).append(
                float(evt.estimated_amount or 0)
            )

    snapshots: list[YearlySnapshot] = []
    balance = profile.total_financial_assets

    for yr in range(current_year, end_year + 1):
        age = yr - birth
        cf = _annual_cashflow_per_person(profile, yr, current_year)
        if cf is not None:
            annual_inflow, annual_outflow_no_premium = cf
            annual_premium = _premium_total_annual(profile, current_year, yr)
            annual_outflow = annual_outflow_no_premium + annual_premium
        else:
            annual_net = _net_annual_from_profile(profile, yr, current_year)
            annual_premium = _premium_total_annual(profile, current_year, yr)
            if yr >= _retirement_year(profile):
                annual_inflow = (profile.retirement_monthly_pension + profile.retirement_monthly_annuity) * 12.0
                if annual_inflow <= 0:
                    annual_inflow = profile.total_annual_income * 0.6
            else:
                annual_inflow = profile.total_annual_income
            annual_outflow = annual_inflow - annual_net
            if annual_outflow < annual_premium:
                annual_outflow = annual_premium

        # 事件支出
        event_total = sum(events_by_year.get(yr, []))

        total_outflow = annual_outflow + event_total
        net = annual_inflow - total_outflow
        balance += net

        snapshots.append(YearlySnapshot(
            year=yr,
            age=age,
            cash_inflow=annual_inflow,
            cash_outflow=total_outflow,
            net_cashflow=net,
            asset_balance=balance,
        ))

    return tuple(snapshots)


# ── Bucket 级 MC 推演 ──────────────────────────────


@dataclass(frozen=True)
class BucketYearlyStats:
    """单个 bucket 在某年的统计快照。

    由 `project_buckets_with_returns()` 在每条 MC 路径上追踪该 bucket 的月度余额,
    年末汇总 p10/p25/p50/p75/p90 五档分位 + 满额概率 (P(balance >= target_amount))。
    """
    bucket_name: str
    year: int
    age: int
    target_amount: float       # 满额目标(0 表示无目标,例如富余资金)
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    full_probability: float    # P(balance >= target_amount) over paths


@dataclass(frozen=True)
class BucketProjectionResult:
    """所有 bucket 的逐年统计结果。"""
    snapshots: tuple[BucketYearlyStats, ...]  # 按 (bucket_name, year) 排序
    bucket_names: tuple[str, ...]
    breakdowns: tuple[BucketYearlyBreakdown, ...] = ()  # v0.6 新增: 资金来源拆分
    total_stats: tuple[PortfolioYearlyStats, ...] = ()
    annualized_returns: tuple[BucketAnnualizedReturnStats, ...] = ()

    def for_bucket(self, name: str) -> tuple[BucketYearlyStats, ...]:
        """按 bucket 名筛选对应年份序列。"""
        return tuple(s for s in self.snapshots if s.bucket_name == name)

    def for_bucket_breakdown(self, name: str) -> tuple[BucketYearlyBreakdown, ...]:
        """按 bucket 名筛选 breakdown 序列。"""
        return tuple(b for b in self.breakdowns if b.bucket_name == name)

    def annualized_return_for_bucket(self, name: str) -> BucketAnnualizedReturnStats | None:
        for item in self.annualized_returns:
            if item.bucket_name == name:
                return item
        return None


@dataclass(frozen=True)
class BucketYearlyBreakdown:
    """单个 bucket 在某年的资金来源拆分 (v0.6 新增)。

    - P50 路径视角: starting + cash + returns - withdrawal = ending (路径级一致)
    - 总余额的 p10-p90 扇带 (来自所有 path 的统计)

    P50 路径: 该年份 ending_balance 处于所有路径中位数的 path.
    这种"以 ending 中位数锁定 path"的方式能保证路径级 sum 等式严格成立.
    """
    bucket_name: str
    year: int
    age: int
    target_amount: float       # 满额目标
    # P50 路径的拆分 (路径级一致)
    starting_p50: float        # 年初余额 (滚存)
    cash_p50: float            # 当年 cash 流入 (monthly_surplus + 应急超额)
    returns_p50: float         # 当年收益 (可负)
    ending_p50: float          # 年末余额 = starting + cash + returns - withdrawal
    withdrawal: float          # 当年提取 (节点 bucket 在 withdrawal_year; 其余 0)
    # 总余额的扇带 (总线)
    ending_p10: float
    ending_p25: float
    ending_p75: float
    ending_p90: float
    full_probability: float    # P(ending >= target) over paths


@dataclass(frozen=True)
class BucketAnnualizedReturnStats:
    """单个 bucket 从当前年到测算截止年的复合年化收益分位数。"""
    bucket_name: str
    start_year: int
    end_year: int
    years: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


@dataclass(frozen=True)
class BucketBreakdownResult:
    """所有 bucket 的逐年资金来源拆分结果。"""
    breakdowns: tuple[BucketYearlyBreakdown, ...]
    bucket_names: tuple[str, ...]

    def for_bucket(self, name: str) -> tuple[BucketYearlyBreakdown, ...]:
        return tuple(b for b in self.breakdowns if b.bucket_name == name)


def project_buckets_with_returns(
    profile: ClientProfile,
    assumptions: Assumptions,
    allocation,  # AllocationPlan (避免循环 import)
    n_sobol_points: int = 5000,
    seed: int = 42,
) -> BucketProjectionResult:
    """逐 bucket 追踪其在 MC 路径下的余额,返回逐年 p10-p90 分位 + 满额概率。

    每个 bucket 独立跟踪余额数组 (n_paths,), 共享同一组 MC 随机数 (同一市场)。
    节点 bucket 在事件年 (withdrawal_year) 年初全额提取, 之后清零并停止累积。
    CI 分期 bucket 在 reserve_years 年后停止月供, 余额留作准备金。

    Cash conservation 与应急再平衡 (v0.5.1):
    - 每月 surplus 只发给"当前 active 节点 bucket" (按 withdrawal_year 时间序最优先);
    - 应急储备超目标值的多余部分按月再平衡到 active 节点 bucket;
    - 应急储备不足时从富余资金拉回 (top-up).

    简化: 所有 bucket 共享 portfolio 级别的月度收益 (r, v), 不分别按 time_label 计策略。
    """
    import numpy as np
    from qmc import generate_sobol_paths, percentiles_from_paths

    assumptions = _merge_assumptions(assumptions, profile.assumptions)
    strategies = _build_strategies(profile.assumptions, profile.risk_preference)
    retire_horizon = 2
    if profile.assumptions and isinstance(profile.assumptions, dict):
        proj = profile.assumptions.get("projection", {})
        if isinstance(proj, dict):
            retire_horizon = int(proj.get("post_retirement_horizon_years", retire_horizon))

    # 1. 收集所有 bucket (按 应急 → CI → 节点 → 富余 顺序)
    buckets: list = [allocation.emergency]
    if allocation.ci_reserve is not None:
        buckets.append(allocation.ci_reserve)
    buckets.extend(allocation.node_buckets)
    if allocation.surplus is not None:
        buckets.append(allocation.surplus)
    if not buckets:
        return BucketProjectionResult(snapshots=(), bucket_names=())

    # 2. 时间范围
    current_year = profile.current_year
    end_year = _projection_end_year(profile)
    birth = profile.primary_breadwinner_birth_year
    n_years = end_year - current_year + 1

    retire_yr = _retirement_year(profile)
    sorted_events = sorted(
        [e for e in profile.events if e.timing_year >= current_year],
        key=lambda e: e.timing_year,
    )

    fi_r = assumptions.fixed_income_return
    fi_v = assumptions.fixed_income_volatility
    eq_r = assumptions.equity_return
    eq_v = assumptions.equity_volatility
    ins_r = assumptions.insurance_return
    ins_v = assumptions.insurance_volatility
    alt_r = assumptions.alternatives_return
    alt_v = assumptions.alternatives_volatility
    rho_fi_eq = assumptions.correlation_fi_eq
    rho_fi_ins = assumptions.correlation_fi_ins
    rho_fi_alt = assumptions.correlation_fi_alt
    rho_eq_ins = assumptions.correlation_eq_ins
    rho_eq_alt = assumptions.correlation_eq_alt
    rho_ins_alt = assumptions.correlation_ins_alt

    # 收集每个 bucket 在每年 (r_b, v_b): 按距 withdrawal_year 年数动态选策略
    # buckets 已收集 (应急 → CI → 节点 → 富余)
    bucket_yearly_rv: list[list[tuple[float, float]]] = []
    # 预存每个 bucket 的 withdrawal_year (None 表示永不提取)
    bucket_wdl_years: list[int | None] = [b.withdrawal_year for b in buckets]

    yearly_data: list[tuple[float, float, float]] = []
    for yr in range(current_year, end_year + 1):
        annual_net = _net_annual_from_profile(profile, yr, current_year)
        yearly_data.append((0.0, 0.0, annual_net))

        # 每个 bucket 自己的 (r_b, v_b)
        bucket_rv_this_year: list[tuple[float, float]] = []
        for b_idx, b in enumerate(buckets):
            wdl = bucket_wdl_years[b_idx]
            years_to_wdl = (wdl - yr) if wdl is not None else None
            weights = _bucket_weights(b.name, years_to_wdl, strategies)
            r_b, v_b = _compute_bucket_rv(
                weights, fi_r, fi_v, eq_r, eq_v, ins_r, ins_v, alt_r, alt_v,
                rho_fi_eq, rho_fi_ins, rho_fi_alt, rho_eq_ins, rho_eq_alt, rho_ins_alt,
            )
            bucket_rv_this_year.append((r_b, v_b))
        bucket_yearly_rv.append(bucket_rv_this_year)

    # 4. 生成 MC 路径
    mc = generate_sobol_paths(
        n_steps=n_years,
        n_sobol_points=n_sobol_points,
        seed=seed,
        use_brownian_bridge=True,
        use_antithetic=True,
    )

    # 5. 初始化每 bucket 的余额数组 + 索引查找
    bucket_balances = [
        np.full(mc.n_paths, b.initial_balance, dtype=np.float64)
        for b in buckets
    ]
    bucket_growth_factors = {
        b.name: np.ones(mc.n_paths, dtype=np.float64)
        for b in buckets
    }
    year_end_paths = {
        b.name: np.zeros((mc.n_paths, n_years), dtype=np.float64)
        for b in buckets
    }
    # v0.6 breakdown 追踪: starting + cash (per path per year per bucket)
    year_starting_paths = {
        b.name: np.zeros((mc.n_paths, n_years), dtype=np.float64)
        for b in buckets
    }
    year_cash_paths = {
        b.name: np.zeros((mc.n_paths, n_years), dtype=np.float64)
        for b in buckets
    }
    year_withdrawal_paths = {
        b.name: np.zeros((mc.n_paths, n_years), dtype=np.float64)
        for b in buckets
    }

    # 名称 → 索引 (避免循环中遍历查找)
    name_to_idx: dict[str, int] = {b.name: i for i, b in enumerate(buckets)}
    emergency_idx: int | None = name_to_idx.get("应急储备")
    surplus_idx: int | None = name_to_idx.get("富余资金")

    # 应急储备目标 = allocation 中已确定的应急目标 (简化: 不随通胀/收益上调)
    emergency_target = float(allocation.emergency.amount) if emergency_idx is not None else 0.0

    # 节点 bucket 按 withdrawal_year 排序 (active 选取用)
    sorted_node_buckets = sorted(
        [b for b in allocation.node_buckets if b.withdrawal_year is not None],
        key=lambda b: b.withdrawal_year,
    )

    def _active_bucket_indices(year: int) -> list[int]:
        """返回给定年份仍参与资金滚动的 bucket 索引。"""
        active: list[int] = []
        for idx, bucket in enumerate(buckets):
            if bucket.event_id is not None and bucket.withdrawal_year is not None and year > bucket.withdrawal_year:
                continue
            active.append(idx)
        return active

    def _apply_negative_net_cashflow(year_idx: int, deficit: float, active_indices: list[int]) -> None:
        """把负现金流按当前余额比例扣减到各 bucket，总额与参考线保持一致。

        若当年总正余额不足以覆盖 deficit，则把剩余缺口压到富余资金；
        若无富余资金，则压到最后一个仍 active 的 bucket，以允许总资产为负。
        """
        if deficit <= 0 or not active_indices:
            return

        positive_indices = [
            idx for idx in active_indices
            if float(bucket_balances[idx].mean()) > 0 or (bucket_balances[idx] > 0).any()
        ]
        if positive_indices:
            positive_total = np.sum([np.maximum(bucket_balances[idx], 0.0) for idx in positive_indices], axis=0)
            covered = np.minimum(deficit, positive_total)
            positive_total_safe = np.where(positive_total > 0, positive_total, 1.0)
            for idx in positive_indices:
                share = covered * np.maximum(bucket_balances[idx], 0.0) / positive_total_safe
                bucket_balances[idx] = bucket_balances[idx] - share
                year_cash_paths[buckets[idx].name][:, year_idx] -= share
            residual = deficit - covered
        else:
            residual = np.full(mc.n_paths, deficit, dtype=np.float64)

        if residual.any():
            fallback_idx = (
                surplus_idx
                if surplus_idx is not None and surplus_idx in active_indices
                else active_indices[-1]
            )
            bucket_balances[fallback_idx] = bucket_balances[fallback_idx] - residual
            year_cash_paths[buckets[fallback_idx].name][:, year_idx] -= residual

    # 6. 逐年推演: 年初记录起点 -> 全年收益 -> 年末净现金流 -> 应急再平衡 -> 年末事件提取
    for yr_idx in range(n_years):
        _, _, annual_net = yearly_data[yr_idx]
        yr = current_year + yr_idx
        bucket_rv_this_year = bucket_yearly_rv[yr_idx]
        z = mc.z[:, yr_idx]
        active_indices = _active_bucket_indices(yr)

        for bi, b in enumerate(buckets):
            year_starting_paths[b.name][:, yr_idx] = bucket_balances[bi]

        for bi, b in enumerate(buckets):
            if b.event_id is not None and b.withdrawal_year is not None and yr > b.withdrawal_year:
                continue
            r_b, v_b = bucket_rv_this_year[bi]
            gross = np.maximum(1 + r_b + v_b * z, 1e-6)
            bucket_growth_factors[b.name] = bucket_growth_factors[b.name] * gross
            bucket_balances[bi] = bucket_balances[bi] * gross

        if annual_net < 0:
            _apply_negative_net_cashflow(yr_idx, float(-annual_net), active_indices)

        annual_contribution = max(annual_net, 0.0)
        emergency_excess = np.zeros(mc.n_paths, dtype=np.float64)
        if emergency_idx is not None and emergency_target > 0:
            excess = bucket_balances[emergency_idx] - emergency_target
            emergency_excess = np.maximum(excess, 0.0)
            bucket_balances[emergency_idx] = bucket_balances[emergency_idx] - emergency_excess
            year_cash_paths["应急储备"][:, yr_idx] -= emergency_excess

            shortfall = np.maximum(emergency_target - bucket_balances[emergency_idx], 0.0)
            if surplus_idx is not None and shortfall.any():
                pull = np.minimum(shortfall, np.maximum(bucket_balances[surplus_idx], 0.0))
                bucket_balances[surplus_idx] = bucket_balances[surplus_idx] - pull
                bucket_balances[emergency_idx] = bucket_balances[emergency_idx] + pull
                year_cash_paths["应急储备"][:, yr_idx] += pull
                year_cash_paths["富余资金"][:, yr_idx] -= pull

        total_inflow = annual_contribution + emergency_excess
        if total_inflow.any():
            remaining = total_inflow.copy()
            for nb in sorted_node_buckets:
                if nb.withdrawal_year is None or nb.withdrawal_year < yr:
                    continue
                ni = name_to_idx.get(nb.name)
                if ni is None or not (nb.has_target and nb.amount > 0):
                    continue
                remaining_years = nb.withdrawal_year - yr + 1
                if remaining_years <= 0:
                    continue
                gap = np.maximum(0.0, nb.amount - bucket_balances[ni])
                cap = gap / remaining_years
                alloc = np.minimum(cap, remaining)
                bucket_balances[ni] += alloc
                year_cash_paths[nb.name][:, yr_idx] += alloc
                remaining -= alloc
                if not remaining.any():
                    break
            if surplus_idx is not None and remaining.any():
                bucket_balances[surplus_idx] += remaining
                year_cash_paths["富余资金"][:, yr_idx] += remaining

        for bi, b in enumerate(buckets):
            if b.event_id is not None and b.withdrawal_year == yr:
                year_withdrawal_paths[b.name][:, yr_idx] = bucket_balances[bi]
                bucket_balances[bi] = 0.0

        # 年末记录
        for bi, b in enumerate(buckets):
            year_end_paths[b.name][:, yr_idx] = bucket_balances[bi]

    # 7. 计算每 bucket 的逐年分位 + 满额概率
    snapshots: list[BucketYearlyStats] = []
    for b in buckets:
        paths = year_end_paths[b.name]
        pcts = percentiles_from_paths(paths, [10, 25, 50, 75, 90])
        if b.has_target and b.amount > 0:
            full_probs = np.mean(paths >= b.amount, axis=0)
        else:
            # 无目标 bucket (富余资金): 余额 ≥ 0 的概率
            full_probs = np.mean(paths >= 0, axis=0)

        for yr_idx in range(n_years):
            yr = current_year + yr_idx
            target = b.amount if b.has_target else 0.0
            snapshots.append(BucketYearlyStats(
                bucket_name=b.name,
                year=yr,
                age=yr - birth,
                target_amount=target,
                p10=round(float(pcts[10][yr_idx])),
                p25=round(float(pcts[25][yr_idx])),
                p50=round(float(pcts[50][yr_idx])),
                p75=round(float(pcts[75][yr_idx])),
                p90=round(float(pcts[90][yr_idx])),
                full_probability=round(float(full_probs[yr_idx]), 4),
            ))

    # 8. v0.6 计算资金来源拆分 (P50 路径 + 总余额扇带)
    # 路径级一致性: starting + cash + returns - withdrawal = ending
    # 选取 P50 路径 = ending 中位数对应的 path
    breakdowns: list[BucketYearlyBreakdown] = []
    for b in buckets:
        end_paths = year_end_paths[b.name]
        start_paths = year_starting_paths[b.name]
        cash_paths = year_cash_paths[b.name]
        withdrawal_paths = year_withdrawal_paths[b.name]
        end_pcts = percentiles_from_paths(end_paths, [10, 25, 50, 75, 90])
        if b.has_target and b.amount > 0:
            full_probs = np.mean(end_paths >= b.amount, axis=0)
        else:
            full_probs = np.mean(end_paths >= 0, axis=0)

        for yr_idx in range(n_years):
            yr = current_year + yr_idx
            sorted_idx = np.argsort(end_paths[:, yr_idx])
            median_path_idx = sorted_idx[len(sorted_idx) // 2]
            starting = float(start_paths[median_path_idx, yr_idx])
            cash = float(cash_paths[median_path_idx, yr_idx])
            ending = float(end_paths[median_path_idx, yr_idx])
            withdrawal = float(withdrawal_paths[median_path_idx, yr_idx])
            returns = ending + withdrawal - starting - cash
            breakdowns.append(BucketYearlyBreakdown(
                bucket_name=b.name,
                year=yr,
                age=yr - birth,
                target_amount=b.amount if b.has_target else 0.0,
                starting_p50=round(starting, 2),
                cash_p50=round(cash, 2),
                returns_p50=round(returns, 2),
                ending_p50=round(ending, 2),
                withdrawal=round(withdrawal, 2),
                ending_p10=round(float(end_pcts[10][yr_idx]), 2),
                ending_p25=round(float(end_pcts[25][yr_idx]), 2),
                ending_p75=round(float(end_pcts[75][yr_idx]), 2),
                ending_p90=round(float(end_pcts[90][yr_idx]), 2),
                full_probability=round(float(full_probs[yr_idx]), 4),
            ))

    total_paths = np.zeros((mc.n_paths, n_years), dtype=np.float64)
    for b in buckets:
        total_paths += year_end_paths[b.name]
    total_pcts = percentiles_from_paths(total_paths, [10, 25, 50, 75, 90])
    total_stats = tuple(
        PortfolioYearlyStats(
            year=current_year + yr_idx,
            p10=round(float(total_pcts[10][yr_idx]), 2),
            p25=round(float(total_pcts[25][yr_idx]), 2),
            p50=round(float(total_pcts[50][yr_idx]), 2),
            p75=round(float(total_pcts[75][yr_idx]), 2),
            p90=round(float(total_pcts[90][yr_idx]), 2),
        )
        for yr_idx in range(n_years)
    )

    annualized_returns: list[BucketAnnualizedReturnStats] = []
    years_elapsed = max(end_year - current_year + 1, 1)
    for b in buckets:
        growth_paths = bucket_growth_factors[b.name]
        annualized_paths = np.power(growth_paths, 1.0 / years_elapsed) - 1.0
        annualized_returns.append(BucketAnnualizedReturnStats(
            bucket_name=b.name,
            start_year=current_year,
            end_year=end_year,
            years=years_elapsed,
            p10=round(float(np.percentile(annualized_paths, 10)), 4),
            p25=round(float(np.percentile(annualized_paths, 25)), 4),
            p50=round(float(np.percentile(annualized_paths, 50)), 4),
            p75=round(float(np.percentile(annualized_paths, 75)), 4),
            p90=round(float(np.percentile(annualized_paths, 90)), 4),
        ))

    return BucketProjectionResult(
        snapshots=tuple(snapshots),
        bucket_names=tuple(b.name for b in buckets),
        breakdowns=tuple(breakdowns),
        total_stats=total_stats,
        annualized_returns=tuple(annualized_returns),
    )
