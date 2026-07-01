"""运行时存储路径。"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def bundled_profiles_dir() -> Path:
    """仓库内置示例档案目录。"""
    return PROJECT_ROOT / "profiles"


def sample_profile_path() -> Path:
    """仓库内置示例档案路径。"""
    return bundled_profiles_dir() / "sample-wang.yaml"


def storage_dir() -> Path:
    """客户持久化目录。

    默认写入仓库内 `profiles/`。
    如设置 `FAPM_STORAGE_DIR`，则写入该外部目录。
    """
    value = os.getenv("FAPM_STORAGE_DIR", "").strip()
    path = Path(value).expanduser() if value else bundled_profiles_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
