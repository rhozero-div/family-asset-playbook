# Family Asset Playbook(家庭资产配置剧本方法论,FAPM)

> 为一个会变化的人生,生成一份可回顾、可重算、可讨论的家庭资产规划剧本。

## 这是什么

一套给顾问使用的家庭资产规划工作流。顾问通过结构化问卷采集家庭信息,系统生成一份可交付给客户阅读和讨论的剧本。

在线演示:

- [https://rhozero-div-family-asset-playbook.hf.space/](https://rhozero-div-family-asset-playbook.hf.space/)

它**不构成投资建议**,也**不是选品工具**。当前产品形态更接近:

- 顾问端:采集、校验、推演、生成剧本
- 客户端:阅读剧本、理解节点压力、讨论后续调整

## 当前产品链

当前仓库内的真实主链路是:

1. 顾问通过 Web 问卷录入客户信息
2. 前端序列化为 YAML
3. 引擎加载 YAML,完成节点推演与资金分层
4. 渲染为客户可读的 Markdown / HTML 剧本

## 对外演示结构

当前仓库包含一套双部署演示结构:

- `frontend/`
  - 独立 Next.js 演示前端
  - 使用静态导出(`output: "export"`)
  - 适合部署到 Cloudflare Pages
- `backend/`
  - Hugging Face Spaces Docker 入口
  - 复用当前 `web.app:app`
  - 适合把现有问卷/剧本 Web 流程直接跑起来

建议分工:

- Cloudflare Pages: 放公开可浏览的模拟网页
- Hugging Face Spaces: 放真正可填写、可生成剧本的 FastAPI Web 入口

如果文档与代码不一致,以**当前 Web 问卷实际产出的 YAML**和**当前引擎实际输出的剧本**为准。

当前计算口径补充说明:

- 现金流按年度汇总
- 重大事件按事件年份年末结算
- 所有图表默认展示到`测算截止年份`;若问卷已录入重大节点,其默认值取最后一个重大节点年份,否则回退为`当前年份 + 30`
- 储蓄险若配置 `linked_account`,会并入对应心理账户初始配置;未指定部分并入富余资金
- 图表总分位数按组合总路径直接计算,不是逐 bucket 分位数简单相加

当前 Web 问卷的主结构为:

1. 家庭成员输入,以及人生节点相关信息
2. 收入情况(逐成员,含未来起薪与退休后收入估计)
3. 常规支出情况(逐成员,含退休后支出系数与家庭级负债/额外支出)
4. 重大支出规划
5. 现有资产(房产、金融资产、流动性、储蓄险)
6. 现有保险
7. 风险偏好与推演假设

当前剧本的阅读顺序为:

1. 综合建议摘要
2. 客户情况概览
3. 资产推演
4. 资产配置执行方案

## 外部依赖

当前项目依赖一个独立维护的 QMC 仓库:

- [`rhozero-div/Quasi-Monte-Carlo-Generator`](https://github.com/rhozero-div/Quasi-Monte-Carlo-Generator)

引擎中的 Monte Carlo 推演通过 `from qmc import ...` 直接引用这个外部包。因此,仅克隆本仓库还不够;运行剧本生成前,还需要让当前 Python 环境能找到 `qmc`。

推荐做法:

1. 先启用本项目自己的虚拟环境 `.venv`
2. 再把 `Quasi-Monte-Carlo-Generator` 安装到同一个环境,或把该仓库根目录加入 `PYTHONPATH`

如果 `qmc` 未接入当前环境,生成剧本时会出现类似 `No module named 'qmc'` 的错误。

### 推荐本地安装步骤

```bash
# 进入项目
cd /path/to/family-asset-playbook

# 使用项目自己的虚拟环境
source .venv/bin/activate

# 安装 Web 与运行依赖
pip install -r web/requirements.txt

# 安装外部 QMC 仓库(示例路径按你的本地目录调整)
pip install -e /path/to/Quasi-Monte-Carlo-Generator
```

如果你不想做 editable install,也可以在启动前临时指定:

```bash
export PYTHONPATH="/path/to/Quasi-Monte-Carlo-Generator:$PYTHONPATH"
```

## 谁用

- **顾问**:完成访谈、录入信息、生成剧本、向客户解释
- **客户**:阅读剧本、理解阶段压力、参与调整

## 怎么开始

1. 阅读 [方法论总览](handbook/00-methodology-overview.md)
2. 阅读 [输入端 schema](handbook/01-input-schema.md),了解当前生产链真正使用的字段
3. 阅读 [输出结构](handbook/05-output-structure.md),了解当前剧本长什么样
4. 确认当前 `.venv` 已接入 `Quasi-Monte-Carlo-Generator`
5. 用 Web 问卷或示例 YAML 跑一遍生成流程

## 演示部署

### Cloudflare Pages

```bash
cd frontend
npm install
npm run build
```

推荐 Pages 设置:

- Build command: `npm run build`
- Output directory: `out`

### Hugging Face Spaces

当前可直接使用:

- [Dockerfile](Dockerfile)
- [backend/Dockerfile](backend/Dockerfile)
- [backend/requirements.txt](backend/requirements.txt)
- [.github/workflows/sync-to-huggingface.yml](.github/workflows/sync-to-huggingface.yml)

Docker 入口会启动:

```bash
uvicorn web.app:app --host 0.0.0.0 --port 7860
```

说明:

- 这条 HF 入口复用当前 FastAPI Web
- GitHub push 到 `main` 后,会通过 `HF_TOKEN` 自动同步到同名 Hugging Face Space
- 公开演示默认关闭服务器端持久化,匿名访客填写的信息不会保存到服务器,也不会展示其他人的已填资料
- 如需在你自己的本地或私有环境中保存客户资料,可在启动前设置 `FAPM_ENABLE_SERVER_STORAGE=1`; 启用后会把客户 YAML 与索引写入 `profiles/`
- 若未额外安装 `qmc`,剧本仍可生成,但会降级为不展示收益扇形图的版本

## 文档导航

- 方法论总览:[`handbook/00-methodology-overview.md`](handbook/00-methodology-overview.md)
- 输入 schema:[`handbook/01-input-schema.md`](handbook/01-input-schema.md)
- 家庭事件:[`handbook/02-life-events.md`](handbook/02-life-events.md)
- 资产假设:[`handbook/03-asset-assumptions.md`](handbook/03-asset-assumptions.md)
- Pareto 生成:[`handbook/04-pareto-generation.md`](handbook/04-pareto-generation.md)
- 输出结构:[`handbook/05-output-structure.md`](handbook/05-output-structure.md)
- 边界声明:[`handbook/06-boundaries.md`](handbook/06-boundaries.md)
- 版本管理:[`handbook/07-versioning.md`](handbook/07-versioning.md)
- 项目文档导航:[`docs/README.md`](docs/README.md)
- 本地走查:[`docs/local-validation-walkthrough.md`](docs/local-validation-walkthrough.md)
- 综合建议摘要逻辑:[`docs/summary-logic-guide.md`](docs/summary-logic-guide.md)
- 图表与 QMC 逻辑:[`docs/chart-and-qmc-logic-guide.md`](docs/chart-and-qmc-logic-guide.md)
- Cloudflare 演示前端:[`frontend/README.md`](frontend/README.md)

## 重要声明

本方法论不构成投资建议。所有数值均用于家庭资产规划讨论,实际配置与执行需结合客户情况与专业人士意见。详见 [边界声明](handbook/06-boundaries.md)。
