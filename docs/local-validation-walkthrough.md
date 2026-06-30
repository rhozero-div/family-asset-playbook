# End-to-End Local Validation Walkthrough

This document describes the **currently runnable** local validation flow in this repository.
All sample data mentioned here is fictional.

## 1. Recommended Validation Path

The preferred validation chain is:

1. Open the web questionnaire
2. Enter a household profile collected by an advisor
3. Let the frontend generate YAML
4. Validate the YAML
5. Generate the client playbook

If you want to verify the **current product**, use this path first.

## 2. Start the Web App

From the repo root:

```bash
source .venv/bin/activate
pip install -r web/requirements.txt
FAPM_ENABLE_SERVER_STORAGE=1 .venv/bin/python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Notes:

- `FAPM_ENABLE_SERVER_STORAGE=1` enables advisor-style local persistence
- Saved YAML files and indexes are written into `profiles/`
- If you want public-demo behavior, omit that environment variable

## 3. Use the Questionnaire

Recommended path:

1. Open `/questionnaire`
2. Fill in the household members and life-milestone context
3. Complete income, spending, major events, assets, insurance, and assumptions
4. Click `Generate Playbook`

You can also open the built-in sample:

```text
http://127.0.0.1:8000/questionnaire/sample-wang
```

## 4. What To Check In the Questionnaire

Before generating the playbook, confirm:

- Family members are entered first, and downstream sections reuse that roster
- Retirement ages are filled in where needed
- Major spending events have years and amounts
- The `measurement_end_year` is not earlier than the last major event year
- Financial assets, liabilities, and liquidity target are filled in consistently
- Risk preference and stage-weight assumptions match the intended scenario

## 5. What To Check In the Generated Playbook

After generation, review the following in order:

1. **Executive Summary**
   - Are the high-level conclusions readable and aligned with the rest of the playbook?
   - Are milestone coverage and surplus-account return ranges explained clearly?

2. **Client Overview**
   - Do starting assets, cash flow, retirement assumptions, and milestone tables match the questionnaire?

3. **Asset Projection**
   - Do the event-year balances and major milestone outcomes make sense?
   - Does the chart horizon end at the configured `measurement_end_year`?

4. **Allocation Execution Plan**
   - Does the bucket structure align with the event order?
   - Do initial allocation, annual surplus routing, and bucket charts remain internally consistent?

## 6. QMC Dependency Check

If the runtime cannot resolve `qmc`, the return-based projection path may fail or degrade.

Recommended setup:

```bash
pip install -e /path/to/Quasi-Monte-Carlo-Generator
```

If needed, confirm that Python can import it:

```bash
.venv/bin/python -c "import qmc; print(qmc.__file__)"
```

## 7. Suggested Regression Checks

When you change questionnaire logic, projection logic, or rendering logic, re-check:

- Questionnaire form loads in both Chinese and English
- Save / load still works locally when persistence is enabled
- Sample profile still generates a playbook successfully
- English homepage and English playbook contain no system Chinese
- Major milestone order, bucket naming, and chart horizons still match the questionnaire

## 8. If Something Looks Wrong

Use this order of diagnosis:

1. Check the questionnaire output
2. Check the generated YAML
3. Check the projection assumptions
4. Check the rendered playbook
5. Check tests related to the affected module

If documentation and behavior differ, prefer actual code behavior and update the documentation afterward.
