"""project_buckets_with_returns 单元测试。

覆盖:
- 基本结构 (BucketYearlyStats, BucketProjectionResult)
- 应急 bucket 维持 (target 小, 满额概率高)
- 节点 bucket 满额 + 提取后清零
- CI 分期 bucket 满额后停止累积
- CI 一次性 (lump) bucket 单纯增长
- 富余 bucket 持续增长 (无 target)
- 空 bucket 列表安全返回
- for_bucket() 筛选
- 满额概率范围 [0, 1]
- 分位单调性 p10 ≤ p25 ≤ p50 ≤ p75 ≤ p90
"""
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.allocator import allocate  # noqa: E402
from engine.handbook_reader import read_assumptions  # noqa: E402
from engine.profile_loader import load_profile  # noqa: E402
from engine.projection import (  # noqa: E402
    BucketAnnualizedReturnStats,
    BucketYearlyStats,
    BucketProjectionResult,
    project_yearly,
    project_to_nodes,
    project_buckets_with_returns,
)

SAMPLE_YAML = ROOT / "samples" / "client-profile.example.yaml"
ASSUMPTIONS_PATH = ROOT / "handbook" / "03-asset-assumptions.md"


def _build():
    """加载示例 profile 并跑出 allocation plan。"""
    profile = load_profile(SAMPLE_YAML, current_year=2026)
    assumptions = read_assumptions(ASSUMPTIONS_PATH)
    projections = project_to_nodes(profile)
    plan = allocate(profile, projections, assumptions)
    return profile, assumptions, plan, projections


class TestBucketMCStructure(unittest.TestCase):
    def test_returns_correct_types(self):
        _, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(
            *_build()[:1], assumptions, plan, n_sobol_points=64, seed=42
        )
        self.assertIsInstance(result, BucketProjectionResult)
        self.assertIsInstance(result.snapshots, tuple)
        for s in result.snapshots:
            self.assertIsInstance(s, BucketYearlyStats)

    def test_bucket_names_match_plan(self):
        _, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(
            _build()[0], assumptions, plan, n_sobol_points=64, seed=42
        )
        # 应急 + 节点 + 富余 (示例档案无 CI lump)
        self.assertIn("应急储备", result.bucket_names)
        # node_buckets 名称
        for nb in plan.node_buckets:
            self.assertIn(nb.name, result.bucket_names)
        if plan.surplus is not None:
            self.assertIn("富余资金", result.bucket_names)

    def test_snapshot_count_matches_buckets_times_years(self):
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        birth = profile.primary_breadwinner_birth_year
        end_year = birth + 100
        n_years = end_year - profile.current_year + 1
        n_buckets = len(result.bucket_names)
        self.assertEqual(len(result.snapshots), n_years * n_buckets)

    def test_percentiles_monotonic(self):
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        for s in result.snapshots:
            self.assertLessEqual(s.p10, s.p25, f"{s.bucket_name} {s.year}")
            self.assertLessEqual(s.p25, s.p50, f"{s.bucket_name} {s.year}")
            self.assertLessEqual(s.p50, s.p75, f"{s.bucket_name} {s.year}")
            self.assertLessEqual(s.p75, s.p90, f"{s.bucket_name} {s.year}")

    def test_full_probability_in_unit_interval(self):
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        for s in result.snapshots:
            self.assertGreaterEqual(s.full_probability, 0.0)
            self.assertLessEqual(s.full_probability, 1.0)


