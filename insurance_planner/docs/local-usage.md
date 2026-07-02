# 本地使用说明

## 1. 本地启动

在项目根目录运行：

```bash
FAPM_ENABLE_SERVER_STORAGE=1 .venv/bin/python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

当前主产品链路不要求单独打开保险页。  
如果只是验证最终交付，优先走主问卷并直接生成剧本。

当前更贴近真实顾问链路的保险使用方式是：

1. 先从 `/questionnaire` 生成剧本
2. 在剧本里的 `方案 A` 或 `方案 B` 下点击保险回填入口
3. 在回填页填写新增保额、手动补年保费
4. 用增量保险配置重新生成剧本

只有在你明确想单独调试这个子模块时，再打开：

- `http://127.0.0.1:8000/insurance-planner`

如果只想看示例：

- `http://127.0.0.1:8000/insurance-planner/sample-wang`

## 2. 独立入口现在是做什么的

独立入口 `/insurance-planner` 仍然保留，但现在更适合理解为：

- 独立调试保险建议逻辑
- 单独检查保险页模板
- 验证示例档案和测试数据

它不再是主产品的默认用户路径。

## 3. 本地保存行为

当启用 `FAPM_ENABLE_SERVER_STORAGE=1` 时：

- 本地可读取已保存客户列表
- 可通过 `/insurance-planner/load/{code}` 重新载入客户 YAML

这个行为主要服务于顾问本地使用，不适合公开匿名部署。

## 4. 公开演示模式

如果不启用 `FAPM_ENABLE_SERVER_STORAGE=1`：

- 页面仍可打开
- 示例仍可使用
- 但不会开放本地已保存客户入口

## 5. 回归测试

当前这部分最直接的测试是：

```bash
.venv/bin/pytest insurance_planner/tests/test_logic.py insurance_planner/tests/test_routes.py
```

这组测试当前覆盖：

- 示例档案是否能生成两套方案
- 方案 A 是否比方案 B 更优先补最前面的缺口
- 手动保费上限是否覆盖自动预算
- 页面是否能正常渲染
- 示例页是否能正常载入
- 报告页与保险回填页是否能正常渲染
- 从回填页回写后是否还能正常重新生成剧本

## 6. 当前更适合怎么理解

当前更适合把这个子模块理解为：

- 保险建议算法、模板与回填重算链路的调试入口
- 不是主产品默认起点
- 不是投保执行器
