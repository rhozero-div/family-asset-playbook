# Pareto Generation Rules

**Version:** 0.1.0  
**Status:** draft

---

## 1. Overview

This chapter defines the rule layer that turns household constraints into representative planning structures.

It covers:

- how the methodology moves from profile constraints to stage-based allocation logic
- how different planning styles relate to each other
- how uncertainty narrows as events approach
- the boundary between this methodology and traditional optimization solvers

This is a methodology chapter, not a code chapter.

## 2. Input and Output

### 2.1 Inputs

The rule layer reads from:

- the client profile
- life-event timing
- asset assumptions
- advisor risk preference
- stage-weight overrides if provided

### 2.2 Outputs

Conceptually, the methodology produces representative planning skeletons rather than one mathematically “perfect” allocation.

In the current product form, that idea is reflected operationally through:

- stage-based weights
- event-driven bucket order
- emergency-first logic
- surplus-account logic
- summary-level interpretation

## 3. Why This Is Called “Pareto” in the Handbook

Historically, this chapter described three representative planning skeletons:

- conservative
- balanced
- aggressive

The important idea was never “solve for one point.”
The important idea was “show a family a small set of interpretable structures that reflect different trade-offs.”

The current product still follows that spirit, even though the actual runtime is now more concretely expressed through bucket rules and stage weights.

## 4. Current Practical Rule Chain

The current engine effectively follows this order:

1. determine emergency reserve need
2. order major events by timing
3. create event buckets in time order
4. send remaining long-horizon money to the surplus account
5. apply stage-based return logic for range projection

This is the real current behavior and should be treated as the active contract.

## 5. Current Annual Net-Surplus Routing Rule

The current bucket-level implementation routes annual net surplus in this fixed order:

1. refill emergency reserve to target first
2. fund the earliest unmet event bucket next
3. continue in event-time order
4. send only remaining funds to the surplus account

This rule directly affects:

- the playbook’s funding-order narrative
- bucket tables
- bucket charts
- the interpretation of milestone pressure

## 6. Current Emergency Rebalancing Rule

The current bucket projection also includes an emergency rebalancing rule:

- if the emergency reserve is above target, excess can flow outward into later funding needs
- if the emergency reserve is below target and surplus money exists, surplus funds can be used to top it back up

The purpose is to keep emergency liquidity near its intended level rather than letting it drift indefinitely.

## 7. Current Surplus-Account Rule

When the household still has capital after emergency and event needs are accounted for, the current methodology creates a **surplus account**.

Its current role is:

- long-horizon flexible capital
- separated from near-term milestone money
- typically treated with longer-horizon stage logic

If a retirement event exists, the surplus account can use retirement timing as a stage-switch reference in the current implementation.

## 8. Current Feasibility Threshold Concept

For milestone shortfalls, the engine may estimate a required annualized return to fill the gap.
That estimate is then interpreted against broad feasibility bands, not sold as a target return.

The purpose is communication:

- “this gap is plausible within a conservative frame”
- “this gap probably needs a more growth-heavy frame”
- “this gap is not reasonable to solve through return assumptions alone”

If the required return becomes too high, the intended client conversation should shift toward:

- reducing the target
- delaying the target
- increasing savings or income

not promising unrealistic investment performance.

## 9. Required-Return Solver Boundary

The required-return estimate is a bounded communication tool, not a recommendation engine.
It exists to signal pressure, not to suggest a client should pursue extreme returns.

## 10. Uncertainty Narrowing

The methodology assumes that planning width should narrow as an event approaches.

In plain language:

- far-away goals can tolerate wider planning ranges
- near-term goals should use tighter and more conservative ranges

This logic is reflected today through stage weights and related helpers.

## 11. Why This Methodology Is Not Classical MPT

This methodology does **not** aim to be a pure mean-variance optimizer.
Its differences include:

- it centers family events, not abstract portfolio efficiency
- it uses buckets and timing order
- it prioritizes interpretability
- it allows the client and advisor to discuss trade-offs in plain language

The methodology can still use mathematical tools such as simulation and distribution summaries.
But the household planning frame is rule-led, not optimizer-led.

## 12. When Advisor Intervention Is Required

Advisor intervention becomes more important when:

- assumptions are materially overridden
- event order changes significantly
- a large shortfall appears
- retirement structure changes materially
- the household case starts to exceed normal family-planning scope

## 13. Relationship to Other Chapters

- input contract: [`01-input-schema.md`](01-input-schema.md)
- life-event rules: [`02-life-events.md`](02-life-events.md)
- asset assumptions: [`03-asset-assumptions.md`](03-asset-assumptions.md)
- output contract: [`05-output-structure.md`](05-output-structure.md)
- boundaries: [`06-boundaries.md`](06-boundaries.md)

## 14. Authority Rule

Older prose about “three skeleton points” should be interpreted through the current runtime shape.
Where old wording and current bucket logic differ, current bucket logic is the active contract.
