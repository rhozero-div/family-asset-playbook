# Documentation Index

`handbook/` contains the product and methodology contract.
`docs/` keeps runtime, validation, and explanatory documents only.

Recommended reading order for the current repo:

1. [local-validation-walkthrough.md](local-validation-walkthrough.md)
   - The real end-to-end local validation flow
   - Best starting point if you want to verify that the questionnaire-to-playbook path still works

2. [summary-logic-guide.md](summary-logic-guide.md)
   - Explains how the Executive Summary is generated

3. [chart-and-qmc-logic-guide.md](chart-and-qmc-logic-guide.md)
   - Explains the client-facing logic behind charts, return ranges, and QMC-based projection

4. [insurance-planner-parameter-guide.md](insurance-planner-parameter-guide.md)
   - Explains the questionnaire's insurance default parameters and how they affect both the insurance section inside the final playbook and the incremental insurance input page opened from Plan A / Plan B

5. [planner-architecture-roadmap.md](planner-architecture-roadmap.md)
   - Records the current architecture boundary: the main product flow is questionnaire -> final playbook, with an optional advisor-side insurance input loop after the playbook is generated

If anything conflicts, use current code behavior, tests, and the active contract in `handbook/` as the source of truth.
