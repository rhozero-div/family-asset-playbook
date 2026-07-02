"""保险规划原型逻辑。

目标:
- 读取现有问卷 YAML
- 基于收入/资产/现有保险/未来现金流压力,给出保险配置结构建议
- 提供两种方向:
  1. 优先配足核心保障
  2. 在预算内尽量都配一些,但保额更克制

说明:
- 当前版本使用 mock 保费曲线
- 仅做结构规划,不输出具体产品推荐
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from engine.profile_loader import ClientProfile, Member, load_profile
from engine.projection import _annual_net_for_year, project_to_nodes
from tools.validate_collected_profile import _validate


@dataclass(frozen=True)
class InsuranceNeed:
    member_name: str
    member_role: str
    product_key: str
    product_label: str
    priority_rank: int
    current_coverage: float
    target_coverage: float
    additional_gap: float
    current_status: str
    target_status: str
    full_additional_annual_premium: float
    supports_partial: bool
    rationale: str


@dataclass(frozen=True)
class ScenarioAllocation:
    member_name: str
    product_label: str
    priority_rank: int
    current_coverage: float
    target_coverage: float
    recommended_additional_coverage: float
    recommended_total_coverage: float
    premium_used: float
    fill_ratio: float
    rationale: str
    current_status: str
    target_status: str


@dataclass(frozen=True)
class ScenarioPlan:
    scenario_key: str
    scenario_label: str
    budget_annual: float
    budget_monthly: float
    premium_used_annual: float
    premium_used_monthly: float
    allocations: tuple[ScenarioAllocation, ...]
    summary: tuple[str, ...]


@dataclass(frozen=True)
class PlanningPreferences:
    manual_premium_cap_annual: float | None = None
    auto_budget_ratio: float | None = None
    term_multiplier_with_dependents: float = 7.0
    term_multiplier_without_dependents: float = 4.0
    ci_income_multiple: float = 3.0
    ci_expense_years: float = 5.0
    child_ci_target: float = 300000.0
    elder_ci_target: float = 300000.0
    include_hci_upgrade: bool = True
    adult_independence_buffer: float = 1.2


@dataclass(frozen=True)
class HouseholdMetrics:
    annual_income: float
    monthly_income: float
    annual_current_surplus: float
    monthly_current_surplus: float
    total_financial_assets: float
    total_outstanding_debt: float
    existing_annual_premium: float
    existing_monthly_premium: float
    premium_budget_annual: float
    premium_budget_monthly: float
    next_10y_major_events: float
    next_10y_negative_gap: float
    dependent_count: int
    key_earner_count: int
    retirement_medical_selfpay_first_year: float


@dataclass(frozen=True)
class MemberPlanView:
    member_name: str
    member_role: str
    medical_current: bool
    medical_target: bool
    medical_plan_a: bool
    medical_plan_b: bool
    current_term_coverage: float
    target_term_coverage: float
    plan_a_term_coverage: float
    plan_b_term_coverage: float
    current_ci_coverage: float
    target_ci_coverage: float
    plan_a_ci_coverage: float
    plan_b_ci_coverage: float
    current_hci_coverage: float
    target_hci_coverage: float
    plan_a_hci_coverage: float
    plan_b_hci_coverage: float
    current_term_premium: float
    current_ci_premium: float
    current_medical_premium: float
    current_hci_premium: float
    target_term_premium: float
    target_ci_premium: float
    target_medical_premium: float
    target_hci_premium: float
    plan_a_term_premium: float
    plan_a_ci_premium: float
    plan_a_medical_premium: float
    plan_a_hci_premium: float
    plan_b_term_premium: float
    plan_b_ci_premium: float
    plan_b_medical_premium: float
    plan_b_hci_premium: float
    current_annual_premium: float
    plan_a_annual_premium: float
    plan_b_annual_premium: float
    gap_explanation: tuple[str, ...]
    plan_a_explanation: tuple[str, ...]
    plan_b_explanation: tuple[str, ...]


@dataclass(frozen=True)
class InsurancePlanningResult:
    profile: ClientProfile
    preferences: PlanningPreferences
    metrics: HouseholdMetrics
    planning_principles: tuple[str, ...]
    assumptions: tuple[str, ...]
    needs: tuple[InsuranceNeed, ...]
    core_plan: ScenarioPlan
    balanced_plan: ScenarioPlan
    member_views: tuple[MemberPlanView, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AdviceRole:
    key: str
    label: str
    has_household_responsibility: bool
    term_priority_rank: int | None
    ci_priority_rank: int | None


def _preferences_from_profile_assumptions(profile: ClientProfile) -> PlanningPreferences:
    assumptions = profile.assumptions or {}
    raw = assumptions.get("insurance_planner", {}) if isinstance(assumptions, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    include_hci_raw = raw.get("include_hci_upgrade", True)
    if isinstance(include_hci_raw, str):
        include_hci_value = include_hci_raw.lower() != "false"
    else:
        include_hci_value = bool(include_hci_raw)
    auto_budget_ratio_pct = raw.get("auto_budget_ratio_pct")
    auto_budget_ratio = None if auto_budget_ratio_pct in (None, "") else float(auto_budget_ratio_pct) / 100.0
    return PlanningPreferences(
        manual_premium_cap_annual=(None if raw.get("manual_premium_cap_annual") in (None, "") else float(raw.get("manual_premium_cap_annual"))),
        auto_budget_ratio=auto_budget_ratio,
        term_multiplier_with_dependents=float(raw.get("term_multiplier_with_dependents", 7.0)),
        term_multiplier_without_dependents=float(raw.get("term_multiplier_without_dependents", 4.0)),
        ci_income_multiple=float(raw.get("ci_income_multiple", 3.0)),
        ci_expense_years=float(raw.get("ci_expense_years", 5.0)),
        child_ci_target=float(raw.get("child_ci_target", 300000.0)),
        elder_ci_target=float(raw.get("elder_ci_target", 300000.0)),
        include_hci_upgrade=include_hci_value,
        adult_independence_buffer=float(raw.get("adult_independence_buffer", 1.2)),
    )


def _age_band_rate(age: int, table: tuple[tuple[int, float], ...]) -> float:
    for max_age, rate in table:
        if age <= max_age:
            return rate
    return table[-1][1]


_TERM_RATE_PER_100K = (
    (30, 90.0),
    (40, 170.0),
    (50, 360.0),
    (60, 900.0),
    (120, 1600.0),
)

_CI_RATE_PER_100K = (
    (17, 650.0),
    (30, 1100.0),
    (40, 2200.0),
    (50, 4300.0),
    (60, 8200.0),
    (120, 12000.0),
)

_MEDICAL_BASE_PREMIUM = (
    (17, 800.0),
    (30, 450.0),
    (40, 700.0),
    (50, 1300.0),
    (60, 2600.0),
    (120, 5200.0),
)

_HCI_RATE_PER_100K = (
    (17, 260.0),
    (30, 220.0),
    (40, 320.0),
    (50, 520.0),
    (60, 900.0),
    (120, 1800.0),
)


def _is_dependent(member: Member) -> bool:
    return member.role in {"dependent", "dependent_elder"}


def _is_key_earner(member: Member) -> bool:
    return (
        member.role in {"primary_breadwinner", "secondary_breadwinner"}
        or member.annual_income > 0
        or member.income_start_annual > 0
    )


def _current_or_near_term_income(member: Member) -> float:
    if member.annual_income > 0:
        return member.annual_income
    if member.income_start_annual > 0 and member.age >= member.income_start_age > 0:
        return member.income_start_annual
    return 0.0


def _personal_expense_annual(member: Member) -> float:
    return member.monthly_expense * 12.0


def _meets_adult_independence_threshold(member: Member, preferences: PlanningPreferences) -> bool:
    if member.age < 18:
        return False
    income = _current_or_near_term_income(member)
    if income <= 0:
        return False
    expense_floor = _personal_expense_annual(member) * preferences.adult_independence_buffer
    return income >= expense_floor


def _household_has_responsibility_flags(profile: ClientProfile, preferences: PlanningPreferences) -> bool:
    for member in profile.members:
        if member.role == "dependent_elder":
            return True
        if member.role == "dependent" and (
            member.age < 18 or not _meets_adult_independence_threshold(member, preferences)
        ):
            return True
    return profile.total_outstanding_debt > 0


def _advice_role(profile: ClientProfile, member: Member, preferences: PlanningPreferences) -> AdviceRole:
    if member.role == "dependent_elder":
        return AdviceRole(
            key="elder_dependent",
            label="受赡养老人",
            has_household_responsibility=False,
            term_priority_rank=None,
            ci_priority_rank=4,
        )
    if member.role == "dependent" and member.age < 18:
        return AdviceRole(
            key="child_dependent",
            label="未成年受抚养人",
            has_household_responsibility=False,
            term_priority_rank=None,
            ci_priority_rank=3,
        )
    if member.role == "primary_breadwinner":
        return AdviceRole(
            key="key_earner_core",
            label="核心收入承担者",
            has_household_responsibility=True,
            term_priority_rank=2,
            ci_priority_rank=3,
        )
    if member.role == "secondary_breadwinner":
        if _household_has_responsibility_flags(profile, preferences):
            return AdviceRole(
                key="key_earner_supporting",
                label="次核心收入承担者",
                has_household_responsibility=True,
                term_priority_rank=2,
                ci_priority_rank=3,
            )
        return AdviceRole(
            key="independent_adult",
            label="独立成年人",
            has_household_responsibility=False,
            term_priority_rank=3,
            ci_priority_rank=2,
        )
    if member.role == "dependent":
        if _meets_adult_independence_threshold(member, preferences):
            return AdviceRole(
                key="independent_adult",
                label="基本经济独立成年人",
                has_household_responsibility=False,
                term_priority_rank=3,
                ci_priority_rank=2,
            )
        return AdviceRole(
            key="dependent_adult_transition",
            label="待独立成年成员",
            has_household_responsibility=False,
            term_priority_rank=None,
            ci_priority_rank=3,
        )
    if _household_has_responsibility_flags(profile, preferences) and _is_key_earner(member):
        return AdviceRole(
            key="key_earner_supporting",
            label="收入承担者",
            has_household_responsibility=True,
            term_priority_rank=2,
            ci_priority_rank=3,
        )
    return AdviceRole(
        key="independent_adult",
        label="独立成年人",
        has_household_responsibility=False,
        term_priority_rank=3,
        ci_priority_rank=2,
    )


def _household_responsibility_pool(profile: ClientProfile) -> float:
    annual_expense = (profile.monthly_living_expense + profile.monthly_liabilities) * 12.0
    future_commitments = sum(
        float(evt.estimated_amount or 0)
        for evt in profile.events
        if profile.current_year <= evt.timing_year <= profile.current_year + 10
    )
    return max(
        profile.total_outstanding_debt + annual_expense * 3.0 + future_commitments * 0.5,
        annual_expense * 5.0,
    )


def _term_life_target(
    member: Member,
    profile: ClientProfile,
    responsibility_pool: float,
    preferences: PlanningPreferences,
    advice_role: AdviceRole,
) -> float:
    if advice_role.term_priority_rank is None:
        return 0.0
    income_base = _current_or_near_term_income(member) or member.income_start_annual
    if income_base <= 0:
        income_base = profile.total_annual_income / max(sum(1 for m in profile.members if _is_key_earner(m)), 1)
    income_share = income_base / max(profile.total_annual_income, income_base, 1.0)
    dependent_multiplier = (
        preferences.term_multiplier_with_dependents
        if advice_role.has_household_responsibility
        else preferences.term_multiplier_without_dependents
    )
    baseline = income_base * dependent_multiplier
    if not advice_role.has_household_responsibility:
        return baseline
    pool_share = responsibility_pool * income_share
    return max(baseline, pool_share)


def _ci_target(member: Member, preferences: PlanningPreferences, advice_role: AdviceRole) -> float:
    if advice_role.key == "child_dependent":
        return preferences.child_ci_target
    if advice_role.key in {"key_earner_core", "key_earner_supporting", "independent_adult"}:
        income_base = _current_or_near_term_income(member) or member.income_start_annual
        if income_base > 0:
            return max(
                income_base * preferences.ci_income_multiple,
                member.monthly_expense * 12.0 * preferences.ci_expense_years,
                500000.0,
            )
    if advice_role.key == "elder_dependent":
        return max(member.monthly_expense * 12.0 * 3.0, preferences.elder_ci_target)
    return max(member.monthly_expense * 12.0 * preferences.ci_expense_years, preferences.child_ci_target)


def _should_consider_hci(
    profile: ClientProfile,
    member: Member,
    preferences: PlanningPreferences,
    advice_role: AdviceRole,
) -> bool:
    if not preferences.include_hci_upgrade:
        return False
    affluent = profile.total_annual_income >= 800000 or profile.total_financial_assets >= 3000000
    return affluent and member.age <= 60 and advice_role.key not in {"child_dependent", "elder_dependent", "dependent_adult_transition"}


def _mock_term_premium(age: int, coverage: float) -> float:
    return coverage / 100000.0 * _age_band_rate(age, _TERM_RATE_PER_100K)


def _mock_ci_premium(age: int, coverage: float) -> float:
    return coverage / 100000.0 * _age_band_rate(age, _CI_RATE_PER_100K)


def _mock_medical_premium(age: int) -> float:
    return _age_band_rate(age, _MEDICAL_BASE_PREMIUM)


def _mock_hci_premium(age: int, coverage: float) -> float:
    return coverage / 100000.0 * _age_band_rate(age, _HCI_RATE_PER_100K)


def _build_needs(
    profile: ClientProfile,
    metrics: HouseholdMetrics,
    preferences: PlanningPreferences,
) -> tuple[InsuranceNeed, ...]:
    needs: list[InsuranceNeed] = []
    responsibility_pool = _household_responsibility_pool(profile)

    for member in profile.members:
        advice_role = _advice_role(profile, member, preferences)
        # 1. 医疗报销保障
        if not member.medical_covered:
            med_limit = 1000000.0 if member.age >= 18 else 500000.0
            needs.append(
                InsuranceNeed(
                    member_name=member.name,
                    member_role=member.role,
                    product_key="medical_base",
                    product_label="基础医疗报销保障",
                    priority_rank=1,
                    current_coverage=0.0,
                    target_coverage=med_limit,
                    additional_gap=med_limit,
                    current_status="缺失",
                    target_status="建议补足基础住院/医疗报销保障",
                    full_additional_annual_premium=_mock_medical_premium(member.age),
                    supports_partial=False,
                    rationale="先补医疗报销能力，避免单次住院或治疗直接侵蚀家庭现金流。",
                )
            )

        # 2. 重疾保障
        ci_target = _ci_target(member, preferences, advice_role)
        ci_gap = max(ci_target - member.critical_illness_coverage, 0.0)
        if ci_gap > 0 and advice_role.ci_priority_rank is not None:
            needs.append(
                InsuranceNeed(
                    member_name=member.name,
                    member_role=member.role,
                    product_key="critical_illness",
                    product_label="重疾保障",
                    priority_rank=advice_role.ci_priority_rank,
                    current_coverage=member.critical_illness_coverage,
                    target_coverage=ci_target,
                    additional_gap=ci_gap,
                    current_status=f"现有约 {member.critical_illness_coverage:,.0f} 元",
                    target_status=f"建议提升至约 {ci_target:,.0f} 元",
                    full_additional_annual_premium=_mock_ci_premium(member.age, ci_gap),
                    supports_partial=True,
                    rationale="重疾保障主要覆盖治疗恢复期、收入暂停期和阶段性现金流波动。",
                )
            )

        # 3. 定寿
        term_target = _term_life_target(member, profile, responsibility_pool, preferences, advice_role)
        term_gap = max(term_target - member.term_life_coverage, 0.0)
        if advice_role.term_priority_rank is not None and term_gap > 0:
            needs.append(
                InsuranceNeed(
                    member_name=member.name,
                    member_role=member.role,
                    product_key="term_life",
                    product_label="定期寿险",
                    priority_rank=advice_role.term_priority_rank,
                    current_coverage=member.term_life_coverage,
                    target_coverage=term_target,
                    additional_gap=term_gap,
                    current_status=f"现有约 {member.term_life_coverage:,.0f} 元",
                    target_status=f"建议提升至约 {term_target:,.0f} 元",
                    full_additional_annual_premium=_mock_term_premium(member.age, term_gap),
                    supports_partial=True,
                    rationale="定期寿险主要覆盖责任期内的收入中断风险，以及家庭对这一成员的现金流依赖。",
                )
            )

        # 4. 高端医疗 / 特需医疗升级
        if _should_consider_hci(profile, member, preferences, advice_role):
            hci_target = 2000000.0
            hci_gap = max(hci_target - member.hci_coverage, 0.0)
            if hci_gap > 0:
                needs.append(
                    InsuranceNeed(
                        member_name=member.name,
                        member_role=member.role,
                        product_key="hci",
                        product_label="高端医疗/特需医疗",
                        priority_rank=5,
                        current_coverage=member.hci_coverage,
                        target_coverage=hci_target,
                        additional_gap=hci_gap,
                        current_status=f"现有约 {member.hci_coverage:,.0f} 元",
                        target_status=f"若预算允许，可补至约 {hci_target:,.0f} 元",
                        full_additional_annual_premium=_mock_hci_premium(member.age, hci_gap),
                        supports_partial=True,
                        rationale="在核心保障已经具备的前提下，再考虑就医便利性和服务升级。",
                    )
                )

    return tuple(sorted(needs, key=lambda item: (item.priority_rank, item.member_name, item.product_key)))


def _build_household_metrics(
    profile: ClientProfile,
    preferences: PlanningPreferences,
) -> HouseholdMetrics:
    annual_surplus = _annual_net_for_year(profile, profile.current_year, profile.current_year)
    monthly_surplus = annual_surplus / 12.0
    annual_income = profile.total_annual_income
    monthly_income = annual_income / 12.0
    existing_annual_premium = profile.insurance_total_annual_premium
    next_10y_major_events = sum(
        float(evt.estimated_amount or 0)
        for evt in profile.events
        if profile.current_year <= evt.timing_year <= profile.current_year + 10
    )
    node_results = project_to_nodes(profile)
    next_10y_negative_gap = 0.0
    for node in node_results:
        if node.year <= profile.current_year + 10 and node.gap_or_surplus < 0:
            next_10y_negative_gap = min(next_10y_negative_gap, node.gap_or_surplus)
    dependent_count = sum(1 for m in profile.members if _is_dependent(m))
    key_earner_count = sum(1 for m in profile.members if _is_key_earner(m))
    retirement_medical_selfpay_first_year = sum(
        m.healthcare_starting_annual * (1 - m.reimbursement_rate)
        for m in profile.members
        if m.healthcare_starting_annual > 0
    )

    if annual_income <= 0:
        budget_ratio = 0.0
    elif preferences.auto_budget_ratio is not None:
        budget_ratio = preferences.auto_budget_ratio
    elif annual_surplus <= 0:
        budget_ratio = existing_annual_premium / annual_income if annual_income > 0 else 0.0
    elif next_10y_negative_gap < 0 or next_10y_major_events > profile.total_financial_assets * 0.8:
        budget_ratio = 0.05
    elif annual_surplus < annual_income * 0.08:
        budget_ratio = 0.06
    else:
        budget_ratio = 0.08

    premium_budget_annual = min(
        annual_income * budget_ratio if annual_income > 0 else 0.0,
        max(existing_annual_premium + max(annual_surplus, 0.0) * 0.45, existing_annual_premium),
    )
    if preferences.manual_premium_cap_annual is not None:
        premium_budget_annual = preferences.manual_premium_cap_annual
    premium_budget_annual = max(premium_budget_annual, existing_annual_premium)

    return HouseholdMetrics(
        annual_income=annual_income,
        monthly_income=monthly_income,
        annual_current_surplus=annual_surplus,
        monthly_current_surplus=monthly_surplus,
        total_financial_assets=profile.total_financial_assets,
        total_outstanding_debt=profile.total_outstanding_debt,
        existing_annual_premium=existing_annual_premium,
        existing_monthly_premium=existing_annual_premium / 12.0,
        premium_budget_annual=premium_budget_annual,
        premium_budget_monthly=premium_budget_annual / 12.0,
        next_10y_major_events=next_10y_major_events,
        next_10y_negative_gap=next_10y_negative_gap,
        dependent_count=dependent_count,
        key_earner_count=key_earner_count,
        retirement_medical_selfpay_first_year=retirement_medical_selfpay_first_year,
    )


def _allocate_core_plan(needs: tuple[InsuranceNeed, ...], annual_budget: float) -> ScenarioPlan:
    remaining = annual_budget
    allocations: list[ScenarioAllocation] = []

    for need in needs:
        premium = 0.0
        ratio = 0.0
        if need.full_additional_annual_premium <= 0 or need.additional_gap <= 0:
            ratio = 1.0
        elif remaining > 0:
            if not need.supports_partial:
                if remaining >= need.full_additional_annual_premium:
                    premium = need.full_additional_annual_premium
                    ratio = 1.0
            else:
                ratio = min(1.0, remaining / need.full_additional_annual_premium)
                premium = need.full_additional_annual_premium * ratio
        recommended_additional = need.additional_gap * ratio
        allocations.append(
            ScenarioAllocation(
                member_name=need.member_name,
                product_label=need.product_label,
                priority_rank=need.priority_rank,
                current_coverage=need.current_coverage,
                target_coverage=need.target_coverage,
                recommended_additional_coverage=recommended_additional,
                recommended_total_coverage=need.current_coverage + recommended_additional,
                premium_used=premium,
                fill_ratio=ratio,
                rationale=need.rationale,
                current_status=need.current_status,
                target_status=need.target_status,
            )
        )
        remaining = max(remaining - premium, 0.0)

    used = annual_budget - remaining
    summary = (
        "先把基础医疗报销保障放在最前，再按成员责任顺序补足定期寿险或重疾保障。",
        "如果预算只够做一部分，优先把关键收入成员的责任期保障补齐，再回头补独立成年人的重疾缺口。",
        "这套方向更强调把高优先级保障尽量做足，而不是同时铺开很多层。",
    )
    return ScenarioPlan(
        scenario_key="core",
        scenario_label="方案 A：优先补足核心保障",
        budget_annual=annual_budget,
        budget_monthly=annual_budget / 12.0,
        premium_used_annual=used,
        premium_used_monthly=used / 12.0,
        allocations=tuple(allocations),
        summary=summary,
    )


def _allocate_balanced_plan(needs: tuple[InsuranceNeed, ...], annual_budget: float) -> ScenarioPlan:
    fixed_needs = [need for need in needs if not need.supports_partial]
    variable_needs = [need for need in needs if need.supports_partial]

    allocations: list[ScenarioAllocation] = []
    remaining = annual_budget
    fixed_by_key = {(need.member_name, need.product_key): 0.0 for need in fixed_needs}

    for need in fixed_needs:
        if remaining >= need.full_additional_annual_premium:
            premium = need.full_additional_annual_premium
            ratio = 1.0
            remaining -= premium
        else:
            premium = 0.0
            ratio = 0.0
        fixed_by_key[(need.member_name, need.product_key)] = ratio
        allocations.append(
            ScenarioAllocation(
                member_name=need.member_name,
                product_label=need.product_label,
                priority_rank=need.priority_rank,
                current_coverage=need.current_coverage,
                target_coverage=need.target_coverage,
                recommended_additional_coverage=need.additional_gap * ratio,
                recommended_total_coverage=need.current_coverage + need.additional_gap * ratio,
                premium_used=premium,
                fill_ratio=ratio,
                rationale=need.rationale,
                current_status=need.current_status,
                target_status=need.target_status,
            )
        )

    def desired_weight(need: InsuranceNeed) -> float:
        if need.product_key == "critical_illness":
            if need.member_role in {"primary_breadwinner", "secondary_breadwinner"} and need.priority_rank >= 3:
                return 0.55
            if need.member_role == "dependent_elder":
                return 0.45
            return 0.70
        if need.product_key == "term_life":
            if need.priority_rank <= 2:
                return 0.70
            return 0.35
        if need.product_key == "hci":
            return 0.35
        return 0.50

    desired_premium_total = sum(
        need.full_additional_annual_premium * desired_weight(need)
        for need in variable_needs
    )
    scale = min(1.0, remaining / desired_premium_total) if desired_premium_total > 0 else 0.0

    for need in variable_needs:
        target_ratio = desired_weight(need) * scale
        target_ratio = min(target_ratio, 1.0)
        premium = need.full_additional_annual_premium * target_ratio
        allocations.append(
            ScenarioAllocation(
                member_name=need.member_name,
                product_label=need.product_label,
                priority_rank=need.priority_rank,
                current_coverage=need.current_coverage,
                target_coverage=need.target_coverage,
                recommended_additional_coverage=need.additional_gap * target_ratio,
                recommended_total_coverage=need.current_coverage + need.additional_gap * target_ratio,
                premium_used=premium,
                fill_ratio=target_ratio,
                rationale=need.rationale,
                current_status=need.current_status,
                target_status=need.target_status,
            )
        )

    used = sum(item.premium_used for item in allocations)
    summary = (
        "先保证基础医疗不断档，再按成员责任结构把预算分散到定寿、重疾和医疗升级上。",
        "每一类都尽量先配一些，但单项保额通常会低于“核心保障优先”方案。",
        "这套方向更适合希望先把结构搭起来、后续再逐年加厚的人。",
    )
    return ScenarioPlan(
        scenario_key="balanced",
        scenario_label="方案 B：尽量都配一些，但单项保额更克制",
        budget_annual=annual_budget,
        budget_monthly=annual_budget / 12.0,
        premium_used_annual=used,
        premium_used_monthly=used / 12.0,
        allocations=tuple(sorted(allocations, key=lambda item: (item.priority_rank, item.member_name, item.product_label))),
        summary=summary,
    )


def _alloc_lookup(plan: ScenarioPlan) -> dict[tuple[str, str], ScenarioAllocation]:
    return {(item.member_name, item.product_label): item for item in plan.allocations}


def _member_responsibility_desc(
    profile: ClientProfile,
    member: Member,
    advice_role: AdviceRole,
    preferences: PlanningPreferences,
) -> str:
    parts: list[str] = []
    if advice_role.key == "key_earner_core":
        parts.append("是家庭当前主要收入来源")
    elif advice_role.key == "key_earner_supporting":
        parts.append("承担家庭的重要补充收入")
    elif advice_role.key == "independent_adult":
        parts.append("当前更接近独立承担自己现金流压力的阶段")
    elif advice_role.key == "dependent_adult_transition":
        threshold = _personal_expense_annual(member) * preferences.adult_independence_buffer
        parts.append(f"目前仍属于家庭支持向独立过渡的阶段，按当前口径需要年收入达到约 {threshold:,.0f} 元才算基本独立")
    elif advice_role.key == "child_dependent":
        parts.append("目前主要是被抚养对象")
    elif advice_role.key == "elder_dependent":
        parts.append("在家庭里更接近需要持续照顾和医疗支持的角色")
    if member.age < 18:
        parts.append(f"当前年龄 {member.age} 岁，还没有独立收入")
    elif member.age >= 55:
        parts.append(f"当前年龄 {member.age} 岁，已经接近退休阶段")
    else:
        parts.append(f"当前年龄 {member.age} 岁，仍处在责任和收入并行阶段")
    if profile.total_outstanding_debt > 0 and _is_key_earner(member):
        parts.append("而家庭目前还有负债责任")
    return "，".join(parts)


def _member_gap_explanation(
    profile: ClientProfile,
    member: Member,
    advice_role: AdviceRole,
    preferences: PlanningPreferences,
    term_need: InsuranceNeed | None,
    ci_need: InsuranceNeed | None,
    med_need: InsuranceNeed | None,
    hci_need: InsuranceNeed | None,
    current_total_premium: float,
    target_total_premium: float,
) -> tuple[str, ...]:
    lines: list[str] = []
    lines.append(f"{member.name}{_member_responsibility_desc(profile, member, advice_role, preferences)}。")

    if term_need:
        if advice_role.has_household_responsibility:
            lines.append(
                f"定寿目标拉到约 {term_need.target_coverage:,.0f} 元，核心不是把寿险做满，而是先把责任期内的收入中断、负债和未来大额支出兜住。"
            )
        else:
            lines.append(
                f"定寿目标落在约 {term_need.target_coverage:,.0f} 元，这一层不是当前最前面的缺口，更像是独立成年人为自己未来责任预留的基础缓冲。"
            )
    elif advice_role.has_household_responsibility:
        lines.append("定寿这块当前口径已经没有明显缺口，所以本次不把它放在最前面。")

    if ci_need:
        if advice_role.key in {"child_dependent", "elder_dependent", "dependent_adult_transition"}:
            lines.append(
                f"重疾目标落在约 {ci_need.target_coverage:,.0f} 元，重点是给家庭留出治疗和恢复期的现金流缓冲，而不是按收入替代来推高保额。"
            )
        else:
            lines.append(
                f"重疾目标按收入和支出口径两边取高，落在约 {ci_need.target_coverage:,.0f} 元，重点是覆盖治疗恢复期和收入暂停期，而不是单看一次性医疗费用。"
            )
    elif member.critical_illness_coverage > 0:
        lines.append("重疾保障已经有一定基础，所以本轮更关注是否还需要向上加厚，而不是从零开始配置。")

    if med_need:
        lines.append("医疗报销保障被放在更前面，因为它对单次住院和治疗的现金流冲击最直接。")

    if hci_need:
        lines.append("高端医疗/特需升级被放在后位，它更偏就医体验和资源可达性，前提是基础保障先别缺。")

    if target_total_premium > current_total_premium:
        lines.append(
            f"如果按当前识别到的目标全部补足，按 mock 口径，这个成员的年保费会从约 {current_total_premium:,.0f} 元上升到约 {target_total_premium:,.0f} 元。"
        )

    return tuple(lines)


def _member_plan_explanation(
    member: Member,
    advice_role: AdviceRole,
    scenario_label: str,
    term_alloc: ScenarioAllocation | None,
    ci_alloc: ScenarioAllocation | None,
    med_alloc: ScenarioAllocation | None,
    hci_alloc: ScenarioAllocation | None,
    current_total_premium: float,
    scenario_total_premium: float,
) -> tuple[str, ...]:
    lines: list[str] = []
    if scenario_label == "A":
        if advice_role.has_household_responsibility:
            lines.append(f"{member.name}在方案A里采用的是“先把责任期风险补厚”的思路。")
        else:
            lines.append(f"{member.name}在方案A里采用的是“先把基础缺口补足”的思路。")
    else:
        if advice_role.has_household_responsibility:
            lines.append(f"{member.name}在方案B里采用的是“责任层先有、再逐步加厚”的思路。")
        else:
            lines.append(f"{member.name}在方案B里采用的是“先把结构搭起来，再逐步加厚”的思路。")

    if med_alloc and med_alloc.fill_ratio > 0:
        lines.append("医疗报销先被纳入，是因为这一层最能直接减轻住院和治疗时的即时现金流压力。")

    if ci_alloc and ci_alloc.fill_ratio > 0:
        if ci_alloc.fill_ratio >= 0.85:
            lines.append(f"重疾基本按目标口径去补，说明当前更重视把收入中断和恢复期风险先压住。")
        else:
            lines.append(f"重疾这次先补到约 {ci_alloc.recommended_total_coverage:,.0f} 元，没有一步补满，主要是给保费预算和其他责任留空间。")

    if term_alloc and term_alloc.fill_ratio > 0:
        if term_alloc.fill_ratio >= 0.85:
            if advice_role.has_household_responsibility:
                lines.append("定寿补得更足，是因为这个成员对家庭责任期现金流的影响更大。")
            else:
                lines.append("定寿也被纳入，但它排在重疾之后，更多是给未来责任和长期现金流做基础缓冲。")
        else:
            if advice_role.has_household_responsibility:
                lines.append("定寿先补一部分，优先把最核心的责任区间兜住，后续如果预算释放再继续加厚。")
            else:
                lines.append("定寿先保留一层基础配置，但当前没有把预算大量压在这一层。")

    if hci_alloc and hci_alloc.fill_ratio > 0:
        lines.append("高端医疗/特需升级只在预算还允许时再考虑，因此它天然排在基础保障后面。")

    if not any(item and item.fill_ratio > 0 for item in (med_alloc, ci_alloc, term_alloc, hci_alloc)):
        lines.append("这个成员在当前预算下没有被优先新增保障，通常意味着当前责任排序靠后，或者预算应先让位给更关键的成员。")
    elif scenario_total_premium > current_total_premium:
        lines.append(
            f"按当前 mock 口径，这个成员的年保费会从约 {current_total_premium:,.0f} 元上升到约 {scenario_total_premium:,.0f} 元，重点不是把总额做高，而是把预算放到更该优先的险种上。"
        )

    return tuple(lines)


def _build_member_views(
    profile: ClientProfile,
    preferences: PlanningPreferences,
    needs: tuple[InsuranceNeed, ...],
    core_plan: ScenarioPlan,
    balanced_plan: ScenarioPlan,
) -> tuple[MemberPlanView, ...]:
    need_lookup = {(need.member_name, need.product_key): need for need in needs}
    core_lookup = _alloc_lookup(core_plan)
    balanced_lookup = _alloc_lookup(balanced_plan)

    views: list[MemberPlanView] = []
    for member in profile.members:
        advice_role = _advice_role(profile, member, preferences)
        current_term_premium = member.term_life_premium
        current_ci_premium = member.critical_illness_premium
        current_medical_premium = member.medical_premium
        current_hci_premium = member.hci_premium
        current_other_premium = member.other_insurance_premium
        current_premium = current_term_premium + current_ci_premium + current_medical_premium + current_hci_premium + current_other_premium

        med_need = need_lookup.get((member.name, "medical_base"))
        med_a = core_lookup.get((member.name, "基础医疗报销保障"))
        med_b = balanced_lookup.get((member.name, "基础医疗报销保障"))

        term_need = need_lookup.get((member.name, "term_life"))
        term_a = core_lookup.get((member.name, "定期寿险"))
        term_b = balanced_lookup.get((member.name, "定期寿险"))

        ci_need = need_lookup.get((member.name, "critical_illness"))
        ci_a = core_lookup.get((member.name, "重疾保障"))
        ci_b = balanced_lookup.get((member.name, "重疾保障"))

        hci_need = need_lookup.get((member.name, "hci"))
        hci_a = core_lookup.get((member.name, "高端医疗/特需医疗"))
        hci_b = balanced_lookup.get((member.name, "高端医疗/特需医疗"))
        target_term_premium = current_term_premium + (term_need.full_additional_annual_premium if term_need else 0.0)
        target_ci_premium = current_ci_premium + (ci_need.full_additional_annual_premium if ci_need else 0.0)
        target_medical_premium = current_medical_premium + (med_need.full_additional_annual_premium if med_need else 0.0)
        target_hci_premium = current_hci_premium + (hci_need.full_additional_annual_premium if hci_need else 0.0)
        target_total_premium = target_term_premium + target_ci_premium + target_medical_premium + target_hci_premium

        gap_explanation = _member_gap_explanation(
            profile, member, advice_role, preferences, term_need, ci_need, med_need, hci_need, current_premium, target_total_premium
        )
        plan_a_term_premium = current_term_premium + (term_a.premium_used if term_a else 0.0)
        plan_a_ci_premium = current_ci_premium + (ci_a.premium_used if ci_a else 0.0)
        plan_a_medical_premium = current_medical_premium + (med_a.premium_used if med_a else 0.0)
        plan_a_hci_premium = current_hci_premium + (hci_a.premium_used if hci_a else 0.0)
        plan_b_term_premium = current_term_premium + (term_b.premium_used if term_b else 0.0)
        plan_b_ci_premium = current_ci_premium + (ci_b.premium_used if ci_b else 0.0)
        plan_b_medical_premium = current_medical_premium + (med_b.premium_used if med_b else 0.0)
        plan_b_hci_premium = current_hci_premium + (hci_b.premium_used if hci_b else 0.0)
        plan_a_total_premium = plan_a_term_premium + plan_a_ci_premium + plan_a_medical_premium + plan_a_hci_premium
        plan_b_total_premium = plan_b_term_premium + plan_b_ci_premium + plan_b_medical_premium + plan_b_hci_premium
        plan_a_total_premium += current_other_premium
        plan_b_total_premium += current_other_premium
        plan_a_explanation = _member_plan_explanation(
            member, advice_role, "A", term_a, ci_a, med_a, hci_a, current_premium, plan_a_total_premium
        )
        plan_b_explanation = _member_plan_explanation(
            member, advice_role, "B", term_b, ci_b, med_b, hci_b, current_premium, plan_b_total_premium
        )

        views.append(
            MemberPlanView(
                member_name=member.name,
                member_role=member.role,
                medical_current=member.medical_covered,
                medical_target=member.medical_covered or med_need is not None,
                medical_plan_a=member.medical_covered or (med_a.fill_ratio > 0 if med_a else False),
                medical_plan_b=member.medical_covered or (med_b.fill_ratio > 0 if med_b else False),
                current_term_coverage=member.term_life_coverage,
                target_term_coverage=term_need.target_coverage if term_need else member.term_life_coverage,
                plan_a_term_coverage=term_a.recommended_total_coverage if term_a else member.term_life_coverage,
                plan_b_term_coverage=term_b.recommended_total_coverage if term_b else member.term_life_coverage,
                current_ci_coverage=member.critical_illness_coverage,
                target_ci_coverage=ci_need.target_coverage if ci_need else member.critical_illness_coverage,
                plan_a_ci_coverage=ci_a.recommended_total_coverage if ci_a else member.critical_illness_coverage,
                plan_b_ci_coverage=ci_b.recommended_total_coverage if ci_b else member.critical_illness_coverage,
                current_hci_coverage=member.hci_coverage,
                target_hci_coverage=hci_need.target_coverage if hci_need else member.hci_coverage,
                plan_a_hci_coverage=hci_a.recommended_total_coverage if hci_a else member.hci_coverage,
                plan_b_hci_coverage=hci_b.recommended_total_coverage if hci_b else member.hci_coverage,
                current_term_premium=current_term_premium,
                current_ci_premium=current_ci_premium,
                current_medical_premium=current_medical_premium,
                current_hci_premium=current_hci_premium,
                target_term_premium=target_term_premium,
                target_ci_premium=target_ci_premium,
                target_medical_premium=target_medical_premium,
                target_hci_premium=target_hci_premium,
                plan_a_term_premium=plan_a_term_premium,
                plan_a_ci_premium=plan_a_ci_premium,
                plan_a_medical_premium=plan_a_medical_premium,
                plan_a_hci_premium=plan_a_hci_premium,
                plan_b_term_premium=plan_b_term_premium,
                plan_b_ci_premium=plan_b_ci_premium,
                plan_b_medical_premium=plan_b_medical_premium,
                plan_b_hci_premium=plan_b_hci_premium,
                current_annual_premium=current_premium,
                plan_a_annual_premium=plan_a_total_premium,
                plan_b_annual_premium=plan_b_total_premium,
                gap_explanation=gap_explanation,
                plan_a_explanation=plan_a_explanation,
                plan_b_explanation=plan_b_explanation,
            )
        )
    return tuple(views)


def analyze_profile(
    profile: ClientProfile,
    preferences: PlanningPreferences | None = None,
) -> InsurancePlanningResult:
    preferences = preferences or _preferences_from_profile_assumptions(profile)
    metrics = _build_household_metrics(profile, preferences)
    needs = _build_needs(profile, metrics, preferences)
    core_plan = _allocate_core_plan(needs, max(metrics.premium_budget_annual - metrics.existing_annual_premium, 0.0))
    balanced_plan = _allocate_balanced_plan(needs, max(metrics.premium_budget_annual - metrics.existing_annual_premium, 0.0))
    member_views = _build_member_views(profile, preferences, needs, core_plan, balanced_plan)

    principles = (
        "先看家庭责任，再看保险结构。责任型家庭通常是先补医疗，再优先把定期寿险和责任期缺口补起来；独立成年人通常是先补医疗和重疾，再考虑定期寿险。",
        f"成年受抚养成员只有在预计年收入达到个人年常规支出的 {preferences.adult_independence_buffer:.1f} 倍时，才按“基本经济独立”切换到独立成年人口径。",
        "保费预算不能只看“想配齐什么”，还要看当前结余、未来重大支出、负债和退休后的现金流压力。",
        "这份建议只做保障结构规划，不替代产品筛选、健康核保和精确保费试算。",
    )
    assumptions = (
        "当前保费测算使用校准后的 mock 曲线，仅用于比较方案相对压力，不代表真实核保报价。",
        f"本次建议把全年总保费上限先控制在约 {metrics.premium_budget_annual:,.0f} 元以内（含现有保费）。",
        "若未来收入、家庭成员、负债或重大支出节点变化，应重新测算预算与保障优先级。",
    )

    warnings: list[str] = []
    if metrics.annual_current_surplus <= 0:
        warnings.append("当前家庭口径下年净现金流已经偏紧，新增保费需要非常克制，必要时应先做保障结构取舍。")
    if metrics.next_10y_negative_gap < 0:
        warnings.append(f"未来 10 年内重大支出测算出现约 {abs(metrics.next_10y_negative_gap):,.0f} 元缺口，新增长期保费不宜过重。")
    if metrics.retirement_medical_selfpay_first_year > 0:
        warnings.append(f"退休首年医疗自付口径约 {metrics.retirement_medical_selfpay_first_year:,.0f} 元，后续加保也要兼顾退休后的持续缴费能力。")

    return InsurancePlanningResult(
        profile=profile,
        preferences=preferences,
        metrics=metrics,
        planning_principles=principles,
        assumptions=assumptions,
        needs=needs,
        core_plan=core_plan,
        balanced_plan=balanced_plan,
        member_views=member_views,
        warnings=tuple(warnings),
    )


def analyze_yaml_text(
    yaml_text: str,
    current_year: int,
    preferences: PlanningPreferences | None = None,
) -> InsurancePlanningResult:
    import yaml

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML 解析失败: {exc}") from exc
    ok, errors = _validate(data if isinstance(data, dict) else {}, Path("<inline>"))
    if not ok:
        raise ValueError("; ".join(errors))

    with NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
        tmp.write(yaml_text)
        tmp_path = Path(tmp.name)
    try:
        profile = load_profile(tmp_path, current_year=current_year)
    finally:
        tmp_path.unlink(missing_ok=True)
    return analyze_profile(profile, preferences=preferences)
