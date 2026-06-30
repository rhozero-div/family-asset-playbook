# FAPM Frontend Demo

This directory contains a standalone frontend demo shell intended for deployment to Cloudflare Pages.

## Purpose

- Show the product structure, questionnaire sections, and playbook reading flow to the public
- Avoid changing the main FastAPI questionnaire / playbook chain directly
- Work alongside the real Hugging Face Spaces app as a separate public-facing demo layer

## Local Run

```bash
cd frontend
npm install
npm run dev
```

Default local address:

```text
http://127.0.0.1:3013
```

## Recommended Deployment Use

- Use this frontend when you want a lightweight public demo
- Use the FastAPI app when you want the real questionnaire and playbook generation workflow

## Recommended Cloudflare Pages Settings

- Build command: `npm run build`
- Output directory: `out`

## Optional Environment Variables

- `NEXT_PUBLIC_DEMO_URL`
  - Public link to the live product demo
- `NEXT_PUBLIC_PLAYBOOK_DEMO_URL`
  - Optional link to a specific playbook demo
