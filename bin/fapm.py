#!/usr/bin/env python3
"""FAPM CLI 便捷入口。

完整实现在 engine.cli;此处仅为 thin wrapper。
"""
import sys
from pathlib import Path

# 让 import 能找到 engine 包
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())