import AppShell from "@/components/AppShell";
import DeploySplit from "@/components/DeploySplit";
import PlaybookPreview from "@/components/PlaybookPreview";
import QuestionnairePreview from "@/components/QuestionnairePreview";
import { deployLinks } from "@/lib/demo-data";

export default function HomePage() {
  return (
    <AppShell eyebrow="Cloudflare + Hugging Face Split" title="A public two-entry demo for the Family Asset Playbook">
      <section className="masthead panel">
        <div className="masthead-copy">
          <p>
            This version does not force the whole product into a single platform.
            It follows the same split-deployment idea used in
            `asset-correlation-monitor`: Cloudflare Pages handles the public-facing
            demo shell, while Hugging Face Spaces runs the real FastAPI web entry.
          </p>
          <div className="cta-row">
            <a href={deployLinks.cloudflare} className="cta-primary">
              Open Cloudflare Demo
            </a>
            <a href={deployLinks.huggingFace} className="cta-secondary">
              Open Hugging Face App
            </a>
          </div>
        </div>
        <div className="route-board">
          <div className="route-card">
            <span>Pages</span>
            <strong>/</strong>
            <em>Public demo of product structure, questionnaire logic, and playbook reading flow</em>
          </div>
          <div className="route-card">
            <span>Spaces</span>
            <strong>/questionnaire</strong>
            <em>The real web entry for filling, saving, and generating playbooks</em>
          </div>
        </div>
      </section>

      <DeploySplit />
      <QuestionnairePreview />
      <PlaybookPreview />
    </AppShell>
  );
}
