# Methodology Overview

**Version:** 0.1.0  
**Status:** draft

---

## 1. Core Proposition

> Household asset planning is not about finding one static optimum. It is about building a playbook that can be discussed, recalculated, and updated around life milestones.

The current product form of FAPM is:

- an advisor collects client information
- the system generates a household planning playbook for the client

That playbook is **not**:

- a product recommendation memo
- a promised-return document
- a fully automated decision engine

It is a structured planning document that organizes:

- life events
- cash-flow pressure
- asset buckets
- execution order
- explicit boundaries

## 2. Why This Is Not a Traditional Optimizer

Most classic asset-allocation tools try to output an “optimal answer” under a fixed set of assumptions.
In family planning, assumptions do not stay fixed.

Examples:

- a housing plan rewrites liquidity constraints
- education changes timing needs
- retirement changes income and spending structure
- health changes protection and medical pressure
- career changes alter cash-flow stability

So the problem is not “what is the mathematically best portfolio today?”
The problem is closer to:

- what needs to be protected first
- what can stay flexible
- how funding order changes as life events move

## 3. Current Product Shape

In its current implementation, FAPM works like this:

1. intake through a structured web questionnaire
2. serialization into YAML
3. profile loading and projection
4. event-driven bucket allocation
5. client-readable playbook generation

This means the methodology is already partly operationalized.
If older design notes differ from current behavior, current code and current output win.

## 4. Core Building Blocks

The methodology currently rests on five building blocks:

1. **Household profile**
   - members, ages, retirement ages, income, spending, assets, liabilities, insurance
2. **Life events**
   - major spending milestones such as housing, education, retirement, health, legacy
3. **Asset assumptions**
   - return, volatility, correlation, and stage-weight templates
4. **Mental buckets**
   - emergency reserve, event buckets, and surplus account
5. **Playbook rendering**
   - a client-facing explanation layer over the calculations

## 5. What the Current Methodology Optimizes For

The current methodology is designed to optimize for:

- readability for client discussion
- timing clarity for major milestones
- separation of short-term and long-term money
- repeatability for recalculation
- explicit non-advisory boundaries

It is **not** optimized for:

- product selection
- minute-by-minute execution timing
- pure mathematical elegance detached from client understanding

## 6. Current Calculation Convention

The current engine uses these core conventions:

- cash flow is aggregated annually
- event spending is settled at year end
- projection charts end at `measurement_end_year`
- savings insurance can flow into a linked bucket or the surplus account
- portfolio percentile bands are calculated from full-path portfolio outcomes

These conventions matter because they shape what the playbook means.

## 7. Role of the Advisor

The advisor is not replaced by the methodology.
The advisor is responsible for:

- collecting accurate inputs
- identifying cases outside the methodology boundary
- explaining what the playbook is and is not saying
- deciding when assumptions should be updated
- guiding discussion around trade-offs

## 8. Role of the Client

The client is not a passive recipient.
The client should be able to:

- see the major milestones clearly
- understand where timing pressure comes from
- question the assumptions
- change event timing or scale
- request recalculation as life changes

## 9. What the Playbook Is Meant To Feel Like

The playbook should feel:

- structured rather than abstract
- practical rather than sales-like
- discussable rather than final
- scenario-based rather than predictive

## 10. Relationship to Other Handbook Chapters

- input contract: [`01-input-schema.md`](01-input-schema.md)
- life-event logic: [`02-life-events.md`](02-life-events.md)
- asset assumptions: [`03-asset-assumptions.md`](03-asset-assumptions.md)
- generation logic: [`04-pareto-generation.md`](04-pareto-generation.md)
- output contract: [`05-output-structure.md`](05-output-structure.md)
- boundaries: [`06-boundaries.md`](06-boundaries.md)
- versioning: [`07-versioning.md`](07-versioning.md)

## 11. Authority Rule

If historical notes, older prototypes, or outdated examples conflict with current code behavior, use:

1. the current questionnaire output
2. the current engine behavior
3. the current playbook output
4. the current tests

as the operative truth.
