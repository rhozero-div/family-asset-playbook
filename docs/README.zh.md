# 文档索引

`handbook/` 保存产品与方法论合同。  
`docs/` 只保留运行、验证和解释性文档。

English version: [README.md](README.md)

当前建议阅读顺序：

1. [local-validation-walkthrough.zh.md](local-validation-walkthrough.zh.md)
   - 当前仓库真实可运行的本地走查流程
   - 最适合验证“从问卷到剧本”是否还正常

2. [summary-logic-guide.zh.md](summary-logic-guide.zh.md)
   - 解释“综合建议摘要”是怎么生成的

3. [chart-and-qmc-logic-guide.zh.md](chart-and-qmc-logic-guide.zh.md)
   - 解释图表、收益区间与 QMC 推演的客户可读口径

4. [insurance-planner-parameter-guide.zh.md](insurance-planner-parameter-guide.zh.md)
   - 解释问卷里“保险建议默认参数”各字段的含义，以及它们如何同时影响最终剧本里的保险建议部分和方案 A / 方案 B 后续打开的保险回填页

5. [planner-architecture-roadmap.zh.md](planner-architecture-roadmap.zh.md)
   - 说明当前架构边界：主链路是“问卷 -> 最终剧本”，剧本生成后还可以按需进入顾问侧保险回填重算链路

如果存在冲突，以当前代码行为、测试，以及 `handbook/` 里的现行合同为准。
