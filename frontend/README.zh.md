# FAPM 前端演示壳

这个目录提供一套独立前端演示壳，适合部署到 Cloudflare Pages。

English version: [README.md](README.md)

## 目的

- 对外展示产品结构、问卷分区和剧本阅读方式
- 不直接改动当前 FastAPI 问卷 / 剧本主链
- 与 Hugging Face Spaces 上的真实应用形成双入口分工

## 本地启动

```bash
cd frontend
npm install
npm run dev
```

默认本地地址：

```text
http://127.0.0.1:3013
```

## 推荐部署用途

- 如果你想放一个轻量的公开演示页，用这个前端壳
- 如果你想保留真实问卷和剧本生成流程，用 FastAPI 那一侧

## 推荐 Cloudflare Pages 设置

- Build command：`npm run build`
- Output directory：`out`

## 可选环境变量

- `NEXT_PUBLIC_DEMO_URL`
  - 线上产品演示地址
- `NEXT_PUBLIC_PLAYBOOK_DEMO_URL`
  - 可选的剧本演示地址
- `NEXT_PUBLIC_FAPM_HF_URL`
  - 演示壳里显示的 Hugging Face 真实应用地址
- `NEXT_PUBLIC_FAPM_CF_URL`
  - 可选的 Cloudflare Pages 完整地址
  - 如果不填，演示壳默认把 Cloudflare 入口链接到当前站点自身 `/`
