export const deployLinks = {
  huggingFace:
    process.env.NEXT_PUBLIC_FAPM_HF_URL || "https://rhozero-div-family-asset-playbook.hf.space/",
  cloudflare:
    process.env.NEXT_PUBLIC_FAPM_CF_URL || "/",
};

export const familyMembers = [
  { name: "Mr. Wang", role: "Primary Earner", age: 38, retirementAge: 60 },
  { name: "Mrs. Wang", role: "Secondary Earner", age: 36, retirementAge: 55 },
  { name: "Wang Xiaoduo", role: "Dependent", age: 6, retirementAge: 60 },
];

export const majorEvents = [
  { year: 2029, title: "Home Upgrade", amount: "RMB 3.0M" },
  { year: 2032, title: "International High School", amount: "RMB 0.8M" },
  { year: 2035, title: "Overseas Undergraduate Study", amount: "RMB 2.0M" },
  { year: 2048, title: "Retirement Transition", amount: "Year-end switch" },
];

export const summaryBullets = [
  "Current financial assets plus future net cash flow are enough to cover the core recorded milestones, but the three years before the home purchase should stay more liquid.",
  "The surplus account is the long-term growth bucket; the demo uses a common outcome range to show long-run volatility without implying a promised return.",
  "The insurance section shows the key protection gaps, two suggestion paths, and a follow-up advisor input loop instead of stopping at a single static recommendation.",
];

export const bucketRows = [
  { name: "Emergency Reserve", amount: "RMB 0.18M", color: "var(--mint)" },
  { name: "Housing Bucket", amount: "RMB 1.26M", color: "var(--amber)" },
  { name: "Education Bucket", amount: "RMB 0.54M", color: "var(--coral)" },
  { name: "Surplus Account", amount: "RMB 0.72M", color: "var(--ink)" },
];

export const chartYears = ["2026", "2029", "2032", "2035", "2040", "2048"];

export const chartBands = [
  { label: "Weaker Outcome", values: [148, 152, 176, 201, 248, 315] },
  { label: "Common Outcome", values: [150, 168, 210, 265, 362, 486] },
  { label: "Stronger Outcome", values: [152, 182, 236, 326, 468, 635] },
];
