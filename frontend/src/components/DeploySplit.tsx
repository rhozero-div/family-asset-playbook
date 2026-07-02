import { deployLinks } from "@/lib/demo-data";

export default function DeploySplit() {
  return (
    <section className="panel split-grid">
      <div className="split-card">
        <div className="badge">Cloudflare Pages</div>
        <h3>Static Demo Frontend</h3>
        <p>
          Built with Next.js static export into `out/`, this side is suited for a public-facing mock page that shows the questionnaire structure, playbook reading flow, and product tone.
        </p>
        <a href={deployLinks.cloudflare} className="inline-link">
          Current demo shell
        </a>
      </div>
      <div className="split-card">
        <div className="badge">Hugging Face Spaces</div>
        <h3>Real FastAPI Demo Entry</h3>
        <p>
          Reuses the current `web.app:app` and runs it through Docker on HF, preserving the real workflow for saving questionnaires, generating playbooks, and browsing the client list.
        </p>
        <a href={deployLinks.huggingFace} className="inline-link">
          Open live HF app
        </a>
      </div>
    </section>
  );
}
