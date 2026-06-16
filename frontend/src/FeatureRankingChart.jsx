export default function FeatureRankingChart({ rankings, metricLabel = "Relevance" }) {
  if (!rankings?.length) {
    return <p className="preview-empty">No feature rankings to display.</p>;
  }

  const maxScore = Math.max(...rankings.map((r) => r.abs_score ?? Math.abs(r.score)), 0.001);

  return (
    <div className="ranking-chart" role="img" aria-label="Feature relevance bar chart">
      {rankings.map((row) => {
        const width = ((row.abs_score ?? Math.abs(row.score)) / maxScore) * 100;
        const negative = row.score < 0;
        return (
          <div key={row.feature} className="ranking-row">
            <span className="ranking-label" title={row.feature}>
              {row.feature}
            </span>
            <div className="ranking-bar-track">
              <div
                className={`ranking-bar-fill ${negative ? "is-negative" : ""}`}
                style={{ width: `${width}%` }}
              />
            </div>
            <span className="ranking-value">
              {row.score > 0 ? "+" : ""}
              {row.score}
            </span>
          </div>
        );
      })}
      <p className="ranking-caption">{metricLabel}</p>
    </div>
  );
}
