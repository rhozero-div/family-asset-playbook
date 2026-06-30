import { familyMembers, majorEvents } from "@/lib/demo-data";

export default function QuestionnairePreview() {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <div className="section-tag">Simulated Questionnaire</div>
          <h2>The questionnaire keeps the advisor-workbench perspective</h2>
        </div>
        <div className="chipline">
          <span className="chip">8 sections</span>
          <span className="chip">member-driven</span>
          <span className="chip">year-end convention</span>
        </div>
      </div>

      <div className="questionnaire-grid">
        <article className="paper-card">
          <h3>1. Family Members and Life Milestones</h3>
          <div className="mini-table">
            <div className="mini-row mini-head">
              <span>Member</span>
              <span>Role</span>
              <span>Retire</span>
            </div>
            {familyMembers.map((member) => (
              <div className="mini-row" key={member.name}>
                <span>{member.name}</span>
                <span>{member.role}</span>
                <span>{member.retirementAge}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="paper-card">
          <h3>4. Major Spending Plan</h3>
          <ul className="timeline-list">
            {majorEvents.map((event) => (
              <li key={event.title}>
                <strong>{event.year}</strong>
                <span>{event.title}</span>
                <em>{event.amount}</em>
              </li>
            ))}
          </ul>
        </article>

        <article className="paper-card">
          <h3>5-7. Assets, Insurance, and Projection Assumptions</h3>
          <div className="meter-stack">
            <div>
              <label>Financial Assets</label>
              <div className="meter">
                <span style={{ width: "68%" }} />
              </div>
            </div>
            <div>
              <label>Liquidity Reserve</label>
              <div className="meter">
                <span style={{ width: "42%" }} />
              </div>
            </div>
            <div>
              <label>Risk Preference</label>
              <div className="risk-pill">Balanced</div>
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
