# Executive Summary Logic Guide

This document is written for advisors.
Its purpose is to explain how the **Executive Summary** section of the playbook is generated, so advisors can:

1. understand what the section is doing
2. explain to clients why the playbook reaches those conclusions
3. distinguish methodology logic from plain-language presentation

This document explains logic and interpretation, not code details.

## 1. What the Executive Summary Is For

The Executive Summary is not an independent second opinion layered on top of the playbook.
It is a compressed reading layer that pulls the most decision-relevant conclusions to the front.

Its job is to answer five questions quickly:

1. Can the recorded major milestones be covered?
2. If there is a surplus account, what does its long-run return range look like?
3. What stage is the household in right now, and what should be handled first?
4. Is there an obvious protection gap in the insurance structure?
5. What signals should be monitored, and what changes should trigger recalculation?

## 2. The Summary Uses Existing Results

The Executive Summary does not create a separate model.
It reads from the same underlying outputs as the rest of the playbook:

- client profile
- major milestone projection
- yearly cash-flow projection
- allocation plan
- bucket projection with return ranges
- insurance structure analysis

So when the summary changes, it should usually be because the underlying planning inputs or calculations changed.

## 3. The Highest-Level Conclusions

The current summary starts with two high-level conclusions.

### 3.1 Major Milestone Coverage Conclusion

This conclusion answers:

- Under the current profile and assumptions, can the recorded major milestones be covered?

If every milestone is covered:

- the summary states that the milestones can be covered
- it usually mentions the last milestone and the approximate remaining balance afterward

If a shortfall exists:

- the summary identifies the earliest uncovered milestone
- it reports the approximate funding gap

Why this comes first:

- clients usually care first about whether the plan “works” for the life events they already know about

### 3.2 Long-Term Surplus Account Return Conclusion

This conclusion appears when a separate surplus account exists.

It answers:

- If long-horizon surplus capital is held through the current modeled horizon, what does the rough annualized growth range look like?

The summary communicates:

- a middle annualized outcome
- a weaker long-run range
- a stronger long-run range

Why it matters:

- it helps distinguish milestone funding from true long-term capital
- it gives clients a useful way to think about the role of surplus money without turning the playbook into a product pitch

## 4. Overall Stage Reading

After the headline conclusions, the summary gives a current-stage reading.

This is not based on a single score.
It is chosen from a set of rule-based cues such as:

- whether current monthly surplus is negative
- whether an early shortfall already appears in the milestone projection
- whether a major event is close in time
- whether retirement cash-flow pressure is approaching
- whether a meaningful surplus account already exists

The current logic typically classifies the household into one of these states:

- cash-flow repair first
- goal trade-off and budget reordering first
- near-term milestone protection first
- retirement preparation brought forward
- sustainable long-term growth after bucket separation
- mid-term accumulation in progress

Why this matters:

- it gives the client a practical frame for reading the rest of the playbook
- it keeps the summary action-oriented rather than descriptive only

## 5. Top Priorities

The next part extracts the most useful actions for the current case.

These are generated from the interaction between:

- current cash surplus
- emergency reserve status
- earliest underfunded bucket
- nearest milestone
- retirement gap
- whether a long-term surplus account already exists

Typical action patterns include:

- repair monthly cash flow first
- refill the emergency buffer first
- lock near-term milestone money separately
- keep funding the nearest underfunded bucket on schedule
- separate long money from near money
- prepare for post-retirement cash-flow gap

These are not product recommendations.
They are priority-order planning actions.

## 6. Insurance Structure Suggestion

The current insurance paragraph is intentionally modest in scope.

It does **not** attempt full insurance product planning, because the questionnaire does not yet collect the inputs required for a full recommendation engine, such as:

- actual household premium burden
- product terms and policy details
- product-level premium-to-coverage trade-offs

So the current summary focuses on **structure gaps**, not product design.

It looks for missing or weak areas such as:

- medical coverage
- critical illness coverage
- term life coverage for key earners

And it combines that with basic premium-pressure awareness:

- if cash flow is already tight, the summary should not imply “buy everything at once”
- if protection gaps exist, the advice should emphasize priority order and affordability discipline

## 7. Monitoring Signals

The summary then highlights a short list of signals worth monitoring over time.

These usually include:

- monthly surplus relative to its current baseline
- whether the emergency reserve stays ring-fenced
- whether the nearest underfunded bucket is progressing on schedule
- the tightest year in regular net cash flow
- debt-service burden
- post-retirement monthly gap
- whether surplus capital is being pulled forward to support near-term needs

Why this matters:

- clients do not need to monitor every number
- they do need a short list of “watch these first” signals

## 8. Recalculation Triggers

The final part of the summary lists changes that should trigger recalculation.

These are currently framed around real-life changes, such as:

- meaningful income change
- meaningful spending or debt-payment change
- adding, removing, moving, or resizing a major milestone
- retirement timing change
- education path change
- housing-plan change
- prolonged use of the emergency layer
- early use of the surplus account

The underlying principle is:

- recalculation is driven more by household-fact changes than by day-to-day market noise

## 9. Why the Summary Uses Plain Language

The playbook uses quantified logic underneath, but the summary avoids overly technical vocabulary where possible.

For example, instead of leading with percentile jargon:

- use “weaker outcome range”
- use “common range”
- use “middle outcome”
- use “stronger outcome range”

The aim is not to hide rigor.
The aim is to present rigor in a form clients can use.

## 10. What the Summary Does Not Do

The Executive Summary does **not**:

- replace the detailed projection tables
- replace the bucket allocation logic
- provide product recommendations
- guarantee future returns or milestone success
- replace legal, tax, actuarial, or insurance specialists

It is a reading layer and action-priority layer, not a substitute for the rest of the playbook.

## 11. Best Advisor Use

Recommended advisor workflow:

1. Read the Executive Summary first
2. Confirm that its claims match the underlying projection tables
3. Use it as the opening frame in client discussion
4. Move into the detailed sections only after the client understands the headline logic

This keeps the conversation structured:

- first the planning conclusion
- then the reasoning
- then the detailed mechanics

## 12. Relation to the Rest of the Methodology

The Executive Summary depends on the current methodology contract:

- input contract: [`handbook/01-input-schema.md`](../handbook/01-input-schema.md)
- life-event logic: [`handbook/02-life-events.md`](../handbook/02-life-events.md)
- asset assumptions: [`handbook/03-asset-assumptions.md`](../handbook/03-asset-assumptions.md)
- output contract: [`handbook/05-output-structure.md`](../handbook/05-output-structure.md)
- chart logic: [chart-and-qmc-logic-guide.md](chart-and-qmc-logic-guide.md)

If summary wording and current calculation ever diverge, trust the current calculation first and update the wording afterward.
