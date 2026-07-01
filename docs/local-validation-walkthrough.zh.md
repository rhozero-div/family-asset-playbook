# 端到端本地走查

本文档描述当前仓库**真实可运行**的本地验证流程。  
文中提到的样例数据均为虚构。

English version: [local-validation-walkthrough.md](local-validation-walkthrough.md)

## 1. 推荐验证路径

当前推荐链路是：

1. 打开 Web 问卷
2. 录入顾问采集到的家庭信息
3. 由前端生成 YAML
4. 校验 YAML
5. 生成客户剧本

如果你要验证“当前产品是否正常”，优先走这条路径。

## 2. 启动 Web 应用

在仓库根目录运行：

```bash
source .venv/bin/activate
pip install -r web/requirements.txt
FAPM_ENABLE_SERVER_STORAGE=1 .venv/bin/python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

说明：

- `FAPM_ENABLE_SERVER_STORAGE=1` 会启用更接近顾问工作流的本地持久化
- 已保存 YAML 与索引会写入 `profiles/`
- 如果你希望这些保存文件落在仓库外，可再设置 `FAPM_STORAGE_DIR=/absolute/path/to/local-data`
- 如果你想模拟公开演示模式，可以去掉这个环境变量

## 3. 使用问卷

推荐路径：

1. 打开 `/questionnaire`
2. 先填写家庭成员与人生节点背景
3. 继续填写收入、支出、重大事件、资产、保险与假设
4. 点击 `Generate Playbook`

也可以直接打开内置样例：

```text
http://127.0.0.1:8000/questionnaire/sample-wang
```

## 4. 问卷层面要检查什么

生成剧本前，重点检查：

- 家庭成员是否先录入，并被后续分区正确复用
- 退休年龄等关键字段是否填全
- 重大支出事件是否有年份和金额
- `measurement_end_year` 是否不早于最后一个重大节点年份
- 金融资产、负债、流动性目标是否一致
- 风险偏好和阶段权重是否符合你要测试的情景

## 5. 剧本层面要检查什么

生成之后，建议按顺序看：

1. **综合建议摘要**
   - 高层结论是否可读
   - 重大节点覆盖结论和富余资金长期收益结论是否清楚

2. **客户情况概览**
   - 初始资产、现金流、退休参数、事件表是否与问卷一致

3. **资产推演**
   - 各节点年份的余额和结果是否合理
   - 图表是否按 `measurement_end_year` 截止

4. **资产配置执行方案**
   - bucket 结构是否与事件顺序一致
   - 初始划拨、年度净结余分配和 bucket 图表是否内部一致

## 6. QMC 依赖检查

如果运行环境找不到 `qmc`，收益推演路径可能失败或降级。

推荐安装方式：

```bash
pip install -e /path/to/Quasi-Monte-Carlo-Generator
```

如有需要，可以确认 Python 能否导入：

```bash
.venv/bin/python -c "import qmc; print(qmc.__file__)"
```

## 7. 建议回归检查

当你改动问卷逻辑、推演逻辑或渲染逻辑后，建议重新检查：

- 问卷中文页和英文页都能正常打开
- 本地持久化启用时，保存 / 加载仍正常
- 样例档案还能成功生成剧本
- 英文首页和英文剧本不再出现系统中文
- 重大节点顺序、bucket 命名和图表截止年份仍与问卷一致

## 8. 如果结果看起来不对

建议按这个顺序排查：

1. 看问卷输出
2. 看生成的 YAML
3. 看推演假设
4. 看渲染出来的剧本
5. 看相关测试

如果文档与行为不同，以实际代码行为为准，再回头更新文档。
