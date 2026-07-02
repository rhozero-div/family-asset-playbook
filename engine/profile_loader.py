"""客户档案加载器。

解析 YAML 档案为强类型 dataclass。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProfileLoadError(Exception):
    """档案加载失败。"""


@dataclass(frozen=True)
class Member:
    """逐人数据。"""
    name: str
    age: int
    role: str
    annual_income: float = 0.0
    income_start_age: int = 0
    income_start_annual: float = 0.0
    monthly_expense: float = 0.0
    retirement_age: int = 60
    retirement_year: int = 0
    retirement_pension: float = 0.0
    retirement_annuity: float = 0.0
    retirement_expense_coeff: float = 0.7
    term_life_coverage: float = 0.0
    term_life_premium: float = 0.0
    term_life_pay_years: int = 0
    critical_illness_coverage: float = 0.0
    critical_illness_premium: float = 0.0
    critical_illness_pay_years: int = 0
    medical_covered: bool = False
    medical_premium: float = 0.0
    medical_pay_years: int = 0
    hci_coverage: float = 0.0
    hci_premium: float = 0.0
    hci_pay_years: int = 0
    other_insurance_premium: float = 0.0
    other_insurance_pay_years: int = 0
    healthcare_starting_annual: float = 0.0
    healthcare_growth_rate: float = 0.05
    healthcare_annual_cap: float = 0.0
    reimbursement_rate: float = 0.0


@dataclass(frozen=True)
class Event:
    """单个事件。"""

    id: str
    type: str
    description: str
    timing_year: int
    estimated_amount: float | None
    expected_replacement_ratio: float | None
    owner: str | None
    certainty: str = "medium"


@dataclass(frozen=True)
class ClientProfile:
    """客户档案。"""

    profile_version: str
    schema_version: str
    family_name: str
    current_year: int
    measurement_end_year: int
    events: tuple[Event, ...]
    risk_preference: str
    # 月度收支
    total_annual_income: float
    monthly_living_expense: float
    household_extra_monthly_expense: float
    monthly_liabilities: float
    liquidity_reserve_months: float
    # 资产存量(汇总)
    total_financial_assets: float       # 可投资金融资产总额
    total_real_estate_value: float
    total_outstanding_debt: float
    # 保障型保险
    insurance_term_life_cov: float
    insurance_term_life_premium: float
    insurance_critical_illness_cov: float
    insurance_critical_illness_premium: float
    insurance_medical_covered: bool
    insurance_medical_premium: float
    insurance_total_annual_premium: float
    # 退休后收支
    retirement_monthly_pension: float
    retirement_monthly_annuity: float
    retirement_monthly_expense: float   # 0 表示沿用当前月支出
    # 退休后医疗与疾病支出(复利递增至封顶)
    healthcare_starting_annual: float   # 退休首年年度支出
    healthcare_growth_rate: float       # 逐年复利增长率
    healthcare_annual_cap: float        # 年度封顶金额(0 表示无封顶)
    healthcare_reimbursement_rate: float  # 赔付率(0~1),保险赔的比例,自付 = gross * (1 - rate)
    # 主要收入者信息
    primary_breadwinner_birth_year: int
    primary_breadwinner_retirement_age: int
    # 负债
    remaining_liability_end_year: int   # 最晚一笔负债还清年份(已还清则为0)
    # 保险缴费剩余年限
    insurance_term_life_pay_years: int
    insurance_critical_illness_pay_years: int  # 现有重疾险剩余缴费年(panel 3)
    insurance_medical_pay_years: int
    # 逐人数据
    members: tuple[Member, ...] = ()
    # 储蓄险(多行)
    savings: tuple[dict, ...] = ()
    # 推演假设(可选)
    assumptions: dict | None = None


_REQUIRED_TOP_LEVEL = {"profile_version", "schema_version", "family", "events"}


def _require(d: dict, key: str, ctx: str) -> Any:
    if key not in d:
        raise ProfileLoadError(f"{ctx}: 缺少必填字段 '{key}'")
    return d[key]


def _parse_event(raw: dict, idx: int) -> Event:
    ctx = f"events[{idx}]"
    return Event(
        id=_require(raw, "id", ctx),
        type=_require(raw, "type", ctx),
        description=_require(raw, "description", ctx),
        timing_year=int(_require(raw, "timing_year", ctx)),
        estimated_amount=raw.get("estimated_amount"),
        certainty=str(raw.get("certainty", "medium")),
        expected_replacement_ratio=raw.get("expected_replacement_ratio"),
        owner=raw.get("owner"),
    )


def _family_name(family: dict) -> str:
    for m in family.get("members", []):
        if m.get("role") == "primary_breadwinner":
            return m.get("name", "unknown")
    return "unknown"


def _primary_age(family: dict) -> int:
    for m in family.get("members", []):
        if m.get("role") == "primary_breadwinner":
            return int(m.get("age", 35))
    return 35


def _parse_insurance(assets: dict) -> dict:
    """从 assets.financial.insurance 提取保险详情。"""
    result = {
        "term_life_cov": 0.0, "term_life_premium": 0.0,
        "term_life_pay_years": 0,
        "ci_cov": 0.0, "ci_premium": 0.0, "ci_pay_years": 0,
        "medical_covered": False, "medical_premium": 0.0,
        "medical_pay_years": 0,
        "hci_cov": 0.0, "hci_premium": 0.0, "hci_pay_years": 0,
        "other_premium": 0.0, "other_pay_years": 0,
        "total_premium": 0.0, "hint": "",
    }
    if not isinstance(assets, dict):
        return result

    cat = assets.get("financial", {})
    if not isinstance(cat, dict):
        return result
    ins = cat.get("insurance", {})
    if not isinstance(ins, dict):
        return result
    result["term_life_cov"] += float(ins.get("term_life_coverage", 0))
    result["term_life_premium"] += float(ins.get("term_life_premium", 0))
    result["term_life_pay_years"] = int(ins.get("term_life_pay_years", 0))
    result["ci_cov"] += float(ins.get("critical_illness_coverage", 0))
    result["ci_premium"] += float(ins.get("critical_illness_premium", 0))
    result["ci_pay_years"] = int(ins.get("critical_illness_pay_years", 0))
    if ins.get("medical_covered"):
        result["medical_covered"] = True
    result["medical_premium"] += float(ins.get("medical_premium", 0))
    result["medical_pay_years"] = int(ins.get("medical_pay_years", 0))
    result["hci_cov"] += float(ins.get("hci_coverage", 0))
    result["hci_premium"] += float(ins.get("hci_premium", 0))
    result["hci_pay_years"] = int(ins.get("hci_pay_years", 0))
    result["other_premium"] += float(ins.get("other_insurance_premium", 0))
    result["other_pay_years"] = int(ins.get("other_insurance_pay_years", 0))

    result["total_premium"] += (result["term_life_premium"]
                                 + result["ci_premium"]
                                 + result["medical_premium"]
                                 + result["hci_premium"]
                                 + result["other_premium"])
    return result


def load_profile(path: str | Path, *, current_year: int | None = None) -> ClientProfile:
    """加载并解析客户档案 YAML。

    Raises:
        ProfileLoadError: 解析失败或字段缺失
    """
    p = Path(path)
    if not p.exists():
        raise ProfileLoadError(f"档案不存在: {p}")

    try:
        import yaml
    except ImportError as e:
        raise ProfileLoadError(
            "需要 PyYAML 解析 YAML。请安装:pip install pyyaml"
        ) from e

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ProfileLoadError(f"YAML 解析失败: {e}") from e

    if not isinstance(raw, dict):
        raise ProfileLoadError("YAML 顶层应为字典")

    missing = _REQUIRED_TOP_LEVEL - set(raw.keys())
    if missing:
        raise ProfileLoadError(f"缺少必填字段: {sorted(missing)}")

    family = _require(raw, "family", "root")
    events_raw = _require(raw, "events", "root")
    if not isinstance(events_raw, list):
        raise ProfileLoadError("events 应为数组")

    events = tuple(
        sorted(
            (_parse_event(e, i) for i, e in enumerate(events_raw)),
            key=lambda ev: ev.timing_year,
        )
    )
    effective_current_year = current_year or 0
    last_event_year = max((evt.timing_year for evt in events), default=effective_current_year)

    advisor = raw.get("advisor_assessment", {})
    risk = advisor.get("risk_tolerance", "balanced")

    assets = raw.get("assets", {})

    # 月度收支: 汇总年收入
    income_raw = raw.get("income", {})
    total_annual = 0.0
    monthly_living = 0.0
    household_extra_monthly = 0.0

    # 从 family.members 读取逐人数据
    ret_pension = 0.0
    ret_annuity = 0.0
    ret_expense = 0.0
    # 先初始化 ins_data, 成员循环 + _parse_insurance 都会填充
    ins_data = {
        "term_life_cov": 0.0, "term_life_premium": 0.0, "term_life_pay_years": 0,
        "ci_cov": 0.0, "ci_premium": 0.0, "ci_pay_years": 0,
        "medical_covered": False, "medical_premium": 0.0, "medical_pay_years": 0,
        "hci_cov": 0.0, "hci_premium": 0.0, "hci_pay_years": 0,
        "other_premium": 0.0, "other_pay_years": 0,
        "total_premium": 0.0, "hint": "",
    }
    member_reimb_rates = []
    breadwinner_retire_age = 60
    members_list = []
    if isinstance(family, dict):
        for m in family.get("members", []):
            if isinstance(m, dict):
                name = str(m.get("name", ""))
                age = int(m.get("age", 0))
                role = str(m.get("role", ""))
                annual_income_val = float(m.get("annual_income", 0))
                income_start_age_val = int(m.get("income_start_age", 0) or 0)
                income_start_annual_val = float(m.get("income_start_annual", 0))
                monthly_expense_val = float(m.get("monthly_expense", 0))

                total_annual += annual_income_val
                monthly_living += monthly_expense_val

                # 退休收入
                ret_pension_val = float(m.get("retirement_pension", 0))
                ret_annuity_val = float(m.get("retirement_annuity", 0))
                ret_pension += ret_pension_val
                ret_annuity += ret_annuity_val

                # 退休后支出 = 当前月支出 × 系数 (如果已退休则不乘系数)
                retire_age_val = int(m.get("retirement_age", 60))
                coeff = float(m.get("retirement_expense_coeff", 0.7))
                if current_year and age >= retire_age_val:
                    coeff = 1.0  # 已退休, 不削減
                ret_expense += monthly_expense_val * coeff

                # 主要收入者退休年龄
                if role == "primary_breadwinner":
                    breadwinner_retire_age = retire_age_val

                # 逐人报销比例
                rr = m.get("reimbursement_rate")
                if rr is not None:
                    member_reimb_rates.append(float(rr))

                # 逐人保险 (累计到 ins_data)
                tl_cov = float(m.get("term_life_coverage", 0))
                tl_premium = float(m.get("term_life_premium", 0))
                tl_pay_years = int(m.get("term_life_pay_years", 0))
                if tl_cov > 0 or tl_premium > 0:
                    ins_data["term_life_cov"] += tl_cov
                    ins_data["term_life_premium"] += tl_premium
                    ins_data["term_life_pay_years"] = max(ins_data.get("term_life_pay_years", 0), tl_pay_years)
                ci_cov = float(m.get("critical_illness_coverage", 0))
                ci_premium = float(m.get("critical_illness_premium", 0))
                ci_pay_years = int(m.get("critical_illness_pay_years", 0))
                if ci_cov > 0 or ci_premium > 0:
                    ins_data["ci_cov"] += ci_cov
                    ins_data["ci_premium"] += ci_premium
                    ins_data["ci_pay_years"] = max(ins_data.get("ci_pay_years", 0), ci_pay_years)
                medical_premium = float(m.get("medical_premium", 0))
                medical_pay_years = int(m.get("medical_pay_years", 0))
                if m.get("medical_covered") or medical_premium > 0:
                    if m.get("medical_covered"):
                        ins_data["medical_covered"] = True
                    ins_data["medical_premium"] += medical_premium
                    ins_data["medical_pay_years"] = max(ins_data.get("medical_pay_years", 0), medical_pay_years)
                hci_cov = float(m.get("hci_coverage", 0))
                hci_premium = float(m.get("hci_premium", 0))
                hci_pay_years = int(m.get("hci_pay_years", 0))
                if hci_cov > 0 or hci_premium > 0:
                    ins_data["hci_cov"] += hci_cov
                    ins_data["hci_premium"] += hci_premium
                    ins_data["hci_pay_years"] = max(ins_data.get("hci_pay_years", 0), hci_pay_years)
                other_insurance_premium = float(m.get("other_insurance_premium", 0))
                other_insurance_pay_years = int(m.get("other_insurance_pay_years", 0))
                if other_insurance_premium > 0:
                    ins_data["other_premium"] += other_insurance_premium
                    ins_data["other_pay_years"] = max(ins_data.get("other_pay_years", 0), other_insurance_pay_years)

                # 逐人医疗参数
                hc_start_member = float(m.get("healthcare_starting_annual", 0))
                hc_growth_member = float(m.get("healthcare_growth_rate", 0.05))
                hc_cap_member = float(m.get("healthcare_annual_cap", 0))
                rr_member = float(rr) if rr is not None else 0.0

                retirement_year_val = (current_year or 0) + retire_age_val - age

                members_list.append(Member(
                    name=name, age=age, role=role,
                    annual_income=annual_income_val,
                    income_start_age=income_start_age_val,
                    income_start_annual=income_start_annual_val,
                    monthly_expense=monthly_expense_val,
                    retirement_age=retire_age_val,
                    retirement_year=retirement_year_val,
                    retirement_pension=ret_pension_val,
                    retirement_annuity=ret_annuity_val,
                    retirement_expense_coeff=coeff,
                    term_life_coverage=tl_cov,
                    term_life_premium=tl_premium,
                    term_life_pay_years=tl_pay_years,
                    critical_illness_coverage=ci_cov,
                    critical_illness_premium=ci_premium,
                    critical_illness_pay_years=ci_pay_years,
                    medical_covered=bool(m.get("medical_covered", False)),
                    medical_premium=medical_premium,
                    medical_pay_years=medical_pay_years,
                    hci_coverage=hci_cov,
                    hci_premium=hci_premium,
                    hci_pay_years=hci_pay_years,
                    other_insurance_premium=other_insurance_premium,
                    other_insurance_pay_years=other_insurance_pay_years,
                    healthcare_starting_annual=hc_start_member,
                    healthcare_growth_rate=hc_growth_member,
                    healthcare_annual_cap=hc_cap_member,
                    reimbursement_rate=rr_member,
                ))

    # 兼容旧格式: 直接从 income 读取
    if total_annual == 0 and isinstance(income_raw, dict):
        for src in income_raw.get("sources", []):
            if isinstance(src, dict):
                total_annual += float(src.get("annual_amount", 0))
        if total_annual == 0:
            total_annual = float(income_raw.get("total_annual_income", 0))
    if monthly_living == 0 and isinstance(income_raw, dict):
        monthly_living = float(income_raw.get("monthly_living_expense", 0))
    if isinstance(income_raw, dict):
        household_extra_monthly = float(income_raw.get("household_extra_monthly_expense", 0))
        monthly_living += household_extra_monthly

    # 退休后收支 (优先使用 member 逐人数据, 兼容旧格式)
    ret = income_raw.get("retirement", {}) if isinstance(income_raw, dict) else {}
    if ret_pension == 0:
        ret_pension = float(ret.get("monthly_pension", 0))
    if ret_annuity == 0:
        ret_annuity = float(ret.get("monthly_annuity", 0))
    if ret_expense == 0:
        ret_expense = float(ret.get("monthly_expense", 0))
    # 退休后医疗与疾病支出
    hc = ret.get("healthcare", {}) if isinstance(ret, dict) else {}
    hc_start = float(hc.get("starting_annual", 0))
    hc_growth = float(hc.get("growth_rate", 0.05))
    hc_cap = float(hc.get("annual_cap", 0))

    # 月度负债还款
    monthly_liab = 0.0
    liability_end_year = 0
    if isinstance(assets, dict):
        for liab in assets.get("liabilities", []):
            if isinstance(liab, dict):
                monthly_liab += float(liab.get("monthly_payment", 0))
                ry = int(liab.get("remaining_years", 0))
                if ry > 0:
                    end_yr = (current_year or 0) + ry
                    if end_yr > liability_end_year:
                        liability_end_year = end_yr

    # 流动性储备月数: 若未明确录入,默认 6 个月
    liquidity = float(assets.get("liquidity_reserve_months", 6)) if isinstance(assets, dict) else 6.0

    # 资产存量(问卷用 flat total_value, 完整格式用子分类累加)
    total_fin = 0.0
    if isinstance(assets, dict):
        fin = assets.get("financial", {})
        if isinstance(fin, dict):
            if "total_value" in fin and not any(c in fin for c in ("fixed_income", "equity", "alternatives")):
                total_fin = float(fin["total_value"])
            else:
                for _cat in ("fixed_income", "equity", "alternatives"):
                    sub = fin.get(_cat, {})
                    if isinstance(sub, dict):
                        total_fin += float(sub.get("total_value", 0))
                ins = fin.get("insurance", {})
                if isinstance(ins, dict):
                    pass  # 储蓄险不纳入可投资资产

    # 保险详情 (合并 assets.financial.insurance 作为成员数据的补充/回退)
    parsed = _parse_insurance(assets)
    # 成员数据优先; 成员未填写时回退到 assets 格式
    for k in ("term_life_cov", "term_life_premium", "term_life_pay_years",
              "ci_cov", "ci_premium", "ci_pay_years",
              "medical_covered", "medical_premium", "medical_pay_years",
              "hci_cov", "hci_premium", "hci_pay_years",
              "other_premium", "other_pay_years"):
        if ins_data.get(k, 0) == 0 or k == "medical_covered":
            if k in parsed and (k != "medical_covered" or parsed.get(k)):
                ins_data[k] = parsed[k]
    # 总保费
    ins_data["total_premium"] = (ins_data["term_life_premium"]
                                 + ins_data["ci_premium"]
                                 + ins_data["medical_premium"])
    # 储蓄险 (多行, 来自问卷动态列表)
    fin_dict = assets.get("financial", {}) if isinstance(assets, dict) else {}
    savings_raw = fin_dict.get("savings", []) if isinstance(fin_dict, dict) else []
    savings = tuple(
        {"amount": float(s["amount"]), "premium": float(s.get("premium", 0)),
         "pay_years": int(s.get("pay_years", 0)), "linked_account": str(s.get("linked_account", ""))}
        for s in savings_raw if isinstance(s, dict) and s.get("amount", 0) > 0
    )
    ins_data["total_premium"] = (
        ins_data["term_life_premium"]
        + ins_data["ci_premium"]
        + ins_data["medical_premium"]
        + ins_data["hci_premium"]
        + ins_data["other_premium"]
        + sum(item["premium"] for item in savings)
    )

    # 赔付率: 从成员逐人读取(取最大值),回退到 assumptions.projection
    raw_asm = raw.get("assumptions", {})
    hc_reimb = 0.0
    if hc_start > 0:
        hc_reimb = float(hc.get("reimbursement_rate", 0))
    elif member_reimb_rates:
        hc_reimb = max(member_reimb_rates)
    elif isinstance(raw_asm, dict):
        proj = raw_asm.get("projection", {})
        if isinstance(proj, dict):
            hc_reimb = float(proj.get("reimbursement_rate", 0))
    # 有医疗险且未设赔付率时默认 0.80
    if hc_reimb == 0 and ins_data.get("medical_covered"):
        hc_reimb = 0.80

    # 重疾保险规划 (已移除策略选择, 仅保留兼容)
    prot = raw.get("protection", {})
    ci_raw = prot.get("critical_illness", {}) if isinstance(prot, dict) else {}

    total_re = 0.0
    total_debt = 0.0
    if isinstance(assets, dict):
        re = assets.get("real_estate", {})
        if isinstance(re, dict):
            pr = re.get("primary_residence", {})
            if isinstance(pr, dict):
                total_re += float(pr.get("estimated_value", 0))
        for liab in assets.get("liabilities", []):
            if isinstance(liab, dict):
                total_debt += float(liab.get("outstanding", 0))

    # 推演假设(可选)
    assumptions = raw.get("assumptions")
    measurement_end_year = effective_current_year + 30
    if isinstance(assumptions, dict):
        projection = assumptions.get("projection", {})
        if isinstance(projection, dict) and projection.get("measurement_end_year") is not None:
            measurement_end_year = int(projection["measurement_end_year"])
    measurement_end_year = max(measurement_end_year, effective_current_year, last_event_year)

    return ClientProfile(
        profile_version=str(raw["profile_version"]),
        schema_version=str(raw["schema_version"]),
        family_name=_family_name(family),
        current_year=effective_current_year,
        measurement_end_year=measurement_end_year,
        events=events,
        risk_preference=risk,
        total_annual_income=total_annual,
        monthly_living_expense=monthly_living,
        household_extra_monthly_expense=household_extra_monthly,
        monthly_liabilities=monthly_liab,
        liquidity_reserve_months=liquidity,
        total_financial_assets=total_fin,
        total_real_estate_value=total_re,
        total_outstanding_debt=total_debt,
        insurance_term_life_cov=ins_data.get("term_life_cov", 0.0),
        insurance_term_life_premium=ins_data.get("term_life_premium", 0.0),
        insurance_critical_illness_cov=ins_data.get("ci_cov", 0.0),
        insurance_critical_illness_premium=ins_data.get("ci_premium", 0.0),
        insurance_medical_covered=ins_data.get("medical_covered", False),
        insurance_medical_premium=ins_data.get("medical_premium", 0.0),
        insurance_total_annual_premium=ins_data.get("total_premium", 0.0),
        retirement_monthly_pension=ret_pension,
        retirement_monthly_annuity=ret_annuity,
        retirement_monthly_expense=ret_expense,
        healthcare_starting_annual=hc_start,
        healthcare_growth_rate=hc_growth,
        healthcare_annual_cap=hc_cap,
        healthcare_reimbursement_rate=hc_reimb,
        primary_breadwinner_birth_year=effective_current_year - _primary_age(family),
        primary_breadwinner_retirement_age=breadwinner_retire_age,
        remaining_liability_end_year=liability_end_year,
        members=tuple(members_list),
        insurance_term_life_pay_years=ins_data.get("term_life_pay_years", 0),
        insurance_critical_illness_pay_years=ins_data.get("ci_pay_years", 0),
        insurance_medical_pay_years=ins_data.get("medical_pay_years", 0),
        savings=savings,
        assumptions=assumptions,
    )