class TestEmergencyBucket(unittest.TestCase):
    def test_emergency_rebalanced_to_target(self):
        """应急储备: v0.5.1 起每月再平衡到目标值,超额流向 active 节点 bucket。

        - p50 应稳定在 target 附近 (不允许明显偏离);
        - 满额概率应接近 1.0 (再平衡机制保证);
        - 不应"持续增长" (旧实现的 bug).
        """
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        em = result.for_bucket("应急储备")
        self.assertGreater(len(em), 5)
        target = plan.emergency.amount
        # 第 1 年末 p50 应在目标附近 (允许 ±10% 误差)
        self.assertAlmostEqual(em[0].p50, target, delta=target * 0.10)
        # 5 年后 p50 也应在目标附近 (再平衡)
        self.assertAlmostEqual(em[5].p50, target, delta=target * 0.10)
        # 不应"持续增长"超过目标太多 (旧 bug)
        self.assertLess(em[5].p50, target * 1.05)
        # 满额概率应接近 1.0 (每月再平衡保证)
        mid = em[len(em) // 2]
        self.assertGreaterEqual(mid.full_probability, 0.95)


class TestNodeBucket(unittest.TestCase):
    def test_node_bucket_withdraws_at_year_end(self):
        """节点 bucket: 提取发生在事件年年末,提取后余额归零。"""
        profile, assumptions, plan, _ = _build()
        if not plan.node_buckets:
            self.skipTest("示例档案无 node_buckets")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        first_node = plan.node_buckets[0]
        nb = result.for_bucket(first_node.name)
        # 找提取年
        withdrawal_year = first_node.withdrawal_year
        if withdrawal_year is None:
            self.skipTest("第一个节点 bucket 无 withdrawal_year")
        pre = next((s for s in nb if s.year == withdrawal_year - 1), None)
        post = next((s for s in nb if s.year == withdrawal_year), None)
        self.assertIsNotNone(pre)
        self.assertIsNotNone(post)
        self.assertGreater(pre.p50, first_node.initial_balance)
        self.assertEqual(post.p50, 0.0)
        self.assertEqual(post.full_probability, 0.0)


class TestCIGradualBucket(unittest.TestCase):
    def test_ci_gradual_stops_growing_at_reserve_end(self):
        """CI 分期 bucket: 提取年 (积累期满) 之后停止月供, 仅累加收益。"""
        profile, assumptions, plan, _ = _build()
        if plan.ci_reserve is None:
            self.skipTest("示例档案无 ci_reserve")
        if plan.ci_strategy != "reserve_gradual":
            self.skipTest("示例档案非 reserve_gradual 策略")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        ci = result.for_bucket(plan.ci_reserve.name)
        self.assertGreater(len(ci), 5)
        wy = plan.ci_reserve.withdrawal_year
        # 提取年后 1 年 vs 提取年: 余额应仍在增长 (但增长变缓, 仅靠收益)
        at_end = next((s for s in ci if s.year == wy), None)
        after_end = next((s for s in ci if s.year == wy + 1), None)
        self.assertIsNotNone(at_end)
        self.assertIsNotNone(after_end)
        # 提取年后 p10 应 >= 0 (没清零)
        self.assertGreaterEqual(after_end.p10, 0.0)


class TestSurplusBucket(unittest.TestCase):
    def test_surplus_grows_with_no_target(self):
        """富余 bucket: 无 target, 持续增长。"""
        profile, assumptions, plan, _ = _build()
        if plan.surplus is None:
            self.skipTest("示例档案无 surplus")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        sp = result.for_bucket("富余资金")
        self.assertGreater(len(sp), 5)
        # target = 0
        self.assertEqual(sp[0].target_amount, 0.0)
        # 持续增长
        self.assertGreater(sp[10].p50, sp[0].p50)
        # 满额概率 = P(balance >= 0) 应接近 1.0
        self.assertGreaterEqual(sp[10].full_probability, 0.95)

    def test_surplus_has_annualized_return_stats(self):
        """富余资金应附带长期复合年化收益分位数。"""
        profile, assumptions, plan, _ = _build()
        if plan.surplus is None:
            self.skipTest("示例档案无 surplus")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        stats = result.annualized_return_for_bucket("富余资金")
        self.assertIsNotNone(stats)
        self.assertIsInstance(stats, BucketAnnualizedReturnStats)
        self.assertLessEqual(stats.p10, stats.p25)
        self.assertLessEqual(stats.p25, stats.p50)
        self.assertLessEqual(stats.p50, stats.p75)
        self.assertLessEqual(stats.p75, stats.p90)


class TestEmptyBuckets(unittest.TestCase):
    def test_empty_allocation_safe(self):
        """空 plan (无 emergency) 会因 emergency 必填而报错; 此处测空 snapshots。"""
        result = BucketProjectionResult(snapshots=(), bucket_names=())
        self.assertEqual(len(result.snapshots), 0)
        self.assertEqual(result.for_bucket("anything"), ())


class TestForBucketFilter(unittest.TestCase):
    def test_for_bucket_returns_only_matching(self):
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        for bname in result.bucket_names:
            filtered = result.for_bucket(bname)
            self.assertGreater(len(filtered), 0)
            for s in filtered:
                self.assertEqual(s.bucket_name, bname)


class TestCashConservation(unittest.TestCase):
    """现金守恒: 年净结余按时间优先分配给节点 bucket。"""

    def test_allocator_does_not_overallocate_node_buckets(self):
        """allocator 应把所有节点 bucket 的 monthly_contribution 设为 0,
        由推演层按时间优先统一分发."""
        profile, assumptions, plan, _ = _build()
        for b in plan.node_buckets:
            self.assertEqual(b.monthly_contribution, 0.0,
                             f"节点 bucket {b.name} monthly_contribution 应为 0")

    def test_active_bucket_receives_annual_surplus(self):
        """active bucket 在事件前应有可观增长 (含年净结余 + 收益 + 应急超额)."""
        profile, assumptions, plan, _ = _build()
        if not plan.node_buckets:
            self.skipTest("示例档案无 node_buckets")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        first_node = plan.node_buckets[0]
        nb = result.for_bucket(first_node.name)
        # 初始值 vs 1 年后
        initial = first_node.initial_balance
        after_1y = nb[1].p50
        # active 1 年应有明显增长 (年净结余 + 收益)
        self.assertGreater(after_1y, initial)

    def test_node_passes_to_next_when_funded(self):
        """第一个节点达标后, surplus 应切换到下一个节点."""
        profile, assumptions, plan, _ = _build()
        if len(plan.node_buckets) < 2:
            self.skipTest("示例档案 node_buckets < 2")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        nb1 = result.for_bucket(plan.node_buckets[0].name)
        nb2 = result.for_bucket(plan.node_buckets[1].name)
        nb1_dict = {s.year: s for s in nb1}
        nb2_dict = {s.year: s for s in nb2}
        wdl1 = plan.node_buckets[0].withdrawal_year
        if wdl1 is None:
            self.skipTest("节点缺 withdrawal_year")
        # 年末口径下, 第二个节点最迟应在第一个节点提取当年开始收到新增流入
        if wdl1 in nb2_dict:
            self.assertGreater(nb2_dict[wdl1].p50, plan.node_buckets[1].initial_balance,
                               "节点2 应在节点1提取当年开始接收后续资金")


class TestSavingsRouting(unittest.TestCase):
    def test_savings_route_to_linked_bucket_and_surplus(self):
        """指定 linked_account 的储蓄险应进入对应心理账户,未指定的并入富余资金。"""
        sample_text = SAMPLE_YAML.read_text(encoding="utf-8")
        injected = sample_text.replace(
            "    insurance:\n",
            "    savings:\n"
            "      - amount: 200000\n"
            "        premium: 0\n"
            "        pay_years: 0\n"
            "        linked_account: \"buy_improvement_house\"\n"
            "      - amount: 100000\n"
            "        premium: 0\n"
            "        pay_years: 0\n"
            "        linked_account: \"富余资金\"\n"
            "    insurance:\n",
            1,
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(injected)
            temp_path = Path(f.name)
        try:
            profile = load_profile(temp_path, current_year=2026)
            assumptions = read_assumptions(ASSUMPTIONS_PATH)
            projections = project_to_nodes(profile)
            plan = allocate(profile, projections, assumptions)
            first_node = plan.node_buckets[0]
            self.assertGreaterEqual(first_node.initial_balance, 200000.0)
            self.assertIsNotNone(plan.surplus)
            self.assertGreaterEqual(plan.surplus.initial_balance, 100000.0)
        finally:
            temp_path.unlink(missing_ok=True)


class TestEmergencyRebalancing(unittest.TestCase):
    """v0.5.1 应急储备再平衡: 超目标值流向 active, 不足从富余拉回."""

    def test_emergency_stays_near_target(self):
        """应急储备每月再平衡, p50 应稳定在 target 附近."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        em = result.for_bucket("应急储备")
        target = plan.emergency.amount
        for s in em:
            # 不允许明显偏离 target (允许 5% 误差)
            self.assertLess(abs(s.p50 - target), target * 0.05,
                            f"{s.year}: p50={s.p50} 偏离 target={target} > 5%")

    def test_emergency_full_probability_close_to_1(self):
        """应急储备满额概率应 ~1.0 (再平衡保证)."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        em = result.for_bucket("应急储备")
        for s in em:
            self.assertGreaterEqual(s.full_probability, 0.95,
                                    f"{s.year}: full_prob={s.full_probability} < 0.95")


class TestBucketLevelStrategy(unittest.TestCase):
    """v0.5.2 Bucket-level 分策略收益: 每个 bucket 用自己的 (r_b, v_b)."""

    def test_bucket_weights_by_distance(self):
        """_bucket_weights 按距 withdrawal 年数动态收敛 (近事件 → 偏保守)."""
        from engine.projection import _bucket_weights
        # 节点 bucket: 距事件 1 年 vs 8 年, 权益权重应不同
        w1 = _bucket_weights("近期-改善型购房", 1)
        w8 = _bucket_weights("远期-王小朵本科留学", 8)
        # 1 年: 近期策略 (87.5/5/2.5/5) → 权益 5%
        # 8 年: 远期策略 (38/43/9/10) → 权益 43%
        self.assertLess(w1[1], w8[1], f"1年权益 {w1[1]} 应 < 8年权益 {w8[1]}")
        # 1 年: 固收 87.5%, 8 年: 固收 38%
        self.assertGreater(w1[0], w8[0], f"1年固收 {w1[0]} 应 > 8年固收 {w8[0]}")

    def test_zero_year_to_withdrawal_stays_in_nearest_conservative_band(self):
        """到提取/退休当年(0年剩余期限)不应错误跳到超远期进取档。"""
        from engine.projection import _bucket_weights
        w0 = _bucket_weights("富余资金", 0)
        self.assertEqual(w0, (87.5, 5.0, 2.5, 5.0))

    def test_special_buckets_fixed_weights(self):
        """应急/富余/CI 等特殊 bucket 用固定策略."""
        from engine.projection import _bucket_weights
        em = _bucket_weights("应急储备", None)
        self.assertEqual(em, (100.0, 0.0, 0.0, 0.0))
        sp = _bucket_weights("富余资金", None)
        self.assertEqual(sp, (17.5, 62.5, 5.0, 15.0))
        ci = _bucket_weights("重疾准备金", None)
        self.assertEqual(ci, (90.0, 2.5, 2.5, 5.0))

    def test_surplus_higher_volatility_than_node_bucket(self):
        """富余资金(超远期进取)的 p10-p90 区间宽度应 > 近期节点 bucket."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=256, seed=42)
        sp = result.for_bucket("富余资金")
        # 找最早到期的节点 bucket (近期)
        ih = result.for_bucket("近期-改善型购房")
        sp_dict = {s.year: s for s in sp}
        ih_dict = {s.year: s for s in ih}
        common_years = set(sp_dict.keys()) & set(ih_dict.keys())
        self.assertGreater(len(common_years), 0)
        for yr in sorted(common_years)[:3]:
            sp_spread = sp_dict[yr].p90 - sp_dict[yr].p10
            ih_spread = ih_dict[yr].p90 - ih_dict[yr].p10
            # 富余(进取, 含存量494K) vs 改善型购房(近期固收为主, 含存量948K)
            # 改善型购房 vol 极低(固收为主), 富余 vol 高得多
            self.assertGreater(sp_spread, ih_spread,
                               f"{yr}: 富余 spread {sp_spread:.0f} 应 > 改善型购房 spread {ih_spread:.0f}")

    def test_near_event_more_conservative(self):
        """节点 bucket 接近 withdrawal 时, 权益比例应下降 (近事件策略更保守)."""
        from engine.projection import _bucket_weights
        w_far = _bucket_weights("中期-教育", 6)   # 中期
        w_near = _bucket_weights("近期-教育", 2)  # 近期
        # 中期 57/29/7/7; 近期 87.5/5/2.5/5
        self.assertGreater(w_far[1], w_near[1], f"中期权益 {w_far[1]} 应 > 近期权益 {w_near[1]}")


class TestBucketBreakdown(unittest.TestCase):
    """v0.6 Bucket 资金来源拆分: 路径级一致性 + 跨年连续性."""

    def test_breakdowns_populated(self):
        """breakdowns 字段应与 snapshots 同等数量 (每个 bucket × 每年)."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        self.assertGreater(len(result.breakdowns), 0)
        # breakdowns 数量 = bucket 数量 × 每年
        n_years = max(s.year for s in result.snapshots) - profile.current_year + 1
        expected = len(result.bucket_names) * n_years
        self.assertEqual(len(result.breakdowns), expected)

    def test_path_level_sum_equation(self):
        """P50 路径: starting + cash + returns = ending + withdrawal。"""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        for b in result.breakdowns:
            lhs = b.starting_p50 + b.cash_p50 + b.returns_p50
            rhs = b.ending_p50 + b.withdrawal
            self.assertAlmostEqual(lhs, rhs, delta=1.0,
                msg=f"{b.bucket_name} {b.year}: starting({b.starting_p50}) + cash({b.cash_p50}) + returns({b.returns_p50}) = {lhs} != ending+withdrawal({rhs})")

    def test_year_over_year_continuity(self):
        """跨年连续性: 差值 ≤ prev_ending (允许跨 bucket 流动: 应急 top-up, 节点提取等)."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        # 按 bucket 分组
        for bname in result.bucket_names:
            bbs = sorted(result.for_bucket_breakdown(bname), key=lambda x: x.year)
            for i in range(1, len(bbs)):
                prev_ending = bbs[i-1].ending_p50
                curr_starting = bbs[i].starting_p50
                # 节点 bucket 在 withdrawal_year 提取后清零, 之后 starting/ending 都是 0
                if curr_starting < 1.0:
                    continue
                # 差值应不超过 prev_ending (允许跨 bucket 流动, 如富余 → 应急 top-up)
                if abs(prev_ending) > 100:
                    diff = abs(curr_starting - prev_ending)
                    self.assertLessEqual(diff, abs(prev_ending),
                        f"{bname} {bbs[i].year}: starting={curr_starting}, prev_ending={prev_ending}, 差 {diff:.0f} > prev_ending")

    def test_returns_can_be_negative(self):
        """收益分量可以为负 (市场下行)."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=256, seed=42)
        # 至少一个 bucket 应在某年有负收益
        any_negative = False
        for b in result.breakdowns:
            if b.returns_p50 < 0:
                any_negative = True
                break
        self.assertTrue(any_negative, "应有至少一个 bucket 出现负收益 (P50 路径)")

    def test_emergency_breakdown_keeps_target(self):
        """应急储备 starting 应保持 target (再平衡保证)."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        em_bs = result.for_bucket_breakdown("应急储备")
        target = plan.emergency.amount
        for b in em_bs:
            # starting 和 ending 都应接近 target (再平衡)
            self.assertAlmostEqual(b.starting_p50, target, delta=target * 0.05,
                msg=f"{b.year}: starting_p50={b.starting_p50}, 偏离 target={target}")
            self.assertAlmostEqual(b.ending_p50, target, delta=target * 0.05)

    def test_node_bucket_withdrawal_year_breakdown(self):
        """节点 bucket 在 withdrawal_year 年末提取: starting 保留年初余额, ending 归零。"""
        profile, assumptions, plan, _ = _build()
        if not plan.node_buckets:
            self.skipTest("示例档案无 node_buckets")
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        first_node = plan.node_buckets[0]
        wdl = first_node.withdrawal_year
        if wdl is None:
            self.skipTest("第一个 node bucket 无 withdrawal_year")
        bbs = result.for_bucket_breakdown(first_node.name)
        at_wdl = next((b for b in bbs if b.year == wdl), None)
        self.assertIsNotNone(at_wdl)
        self.assertGreater(at_wdl.starting_p50, 0.0)
        self.assertEqual(at_wdl.withdrawal, round(first_node.amount, 2))
        self.assertAlmostEqual(at_wdl.ending_p50, 0, delta=1.0)
        lhs = at_wdl.starting_p50 + at_wdl.cash_p50 + at_wdl.returns_p50
        rhs = at_wdl.ending_p50 + at_wdl.withdrawal
        self.assertAlmostEqual(lhs, rhs, delta=1.0)

    def test_total_stats_monotonic(self):
        """组合总资产分位数应来自总路径,并保持单调。"""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        self.assertGreater(len(result.total_stats), 0)
        for s in result.total_stats:
            self.assertLessEqual(s.p10, s.p25)
            self.assertLessEqual(s.p25, s.p50)
            self.assertLessEqual(s.p50, s.p75)
            self.assertLessEqual(s.p75, s.p90)

    def test_breakdown_percentile_band(self):
        """总余额扇带 (p10-p90) 应 >= 0, 单调."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        for b in result.breakdowns:
            self.assertLessEqual(b.ending_p10, b.ending_p25, f"{b.bucket_name} {b.year}")
            self.assertLessEqual(b.ending_p25, b.ending_p75, f"{b.bucket_name} {b.year}")
            self.assertLessEqual(b.ending_p75, b.ending_p90, f"{b.bucket_name} {b.year}")

    def test_breakdown_full_probability_matches_stats(self):
        """breakdown.full_probability 应与 stats.full_probability 一致."""
        profile, assumptions, plan, _ = _build()
        result = project_buckets_with_returns(profile, assumptions, plan,
                                              n_sobol_points=64, seed=42)
        # 构造 (bucket, year) -> full_probability 字典
        stats_dict = {(s.bucket_name, s.year): s.full_probability for s in result.snapshots}
        for b in result.breakdowns:
            stats_prob = stats_dict.get((b.bucket_name, b.year))
            self.assertIsNotNone(stats_prob)
            self.assertEqual(b.full_probability, stats_prob,
                f"{b.bucket_name} {b.year}: breakdown full_prob {b.full_probability} != stats {stats_prob}")


class TestTotalPathConservation(unittest.TestCase):
    def test_zero_return_bucket_total_matches_yearly_balance_even_with_negative_cashflow(self):
        """零收益零波动下，bucket 总资产路径必须与不投资参考线完全一致。"""
        sample_text = SAMPLE_YAML.read_text(encoding="utf-8")
        injected = (
            sample_text
            .replace("monthly_expense: 8000", "monthly_expense: 38000", 1)
            .replace("monthly_expense: 6000", "monthly_expense: 26000", 1)
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(injected)
            temp_path = Path(f.name)
        try:
            profile = load_profile(temp_path, current_year=2026)
            assumptions = read_assumptions(ASSUMPTIONS_PATH)
            assumptions = replace(
                assumptions,
                fixed_income_return=0.0,
                fixed_income_volatility=0.0,
                equity_return=0.0,
                equity_volatility=0.0,
                insurance_return=0.0,
                insurance_volatility=0.0,
                alternatives_return=0.0,
                alternatives_volatility=0.0,
            )
            projections = project_to_nodes(profile)
            plan = allocate(profile, projections, assumptions)
            yearly = project_yearly(profile)
            result = project_buckets_with_returns(
                profile, assumptions, plan, n_sobol_points=64, seed=42
            )
            total_by_year = {s.year: s for s in result.total_stats}
            self.assertTrue(any(s.net_cashflow < 0 for s in yearly), "测试档案应出现负现金流年份")
            for snap in yearly[:10]:
                total = total_by_year[snap.year]
                self.assertAlmostEqual(total.p50, round(snap.asset_balance, 2), delta=1.0)
                self.assertAlmostEqual(total.p10, round(snap.asset_balance, 2), delta=1.0)
                self.assertAlmostEqual(total.p90, round(snap.asset_balance, 2), delta=1.0)
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
