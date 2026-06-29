import AppShell from "@/components/AppShell";
import DeploySplit from "@/components/DeploySplit";
import PlaybookPreview from "@/components/PlaybookPreview";
import QuestionnairePreview from "@/components/QuestionnairePreview";
import { deployLinks } from "@/lib/demo-data";

export default function HomePage() {
  return (
    <AppShell eyebrow="Cloudflare + Hugging Face Split" title="把家庭资产剧本做成一套可公开演示的双入口">
      <section className="masthead panel">
        <div className="masthead-copy">
          <p>
            这一版不是把现有站点硬塞进单个平台，而是沿用
            `asset-correlation-monitor` 的拆分方式：Cloudflare Pages
            负责公开演示壳，Hugging Face Spaces Docker 负责真正的 FastAPI Web 入口。
          </p>
          <div className="cta-row">
            <a href={deployLinks.cloudflare} className="cta-primary">
              打开 Cloudflare 演示
            </a>
            <a href={deployLinks.huggingFace} className="cta-secondary">
              打开 Hugging Face 应用
            </a>
          </div>
        </div>
        <div className="route-board">
          <div className="route-card">
            <span>Pages</span>
            <strong>/</strong>
            <em>对外展示产品结构、问卷逻辑与剧本阅读体验</em>
          </div>
          <div className="route-card">
            <span>Spaces</span>
            <strong>/questionnaire</strong>
            <em>真正可填写、可保存、可生成剧本的 Web 入口</em>
          </div>
        </div>
      </section>

      <DeploySplit />
      <QuestionnairePreview />
      <PlaybookPreview />
    </AppShell>
  );
}
