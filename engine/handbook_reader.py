"""手册假设读取器。

从 handbook/03-asset-assumptions.md 解析资产大类的预期收益与波动率单值。

策略:
- 用 regex 匹配表格中的 "X%" 形式
- 解析失败时使用 fallback 默认值(不抛错,避免外部 markdown 排版变化导致引擎不可用)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class HandbookReadError(Exception):
    """手册读取失败。"""


# Fallback 默认值:与 handbook/03 占位值一致(取原区间中点)
_FALLBACK = {
    "fixed_income_return": 0.02,
    "fixed_income_volatility": 0.02,
    "equity_return": 0.07,
    "equity_volatility": 0.30,
    "insurance_return": 0.02,
    "insurance_volatility": 0.0,
    "alternatives_return": 0.05,
    "alternatives_volatility": 0.30,
    # 相关性默认值
    "correlation_fi_eq": 0.3,
    "correlation_fi_ins": 0.0,
    "correlation_fi_alt": -0.3,
    "correlation_eq_ins": 0.0,
    "correlation_eq_alt": 0.0,
    "correlation_ins_alt": 0.0,
}


@dataclass(frozen=True)
class Assumptions:
    """资产大类假设(单值)。"""

    fixed_income_return: float
    fixed_income_volatility: float
    equity_return: float
    equity_volatility: float
    insurance_return: float
    insurance_volatility: float
    alternatives_return: float
    alternatives_volatility: float
    # 相关性矩阵(上三角, 6 个唯一对)
    correlation_fi_eq: float = 0.3
    correlation_fi_ins: float = 0.0
    correlation_fi_alt: float = -0.3
    correlation_eq_ins: float = 0.0
    correlation_eq_alt: float = 0.0
    correlation_ins_alt: float = 0.0


# 大类中文 → attr 映射
_CLASS_MAP = {
    "固收": "fixed_income",
    "权益": "equity",
    "保险": "insurance",
    "另类": "alternatives",
}

# 匹配 "3.5%" 或 "9%"
_SINGLE_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")


def _parse_single(text: str) -> float | None:
    m = _SINGLE_RE.search(text)
    if not m:
        return None
    return float(m.group(1)) / 100


def _find_class_row_singles(content: str, cn_name: str) -> tuple[str, str] | None:
    """在整个手册中查找以 "| cn_name |" 开头的表格行,返回该行内两个单值字符串。

    只匹配**恰好**等于 cn_name 的首格,且 cells[2] 包含 % 符号,
    跳过角色/权重等不含百分比的描述行。
    """
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 4 and cells[1] == cn_name and "%" in cells[2]:
            return cells[2], cells[3]
    return None


def read_assumptions(path: str | Path) -> Assumptions:
    """读取并解析 handbook/03-asset-assumptions.md。

    若找不到匹配值,使用 _FALLBACK 默认值(不报错)。
    """
    p = Path(path)
    if not p.exists():
        raise HandbookReadError(f"手册文件不存在: {p}")

    content = p.read_text(encoding="utf-8")

    result: dict[str, float] = {}

    for cn_name, prefix in _CLASS_MAP.items():
        return_attr = f"{prefix}_return"
        vol_attr = f"{prefix}_volatility"

        row = _find_class_row_singles(content, cn_name)
        if row is None:
            continue
        return_str, vol_str = row
        ret = _parse_single(return_str)
        vol = _parse_single(vol_str)
        if ret is not None:
            result[return_attr] = ret
        if vol is not None:
            result[vol_attr] = vol

    # 用 fallback 填缺失
    for k, v in _FALLBACK.items():
        result.setdefault(k, v)

    return Assumptions(**result)
