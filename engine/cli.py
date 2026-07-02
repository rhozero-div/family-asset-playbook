"""CLI 入口(串联各模块)。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
import warnings

from engine.handbook_reader import HandbookReadError, read_assumptions
from engine.markdown_renderer import render_playbook
from engine.profile_loader import ProfileLoadError, load_profile
from engine.projection import (project_to_nodes, project_to_terminal,
                                project_yearly, project_yearly_with_returns,
                                project_buckets_with_returns)
from insurance_planner.logic import analyze_profile as analyze_insurance_profile


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fapm",
        description="Family Asset Playbook Methodology — 计算引擎 CLI",
    )
    parser.add_argument("--profile", required=True, help="客户档案 YAML 路径")
    parser.add_argument("--out", help="输出 Markdown 路径(默认 stdout)")
    parser.add_argument(
        "--handbook",
        default="handbook",
        help="手册层目录(默认 ./handbook)",
    )
    parser.add_argument(
        "--current-year",
        type=int,
        help="当前年份(默认系统年)",
    )
    return parser


def _resolve_current_year(args: argparse.Namespace) -> int:
    if args.current_year:
        return args.current_year
    return datetime.now().year


def _resolve_terminal_start_year(profile) -> int:
    """终老推演从最后一个未来事件年开始；若没有未来事件，则从当前年开始。"""
    return max(
        (e.timing_year for e in profile.events if e.timing_year >= profile.current_year),
        default=profile.current_year,
    )


def _generate_playbook(
    *,
    profile_path: Path,
    handbook_dir: Path,
    current_year: int,
    lang: str = "zh",
) -> str:
    profile = load_profile(profile_path, current_year=current_year)
    assumptions_path = handbook_dir / "03-asset-assumptions.md"
    assumptions = read_assumptions(assumptions_path)

    projections = project_to_nodes(profile)

    from engine.allocator import allocate
    plan = allocate(profile, projections, assumptions)

    # 终老推演: 从最后一个事件年或当前年之后开始
    last_event_year = _resolve_terminal_start_year(profile)
    # 用 projection 最后一个节点的 balance_after 作为起点
    last_balance = projections[-1].balance_after if projections else profile.total_financial_assets
    terminal = project_to_terminal(profile, last_balance, max(last_event_year, profile.current_year))

    yearly = project_yearly(profile)
    return_snapshots = ()
    bucket_result = None
    insurance_result = analyze_insurance_profile(profile)
    try:
        return_snapshots = project_yearly_with_returns(profile, assumptions)
        bucket_result = project_buckets_with_returns(profile, assumptions, plan)
    except ModuleNotFoundError as exc:
        if exc.name != "qmc" and "qmc" not in str(exc):
            raise
        warnings.warn(
            "qmc dependency unavailable; generating playbook without return fan charts",
            RuntimeWarning,
            stacklevel=2,
        )

    return render_playbook(
        profile=profile,
        plan=plan,
        risk_preference=profile.risk_preference,
        projections=projections,
        terminal_steps=terminal,
        yearly_snapshots=yearly,
        return_snapshots=return_snapshots,
        bucket_result=bucket_result,
        insurance_result=insurance_result,
        lang=lang,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 入口,返回退出码。

    Exit codes:
        0 成功
        1 参数错误(argparse 缺省)
        2 档案不存在 / 解析失败
        3 档案 schema 不匹配
        4 手册读取失败
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    profile_path = Path(args.profile)
    handbook_dir = Path(args.handbook)
    if not handbook_dir.is_dir():
        print(f"handbook 目录不存在: {handbook_dir}", file=sys.stderr)
        return 4

    try:
        current_year = _resolve_current_year(args)
        markdown = _generate_playbook(
            profile_path=profile_path,
            handbook_dir=handbook_dir,
            current_year=current_year,
        )
    except ProfileLoadError as e:
        msg = str(e)
        if "不存在" in msg:
            print(f"档案不存在: {profile_path}", file=sys.stderr)
            return 2
        print(f"档案解析失败: {e}", file=sys.stderr)
        return 3
    except HandbookReadError as e:
        print(f"手册读取失败: {e}", file=sys.stderr)
        return 4

    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"已写入: {args.out}", file=sys.stderr)
    else:
        print(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
