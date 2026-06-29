# 输入端 Schema(Input Schema)

**版本:** 0.1.0
**状态:** draft

---

## 1. 本章的用途

本章描述**当前生产链实际使用的输入 schema**。

这里的“当前生产链”特指:

- Web 问卷
- 前端序列化得到的 YAML
- `engine.profile_loader` 实际消费的字段

若历史文档、旧问卷模板或旧示例与本章冲突,以本章和当前代码行为为准。

---

## 2. 当前主链路

当前主链路是:

1. 顾问在 Web 问卷录入信息
2. 前端将表单序列化为 YAML
3. `tools/validate_collected_profile.py` 做基础校验
4. `engine.profile_loader` 解析为 `ClientProfile`

因此,本章优先说明**当前 Web 问卷稳定产出的字段**。某些历史字段仍被兼容解析,但不再是当前问卷的主口径。

### 当前 Web 问卷版面顺序

1. 家庭成员输入,以及人生节点相关信息
2. 收入情况
3. 常规支出情况
4. 重大支出规划
5. 现有资产
6. 现有保险
7. 风险偏好与推演假设

---

## 3. 顶层结构

当前主口径下,最常见的顶层结构如下:

```yaml
profile_version: "0.1"
schema_version: "handbook-v0.1"
family: { ... }
income: { ... }
events: [ ... ]
assets: { ... }
advisor_assessment: { ... }   # 可选
assumptions: { ... }          # 可选
```

### 最小可解析顶层字段

当前 `engine.profile_loader` 的**最小硬性要求**只有:

- `profile_version`
- `schema_version`
- `family`
- `events`

也就是说,`income`、`assets`、`advisor_assessment`、`assumptions` 在技术上都可以缺省;只是当前 Web 问卷主链通常会一并输出这些字段。

### 兼容字段

以下字段在校验器或历史资料中仍可能出现:

- `support`
- `objectives`
- `assets.overseas*`
- `assets.financial.fixed_income / equity / alternatives / insurance`

这些字段并非全部由当前 Web 问卷直接产出,但引擎对其中一部分保留了兼容解析。

---

## 4. family:家庭成员与逐人参数

### 核心结构

```yaml
family:
  members:
    - name: "王先生"
      age: 38
      role: "primary_breadwinner"
      annual_income: 800000
      monthly_expense: 15000
      retirement_age: 60
      retirement_pension: 5000
      retirement_annuity: 2000
      retirement_expense_coeff: 0.7
      medical_covered: true
      term_life_coverage: 1000000
      critical_illness_coverage: 500000
      hci_coverage: 0
      reimbursement_rate: 0.8
      healthcare_starting_annual: 20000
      healthcare_growth_rate: 0.05
      healthcare_annual_cap: 80000
```

### 关键说明

- `family.members` 是当前生产链最核心的输入区。
- 当前引擎优先使用**逐人收支与逐人退休参数**,而不是仅使用家庭汇总口径。
- `family.residence`、`family.cost_of_living_level` 等字段在历史文档中存在,但当前 Web 问卷主流程并不强依赖它们。

### 角色枚举

| 取值 | 含义 |
|---|---|
| `primary_breadwinner` | 主要收入者 |
| `secondary_breadwinner` | 次要收入者 |
| `dependent` | 受抚养人 |
| `dependent_elder` | 受赡养老人 |
| `other` | 其他 |

---

## 5. income:家庭汇总收支

虽然当前问卷主要从 `family.members` 派生家庭收支,但 YAML 中仍会写入一层家庭汇总值:

```yaml
income:
  total_annual_income: 1200000
  monthly_living_expense: 25000
  retirement:
    monthly_pension: 5000
    monthly_annuity: 3000
```

### 当前行为

- 引擎优先使用 `family.members[].annual_income` 和 `family.members[].monthly_expense`。
- 当逐人字段缺失时,才会回退使用 `income.total_annual_income` 与 `income.monthly_living_expense`。
- 当前问卷的 `收入情况` 同时支持未成年人/待就业成员录入:
  - `income_start_age`
  - `income_start_annual`
- 当前问卷的 `常规支出情况` 主要写入成员级 `monthly_expense` 与 `retirement_expense_coeff`。
- `income.sources` 与 `income.expectations` 属于历史/兼容口径,不是当前 Web 问卷的主输出。

---

## 6. events:规划节点

当前主链路中的事件结构如下:

```yaml
events:
  - id: "housing_001"
    type: "housing"
    description: "改善型购房"
    timing_year: 2029
    estimated_amount: 3000000
    certainty: "high"
    owner: "王先生"
    expected_replacement_ratio: 0.6   # 仅退休事件常用
```

### 必填字段

| 字段 | 说明 |
|---|---|
| `id` | 档案内唯一 |
| `type` | `housing/education/retirement/health/legacy/other` |
| `description` | 人类可读事件名 |
| `timing_year` | 4 位年份 |
| `certainty` | 当前问卷可缺省; 若缺失,校验器与 loader 默认回退为 `medium` |
### 常用选填字段

- `estimated_amount`
- `owner`
- `expected_replacement_ratio`

