# Charts, Return Projection, and QMC Logic Guide

This document is written for advisors.
Its purpose is to explain the charts in the playbook, the logic behind return projection, and the role of `QMC` in the current system.

The goal is not to teach quant finance or programming.
The goal is to help an advisor answer three practical questions:

1. What each chart is actually showing
2. How the bands, lines, and shaded areas are produced
3. How to explain the charts to a client without becoming overly technical

This document explains the **current production logic**, not implementation details.

## 1. The Two Main Chart Families

The current playbook uses two broad families of charts and tables.

### 1.1 Deterministic Projection

These outputs answer:

- If we ignore investment return for a moment, can the household still cover each major milestone?
- How much money is available at each major event year?
- Where does the first shortfall appear, if any?

This layer is useful because it isolates the funding question before adding market uncertainty.

### 1.2 Return-Based Projection

These outputs answer:

- If the allocated buckets participate in investment return, how wide is the range of possible outcomes?
- How does the total household asset path behave over time?
- How do individual buckets behave under weaker and stronger market paths?

This layer does **not** promise a return.
It is a communication tool for discussing plausible ranges under current assumptions.

## 2. What the Main Charts Mean

### 2.1 Total Household Asset Path

This chart combines:

- annual cash inflow
- annual cash outflow
- the deterministic cash-flow reference line
- return-based percentile bands for the total portfolio

How to explain it:

- the bars show household cash movement
- the dashed reference line shows what happens without investment return
- the shaded range shows how total assets may vary if investment return is included

Important point:

- the return-based line is **not guaranteed to stay above** the no-investment reference
- investment can help, but it can also underperform in some paths

### 2.2 Bucket Balance Timeline

This chart stacks all buckets together, such as:

- emergency reserve
- event buckets
- surplus account

How to explain it:

- each color block is one mental account
- event buckets are built up before their event year and then withdrawn at the end of that year
- the outer band shows the range for the total portfolio under return assumptions

### 2.3 Bucket Funding Source Charts

These charts expand each bucket separately.
They typically show:

- starting balance carried from the prior year
- current-year cash contribution
- current-year investment return
- the resulting year-end balance band

How to explain it:

- they help the client see **where the money came from**
- they separate savings discipline from market contribution
- they show that a bucket can have negative return in a year even when the long-run balance still grows

## 3. What the Percentile Bands Mean

The playbook commonly uses five bands:

- `p10`
- `p25`
- `p50`
- `p75`
- `p90`

For client communication, avoid saying `p10` or `p90` unless needed.
Prefer plain-language phrasing:

- weaker outcome range
- common range
- middle outcome
- stronger outcome range

A practical interpretation:

- `p50` is the middle outcome
- `p25-p75` is the more common middle range
- `p10-p90` is a wider outer range

These are **distribution summaries**, not promises and not hard boundaries.

## 4. Why We Use QMC

`QMC` stands for Quasi-Monte Carlo.

In plain language:

- the system needs many possible market paths
- a naive random simulation can be noisy
- QMC generates a more even spread of paths, which usually makes the output more stable for the same number of samples

What an advisor needs to know:

- QMC is a simulation-quality tool, not a claim that the future is knowable
- it improves the smoothness and stability of the range estimates
- it does not remove model risk

## 5. What Actually Drives the Return Projection

The current return-based projection is driven by four ingredients:

1. Asset-class return assumptions
2. Asset-class volatility assumptions
3. Correlation assumptions between asset classes
4. Bucket-level stage weights over time

The bucket logic matters because:

- near-term money is allocated more conservatively
- long-term money can carry more growth exposure
- the surplus account is treated as long-horizon capital unless a retirement switch changes its stage

## 6. Why Bucket Logic Matters More Than a Single Portfolio Average

This methodology does not treat the household as one undifferentiated pool of money.
It separates the household into buckets with different purposes.

That changes the interpretation materially:

- emergency money should behave differently from long-term surplus capital
- money needed in 2 years should not be modeled like money needed in 20 years
- the client can discuss each bucket separately instead of arguing about a single average portfolio

This is one reason the playbook is more readable for family planning than a generic optimizer output.

## 7. Why Event Timing Is End-of-Year

The current system uses an annual, end-of-year convention:

- cash flow is aggregated by year
- event spending happens at the end of the event year
- yearly return is also applied on a yearly basis

This is a modeling choice made for consistency and clarity.
It means:

- the charts are easier to explain
- the cash-flow and bucket logic stay aligned
- the system is not trying to act like a monthly execution planner

## 8. Why the Total Percentile Band Is Not the Sum of Bucket Percentiles

This is important.

The total portfolio percentile band is calculated from the **full portfolio path**, not by summing the `p10` or `p50` of each bucket independently.

Why:

- different buckets move together through shared market paths
- percentiles are not additive
- adding bucket percentiles directly would distort the range

So if a client asks why the total band does not equal the sum of the visible bucket bands, the answer is:

- because the total band is calculated at the full-portfolio path level, which is the correct statistical treatment

## 9. How To Explain Negative Return Years

In the current playbook, some years in the middle outcome can still show negative investment return.

That is not a bug.
It is actually useful:

- it reminds the client that investment return is uncertain
- it prevents the chart from implying “investment always helps”
- it makes the playbook more honest for discussion

Good phrasing:

- “This range includes years where market return may be negative, even if the long-run plan still remains workable.”

## 10. What the Charts Do Not Mean

The charts do **not** mean:

- a guaranteed return
- a promised funding outcome
- a product recommendation
- a precise forecast of market behavior
- a replacement for legal, tax, actuarial, or insurance product advice

They are a planning and communication tool under explicit assumptions.

## 11. How Advisors Should Use These Charts

Recommended advisor posture:

1. Start with milestone coverage, not return
2. Use the total asset path to explain timing pressure
3. Use bucket charts to explain funding order and account purpose
4. Use the return ranges as scenario language, not prediction language
5. Recalculate when household facts change, not only when markets move

## 12. When To Recalculate Instead of Over-Explaining

If a client changes:

- a major event year
- an event amount
- retirement timing
- household income
- ongoing spending
- debt burden
- insurance structure

then recalculation is usually more useful than prolonged interpretation of an outdated chart.

## 13. Relation to the Handbook

These charts sit on top of the current methodology contract:

- event structure: [`handbook/02-life-events.md`](../handbook/02-life-events.md)
- asset assumptions: [`handbook/03-asset-assumptions.md`](../handbook/03-asset-assumptions.md)
- Pareto and stage logic: [`handbook/04-pareto-generation.md`](../handbook/04-pareto-generation.md)
- output contract: [`handbook/05-output-structure.md`](../handbook/05-output-structure.md)

If chart behavior and older prose ever differ, use the current engine behavior and update the prose afterward.
