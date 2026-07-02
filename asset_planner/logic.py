"""资产规划原型逻辑。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from engine.allocator import AllocationPlan, _phase_strategies, allocate
from engine.handbook_reader import Assumptions, read_assumptions
from engine.profile_loader import ClientProfile, load_profile
from engine.projection import NodeProjection, project_to_nodes
from tools.validate_collected_profile import _validate

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AssetPlannerResult:
    profile: ClientProfile
    assumptions: Assumptions
    projections: tuple[NodeProjection, ...]
    allocation: AllocationPlan
    phase_rows: tuple[dict, ...]
    all_nodes_covered: bool
    earliest_shortfall: NodeProjection | None


def _phase_rows(profile: ClientProfile) -> tuple[dict, ...]:
    labels = ["近期", "中期", "远期", "超远期"]
    rows = []
    for idx, (lo, hi, weights) in enumerate(_phase_strategies(profile)):
        rows.append(
            {
                "label": labels[idx] if idx < len(labels) else f"阶段 {idx + 1}",
                "years_text": f"{lo + 1}-{hi}" if hi < 999 else f">{lo}",
                "fixed_income": weights[0],
                "equity": weights[1],
                "insurance": weights[2],
                "alternatives": weights[3],
            }
        )
    return tuple(rows)


def analyze_profile(profile: ClientProfile) -> AssetPlannerResult:
    assumptions = read_assumptions(PROJECT_ROOT / "handbook" / "03-asset-assumptions.md")
    projections = project_to_nodes(profile)
    allocation = allocate(profile, projections, assumptions)
    earliest_shortfall = next((node for node in projections if node.gap_or_surplus < 0), None)
    return AssetPlannerResult(
        profile=profile,
        assumptions=assumptions,
        projections=projections,
        allocation=allocation,
        phase_rows=_phase_rows(profile),
        all_nodes_covered=earliest_shortfall is None,
        earliest_shortfall=earliest_shortfall,
    )


def analyze_yaml_text(yaml_text: str, current_year: int) -> AssetPlannerResult:
    import yaml

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML 解析失败: {exc}") from exc
    ok, errors = _validate(data if isinstance(data, dict) else {}, Path("<inline>"))
    if not ok:
        raise ValueError("; ".join(errors))

    with NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
        tmp.write(yaml_text)
        tmp_path = Path(tmp.name)
    try:
        profile = load_profile(tmp_path, current_year=current_year)
    finally:
        tmp_path.unlink(missing_ok=True)
    return analyze_profile(profile)