### 当前用途

- 事件驱动阶段划分
- 资金在事件年份年末提取,并作为 bucket 目标年份
- 风险提示与重规划触发点

---

## 7. assets:现有资产、负债与储蓄险

### 当前 Web 问卷主口径

```yaml
assets:
  real_estate:
    primary_residence:
      estimated_value: 8000000
  financial:
    total_value: 1500000
    savings:
      - amount: 200000
        premium: 10000
        pay_years: 5
        linked_account: "富余资金"
  liquidity_reserve_months: 6
  liabilities:
    - outstanding: 1500000
      monthly_payment: 18000
      remaining_years: 12
```

### 当前行为

- 当前 Web 问卷使用的是 `assets.financial.total_value` 聚合口径。
- `assets.financial.savings` 用于储蓄险记录,不计入可投资金融资产。
- `linked_account` 若匹配某个心理账户 / 事件 ID,对应储蓄险会直接并入该账户初始配置; 未指定或未匹配部分并入富余资金。
- 负债通过 `monthly_payment` 和 `remaining_years` 进入现金流推演,但引擎内部统一折算为年度现金流并按年末结算。
- `liquidity_reserve_months` 用作应急储备目标月数;若未录入,当前引擎默认按 `6` 个月处理。

### 兼容口径

历史档案或示例中仍可能出现:

```yaml
assets:
  financial:
    fixed_income: { total_value: 800000 }
    equity: { total_value: 600000 }
    insurance: { ... }
    alternatives: { total_value: 100000 }
```

引擎仍可解析该口径,但这不是当前 Web 问卷默认产出格式。

---

## 8. advisor_assessment:顾问评估

当前问卷主流程中最稳定使用的是风险偏好:

```yaml
advisor_assessment:
  risk_tolerance: "balanced"
```

### 当前用途

- 决定默认风险偏好口径
- 进入剧本元数据

`knowledge_level`、`notes` 等字段仍可保留,但不是当前 Web 问卷的核心输出。

---

## 9. assumptions:推演假设覆盖

当前 Web 问卷允许顾问覆盖部分默认假设:

```yaml
assumptions:
  asset_classes:
    fixed_income:
      return_pct: 0.02
      volatility_pct: 0.02
    equity:
      return_pct: 0.07
      volatility_pct: 0.30
  correlations:
    fi_eq: 0.3
  phases:
    - max_years: 3
      weights:
        fixed_income: 0.875
        equity: 0.05
        insurance: 0.025
        alternatives: 0.05
  projection:
    post_retirement_horizon_years: 2
    measurement_end_year: 2048
```

### 当前用途

- 覆盖 handbook 默认假设
- 调整 bucket 推演与收益假设
- `assumptions.phases[].weights` 当前主口径使用对象结构,字段顺序为 `fixed_income / equity / insurance / alternatives`
- `assumptions.phases[].weights` 示例默认使用 `0-1` 小数口径; 当前引擎同时兼容 `0-100` 百分数口径，并会统一转换为百分数参与计算
- `assumptions.projection.post_retirement_horizon_years` 用于退休后阶段的策略切换视野
- `assumptions.projection.measurement_end_year` 是当前图表统一的测算截止年份
- 当前问卷中:
  - 若已录入重大节点,`measurement_end_year` 默认取最后一个重大节点年份
  - 若尚未录入重大节点,默认回退为 `当前年份 + 30`
  - 前后端都约束其**不能早于最后一个重大节点年份**

### 当前默认值与回退口径

- 若未识别到 `primary_breadwinner`,当前 loader 会回退:
  - `family_name = "unknown"`
  - 主要收入者年龄默认按 `35` 岁推导
- 若 `advisor_assessment.risk_tolerance` 缺失,当前引擎默认取 `balanced`
- 若 `family.members[].retirement_age` 缺失,当前引擎默认取 `60`
- 若 `family.members[].retirement_expense_coeff` 缺失,当前引擎默认取 `0.7`
- 若有医疗保障但未录入赔付率,当前引擎默认取 `0.80`
- 若 `income.retirement.healthcare` 未录入,当前旧聚合口径默认:
  - `starting_annual = 20000`
  - `growth_rate = 0.05`
  - `annual_cap = 80000`
- 对保险缴费期(`term_life_pay_years / ci_pay_years / medical_pay_years`),当前家庭级聚合口径取**所有成员中的最大值**,而不是逐保单分别建模

这部分属于顾问高级设置,不是客户自助字段。

---

## 10. 历史字段与现状说明

以下内容在旧版文档中被强调,但在当前主链路里并非核心:

- `support`
- `objectives`
- `income.sources`
- `income.expectations`
- 海外模块表单化采集

这些字段不是“错误字段”,而是**历史口径或兼容口径**。如果后续继续强化它们,应以代码实现和现行问卷同步更新本章。

---

## 11. 关联

- 当前剧本结构见 [`05-output-structure.md`](05-output-structure.md)
- 事件划分规则见 [`02-life-events.md`](02-life-events.md)
- 默认资产假设见 [`03-asset-assumptions.md`](03-asset-assumptions.md)
