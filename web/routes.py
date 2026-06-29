"""路由定义。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.markdown_renderer import render_markdown
from web.yaml_handler import (
    save_yaml_and_generate,
    save_yaml_only,
    read_clients,
    update_client,
    next_client_code,
    _family_name,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PROJECT_ROOT / "profiles"

templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web" / "templates"))
templates.env.globals["asset_version"] = "20260629-11"

router = APIRouter()


def _qi(  # noqa: PLR0913
    request: Request,
    *,
    yaml_content: str = "",
    current_year: int = 2026,
    error: str = "",
    success: str = "",
    client_code: str = "",
    force_prefill: bool = False,
    sample_data_json: str = "{}",
) -> dict:
    """问卷模板 context 快捷构造。"""
    return {
        "request": request,
        "yaml_content": yaml_content,
        "current_year": current_year,
        "error": error,
        "success": success,
        "client_code": client_code,
        "force_prefill": force_prefill,
        "sample_data_json": sample_data_json,
    }


# ====== 首页 ======

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    clients = read_clients()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "version": "0.1.0", "clients": clients},
    )


# ====== 问卷 ======

@router.get("/questionnaire", response_class=HTMLResponse)
async def questionnaire_new(request: Request):
    """新建问卷: 空白表单,自动分配客户代码。"""
    return templates.TemplateResponse(
        "questionnaire.html",
        _qi(request, client_code=next_client_code()),
    )


@router.get("/questionnaire/sample-wang", response_class=HTMLResponse)
async def questionnaire_sample_wang(request: Request):
    """以王先生示例预填问卷。"""
    import json, yaml
    from web.yaml_handler import save_yaml_only
    sample_path = PROFILES_DIR / "sample-wang.yaml"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="示例档案不存在")
    yaml_text = sample_path.read_text(encoding="utf-8")
    data = yaml.safe_load(yaml_text)
    # 保存一份到客户列表,获取代码
    ok, code, err = save_yaml_only(yaml_text, "")
    if not ok:
        raise HTTPException(status_code=500, detail=err)
    return templates.TemplateResponse(
        "questionnaire.html",
        _qi(request, client_code=code, force_prefill=True,
            sample_data_json=json.dumps(data, ensure_ascii=False)),
    )


@router.get("/questionnaire/load/{code}", response_class=HTMLResponse)
async def questionnaire_load(request: Request, code: str):
    """加载已有客户 YAML 到问卷。"""
    import json, yaml
    clients = read_clients()
    entry = next((c for c in clients if c["code"] == code), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"未找到客户: {code}")
    yaml_path = PROFILES_DIR / entry["yaml_file"]
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="客户档案文件不存在")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return templates.TemplateResponse(
        "questionnaire.html",
        _qi(request, client_code=code, force_prefill=True,
            sample_data_json=json.dumps(data, ensure_ascii=False)),
    )


@router.post("/questionnaire/save", response_class=HTMLResponse)
async def questionnaire_save(
    request: Request,
    yaml_content: str = Form(default=""),
    yaml_file: UploadFile | None = File(default=None),
    current_year: int = Form(default=2026),
    client_code: str = Form(default=""),
):
    """仅保存问卷,不生成剧本。"""
    import json, yaml
    yaml_text = yaml_content or ""
    if yaml_file and yaml_file.filename:
        content_bytes = await yaml_file.read()
        yaml_text = content_bytes.decode("utf-8", errors="replace")

    if not yaml_text.strip():
        return templates.TemplateResponse(
            "questionnaire.html",
            _qi(request, error="请先填写表单或粘贴 YAML", client_code=client_code),
            status_code=400,
        )

    ok, code, error = save_yaml_only(yaml_text, client_code)
    if not ok:
        return templates.TemplateResponse(
            "questionnaire.html",
            _qi(request, error=error, client_code=client_code, yaml_content=yaml_text),
            status_code=400,
        )

    # 重新加载已保存的数据回填
    try:
        data = yaml.safe_load(PROFILES_DIR / f"{code}.yaml")
    except Exception:
        data = yaml.safe_load(yaml_text)
    return templates.TemplateResponse(
        "questionnaire.html",
        _qi(request, client_code=code, force_prefill=True,
            success=f"客户 {code} 已保存",
            sample_data_json=json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False)),
    )


@router.post("/questionnaire/generate", response_class=HTMLResponse)
async def questionnaire_generate(
    request: Request,
    yaml_content: str = Form(default=""),
    yaml_file: UploadFile | None = File(default=None),
    current_year: int = Form(default=2026),
    client_code: str = Form(default=""),
):
    """保存问卷并生成剧本。"""
    yaml_text = yaml_content or ""
    if yaml_file and yaml_file.filename:
        content_bytes = await yaml_file.read()
        yaml_text = content_bytes.decode("utf-8", errors="replace")

    if not yaml_text.strip():
        return templates.TemplateResponse(
            "questionnaire.html",
            _qi(request, error="请先填写表单或粘贴 YAML", client_code=client_code),
            status_code=400,
        )

    ok, playbook_md, error = save_yaml_and_generate(yaml_text, current_year, client_code)
    if not ok:
        return templates.TemplateResponse(
            "questionnaire.html",
            _qi(request, error=error, client_code=client_code, yaml_content=yaml_text),
            status_code=400,
        )

    # 获取保存后的 code
    code = client_code
    if not code:
        from web.yaml_handler import _resolve_code
        code = _resolve_code(yaml_text, "", PROFILES_DIR)
    name = _family_name(yaml_text)

    playbook_html = render_markdown(playbook_md)
    return templates.TemplateResponse(
        "playbook.html",
        {
            "request": request,
            "playbook_md": playbook_md,
            "playbook_html": playbook_html,
            "current_year": current_year,
            "client_code": code,
            "client_name": name,
        },
    )


# ====== 剧本 ======

@router.get("/playbook/{code}", response_class=HTMLResponse)
async def playbook_view(request: Request, code: str):
    profile_path = PROFILES_DIR / f"{code}.yaml"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"未找到档案: {code}")
    yaml_text = profile_path.read_text(encoding="utf-8")
    ok, playbook_md, error_msg = save_yaml_and_generate(yaml_text, 2026, code)
    if not ok:
        raise HTTPException(status_code=500, detail=error_msg)
    name = _family_name(yaml_text)
    playbook_html = render_markdown(playbook_md)
    return templates.TemplateResponse(
        "playbook.html",
        {
            "request": request,
            "playbook_md": playbook_md,
            "playbook_html": playbook_html,
            "current_year": 2026,
            "client_code": code,
            "client_name": name,
        },
    )


# ====== 客户管理 ======

@router.post("/clients/update", response_class=HTMLResponse)
async def clients_update(
    request: Request,
    code: str = Form(...),
    tag1: str = Form(default=""),
    tag2: str = Form(default=""),
    notes: str = Form(default=""),
):
    update_client(code, {"tags": [tag1, tag2], "notes": notes})
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


# ====== API ======

@router.post("/api/validate")
async def api_validate(yaml_content: str = Form(...)):
    from web.yaml_handler import receive_yaml_text
    ok, _, error_msg = receive_yaml_text(yaml_content)
    return {"ok": ok, "error": error_msg}


@router.post("/api/playbook")
async def api_playbook(
    yaml_content: str = Form(...),
    current_year: int = Form(default=2026),
):
    ok, playbook_md, error_msg = save_yaml_and_generate(
        yaml_text=yaml_content, current_year=current_year
    )
    if not ok:
        raise HTTPException(status_code=400, detail=error_msg)
    return {"markdown": playbook_md, "ok": True}
