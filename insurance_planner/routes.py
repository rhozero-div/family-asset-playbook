"""保险规划原型网页路由。"""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from insurance_planner.logic import PlanningPreferences, analyze_yaml_text
from web.markdown_renderer import render_markdown
from web.runtime import server_storage_enabled
from web.storage_paths import PROJECT_ROOT, sample_profile_path, storage_dir
from web.yaml_handler import _family_name, generate_playbook_from_yaml, read_clients

templates = Jinja2Templates(directory=str(PROJECT_ROOT / "insurance_planner" / "templates"))
playbook_templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web" / "templates"))
templates.env.globals["asset_version"] = "20260701-01"
playbook_templates.env.globals["asset_version"] = "20260630-03"
playbook_templates.env.globals["storage_enabled"] = server_storage_enabled()
playbook_templates.env.globals["lang_attr"] = lambda lang: "en" if lang == "en" else "zh-CN"

router = APIRouter()


def _optional_float(value: str | float | int | None, field_label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field_label} 请输入有效数字。") from exc


def _ctx(
    request: Request,
    *,
    yaml_content: str = "",
    current_year: int = 2026,
    error: str = "",
    sample_name: str = "",
    form_values: dict | None = None,
    client_code: str = "",
) -> dict:
    clients = read_clients() if server_storage_enabled() else []
    return {
        "request": request,
        "yaml_content": yaml_content,
        "current_year": current_year,
        "error": error,
        "sample_name": sample_name,
        "clients": clients,
        "storage_enabled": server_storage_enabled(),
        "form_values": form_values or {},
        "client_code": client_code,
    }


def _chart_payload(result) -> list[dict]:
    items: list[dict] = []
    for view in result.member_views:
        items.append(
            {
                "member_name": view.member_name,
                "member_role": view.member_role,
                "coverage_labels": ["定寿", "重疾", "高端医疗"],
                "current_coverage": [view.current_term_coverage, view.current_ci_coverage, view.current_hci_coverage],
                "target_coverage": [view.target_term_coverage, view.target_ci_coverage, view.target_hci_coverage],
                "plan_a_coverage": [view.plan_a_term_coverage, view.plan_a_ci_coverage, view.plan_a_hci_coverage],
                "plan_b_coverage": [view.plan_b_term_coverage, view.plan_b_ci_coverage, view.plan_b_hci_coverage],
                "premium_labels": ["定寿", "重疾", "医疗报销", "高端医疗"],
                "current_premium_by_product": [
                    view.current_term_premium,
                    view.current_ci_premium,
                    view.current_medical_premium,
                    view.current_hci_premium,
                ],
                "target_premium_by_product": [
                    view.target_term_premium,
                    view.target_ci_premium,
                    view.target_medical_premium,
                    view.target_hci_premium,
                ],
                "plan_a_premium_by_product": [
                    view.plan_a_term_premium,
                    view.plan_a_ci_premium,
                    view.plan_a_medical_premium,
                    view.plan_a_hci_premium,
                ],
                "plan_b_premium_by_product": [
                    view.plan_b_term_premium,
                    view.plan_b_ci_premium,
                    view.plan_b_medical_premium,
                    view.plan_b_hci_premium,
                ],
                "current_total_premium": view.current_annual_premium,
                "plan_a_total_premium": view.plan_a_annual_premium,
                "plan_b_total_premium": view.plan_b_annual_premium,
                "medical_current": view.medical_current,
                "medical_target": view.medical_target,
                "medical_plan_a": view.medical_plan_a,
                "medical_plan_b": view.medical_plan_b,
            }
        )
    return items


def _optional_int(value: str | int | None, field_label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_label} 请输入有效整数。") from exc


