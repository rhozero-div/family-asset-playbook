# Input Schema

**Version:** 0.1.0  
**Status:** draft

---

## 1. Purpose of This Chapter

This chapter describes the **actual input schema used by the current production chain**.

“Current production chain” specifically means:

- the web questionnaire
- the YAML produced by the frontend
- the fields actually consumed by `engine.profile_loader`

If older notes, legacy templates, or outdated examples conflict with this chapter, this chapter and current code behavior take priority.

## 2. Current Main Flow

The current intake path is:

1. advisor fills in the web questionnaire
2. frontend serializes the form into YAML
3. backend validates and loads the profile
4. projection and allocation logic consume the loaded fields
5. the playbook renderer uses those results

## 3. Current Questionnaire Structure

The current questionnaire is organized as:

1. family members and life-milestone context
2. income
3. regular spending
4. major spending plan
5. current assets
6. current insurance
7. risk preference
8. advanced assumptions

## 4. Top-Level Data Areas

The current profile is effectively organized into these logical areas:

- `family`
- `events`
- `assets`
- `advisor_assessment`
- `assumptions`

Some legacy compatibility fields may still exist, but current logic is centered on the member-driven structure.

## 5. Family Members

Each member may provide fields such as:

- `name`
- `age`
- `role`
- `annual_income`
- `income_start_age`
- `income_start_annual`
- `monthly_expense`
- `retirement_age`
- `retirement_pension`
- `retirement_annuity`
- `retirement_expense_coeff`
- healthcare-related fields
- insurance-related fields

The member roster is important because downstream sections reuse it.

### 5.1 Current Roles

Typical roles include:

- `primary_breadwinner`
- `secondary_breadwinner`
- `dependent`
- `dependent_elder`
- `other`

The role influences interpretation more than hard validation.

## 6. Income Inputs

The current methodology supports:

- current annual income for working members
- simplified future income start age and future annual income for minors or not-yet-working members
- pension and annuity estimates after retirement

The goal is not payroll precision.
The goal is to estimate future household cash flow at a planning level.

## 7. Spending Inputs

The current spending model includes:

- current monthly spending by member
- retirement spending coefficient by member
- household-level extra monthly spending
- household liabilities entered as cash-flow pressure

This design supports future cash-flow estimation at the member level while still allowing some household-level items.

## 8. Major Events

Each event typically contains:

- `id`
- `type`
- `description`
- `timing_year`
- `estimated_amount`
- optional owner-related context

The current engine uses event year and amount as the most critical planning fields.

### 8.1 Event Types

Typical event types include:

- `housing`
- `education`
- `retirement`
- `health`
- `legacy`
- `other`

## 9. Assets

The current asset intake is focused on:

- primary residence value
- financial assets
- liquidity reserve target in months
- savings insurance
- liabilities

Financial assets are treated as the initial investable base for the planning engine.

## 10. Insurance

The current insurance input supports broad structure review rather than full product planning.

Relevant fields can include:

- medical coverage flag, annual premium, and remaining pay years
- term life coverage, annual premium, and remaining pay years
- critical illness coverage, annual premium, and remaining pay years
- high-end medical coverage, annual premium, and remaining pay years
- other insurance annual premium and remaining pay years
- reimbursement ratio
- retirement healthcare annual spending, growth rate, and annual cap
- savings insurance amount and premium
- linked bucket for savings insurance

In the current questionnaire UI, section 6 is member-driven:

- one member block per family member
- one row per insurance product inside that member block
- savings insurance remains a separate multi-row household section

The methodology currently uses this to identify structure gaps and to support incremental insurance re-runs from the playbook, not product recommendations.

## 11. Advisor Assessment

The advisor layer typically includes:

- risk preference
- notes
- optional interpretation fields

This is where human override, context, and explanation live.

## 12. Assumptions Override

The profile can override default assumptions, including:

- asset-class return assumptions
- volatilities
- correlations
- phase weights
- projection settings

If present, these overrides take precedence over handbook defaults for the affected fields.

## 13. Current Validation Principles

The current validation logic cares most about:

- required numeric fields being present where needed
- event year ordering making sense
- measurement end year not being earlier than the last major event year
- questionnaire output being parseable into the runtime profile shape

Validation is meant to keep the workflow usable, not to act like a rigid actuarial data warehouse.

## 14. Backward Compatibility Reality

Some legacy fields still appear in examples or old notes.
Where the current member-based questionnaire and the old aggregate-style fields differ:

- prefer the member-based structure
- preserve compatibility only where runtime behavior still explicitly supports it

## 15. Data Privacy Note

Client profiles may contain sensitive household information.
When using local persistence:

- YAML and indexes are written into `profiles/`
- operators should treat those files as sensitive
- demo deployments should default to non-persistent public mode unless explicitly intended otherwise

## 16. Relationship to Other Chapters

- life-event rules: [`02-life-events.md`](02-life-events.md)
- asset assumptions: [`03-asset-assumptions.md`](03-asset-assumptions.md)
- generation logic: [`04-pareto-generation.md`](04-pareto-generation.md)
- output contract: [`05-output-structure.md`](05-output-structure.md)

## 17. Authority Rule

The authoritative schema is defined by:

1. the current questionnaire behavior
2. the YAML it generates
3. the fields consumed by the current engine

This chapter should be updated whenever those three drift.
