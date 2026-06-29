"""手册结构校验脚本(可独立运行,供 CI 使用)。

无需任何第三方依赖,使用标准库。

用法:
    python3 tools/validate_handbook.py

退出码:
    0 - 全部通过
    1 - 有错误
"""
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_DIR = REPO_ROOT / "handbook"

REQUIRED_FILES = [
    "00-methodology-overview.md",
    "01-input-schema.md",
    "02-life-events.md",
    "03-asset-assumptions.md",
    "04-pareto-generation.md",
    "05-output-structure.md",
    "06-boundaries.md",
    "07-versioning.md",
]


def count_h1_outside_code_fences(content: str) -> int:
    """统计 markdown 中位于 fenced/indented code block 之外的 H1 行数。

    支持 ```、~~~、4 空格缩进代码块。Fenced 用首个出现的 fence 类型配对。
    """
    count = 0
    in_fence: str | None = None
    for line in content.splitlines():
        stripped = line.lstrip()
        # 跳过 4 空格缩进代码块(Markdown 规范)
        if in_fence is None and line.startswith("    "):
            continue
        # 检测 fenced code block 开始/结束
        if in_fence is None:
            if stripped.startswith("```"):
                in_fence = "```"
                continue
            if stripped.startswith("~~~"):
                in_fence = "~~~"
                continue
        else:
            if stripped.startswith(in_fence):
                in_fence = None
            continue
        # 在非代码块区域统计 H1
        if line.startswith("# "):
            count += 1
    return count


def check_handbook_files() -> list[str]:
    """检查所有手册章节的结构,返回错误列表。"""
    errors: list[str] = []
    for filename in REQUIRED_FILES:
        path = HANDBOOK_DIR / filename
        if not path.exists():
            errors.append(f"缺少手册章节: {filename}")
            continue
        content = path.read_text(encoding="utf-8")

        if not re.search(r"\*\*版本:\*\*\s+\S+", content):
            errors.append(f"{filename} 缺少版本声明")
        if not re.search(r"\*\*状态:\*\*\s+\S+", content):
            errors.append(f"{filename} 缺少状态声明")

        h1_count = count_h1_outside_code_fences(content)
        if h1_count != 1:
            errors.append(f"{filename} H1 数量应为 1,实际 {h1_count}")

    return errors


def check_sample_yaml() -> list[str]:
    """检查示例客户档案的结构,返回错误列表。"""
    errors: list[str] = []
    sample = REPO_ROOT / "samples" / "client-profile.example.yaml"
    if not sample.exists():
        return [f"缺少示例档案: {sample}"]

    try:
        import yaml  # type: ignore
    except ImportError:
        errors.append("PyYAML 未安装,无法校验示例 YAML(可选安装:pip install pyyaml)")
        return errors

    try:
        data = yaml.safe_load(sample.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        errors.append(f"示例 YAML 解析失败: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append("示例 YAML 顶层应为字典")
        return errors

    required = {"profile_version", "schema_version", "family", "events", "assets"}
    missing = required - set(data.keys())
    if missing:
        errors.append(f"示例 YAML 缺少维度: {sorted(missing)}")

    if data.get("profile_version") != "0.1":
        errors.append(f"示例 YAML profile_version 应为 0.1,实际 {data.get('profile_version')}")

    return errors


def main() -> int:
    errors = check_handbook_files() + check_sample_yaml()
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(REQUIRED_FILES)} 个手册章节均通过结构校验")
    print("OK: 示例客户档案通过结构校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
