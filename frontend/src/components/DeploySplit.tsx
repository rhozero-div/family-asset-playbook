import { deployLinks } from "@/lib/demo-data";

export default function DeploySplit() {
  return (
    <section className="panel split-grid">
      <div className="split-card">
        <div className="badge">Cloudflare Pages</div>
        <h3>静态演示前端</h3>
        <p>
          使用 Next.js 静态导出生成 `out/`，适合放一个公开可浏览的模拟网页，
          用来展示问卷结构、剧本阅读路径和产品调性。
        </p>
        <a href={deployLinks.cloudflare} className="inline-link">
          Pages 演示地址
        </a>
      </div>
      <div className="split-card">
        <div className="badge">Hugging Face Spaces</div>
        <h3>FastAPI 真正演示入口</h3>
        <p>
          复用现有 `web.app:app`，通过 Docker 在 HF 上跑起来，保留问卷保存、
          生成剧本和客户列表的真实流程。
        </p>
        <a href={deployLinks.huggingFace} className="inline-link">
          Spaces 演示地址
        </a>
      </div>
    </section>
  );
}
