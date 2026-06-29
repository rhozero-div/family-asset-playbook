# Web 应用部署指南

本文档说明如何在本地启动当前 `family-asset-playbook` Web 应用。

## 当前用途

当前 Web 主要用于:

- 顾问填写/加载问卷
- 保存 YAML 档案
- 直接生成客户剧本

它不是公网产品部署说明,而是**本地运行说明**。

## 前置条件

- Python 3.11+
- 已克隆 `family-asset-playbook` 仓库
- 已准备本项目运行环境
- 若要生成含收益推演的剧本,还需要让当前环境可导入外部 `qmc`

## 安装依赖

```bash
cd family-asset-playbook
pip install -r web/requirements.txt
```

依赖:
- fastapi
- uvicorn[standard]
- jinja2
- python-multipart
- markdown

如需完整生成剧本,另需保证当前 Python 环境可以导入:

- [`rhozero-div/Quasi-Monte-Carlo-Generator`](https://github.com/rhozero-div/Quasi-Monte-Carlo-Generator)

## 启动服务器

```bash
uvicorn web.app:app --reload --port 8000
```

输出:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345]
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## 访问

打开浏览器:`http://localhost:8000`

页面:
- `/` 首页
- `/questionnaire` 问卷/输入页
- `/questionnaire/sample-wang` 加载王先生示例问卷
- `/playbook/{code}` 查看已保存档案对应的剧本

## 使用流程

1. 打开 `/questionnaire`
2. 填写顾问问卷,或访问 `/questionnaire/sample-wang` 载入示例
3. 根据需要调整当前年份与测算截止年份
4. 点击 `保存` 或 `生成剧本`
5. 浏览器渲染剧本页面

## 安全提示

⚠️ **v0.1 无认证机制**,仅适合:
- 本地开发
- 内网 / VPN 环境

**不要**部署到公网,任何人都能上传任意 YAML。

生产部署需要:
- 反向代理(Nginx) + HTTPS
- 用户认证(留待 v0.2)
- 速率限制

## 调试

- 服务器日志在终端输出
- 浏览器开发者工具查看网络请求
- 上传 YAML 失败时,查看错误 banner 中的具体提示

## 停止服务器

`Ctrl+C`

## 已知限制

- 以服务端渲染为主,但问卷页仍包含前端脚本用于动态表单与序列化
- 无数据库,档案存文件系统 `profiles/`
- 无多用户隔离
- 不适合直接暴露到公网
