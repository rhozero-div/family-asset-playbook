"""FastAPI 应用入口。

仅做应用初始化与挂载,路由在 routes.py。
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_DIR.parent

app = FastAPI(
    title="FAPM Web",
    version="0.1.0",
    description="家庭资产配置剧本方法论 — Web 入口",
)

# 静态文件
app.mount(
    "/static",
    StaticFiles(directory=str(WEB_DIR / "static")),
    name="static",
)

# 路由(延迟 import 避免循环)
from web.routes import router  # noqa: E402

app.include_router(router)