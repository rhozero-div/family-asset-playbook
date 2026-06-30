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

If anything conflicts, use current code behavior, tests, and the active contract in `handbook/` as the source of truth.