def _recommendation_rows(result, scenario_key: str) -> list[dict]:
    horizon_years = max(result.profile.measurement_end_year - result.profile.current_year + 1, 1)
    member_lookup = {member.name: member for member in result.profile.members}
    rows: list[dict] = []
    for idx, view in enumerate(result.member_views):
        member = member_lookup.get(view.member_name)
        term_target = view.plan_a_term_coverage if scenario_key == "core" else view.plan_b_term_coverage
        ci_target = view.plan_a_ci_coverage if scenario_key == "core" else view.plan_b_ci_coverage
        hci_target = view.plan_a_hci_coverage if scenario_key == "core" else view.plan_b_hci_coverage
        medical_target = view.medical_plan_a if scenario_key == "core" else view.medical_plan_b
        term_add = max(term_target - view.current_term_coverage, 0.0)
        ci_add = max(ci_target - view.current_ci_coverage, 0.0)
        hci_add = max(hci_target - view.current_hci_coverage, 0.0)
        medical_add = bool(medical_target and not view.medical_current)
        term_years = ""
        if member and term_add > 0:
            term_years = str(max(min(member.retirement_age - member.age, horizon_years), 1))
        ci_years = str(max(min(20, horizon_years), 1)) if ci_add > 0 else ""
        medical_years = str(horizon_years) if medical_add else ""
        hci_years = str(horizon_years) if hci_add > 0 else ""
        rows.append(
            {
                "idx": idx,
                "member_name": view.member_name,
                "member_role": view.member_role,
                "medical_add": medical_add,
                "medical_pay_years": medical_years,
                "term_cov": int(term_add) if term_add > 0 else 0,
                "term_pay_years": term_years,
                "ci_cov": int(ci_add) if ci_add > 0 else 0,
                "ci_pay_years": ci_years,
                "hci_cov": int(hci_add) if hci_add > 0 else 0,
                "hci_pay_years": hci_years,
                "current_medical": view.medical_current,
                "current_term": int(view.current_term_coverage),
                "current_ci": int(view.current_ci_coverage),
                "current_hci": int(view.current_hci_coverage),
            }
        )
    return rows


def _merge_overlay_value(member: dict, key: str, amount: float) -> None:
    if amount <= 0:
        return
    member[key] = float(member.get(key, 0) or 0) + amount


def _merge_overlay_years(member: dict, key: str, years: int | None) -> None:
    if years is None or years <= 0:
        return
    member[key] = max(int(member.get(key, 0) or 0), years)


def _apply_incremental_recommendation(yaml_text: str, form_data, scenario_key: str) -> str:
    import yaml

    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError("问卷 YAML 结构无效。")
    family = data.get("family")
    if not isinstance(family, dict):
        raise ValueError("问卷 YAML 缺少 family.members。")
    members = family.get("members")
    if not isinstance(members, list):
        raise ValueError("问卷 YAML 缺少 family.members。")

    prefix = "plan_a" if scenario_key == "core" else "plan_b"
    for idx, member in enumerate(members):
        if not isinstance(member, dict):
            continue
        base = f"{prefix}_{idx}_"
        medical_flag = str(form_data.get(base + "medical", "")).strip().lower()
        if medical_flag == "true":
            member["medical_covered"] = True

        term_cov = _optional_float(form_data.get(base + "term_cov"), "定寿保额") or 0.0
        term_premium = _optional_float(form_data.get(base + "term_premium"), "定寿年保费") or 0.0
        term_years = _optional_int(form_data.get(base + "term_pay_years"), "定寿剩余缴费年数")
        _merge_overlay_value(member, "term_life_coverage", term_cov)
        _merge_overlay_value(member, "term_life_premium", term_premium)
        _merge_overlay_years(member, "term_life_pay_years", term_years)

        ci_cov = _optional_float(form_data.get(base + "ci_cov"), "重疾保额") or 0.0
        ci_premium = _optional_float(form_data.get(base + "ci_premium"), "重疾年保费") or 0.0
        ci_years = _optional_int(form_data.get(base + "ci_pay_years"), "重疾剩余缴费年数")
        _merge_overlay_value(member, "critical_illness_coverage", ci_cov)
        _merge_overlay_value(member, "critical_illness_premium", ci_premium)
        _merge_overlay_years(member, "critical_illness_pay_years", ci_years)

        medical_premium = _optional_float(form_data.get(base + "medical_premium"), "医疗年保费") or 0.0
        medical_years = _optional_int(form_data.get(base + "medical_pay_years"), "医疗剩余缴费年数")
        _merge_overlay_value(member, "medical_premium", medical_premium)
        _merge_overlay_years(member, "medical_pay_years", medical_years)

        hci_cov = _optional_float(form_data.get(base + "hci_cov"), "高端医疗保额") or 0.0
        hci_premium = _optional_float(form_data.get(base + "hci_premium"), "高端医疗年保费") or 0.0
        hci_years = _optional_int(form_data.get(base + "hci_pay_years"), "高端医疗剩余缴费年数")
        _merge_overlay_value(member, "hci_coverage", hci_cov)
        _merge_overlay_value(member, "hci_premium", hci_premium)
        _merge_overlay_years(member, "hci_pay_years", hci_years)

    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


