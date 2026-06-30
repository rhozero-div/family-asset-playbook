# Family Life Events

**Version:** 0.1.0  
**Status:** draft

---

## 1. Overview

Life events are the core driver of this methodology.
A family is not modeled as a flat span of time but as a sequence of milestones that change planning constraints.

Each event can change one or more of the following:

- liquidity need
- required spending
- timing pressure
- risk tolerance in practice
- the role of different asset buckets

This chapter defines event categories, fields, timing logic, and how events interact with the rest of the planning system.

## 2. Current Event Types

Typical event categories include:

| Type | Code | Typical meaning |
|---|---|---|
| Housing | `housing` | home purchase, upgrade, down payment support |
| Education | `education` | K-12, international school, college, overseas study |
| Retirement | `retirement` | retirement transition and post-work income change |
| Health | `health` | reserve planning for health-related pressure |
| Legacy | `legacy` | inheritance or family transfer structure |
| Other | `other` | large planned spending not covered above |

## 3. Current Required Event Fields

The most important current fields are:

- `id`
- `type`
- `description`
- `timing_year`
- `estimated_amount`

Optional ownership or context fields may exist, but year and amount are the core planning inputs.

## 4. Why Events Matter Operationally

In the current system, events drive:

- deterministic milestone projection
- bucket creation order
- bucket withdrawal timing
- chart horizon defaults
- summary conclusions about milestone coverage

This means event quality strongly affects the usefulness of the entire playbook.

## 5. Current Timing Convention

The current engine uses a **year-end convention**:

- cash flow is aggregated by year
- event spending is settled at the end of the event year
- return projection also proceeds on a yearly basis

This keeps the entire modeling chain internally consistent.

## 6. Stage Interpretation

The methodology currently uses event distance to determine funding stage.
In plain terms:

- near-term: money needed soon
- mid-term: money needed after a moderate waiting period
- long-term: money needed further out
- ultra-long-term: money with the longest horizon

This stage concept affects:

- default bucket language
- stage color / symbol display
- default stage weights for return projection

## 7. Current Relationship to Buckets

In the current implementation, major events usually become dedicated funding buckets.

The general order is:

1. emergency reserve first
2. event buckets in time order
3. surplus account after all identified targets

This means event sequencing is not cosmetic.
It directly changes the allocation story.

## 8. Event Changes and Recalculation

The playbook should be recalculated when an event is:

- added
- removed
- delayed
- moved earlier
- resized materially

This is because event changes can alter:

- funding order
- shortfall timing
- bucket stage assignment
- overall family planning conclusions

## 9. Retirement as an Event

Retirement is special.
It is not just a spending event.
It is also a structural shift in:

- income
- spending pattern
- time horizon
- surplus-account stage logic

That is why retirement is treated as a core milestone in the current methodology.

## 10. Event Quality Guidance

Useful event entries should be:

- concrete enough to discuss timing
- realistic enough to anchor scale
- limited enough to avoid becoming fantasy scenarios

The methodology works best when events are planning-grade signals, not exhaustive life storytelling.

## 11. Overseas / Cross-Border Implications

Some event types may imply overseas exposure, such as:

- overseas education
- migration
- cross-border retirement

The current methodology can acknowledge these pressures, but it is not a full cross-border planning framework.
Complex tax, legal, and jurisdictional issues remain outside scope.

## 12. Current Non-Use Cases

The event framework is not meant to handle:

- every monthly lifestyle preference
- product-level trade execution
- enterprise cash-flow modeling
- highly complex trust or cross-border structuring

When a case crosses that line, the playbook should be treated as incomplete and specialist help should be introduced.

## 13. Relationship to Other Chapters

- input contract: [`01-input-schema.md`](01-input-schema.md)
- asset assumptions: [`03-asset-assumptions.md`](03-asset-assumptions.md)
- generation logic: [`04-pareto-generation.md`](04-pareto-generation.md)
- output contract: [`05-output-structure.md`](05-output-structure.md)

## 14. Authority Rule

If older documents mention now-removed fields such as event certainty behavior that the current questionnaire no longer uses, current runtime behavior takes priority.
