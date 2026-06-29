# FAPM Frontend Demo

这个目录提供一套独立的前端演示壳,用于部署到 Cloudflare Pages。

## 目的

- 对外展示产品结构、问卷分区和剧本阅读方式
- 不直接改动当前 FastAPI Web 主链
- 与 Hugging Face Spaces 上的真实 Web 入口形成双站分工

## 本地启动

```bash
cd frontend
npm install
npm run dev
```

默认地址:

```text
http://127.0.0.1:3013
```

## Cloudflare Pages

推荐设置:

- Build command: `npm run build`
- Output directory: `out`

可选环境变量:

- `NEXT_PUBLIC_FAPM_HF_URL`
- `NEXT_PUBLIC_FAPM_CF_URL`
