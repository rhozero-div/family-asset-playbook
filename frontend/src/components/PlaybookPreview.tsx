import { bucketRows, chartBands, chartYears, summaryBullets } from "@/lib/demo-data";

function areaPoints(values: number[]) {
  const width = 100;
  const height = 56;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const spread = Math.max(max - min, 1);
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / spread) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

export default function PlaybookPreview() {
  const lower = chartBands[0].values;
  const middle = chartBands[1].values;
  const upper = chartBands[2].values;

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <div className="section-tag">Simulated Playbook</div>
          <h2>The playbook leads with conclusions and execution actions</h2>
        </div>
      </div>

      <div className="playbook-preview">
        <article className="summary-card">
          <div className="summary-topline">Executive Summary</div>
          <h3>Major milestones remain coverable overall, and the key action is liquidity discipline in the three years before the housing event.</h3>
          <ul>
            {summaryBullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
        </article>

        <div className="preview-grid">
          <article className="paper-card">
            <h3>C1. Initial Capital Allocation</h3>
            <div className="bucket-list">
              {bucketRows.map((row) => (
                <div className="bucket-row" key={row.name}>
                  <div className="bucket-meta">
                    <span>{row.name}</span>
                    <strong>{row.amount}</strong>
                  </div>
                  <div className="bucket-bar">
                    <span style={{ width: row.name === "Housing Bucket" ? "72%" : row.name === "Surplus Account" ? "48%" : "36%", background: row.color }} />
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="paper-card">
            <h3>B. Cash Flow and Asset Balance Timeline</h3>
            <div className="chart-card">
              <svg viewBox="0 0 100 64" className="fan-chart" aria-hidden="true">
                <polygon
                  points={`${areaPoints(lower)} 100,64 0,64`}
                  className="fan fan-outer"
                />
                <polygon
                  points={`${areaPoints(middle)} 100,64 0,64`}
                  className="fan fan-inner"
                />
                <polyline points={areaPoints(upper)} className="fan-line fan-top" />
                <polyline points={areaPoints(middle)} className="fan-line fan-mid" />
              </svg>
              <div className="chart-years">
                {chartYears.map((year) => (
                  <span key={year}>{year}</span>
                ))}
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