@router.get("/insurance-planner", response_class=HTMLResponse)
async def insurance_planner_home(request: Request):
    return templates.TemplateResponse(
        request,
        "form.html",
        _ctx(request),
    )


@router.get("/insurance-planner/sample-wang", response_class=HTMLResponse)
async def insurance_planner_sample_wang(request: Request):
    sample_path = sample_profile_path()
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="示例档案不存在")
    yaml_text = sample_path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        request,
        "form.html",
        _ctx(request, yaml_content=yaml_text, sample_name="王先生示例"),
    )


@router.get("/insurance-planner/load/{code}", response_class=HTMLResponse)
async def insurance_planner_load(request: Request, code: str):
    if not server_storage_enabled():
        raise HTTPException(status_code=404, detail="演示模式不开放已保存问卷")
    clients = read_clients()
    entry = next((c for c in clients if c["code"] == code), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"未找到客户: {code}")
    yaml_path = storage_dir() / entry["yaml_file"]
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="客户档案文件不存在")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        request,
        "form.html",
        _ctx(request, yaml_content=yaml_text, sample_name=f"{entry['name']}（{code}）", client_code=code),
    )


@router.post("/insurance-planner/analyze", response_class=HTMLResponse)
async def insurance_planner_analyze(
    request: Request,
    yaml_content: str = Form(default=""),
    yaml_file: UploadFile | None = File(default=None),
    current_year: int = Form(default=2026),
    client_code: str = Form(default=""),
    manual_premium_cap_annual: str | None = Form(default=None),
    auto_budget_ratio_pct: str | None = Form(default=None),
    term_multiplier_with_dependents: float = Form(default=7.0),
    term_multiplier_without_dependents: float = Form(default=4.0),
    ci_income_multiple: float = Form(default=3.0),
    ci_expense_years: float = Form(default=5.0),
    child_ci_target: float = Form(default=300000.0),
    elder_ci_target: float = Form(default=300000.0),
    include_hci_upgrade: str = Form(default="true"),
):
    yaml_text = yaml_content or ""
    if yaml_file and yaml_file.filename:
        yaml_text = (await yaml_file.read()).decode("utf-8", errors="replace")

    try:
        manual_premium_cap_annual_value = _optional_float(manual_premium_cap_annual, "总年保费上限")
        auto_budget_ratio_pct_value = _optional_float(auto_budget_ratio_pct, "自动预算比例")
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "form.html",
            _ctx(
                request,
                yaml_content=yaml_text,
                current_year=current_year,
                error=str(exc),
                client_code=client_code,
                form_values={
                    "manual_premium_cap_annual": manual_premium_cap_annual,
                    "auto_budget_ratio_pct": auto_budget_ratio_pct,
                    "term_multiplier_with_dependents": term_multiplier_with_dependents,
                    "term_multiplier_without_dependents": term_multiplier_without_dependents,
                    "ci_income_multiple": ci_income_multiple,
                    "ci_expense_years": ci_expense_years,
                    "child_ci_target": child_ci_target,
                    "elder_ci_target": elder_ci_target,
                    "include_hci_upgrade": include_hci_upgrade,
                },
            ),
            status_code=400,
        )

    form_values = {
        "manual_premium_cap_annual": manual_premium_cap_annual or "",
        "auto_budget_ratio_pct": auto_budget_ratio_pct or "",
        "term_multiplier_with_dependents": term_multiplier_with_dependents,
        "term_multiplier_without_dependents": term_multiplier_without_dependents,
        "ci_income_multiple": ci_income_multiple,
        "ci_expense_years": ci_expense_years,
        "child_ci_target": child_ci_target,
        "elder_ci_target": elder_ci_target,
        "include_hci_upgrade": include_hci_upgrade,
    }

    if not yaml_text.strip():
        return templates.TemplateResponse(
            request,
            "form.html",
            _ctx(request, yaml_content=yaml_text, current_year=current_year, error="请先粘贴或上传问卷 YAML。", form_values=form_values, client_code=client_code),
            status_code=400,
        )

    preferences = PlanningPreferences(
        manual_premium_cap_annual=manual_premium_cap_annual_value,
        auto_budget_ratio=(auto_budget_ratio_pct_value / 100.0) if auto_budget_ratio_pct_value is not None else None,
        term_multiplier_with_dependents=term_multiplier_with_dependents,
        term_multiplier_without_dependents=term_multiplier_without_dependents,
        ci_income_multiple=ci_income_multiple,
        ci_expense_years=ci_expense_years,
        child_ci_target=child_ci_target,
        elder_ci_target=elder_ci_target,
        include_hci_upgrade=(include_hci_upgrade != "false"),
    )

    try:
        result = analyze_yaml_text(yaml_text, current_year=current_year, preferences=preferences)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "form.html",
            _ctx(request, yaml_content=yaml_text, current_year=current_year, error=str(exc), form_values=form_values, client_code=client_code),
            status_code=400,
        )

    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "request": request,
            "result": result,
            "yaml_content": yaml_text,
            "current_year": current_year,
            "client_code": client_code,
            "chart_payload": json.dumps(_chart_payload(result), ensure_ascii=False),
            "needs_json": json.dumps(
                [
                    {
                        "member": need.member_name,
                        "product": need.product_label,
                        "priority": need.priority_rank,
                        "current": need.current_coverage,
                        "target": need.target_coverage,
                        "premium": need.full_additional_annual_premium,
                    }
                    for need in result.needs
                ],
                ensure_ascii=False,
            ),
        },
    )


