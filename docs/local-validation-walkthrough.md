# 端到端走查:从顾问问卷到客户剧本

本文档描述**当前仓库真实可运行**的本地验证流程。所有数据均为虚构。

---

## 1. 当前推荐流程

当前推荐验证链路是:

1. 打开 Web 问卷
2. 录入顾问采集到的家庭信息
3. 由前端生成 YAML
4. 校验 YAML
5. 生成客户剧本

如果你需要验证“当前产品”,优先走这条链路。

---

## 2. 启动 Web 应用

在仓库根目录运行:

```bash
uvicorn web.app:app --reload
```

打开浏览器访问:

```text
http://127.0.0.1:8000/questionnaire
```

---

## 3. 运行前依赖

在当前仓库里,剧本生成不仅依赖本项目 `.venv`,还依赖外部 QMC 仓库:

- [`rhozero-div/Quasi-Monte-Carlo-Generator`](https://github.com/rhozero-div/Quasi-Monte-Carlo-Generator)

如果当前 Python 环境找不到 `qmc`,在生成剧本时会报:

```text
ModuleNotFoundError: No module named 'qmc'
```

推荐约定:

1. 使用本项目的 `.venv`
2. 将 `Quasi-Monte-Carlo-Generator` 安装到同一个环境,或在启动前将其 repo 根目录加入 `PYTHONPATH`

如果这一步没完成,后续问卷到剧本的 dry run 会被环境问题阻塞。

### 一套可直接执行的准备命令

```bash
cd /path/to/family-asset-playbook
source .venv/bin/activate
pip install -r web/requirements.txt
pip install -e /path/to/Quasi-Monte-Carlo-Generator
```

若暂时不安装外部仓库,可以先用:

```bash
export PYTHONPATH="/path/to/Quasi-Monte-Carlo-Generator:$PYTHONPATH"
```

再执行后续 dry run。

---

## 4. 填写顾问问卷

当前问卷围绕 7 个区域组织:

1. 家庭成员输入,以及人生节点相关信息
2. 收入情况
3. 常规支出情况
4. 重大支出规划
5. 现有资产
6. 现有保险
7. 风险偏好与推演假设

这份问卷是当前生产链的真实输入端。

---

## 5. 保存与生成

在问卷页你可以做两件事:

- `保存`:仅保存 YAML
- `生成剧本`:保存后直接生成客户剧本

生成时系统会:

1. 将表单序列化为 YAML
2. 调用 `tools/validate_collected_profile.py` 做基础校验
3. 调用引擎生成 Markdown
4. 渲染为 HTML 剧本页面

---

## 6. 使用示例档案快速验证

如果你只想快速走一遍:

1. 访问 `/questionnaire/sample-wang`
2. 系统会加载 `profiles/sample-wang.yaml`
3. 直接点击“生成剧本”

这样可以快速验证:

- YAML 加载
- 引擎解析
- 剧本渲染

---

## 7. CLI 验证

如果你已经有 YAML,也可以直接走 CLI:

```bash
./bin/fapm.py --profile samples/client-profile.example.yaml --current-year 2026 --out playbook.md
```

成功后会得到 `playbook.md`。

当前 CLI 的几个默认口径:

- `--handbook` 默认指向仓库内 `./handbook`
- 若未显式传 `--current-year`,默认使用系统年
- 终老推演默认从“最后一个未来事件年份”开始;若没有未来事件,则从 `current_year` 开始
- 若 YAML 中已有 `assumptions.projection.measurement_end_year`,主图表会统一展示到该年份
- 若未指定 `measurement_end_year`,当前默认取最后一个重大节点年份;若没有重大节点,回退到 `当前年份 + 30`

当前输出的核心章节应包含:

- `综合建议摘要`
- `A. 客户情况概览`
- `B. 资产推演`
- `C. 资产配置执行方案`
- `C3. 心理账户余额（居中情景）`
- `C4. 心理账户余额(按阶段着色)`
- `C5. 各层余额时序堆叠`
- `C6. 各层余额与资金来源`

---

## 8. YAML 校验

独立校验命令:

```bash
python3 tools/validate_collected_profile.py samples/client-profile.example.yaml
```

当前校验器主要负责:

- 顶层字段是否存在
- 事件字段是否合法
- 枚举值是否合法
- 基本类型是否正确

---

## 9. 常见问题

### Q:为什么文档和剧本结构有时对不上?

A: 因为项目经历过多轮迭代。当前验证时,请优先相信 Web 问卷和引擎实际输出。

### Q:当前问卷是否就是顾问正式使用的入口?

A: 是。当前产品链默认把 Web 问卷视为顾问入口,生成的剧本则面向客户阅读与讨论。

### Q:这是不是投资建议?

A: 不是。剧本用于家庭资产规划讨论,不等于具体产品推荐或收益承诺。

### Q:为什么 YAML 校验通过了,生成剧本却失败?

A: 最常见原因不是业务数据错误,而是运行环境没有接好外部 `qmc` 仓库。校验器只检查 YAML 结构,不执行 MC 推演;剧本生成则会真正加载 `qmc` 和相关科学计算依赖。
