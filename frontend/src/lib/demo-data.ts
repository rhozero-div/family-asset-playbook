export const deployLinks = {
  huggingFace:
    process.env.NEXT_PUBLIC_FAPM_HF_URL || "https://huggingface.co/spaces/your-space",
  cloudflare:
    process.env.NEXT_PUBLIC_FAPM_CF_URL || "https://your-project.pages.dev",
};

export const familyMembers = [
  { name: "王先生", role: "主要收入者", age: 38, retirementAge: 60 },
  { name: "王太太", role: "次要收入者", age: 36, retirementAge: 55 },
  { name: "王小朵", role: "受抚养人", age: 6, retirementAge: 60 },
];

export const majorEvents = [
  { year: 2029, title: "改善型购房", amount: "300 万" },
  { year: 2032, title: "国际高中", amount: "80 万" },
  { year: 2035, title: "本科留学", amount: "200 万" },
  { year: 2048, title: "退休转换", amount: "年末切换" },
];

export const summaryBullets = [
  "现有金融资产与未来净现金流叠加后，可覆盖已录入的核心重大节点，但购房前 3 年应保持更高流动性。",
  "富余资金账户适合承担长期增值任务；演示页用“常见结果区间”表达长期波动，不直接承诺收益。",
  "保险部分只做结构缺失提醒，不做产品推荐或保额测算，避免与当前方法论边界冲突。",
];

export const bucketRows = [
  { name: "应急准备金", amount: "18 万", color: "var(--mint)" },
  { name: "购房账户", amount: "126 万", color: "var(--amber)" },
  { name: "教育账户", amount: "54 万", color: "var(--coral)" },
  { name: "富余资金", amount: "72 万", color: "var(--ink)" },
];

export const chartYears = ["2026", "2029", "2032", "2035", "2040", "2048"];

export const chartBands = [
  { label: "偏保守结果", values: [148, 152, 176, 201, 248, 315] },
  { label: "常见结果", values: [150, 168, 210, 265, 362, 486] },
  { label: "偏乐观结果", values: [152, 182, 236, 326, 468, 635] },
];
