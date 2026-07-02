# Insurance Planner Default Parameters

This note explains the `Insurance Planning Defaults` subsection under `8. Projection Assumptions (Advanced)` in the questionnaire.

These values are saved with the questionnaire and become the default inputs for the insurance section inside the final playbook.  
They also carry into the advisor-side insurance input page opened from Plan A or Plan B.  
If you intentionally use the retained standalone insurance page and provide manual overrides there, those manual values take precedence for that run.

## 1. Budget Parameters

### Annual premium cap

- Field: `manual_premium_cap_annual`
- Meaning: a hard manual cap for the household's total annual premium budget
- Effect:
  - If filled, it overrides the automatic budget logic
  - Plan A and Plan B both allocate within this cap

### Auto budget ratio

- Field: `auto_budget_ratio_pct`
- Meaning: if no manual premium cap is entered, use this share of annual income as the starting point for the automatic premium budget
- Effect:
  - The system starts from `annual income × ratio`
  - Then constrains it with existing premiums, current surplus, and future pressure

### If both are left blank

The system still sets a budget automatically. It currently looks at:

- current annual income
- current annual surplus
- existing annual premium
- major events over the next 10 years
- whether the next 10 years show a projected cash-flow gap

So leaving both blank does not mean "no budget"; it means the system estimates the budget on its own.

## 2. Term-Life Target Parameters

### Term multiple for responsibility-heavy households

- Field: `term_multiplier_with_dependents`
- Typical use:
  - households with minor children
  - dependent elders
  - material debt responsibility
  - or clear dependence on that member's income
- Effect:
  - term-life target considers `income × this multiple`
  - and compares it against the member's share of the household responsibility pool

### Term multiple for low-responsibility households

- Field: `term_multiplier_without_dependents`
- Typical use:
  - independent adults
  - lower-responsibility households
- Effect:
  - term-life targets stay more conservative
  - they usually rely on the income-multiple method rather than a heavy responsibility-pool adjustment

## 3. Critical-Illness Target Parameters

### Income multiple

- Field: `ci_income_multiple`
- Meaning: measures the impact of illness on income interruption

### Expense years

- Field: `ci_expense_years`
- Meaning: measures how many years of ordinary spending should be reserved for treatment and recovery

### Are they redundant?

No. They represent two different lenses:

- income-multiple method
  - focuses on earnings interruption
- expense-years method
  - focuses on household spending buffer

The current algorithm takes the higher of the two.  
They are compared, not added together.

## 4. Child and Elder Critical-Illness Targets

### Child critical-illness target

- Field: `child_ci_target`
- Current method: absolute amount

Children are not modeled through income replacement, so the system currently uses a direct absolute-value target.

### Elder critical-illness target

- Field: `elder_ci_target`
- Current method: absolute floor, then compared against a personal-expense-based target

Elders are also not modeled as a share of household income. The system uses a more stable absolute-value baseline.

## 5. Adult-Dependent Independence Threshold

### Adult independence buffer

- Field: `adult_independence_buffer`
- Purpose: decides when an adult dependent moves from "still supported by the household" into "independent adult"

Current rule:

- `projected annual income >= personal annual regular spending × this buffer`

Only after that threshold is met does the system switch the member into the independent-adult recommendation logic.

## 6. High-End Medical Toggle

### Consider HCI upgrade

- Field: `include_hci_upgrade`
- Effect:
  - if turned off
    - the insurance planner does not generate HCI / premium-medical upgrade recommendations
  - if turned on
    - the planner still only considers HCI when income or assets are high enough

## 7. Current Method Boundary

These parameters do three things:

- adjust budget
- adjust target coverage
- adjust role-switching and recommendation scope

They do not turn the module into a pricing engine.  
The module still provides high-level protection structure guidance only, not product recommendation, underwriting, or real premium quotes.
