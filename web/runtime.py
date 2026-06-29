"""运行时开关。"""
from __future__ import annotations

import os


def server_storage_enabled() -> bool:
    """是否允许服务器端持久化客户数据。"""
    value = os.getenv("FAPM_ENABLE_SERVER_STORAGE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}