@router.post("/insurance-planner/recommendation", response_class=HTMLResponse)
async def insurance_recommendation(
    request: Request,
    yaml_content: str = Form(default=""),
    yaml_file: UploadFile | None = File(default=None),
    current_year: int = Form(default=2026),
    client_code: str = Form(default=""),
    focus_plan: str = Form(default="core"),
    lang: str = Form(default="zh"),
):
    yaml_text = yaml_content or ""
    if yaml_file and yaml_file.filename:
        yaml_text = (await yaml_file.read()).decode("utf-8", errors="replace")
    if not yaml_text.strip():
        raise HTTPException(status_code=400, detail="请先提供问卷 YAML。")

    try:
        result = analyze_yaml_text(yaml_text, current_year=current_year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return templates.TemplateResponse(
        request,
        "apply.html",
        {
            "request": request,
            "result": result,
            "yaml_content": yaml_text,
            "current_year": current_year,
            "client_code": client_code,
            "lang": "en" if lang == "en" else "zh",
            "focus_plan": "balanced" if focus_plan == "balanced" else "core",
            "plan_a_rows": _recommendation_rows(result, "core"),
            "plan_b_rows": _recommendation_rows(result, "balanced"),
        },
    )


@router.post("/insurance-planner/recalculate", response_class=HTMLResponse)
async def insurance_recalculate(
    request: Request,
):
    form = await request.form()
    yaml_text = str(form.get("yaml_content", "") or "")
    current_year = int(form.get("current_year", 2026) or 2026)
    client_code = str(form.get("client_code", "") or "")
    lang = "en" if str(form.get("lang", "zh")) == "en" else "zh"
    scenario_key = "balanced" if str(form.get("scenario_key", "core")) == "balanced" else "core"
    if not yaml_text.strip():
        raise HTTPException(status_code=400, detail="请先提供问卷 YAML。")

    merged_yaml = _apply_incremental_recommendation(yaml_text, form, scenario_key)
    ok, playbook_md, error = generate_playbook_from_yaml(merged_yaml, current_year=current_year, lang=lang)
    if not ok:
        raise HTTPException(status_code=400, detail=error)
    return playbook_templates.TemplateResponse(
        request,
        "playbook.html",
        {
            "request": request,
            "playbook_md": playbook_md,
            "playbook_html": render_markdown(playbook_md),
            "yaml_content": merged_yaml,
            "current_year": current_year,
            "client_code": client_code,
            "client_name": _family_name(merged_yaml),
            "lang": lang,
        },
    )
