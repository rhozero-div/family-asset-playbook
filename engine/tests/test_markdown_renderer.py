"""markdown_renderer 单元测试。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.allocator import allocate  # noqa: E402
from engine.handbook_reader import read_assumptions  # noqa: E402
from engine.markdown_renderer import render_playbook  # noqa: E402
from engine.profile_loader import load_profile  # noqa: E402
from engine.projection import (  # noqa: E402
    YearlyReturnSnapshot,
    project_to_nodes,
    project_to_terminal,
    project_yearly,
    project_buckets_with_returns,
)

SAMPLE_YAML = ROOT / "samples" / "client-profile.example.yaml"
ASSUMPTIONS_PATH = ROOT / "handbook" / "03-asset-assumptions.md"
_DEFAULT = object()


def _build(include_bucket_result: bool = True):
    profile = load_profile(SAMPLE_YAML, current_year=2026)
    assumptions = read_assumptions(ASSUMPTIONS_PATH)
    projections = project_to_nodes(profile)
    plan = allocate(profile, projections, assumptions)
    last_balance = projections[-1].balance_after if projections else profile.total_financial_assets
    last_year = max((e.timing_year for e in profile.events if e.timing_year >= profile.current_year), default=2036)
    terminal = project_to_terminal(profile, last_balance, max(last_year, profile.current_year))
    yearly = project_yearly(profile)
    bucket_result = None
    if include_bucket_result:
        try:
            bucket_result = project_buckets_with_returns(
                profile, assumptions, plan, n_sobol_points=64, seed=42
            )
        except ModuleNotFoundError as exc:
            if exc.name == "qmc":
                raise unittest.SkipTest("qmc dependency is unavailable in this environment") from exc
            raise
    return profile, projections, plan, terminal, yearly, assumptions, bucket_result


def _render(**kw):
    requested_bucket_result = kw.get("bucket_result", _DEFAULT)
    include_bucket_result = requested_bucket_result is _DEFAULT
    p, projs, plan, term, yearly, _, bucket_result = _build(include_bucket_result=include_bucket_result)
    return render_playbook(
        profile=kw.get("profile", p),
        plan=kw.get("plan", plan),
        risk_preference=kw.get("risk_preference", p.risk_preference),
        projections=kw.get("projections", projs),
        terminal_steps=kw.get("terminal_steps", term),
        yearly_snapshots=kw.get("yearly_snapshots", yearly),
        bucket_result=bucket_result if requested_bucket_result is _DEFAULT else requested_bucket_result,
    )


class TestRenderPlaybook(unittest.TestCase):
    def test_renders_metadata(self):
        md = _render(bucket_result=None)
        self.assertIn("王先生", md)
        self.assertIn("handbook-v0.1", md)
        self.assertIn("不构成投资建议", md)

    def test_renders_all_sections(self):
        md = _render(bucket_result=None)
        for label in (
            "综合建议摘要",
            "A. 客户情况概览",
            "B. 资产推演",
            "C. 资产配置执行方案",
        ):
            self.assertIn(label, md)

    def test_does_not_render_change_log(self):
        md = _render(bucket_result=None)
        self.assertNotIn("剧本变更记录", md)

    def test_renders_disclaimer(self):
        md = _render(bucket_result=None)
        self.assertIn("不构成投资建议", md)

    def test_renders_initial_assets(self):
        md = _render(bucket_result=None)
        self.assertIn("家庭净资产", md)
        self.assertIn("月度结余", md)
        self.assertIn("金融资产", md)
        self.assertIn("退休后预期", md)
        self.assertIn("| 项目 | 金额/参数 | 说明 |", md)

    def test_renders_event_timeline(self):
        md = _render(bucket_result=None)
        self.assertIn("人生阶段节点", md)
        self.assertIn("改善型购房", md)
        self.assertNotIn("确定性", md)

    def test_renders_advice_summary_module(self):
        md = _render(bucket_result=None)
        self.assertIn("## 综合建议摘要", md)
        self.assertIn("重大节点覆盖结论", md)
        self.assertIn("现阶段的整体判断", md)
        self.assertIn("现在最值得优先做的 3 件事", md)
        self.assertIn("保障配置建议", md)
        self.assertIn("后续需要持续关注的几个信号", md)
        self.assertIn("出现哪些变化时，建议尽快重算", md)
        self.assertNotIn("可执行的阅读提要", md)

    def test_summary_section_appears_before_customer_overview(self):
        md = _render(bucket_result=None)
        self.assertLess(md.index("## 综合建议摘要"), md.index("## A. 客户情况概览"))

    def test_summary_contains_action_and_recalc_style_guidance(self):
        md = _render(bucket_result=None)
        self.assertIn("先", md)
        self.assertIn("建议重算", md)

    def test_summary_headline_contains_node_and_surplus_conclusions(self):
        md = _render()
        self.assertIn("重大节点覆盖结论", md)
        self.assertIn("富余资金长期收益结论", md)

    def test_renders_member_level_healthcare_selfpay_summary(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "profile_version: '0.1'\n"
                "schema_version: 'handbook-v0.1'\n"
                "family:\n"
                "  members:\n"
                "    - name: 张先生\n"
                "      age: 40\n"
                "      role: primary_breadwinner\n"
                "      annual_income: 600000\n"
                "      monthly_expense: 10000\n"
                "      retirement_age: 60\n"
                "      retirement_pension: 5000\n"
                "      retirement_annuity: 2000\n"
                "      retirement_expense_coeff: 0.7\n"
                "      medical_covered: true\n"
                "      reimbursement_rate: 0.8\n"
                "      healthcare_starting_annual: 20000\n"
                "      healthcare_growth_rate: 0.05\n"
                "      healthcare_annual_cap: 80000\n"
                "events: []\n"
                "assets:\n"
                "  financial:\n"
                "    total_value: 1000000\n"
            )
            path = Path(f.name)
        try:
            profile = load_profile(path, current_year=2026)
            assumptions = read_assumptions(ASSUMPTIONS_PATH)
            projections = project_to_nodes(profile)
            plan = allocate(profile, projections, assumptions)
            terminal = project_to_terminal(profile, profile.total_financial_assets, profile.current_year)
            yearly = project_yearly(profile)
            md = render_playbook(
                profile=profile,
                plan=plan,
                projections=projections,
                terminal_steps=terminal,
                yearly_snapshots=yearly,
                bucket_result=None,
            )
            self.assertIn("退休首年医疗自付", md)
            self.assertIn("张先生 ¥4,000", md)
        finally:
            path.unlink(missing_ok=True)

    def test_renders_projection_table(self):
        md = _render(bucket_result=None)
        self.assertIn("累积资产", md)
        self.assertIn("逐年净现金流序列", md)

    def test_rendered_return_chart_title_uses_measurement_end_year(self):
        profile, projections, plan, terminal, yearly, assumptions, _ = _build(include_bucket_result=False)
        profile = profile.__class__(**{**profile.__dict__, "measurement_end_year": 2042})
        md = render_playbook(
            profile=profile,
            plan=plan,
            projections=projections,
            terminal_steps=terminal,
            yearly_snapshots=yearly,
            return_snapshots=tuple(
                YearlyReturnSnapshot(
                    year=s.year,
                    age=s.age,
                    p10=0,
                    p25=0,
                    p50=0,
                    p75=0,
                    p90=0,
                )
                for s in yearly
            ),
            bucket_result=None,
        )
        self.assertIn("展示至 2042 年", md)
        self.assertNotIn("展示至 80 岁", md)

    def test_renders_allocation_overview(self):
        md = _render(bucket_result=None)
        self.assertIn("初始存量资金分配", md)
        self.assertIn("年度净结余分配", md)
        self.assertIn("应急储备", md)

    def test_renders_bucket_c6_section(self):
        """C6 节标题与粉丝带图应出现。"""
        md = _render()
        self.assertIn("各层余额与资金来源", md)

    def test_renders_bucket_fan_chart_data(self):
        """每个 bucket 都应有 1 个 canvas + 1 个 JSON script 标签 (混合 bar+fan)。"""
        import json
        md = _render()
        self.assertIn("bucket-chart-grid", md)
        # script id 计数 = bucket 数
        import re
        script_ids = re.findall(r'id="bucket-fan-data-b_\d+"', md)
        canvas_ids = re.findall(r'id="bucketFanChart_b_\d+"', md)
        self.assertEqual(len(script_ids), len(canvas_ids))
        self.assertGreater(len(script_ids), 0)
        # 验证 JSON 结构 (混合图: 含 starting/cash/returns + p10-p90)
        m = re.search(r'<script id="bucket-fan-data-(b_\d+)" type="application/json">({[^<]+})</script>', md)
        self.assertIsNotNone(m)
        data = json.loads(m.group(2))
        for key in ("labels", "starting", "cash", "returns",
                    "p10", "p25", "p50", "p75", "p90",
                    "withdrawal_year", "target_amount"):
            self.assertIn(key, data)
        self.assertNotIn("ci_total_target", data)
        # 节点 bucket 包含 withdrawal_year + target_amount
        for sid_match in re.finditer(r'<script id="bucket-fan-data-(b_\d+)" type="application/json">({[^<]+})</script>', md):
            d = json.loads(sid_match.group(2))
            if d["withdrawal_year"] is not None:
                self.assertIsNotNone(d["target_amount"])
                self.assertGreater(d["target_amount"], 0)
                break

    def test_c6b_breakdown_chart_removed(self):
        """v0.6.1: C6b 独立资金来源图已合并到 C6, 不再单独渲染."""
        import re
        md = _render()
        self.assertNotIn("bucket-breakdown-data", md)
        self.assertNotIn("bucketBreakdownChart", md)

    def test_c6_skipped_when_bucket_result_none(self):
        """bucket_result 为 None 时, C6 不输出内容但不崩溃。"""
        try:
            md = _render(bucket_result=None)
        except Exception:
            self.fail("C6 raised when bucket_result=None")
        self.assertNotIn("bucket-fan-data", md)
