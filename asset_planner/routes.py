"""资产规划原型网页路由。"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from asset_planner.logic import analyze_yaml_text
from web.runtime import server_storage_enabled
from web.storage_paths import PROJECT_ROOT, sample_profile_path, storage_dir
from web.yaml_handler import read_clients

templates = Jinja2Templates(directory=str(PROJECT_ROOT / "asset_planner" / "templates"))
templates.env.globals["asset_version"] = "20260702-01"

router = APIRouter()


def _ctx(
    request: Request,
    *,
    yaml_content: str = "",
    current_year: int = 2026,
    error: str = "",
    sample_name: str = "",
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
        "client_code": client_code,
    }


@router.get("/asset-planner", response_class=HTMLResponse)
async def asset_planner_home(request: Request):
    return templates.TemplateResponse(request, "form.html", _ctx(request))


@router.get("/asset-planner/sample-wang", response_class=HTMLResponse)
async def asset_planner_sample_wang(request: Request):
    sample_path = sample_profile_path()
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="示例档案不存在")
    yaml_text = sample_path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        request,
        "form.html",
        _ctx(request, yaml_content=yaml_text, sample_name="王先生示例"),
    )


@router.get("/asset-planner/load/{code}", response_class=HTMLResponse)
async def asset_planner_load(request: Request, code: str):
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


@router.post("/asset-planner/analyze", response_class=HTMLResponse)
async def asset_planner_analyze(
    request: Request,
    yaml_content: str = Form(default=""),
    yaml_file: UploadFile | None = File(default=None),
    current_year: int = Form(default=2026),
    client_code: str = Form(default=""),
):
    yaml_text = yaml_content or ""
    if yaml_file and yaml_file.filename:
        yaml_text = (await yaml_file.read()).decode("utf-8", errors="replace")

    if not yaml_text.strip():
        return templates.TemplateResponse(
            request,
            "form.html",
            _ctx(request, yaml_content=yaml_text, current_year=current_year, error="请先粘贴或上传问卷 YAML。", client_code=client_code),
            status_code=400,
        )

    try:
        result = analyze_yaml_text(yaml_text, current_year=current_year)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "form.html",
            _ctx(request, yaml_content=yaml_text, current_year=current_year, error=str(exc), client_code=client_code),
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
        },
    )
