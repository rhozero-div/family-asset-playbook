# Asset Class Assumptions

**Version:** 0.1.0  
**Status:** draft

---

## 1. Overview

This chapter defines the asset-assumption layer used in playbook generation:

- the role of the core asset classes
- default return and volatility assumptions
- default correlation assumptions
- override boundaries
- update and versioning rules

> Important:
> 1. Current numbers are placeholder defaults for demonstration and planning structure.
> 2. These numbers are **not investment advice** and **not promises of future return**.
> 3. Actual deployment should recalibrate them with real market data.

## 2. Current Core Asset Classes

The methodology currently works with four main classes:

| Class | Code | Role |
|---|---|---|
| Fixed income | `fixed_income` | liquidity support and rigid-spending matching |
| Equity | `equity` | long-term growth |
| Insurance / savings insurance | `insurance` | protection-related capital and long-duration reserve behavior |
| Alternatives | `alternatives` | diversification and non-core exposure |

The current mainline is built around these four core asset classes.

## 3. Current Default Placeholder Assumptions

The current methodology references placeholder-style defaults such as:

- fixed income: lower return, lower volatility
- equity: higher return, higher volatility
- savings-style insurance: low volatility, lower return
- alternatives: moderate-to-higher volatility and diversification role

These are planning assumptions, not product claims.

## 4. Correlation Logic

The current methodology also uses a default correlation matrix between asset classes.
That matrix exists because bucket-level or portfolio-level return projection should not assume each class moves independently.

Key point:

- these are communication and modeling defaults
- they are not precise forecasts of real-market co-movement

## 5. Why These Assumptions Exist

The assumptions are needed because the system must:

- estimate return ranges
- estimate uncertainty width
- distinguish short-horizon and long-horizon money
- generate bucket-level and total-portfolio range charts

Without an assumption layer, the playbook could still do deterministic funding logic, but not return-range communication.

## 6. Advisor Override Boundary

Advisors may override assumptions in the profile when appropriate, especially for:

- return assumptions
- volatility assumptions
- correlation assumptions
- stage-weight assumptions

But the advisor should not treat overrides as hidden product recommendations.
Overrides should remain:

- explainable
- documented
- within a coherent planning narrative

## 7. What Should Not Be Overridden Lightly

The following should remain stable unless the methodology itself changes:

- the existence of the core asset-class roles
- the idea that different buckets can carry different stage logic
- the non-advisory boundary statement

## 8. Runtime Fallback Behavior

The current runtime may fall back to built-in defaults if handbook parsing is incomplete or assumption fields are missing.

This behavior exists for compatibility and operability.
It should not be treated as a substitute for maintaining the handbook properly.

## 9. Update Mechanism

Assumptions should be reviewed when:

- the methodology version changes materially
- return / volatility defaults are intentionally recalibrated
- the explanation layer needs to stay aligned with actual runtime behavior

## 10. Relationship to Other Chapters

- life-event timing: [`02-life-events.md`](02-life-events.md)
- generation logic: [`04-pareto-generation.md`](04-pareto-generation.md)
- output contract: [`05-output-structure.md`](05-output-structure.md)
- boundaries: [`06-boundaries.md`](06-boundaries.md)
- versioning: [`07-versioning.md`](07-versioning.md)

## 11. Authority Rule

If the handbook prose and actual engine behavior diverge, current engine behavior is operative and the handbook should be updated to match it.
