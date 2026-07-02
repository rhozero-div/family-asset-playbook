"""保险规划逻辑测试。"""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.profile_loader import load_profile  # noqa: E402
from insurance_planner.logic import PlanningPreferences, analyze_profile  # noqa: E402


class TestInsurancePlannerLogic(unittest.TestCase):
    def test_sample_profile_generates_two_plans(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        result = analyze_profile(profile)

        self.assertGreater(result.metrics.annual_income, 0)
        self.assertGreater(len(result.needs), 0)
        self.assertEqual(result.core_plan.scenario_key, "core")
        self.assertEqual(result.balanced_plan.scenario_key, "balanced")
        self.assertLessEqual(result.core_plan.premium_used_annual, result.core_plan.budget_annual + 1e-6)
        self.assertLessEqual(result.balanced_plan.premium_used_annual, result.balanced_plan.budget_annual + 1e-6)

    def test_core_plan_prioritizes_first_need_at_least_as_much_as_balanced(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        result = analyze_profile(profile)
        key = (result.needs[0].member_name, result.needs[0].product_label)

        core_item = next(item for item in result.core_plan.allocations if (item.member_name, item.product_label) == key)
        balanced_item = next(item for item in result.balanced_plan.allocations if (item.member_name, item.product_label) == key)
        self.assertGreaterEqual(core_item.fill_ratio, balanced_item.fill_ratio)

    def test_manual_premium_cap_overrides_auto_budget(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        result = analyze_profile(
            profile,
            PlanningPreferences(manual_premium_cap_annual=12000),
        )
        self.assertEqual(result.metrics.premium_budget_annual, 12000)

    def test_gap_explanation_mentions_total_premium_change(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        result = analyze_profile(profile)
        mr_wang = next(view for view in result.member_views if view.member_name == "王先生")
        self.assertTrue(any("年保费会从约" in line for line in mr_wang.gap_explanation))

    def test_responsibility_family_puts_term_before_ci_for_earners(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        result = analyze_profile(profile)
        mr_wang_term = next(
            need for need in result.needs if need.member_name == "王先生" and need.product_key == "term_life"
        )
        mr_wang_ci = next(
            need for need in result.needs if need.member_name == "王先生" and need.product_key == "critical_illness"
        )
        self.assertLess(mr_wang_term.priority_rank, mr_wang_ci.priority_rank)

    def test_child_does_not_receive_term_life_need(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        result = analyze_profile(profile)
        self.assertFalse(any(need.member_name == "王小明" and need.product_key == "term_life" for need in result.needs))

    def test_independent_adult_puts_ci_before_term(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        solo_profile = replace(
            profile,
            total_outstanding_debt=0.0,
            monthly_liabilities=0.0,
            events=tuple(),
            members=(
                replace(
                    profile.members[0],
                    name="李女士",
                    role="secondary_breadwinner",
                    age=32,
                    annual_income=300000.0,
                    monthly_expense=12000.0,
                    term_life_coverage=0.0,
                    critical_illness_coverage=0.0,
                ),
            ),
            total_annual_income=300000.0,
            monthly_living_expense=12000.0,
        )
        result = analyze_profile(solo_profile)
        ci_need = next(need for need in result.needs if need.product_key == "critical_illness")
        term_need = next(need for need in result.needs if need.product_key == "term_life")
        self.assertLess(ci_need.priority_rank, term_need.priority_rank)

    def test_dependent_adult_with_buffered_income_switches_to_independent_logic(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        adult_child = replace(
            profile.members[2],
            name="王小明",
            age=23,
            role="dependent",
            annual_income=0.0,
            income_start_age=22,
            income_start_annual=180000.0,
            monthly_expense=8000.0,
            term_life_coverage=0.0,
            critical_illness_coverage=0.0,
        )
        updated_members = (profile.members[0], profile.members[1], adult_child)
        updated_profile = replace(
            profile,
            members=updated_members,
            total_annual_income=profile.members[0].annual_income + profile.members[1].annual_income + adult_child.income_start_annual,
        )
        result = analyze_profile(updated_profile)
        child_ci = next(
            need for need in result.needs if need.member_name == "王小明" and need.product_key == "critical_illness"
        )
        child_term = next(
            need for need in result.needs if need.member_name == "王小明" and need.product_key == "term_life"
        )
        self.assertLess(child_ci.priority_rank, child_term.priority_rank)

    def test_questionnaire_assumptions_can_override_insurance_defaults(self):
        profile = load_profile(ROOT / "profiles" / "sample-wang.yaml", current_year=2026)
        updated_assumptions = dict(profile.assumptions or {})
        updated_assumptions["insurance_planner"] = {
            "term_multiplier_with_dependents": 8.5,
            "term_multiplier_without_dependents": 3.5,
            "ci_income_multiple": 4.0,
            "ci_expense_years": 6.0,
            "child_ci_target": 450000.0,
            "elder_ci_target": 350000.0,
            "adult_independence_buffer": 1.35,
            "include_hci_upgrade": False,
        }
        updated_profile = replace(profile, assumptions=updated_assumptions)
        result = analyze_profile(updated_profile)

        self.assertAlmostEqual(result.preferences.term_multiplier_with_dependents, 8.5)
        self.assertAlmostEqual(result.preferences.adult_independence_buffer, 1.35)
        self.assertFalse(result.preferences.include_hci_upgrade)


if __name__ == "__main__":
    unittest.main()
