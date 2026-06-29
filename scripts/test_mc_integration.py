"""
MC 工具集成试运行 —— 模拟一个简单组合的月粒度推演。

模拟参数:
  - 初始资产: 500 万
  - 月收入: 5 万, 月支出: 3 万
  - 年化收益: 6%, 年化波动: 10%
  - 时间跨度: 30 年 (360 个月)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from qmc import generate_sobol_paths, percentiles_from_paths

# ── 参数 ──
INITIAL_BALANCE = 5_000_000
MONTHLY_INCOME = 50_000
MONTHLY_EXPENSE = 30_000
MONTHLY_NET = MONTHLY_INCOME - MONTHLY_EXPENSE
ANNUAL_RETURN = 0.06
ANNUAL_VOL = 0.10
N_YEARS = 30
N_MONTHS = N_YEARS * 12
N_SOBOL = 5000
SEED = 42

# ── 生成 Sobol 创新 ──
print(f"生成 {N_SOBOL * 2} 路径 × {N_MONTHS} 个月...")
mc = generate_sobol_paths(
    n_steps=N_MONTHS,
    n_sobol_points=N_SOBOL,
    seed=SEED,
    use_brownian_bridge=True,
    use_antithetic=True,
)
print(f"  创新矩阵 shape: {mc.z.shape}")
print(f"  均值: {mc.z.mean():.4f}, 方差: {mc.z.var():.4f}")

# ── 逐月推演 ──
monthly_return = ANNUAL_RETURN / 12
monthly_vol = ANNUAL_VOL / np.sqrt(12)

# 向量化: 所有路径同步推演
balances = np.full(mc.n_paths, INITIAL_BALANCE, dtype=np.float64)
# 每年末存快照
year_end_balances = np.zeros((mc.n_paths, N_YEARS), dtype=np.float64)

for yr in range(N_YEARS):
    for m in range(12):
        idx = yr * 12 + m
        z = mc.z[:, idx]
        r = monthly_return + monthly_vol * z
        balances = balances * (1.0 + r) + MONTHLY_NET
    year_end_balances[:, yr] = balances

# ── 百分位 ──
pcts = percentiles_from_paths(year_end_balances)
percentile_keys = [10, 25, 50, 75, 90]

print(f"\n{'年':>4} | {'p10':>12} | {'p25':>12} | {'p50':>12} | {'p75':>12} | {'p90':>12} | {'均值':>12}")
print("-" * 85)
for yr in [0, 5, 10, 15, 20, 25, 29]:
    row = [f"{yr:>4}"]
    for p in percentile_keys:
        row.append(f"{pcts[p][yr]:>12,.0f}")
    row.append(f"{year_end_balances[:, yr].mean():>12,.0f}")
    print(" | ".join(row))
