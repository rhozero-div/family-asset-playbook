"""客户档案 YAML 校验脚本。

校验 AGENT 产出的 YAML 是否符合 FAPM 输入 schema,
失败时给出可读的修复建议。

用法:
    python tools/validate_collected_profile.py <yaml-path>

退出码:
    0 通过
    1 失败
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_TOP_LEVEL = {
    "profile_version",
    "schema_version",
    "family",
    "events",
}

VALID_EVENT_TYPES = {"housing", "education", "retirement", "health", "legacy", "other"}
VALID_HEALTH = {"good", "fair", "poor"}
VALID_ROLE = {
    "primary_breadwinner",
    "secondary_breadwinner",
    "dependent",
    "dependent_elder",
    "other",
}
VALID_COST_OF_LIVING = {"low", "medium", "high"}
VALID_INCOME_TYPE = {"salary", "business", "property", "other"}
VALID_INCOME_STABILITY = {"stable", "variable", "declining"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_INHERITANCE_TIMING = {"near", "medium", "far", "uncertain"}
VALID_RISK_TOLERANCE = {"conservative", "balanced", "aggressive"}
VALID_KNOWLEDGE = {"low", "medium", "high"}
VALID_LIABILITY_TYPE = {"mortgage", "consumer_loan", "business_loan", "other"}


def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        sys.exit("需要 PyYAML,请运行: pip install pyyaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _validate(data: dict, path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, [f"{path} 顶层应为字典,实际为 {type(data).__name__}"]

    # 必填顶层
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"缺少顶层字段: {sorted(missing)}")

    # family
    family = data.get("family", {})
    if not isinstance(family, dict):
        family = {}
    members = family.get("members", [])
    member_names: set[str] = set()
    for i, m in enumerate(members):
        if not isinstance(m, dict):
            continue
        if "name" not in m:
            errors.append(f"family.members[{i}] 缺 'name'")
        else:
            member_names.add(m["name"])
        if "age" not in m:
            errors.append(f"family.members[{i}] 缺 'age'")
        if "role" not in m:
            errors.append(f"family.members[{i}] 缺 'role'")
        elif m["role"] not in VALID_ROLE:
            errors.append(
                f"family.members[{i}].role '{m['role']}' 不在 {sorted(VALID_ROLE)}"
            )
        if "health" in m and m["health"] not in VALID_HEALTH:
            errors.append(
                f"family.members[{i}].health '{m['health']}' 不在 {sorted(VALID_HEALTH)}"
            )
    col = family.get("cost_of_living_level")
    if col and col not in VALID_COST_OF_LIVING:
        errors.append(
            f"family.cost_of_living_level '{col}' 不在 {sorted(VALID_COST_OF_LIVING)}"
        )

    # income
    income = data.get("income", {})
    if isinstance(income, dict):
        sources = income.get("sources", [])
        for i, s in enumerate(sources):
            if not isinstance(s, dict):
                continue
            if "type" not in s:
                errors.append(f"income.sources[{i}] 缺 'type'")
            elif s["type"] not in VALID_INCOME_TYPE:
                errors.append(
                    f"income.sources[{i}].type '{s['type']}' 不在 {sorted(VALID_INCOME_TYPE)}"
                )
            if (
                "owner" in s
                and s["owner"] not in member_names
                and member_names
            ):
                errors.append(
                    f"income.sources[{i}].owner '{s['owner']}' 不在 family.members 中"
                )
            if "stability" in s and s["stability"] not in VALID_INCOME_STABILITY:
                errors.append(
                    f"income.sources[{i}].stability '{s['stability']}' 不在 {sorted(VALID_INCOME_STABILITY)}"
                )
        exp = income.get("expectations", {})
        if isinstance(exp, dict) and "confidence" in exp:
            if exp["confidence"] not in VALID_CONFIDENCE:
                errors.append(
                    f"income.expectations.confidence '{exp['confidence']}' 不在 {sorted(VALID_CONFIDENCE)}"
                )

    # events
    events = data.get("events", [])
    if not isinstance(events, list):
        errors.append("events 应为数组")
        events = []
    seen_ids: set[str] = set()
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        ctx = f"events[{i}]"
        if "id" not in e:
            errors.append(f"{ctx} 缺 'id'")
        elif e["id"] in seen_ids:
            errors.append(f"{ctx}.id '{e['id']}' 重复")
        else:
            seen_ids.add(e["id"])
        if "type" not in e:
            errors.append(f"{ctx} 缺 'type'")
        elif e["type"] not in VALID_EVENT_TYPES:
            errors.append(
                f"{ctx}.type '{e['type']}' 不在 {sorted(VALID_EVENT_TYPES)}"
            )
        if "description" not in e:
            errors.append(f"{ctx} 缺 'description'")
        if "timing_year" not in e:
            errors.append(f"{ctx} 缺 'timing_year'")
        elif not isinstance(e["timing_year"], int):
            errors.append(f"{ctx}.timing_year 应为整数")
        if "certainty" in e and e["certainty"] not in {"high", "medium", "low"}:
            errors.append(
                f"{ctx}.certainty '{e['certainty']}' 不在 {sorted({'high', 'medium', 'low'})}"
            )

    projection = data.get("assumptions", {}).get("projection", {}) if isinstance(data.get("assumptions"), dict) else {}
    measurement_end_year = projection.get("measurement_end_year") if isinstance(projection, dict) else None
    if measurement_end_year is not None:
        if not isinstance(measurement_end_year, int):
            errors.append("assumptions.projection.measurement_end_year 应为整数")
        else:
            last_event_year = max(
                (e.get("timing_year") for e in events if isinstance(e, dict) and isinstance(e.get("timing_year"), int)),
                default=None,
            )
            if last_event_year is not None and measurement_end_year < last_event_year:
                errors.append(
                    f"assumptions.projection.measurement_end_year={measurement_end_year} 不能早于最后一个事件年份 {last_event_year}"
                )

    # assets
    assets = data.get("assets", {})
    if isinstance(assets, dict):
        overseas = assets.get("overseas_module_enabled")
        if overseas is not None and not isinstance(overseas, bool):
            errors.append(
                f"assets.overseas_module_enabled 应为 bool,实际 {type(overseas).__name__}"
            )
        if overseas is True and "overseas" not in assets:
            errors.append(
                "assets.overseas_module_enabled=true 但缺 assets.overseas 字段"
            )
        # 保险子字段校验
        for loc, ins_data in _iter_insurance(assets):
            _validate_insurance(ins_data, loc, errors)
        liquidity = assets.get("liquidity_reserve_months")
        if liquidity is not None and not isinstance(liquidity, (int, float)):
            errors.append("assets.liquidity_reserve_months 应为数字")

    # advisor_assessment (可选,但若存在需校验)
    adv = data.get("advisor_assessment", {})
    if isinstance(adv, dict):
        if "risk_tolerance" in adv and adv["risk_tolerance"] not in VALID_RISK_TOLERANCE:
            errors.append(
                f"advisor_assessment.risk_tolerance '{adv['risk_tolerance']}' 不在 {sorted(VALID_RISK_TOLERANCE)}"
            )
        if "knowledge_level" in adv and adv["knowledge_level"] not in VALID_KNOWLEDGE:
            errors.append(
                f"advisor_assessment.knowledge_level '{adv['knowledge_level']}' 不在 {sorted(VALID_KNOWLEDGE)}"
            )

    return len(errors) == 0, errors


def _iter_insurance(assets: dict) -> list[tuple[str, dict]]:
    """遍历境内+海外保险数据,返回 [(位置标签, 保险字典)]。"""
    results = []
    fin = assets.get("financial", {})
    if isinstance(fin, dict) and isinstance(fin.get("insurance"), dict):
        results.append(("assets.financial.insurance", fin["insurance"]))
    ov = assets.get("overseas", {})
    if isinstance(ov, dict) and isinstance(ov.get("insurance"), dict):
        results.append(("assets.overseas.insurance", ov["insurance"]))
    return results


def _validate_insurance(ins: dict, loc: str, errors: list[str]) -> None:
    opts = ("term_life_coverage", "term_life_premium",
            "critical_illness_coverage", "critical_illness_premium",
            "savings_value", "savings_premium", "medical_premium")
    for key in opts:
        val = ins.get(key)
        if val is not None and not isinstance(val, (int, float)):
            errors.append(f"{loc}.{key} 应为数字")
        elif val is not None and val < 0:
            errors.append(f"{loc}.{key} = {val}, 应为非负数")
    mc = ins.get("medical_covered")
    if mc is not None and not isinstance(mc, bool):
        errors.append(f"{loc}.medical_covered 应为 bool 类型")


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("用法: python tools/validate_collected_profile.py <yaml-path>")

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 1

    try:
        data = _load_yaml(path)
    except Exception as e:
        print(f"YAML 解析失败: {e}", file=sys.stderr)
        return 1

    ok, errors = _validate(data, path)
    if ok:
        members = (
            data.get("family", {}).get("members", [])
            if isinstance(data.get("family"), dict)
            else []
        )
        events = data.get("events", []) if isinstance(data.get("events"), list) else []
        print(
            f"OK: {path.name} 通过校验, {len(members)} 个家庭成员, {len(events)} 个事件"
        )
        return 0

    print(f"ERROR: {path.name} 有 {len(errors)} 处问题:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
