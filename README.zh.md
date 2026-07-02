# 家庭资产配置剧本方法论（FAPM）

> 为一个会变化的人生，生成一份可回顾、可重算、可讨论的家庭资产规划剧本。

English version: [README.md](README.md)

## 这是什么

Family Asset Playbook 是一套面向顾问的家庭资产高层规划工作流。
顾问通过结构化问卷采集家庭信息，系统生成一份可交付给客户阅读、讨论、并在未来回看和重算的剧本。

在线演示：

- [https://rhozero-div-family-asset-playbook.hf.space/](https://rhozero-div-family-asset-playbook.hf.space/)

这个项目**不构成投资建议**，也**不是选品工具**。
它当前更接近：

- 顾问端：采集、校验、推演、生成剧本
- 客户端：阅读剧本、理解节点压力、讨论调整

## 当前产品链

当前仓库里的真实主链路是：

1. 顾问填写 Web 问卷
2. 前端把问卷序列化成 YAML
3. 引擎加载 YAML，完成未来现金流推演与资金分层
4. 系统渲染出客户可读的 Markdown / HTML 剧本，并在末尾附上保险配置建议
5. 如需细化保险方案，顾问可从剧本里的方案 A / 方案 B 打开“保险配置回填页”，把新增保额与手工补录保费叠加回原问卷，再重新生成剧本

如果文档与代码不一致，以**当前问卷实际产出的 YAML**和**当前引擎实际输出的剧本**为准。

## 对外演示结构

当前仓库包含一套双部署演示结构：

- `frontend/`
  - 独立的 Next.js 演示前端
  - 使用静态导出 `output: "export"`
  - 适合部署到 Cloudflare Pages
- `backend/`
  - Hugging Face Spaces 的 Docker 入口
  - 复用当前 `web.app:app`
  - 适合承载真实问卷 / 剧本流程

建议分工：

- Cloudflare Pages：放公开可浏览的模拟演示
- Hugging Face Spaces：放真正可填写、可生成剧本的 FastAPI Web 入口

## 当前计算口径

- 现金流按年度汇总
- 重大事件按**事件年份年末**结算
- 图表默认展示到 `measurement_end_year`
  - 若问卷已录入重大节点，默认取最后一个重大节点年份
  - 否则回退为 `current_year + 30`
- 储蓄险若配置 `linked_account`，会并入对应心理账户初始配置
- 未指定有效 `linked_account` 的储蓄险进入富余资金账户
- 组合总分位数按**完整组合路径**计算，不是把各 bucket 分位数简单相加

## 当前问卷结构

当前 Web 问卷结构为：

1. 家庭成员与人生节点背景
2. 收入
   - 按成员录入
   - 支持未成年 / 尚未工作成员的未来起薪年龄与未来收入估计
   - 支持退休后收入估计
3. 常规支出
   - 按成员录入
   - 支持退休后支出折算系数
   - 支持家庭级负债与额外支出
4. 重大支出规划
5. 现有资产
   - 房产
   - 金融资产
   - 流动性目标
   - 储蓄险
6. 现有保险
   - 按成员分区块
   - 每个险种一行
   - 单独录入现有保额、年保费、剩余缴费年数
   - 退休医疗参数仍按成员录入
7. 风险偏好与推演假设
8. 高级推演假设

## 当前剧本阅读顺序

生成剧本的阅读顺序为：

1. 综合建议摘要
2. 客户情况概览
3. 资产推演
4. 资产配置执行方案
5. 保险配置建议
   - 方案 A / 方案 B 可继续进入保险配置回填页
   - 回填页中的新增方案会以增量方式叠加回原问卷
   - 保费字段默认由顾问手工补录

## 外部依赖

当前项目依赖一个独立维护的 QMC 仓库：

- [`rhozero-div/Quasi-Monte-Carlo-Generator`](https://github.com/rhozero-div/Quasi-Monte-Carlo-Generator)

Monte Carlo 推演会直接通过 `from qmc import ...` 引用这个外部包。
如果你想跑完整的收益推演和图表逻辑，仅克隆本仓库还不够；当前 Python 环境还必须能找到 `qmc`。

推荐方式：

1. 先启用本项目自己的 `.venv`
2. 再把 `Quasi-Monte-Carlo-Generator` 装进同一个环境，或把该仓库根目录加入 `PYTHONPATH`

### 推荐本地安装步骤

```bash
cd /path/to/family-asset-playbook

source .venv/bin/activate

pip install -r web/requirements.txt

pip install -e /path/to/Quasi-Monte-Carlo-Generator
```

如果你不想做 editable install，也可以：

```bash
export PYTHONPATH="/path/to/Quasi-Monte-Carlo-Generator:$PYTHONPATH"
```

## 本地运行

本地使用时，默认建议启用服务器端持久化：

```bash
FAPM_ENABLE_SERVER_STORAGE=1 .venv/bin/python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

启用 `FAPM_ENABLE_SERVER_STORAGE=1` 后：

- 客户 YAML 与索引会写入 `profiles/`
- 已保存问卷可以在本地重新打开
- 本地测试会更接近真实顾问工作流

可选覆盖：

- 如果你希望客户 YAML 和 `clients.json` 保存在仓库外，可额外设置 `FAPM_STORAGE_DIR=/absolute/path/to/local-data`
- 如果不设置，本地持久化仍默认写入仓库内的 `profiles/`

不启用时：

- 应用会以公开演示模式运行
- 匿名填写信息不会保存到服务器
- 已保存客户浏览功能会关闭

因此，非持久化模式只建议用于公开演示、匿名试用或明确要求不落盘的场景。

## 谁用

- **顾问**：访谈、录入信息、生成剧本、向客户解释
- **客户**：阅读剧本、理解节点压力、讨论调整

## 怎么开始

1. 阅读 [方法论总览](handbook/00-methodology-overview.zh.md)
2. 阅读 [输入端 Schema](handbook/01-input-schema.zh.md)
3. 阅读 [输出结构](handbook/05-output-structure.zh.md)
4. 确认 `.venv` 已接入 `Quasi-Monte-Carlo-Generator`
5. 用 Web 问卷或示例 YAML 跑一遍生成流程

## 演示部署

### Cloudflare Pages

```bash
cd frontend
npm install
npm run build
```

推荐 Pages 设置：

- Build command：`npm run build`
- Output directory：`out`

### Hugging Face Spaces

当前部署可直接使用：

- [Dockerfile](Dockerfile)
- [backend/Dockerfile](backend/Dockerfile)
- [backend/requirements.txt](backend/requirements.txt)
- [.github/workflows/sync-to-huggingface.yml](.github/workflows/sync-to-huggingface.yml)

Docker 入口运行：

```bash
uvicorn web.app:app --host 0.0.0.0 --port 7860
```

说明：

- Hugging Face 部署复用当前 FastAPI Web
- push 到 `main` 后，会通过 `HF_TOKEN` 同步到同名 Hugging Face Space
- 公开演示默认关闭服务器端持久化
- 匿名用户不能把客户信息保存到服务器，也看不到其他人的已保存资料
- 你自己本地 `localhost` 预览时，通常应启用 `FAPM_ENABLE_SERVER_STORAGE=1`
- 若运行环境未安装 `qmc`，剧本可能降级，不展示收益扇形图

## 文档导航

- [README.md](README.md) - English version
- [方法论总览](handbook/00-methodology-overview.zh.md)
- [输入端 Schema](handbook/01-input-schema.zh.md)
- [家庭事件](handbook/02-life-events.zh.md)
- [资产假设](handbook/03-asset-assumptions.zh.md)
- [Pareto 生成规则](handbook/04-pareto-generation.zh.md)
- [输出结构](handbook/05-output-structure.zh.md)
- [边界声明](handbook/06-boundaries.zh.md)
- [版本管理](handbook/07-versioning.zh.md)
- [文档索引](docs/README.zh.md)
- [本地走查](docs/local-validation-walkthrough.zh.md)
- [综合建议摘要逻辑说明](docs/summary-logic-guide.zh.md)
- [图表、收益测算与 QMC 逻辑说明](docs/chart-and-qmc-logic-guide.zh.md)
- [Cloudflare 演示前端说明](frontend/README.zh.md)

## 重要声明

本方法论不构成投资建议。
所有数值仅用于家庭资产规划讨论。
实际配置与执行需结合客户真实情况与专业判断。
完整边界请见 [边界声明](handbook/06-boundaries.zh.md)。
