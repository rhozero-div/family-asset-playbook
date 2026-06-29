import { familyMembers, majorEvents } from "@/lib/demo-data";

export default function QuestionnairePreview() {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <div className="section-tag">Simulated Questionnaire</div>
          <h2>问卷页保持顾问工作台视角</h2>
        </div>
        <div className="chipline">
          <span className="chip">8 个分区</span>
          <span className="chip">成员驱动</span>
          <span className="chip">年末口径</span>
        </div>
      </div>

      <div className="questionnaire-grid">
        <article className="paper-card">
          <h3>1. 家庭成员与人生节点</h3>
          <div className="mini-table">
            <div className="mini-row mini-head">
              <span>成员</span>
              <span>角色</span>
              <span>退休</span>
            </div>
            {familyMembers.map((member) => (
              <div className="mini-row" key={member.name}>
                <span>{member.name}</span>
                <span>{member.role}</span>
                <span>{member.retirementAge} 岁</span>
              </div>
            ))}
          </div>
        </article>

        <article className="paper-card">
          <h3>4. 重大支出规划</h3>
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
          <h3>5-7. 资产、保险与推演假设</h3>
          <div className="meter-stack">
            <div>
              <label>金融资产</label>
              <div className="meter">
                <span style={{ width: "68%" }} />
              </div>
            </div>
            <div>
              <label>流动性储备</label>
              <div className="meter">
                <span style={{ width: "42%" }} />
              </div>
            </div>
            <div>
              <label>风险偏好</label>
              <div className="risk-pill">平衡型 · balanced</div>
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
