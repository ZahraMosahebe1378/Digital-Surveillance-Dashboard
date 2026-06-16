import { useState } from "react";
import FeatureRankingChart from "./FeatureRankingChart";

const MODEL_FAMILIES = [
  {
    id: "ai_based",
    label: "AI-based models",
    hint: "Decision Tree",
    icon: "🌳",
  },
  {
    id: "statistical",
    label: "Statistical models",
    hint: "Negative Binomial Regression",
    icon: "📈",
  },
  {
    id: "heuristic",
    label: "Heuristic models",
    hint: "Coming soon",
    icon: "🧭",
  },
];

const OUTCOME_LABELS = {
  covid_cases: "COVID-19 cases",
  influenza_cases: "Influenza cases",
  rsv_cases: "RSV cases",
};

function formatOutcome(key) {
  return OUTCOME_LABELS[key] ?? key.replace(/_/g, " ");
}

export default function FeatureSelectionPage() {
  const [modelFamily, setModelFamily] = useState("ai_based");
  const [file, setFile] = useState(null);
  const [outcomeFile, setOutcomeFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeOutcome, setActiveOutcome] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) {
      setError("Please upload your preprocessed wastewater CSV (weekly_mean_w_avg).");
      return;
    }
    if (!outcomeFile) {
      setError("Please upload your Cases outcome file (Cases.xlsx with Number of cases).");
      return;
    }

    if (modelFamily === "heuristic") {
      setError("Heuristic models are not available yet. Choose AI-based or Statistical.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("outcome_file", outcomeFile);
    formData.append("model_family", modelFamily);

    try {
      const response = await fetch("/api/feature-selection", {
        method: "POST",
        body: formData,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = body.detail;
        throw new Error(
          typeof detail === "string" ? detail : `Request failed: ${response.status}`
        );
      }
      setResult(body);
      const firstOutcome = body.outcomes?.[0] ?? null;
      setActiveOutcome(firstOutcome);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const activeResult =
    activeOutcome && result?.results_by_outcome
      ? result.results_by_outcome[activeOutcome]
      : null;

  const metricLabel =
    modelFamily === "statistical"
      ? "Coefficient (negative binomial)"
      : "Feature importance (decision tree)";

  return (
    <>
      <header className="hero">
        <div className="hero-badge">feature relevance step</div>
        <h1>Variable relevance analysis</h1>
        <p>
          Measure how weekly predictors relate to COVID-19, RSV, and Influenza case
          outcomes using your preprocessed dashboard data.
        </p>
      </header>

      <div className="model-family-nav">
        {MODEL_FAMILIES.map((family) => (
          <button
            key={family.id}
            type="button"
            className={`model-family-btn ${modelFamily === family.id ? "is-active" : ""}`}
            onClick={() => {
              setModelFamily(family.id);
              setResult(null);
              setError("");
            }}
          >
            <span className="model-family-icon" aria-hidden="true">
              {family.icon}
            </span>
            <span className="model-family-label">{family.label}</span>
            <span className="model-family-hint">{family.hint}</span>
          </button>
        ))}
      </div>

      <form className="card upload-card" onSubmit={handleSubmit}>
        <h2 className="card-title">Upload wastewater + Cases outcomes</h2>

        <label className="file-drop">
          <span className="file-drop-icon" aria-hidden="true">🧪</span>
          <span className="file-drop-text">
            {file ? file.name : "Wastewater predictors (weekly CSV)"}
          </span>
          <span className="file-drop-hint">
            Uses column <strong>weekly_mean_w_avg</strong> as the predictor
          </span>
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>

        <label className="file-drop">
          <span className="file-drop-icon" aria-hidden="true">🦠</span>
          <span className="file-drop-text">
            {outcomeFile ? outcomeFile.name : "Cases outcomes (Cases.xlsx)"}
          </span>
          <span className="file-drop-hint">
            Outcome column <strong>Number of cases</strong> · split by Disease (COVID / Influenza / RSV)
          </span>
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,text/csv"
            onChange={(e) => setOutcomeFile(e.target.files?.[0] || null)}
          />
        </label>

        <div className="actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Analyzing…" : "Run relevance analysis"}
          </button>
        </div>
        {error && <p className="alert alert-error">{error}</p>}
      </form>

      {result?.available && (
        <section className="results">
          <div className="card">
            <h2 className="card-title">Timeline check</h2>
            <div className="meta-chips">
              <span className="chip">
                <strong>Frequency</strong> {result.timeline_validation?.frequency}
              </span>
              <span className="chip">
                <strong>Weeks</strong> {result.timeline_validation?.week_count}
              </span>
              <span className="chip">
                <strong>Span</strong> {result.timeline_validation?.timeline_start} →{" "}
                {result.timeline_validation?.timeline_end}
              </span>
              <span className="chip">
                <strong>Outcome</strong> {result.outcome_column}
              </span>
              <span className="chip">
                <strong>Predictor</strong> {result.predictor_column}
              </span>
              <span className="chip">
                <strong>Model</strong> {result.model_name}
              </span>
            </div>
            <p className="rule-text">
              {result.features_analyzed?.length} predictors analyzed across{" "}
              {result.weekly_rows} weekly rows.
            </p>
          </div>

          <div className="card">
            <h2 className="card-title">Outcomes analyzed</h2>
            <div className="outcome-tabs">
              {result.outcomes?.map((outcome) => (
                <button
                  key={outcome}
                  type="button"
                  className={`outcome-tab ${activeOutcome === outcome ? "is-active" : ""}`}
                  onClick={() => setActiveOutcome(outcome)}
                >
                  {formatOutcome(outcome)}
                </button>
              ))}
            </div>

            {activeResult && (
              <>
                <div className="interpretation-card">
                  <h3 className="interpretation-title">Summary</h3>
                  <p className="interpretation-text">{activeResult.summary}</p>
                </div>

                <div className="stat-grid">
                  {Object.entries(activeResult.metrics || {}).map(([key, value]) => (
                    <div key={key} className="stat-card" style={{ "--accent": "#4477AA" }}>
                      <span className="stat-label">{key.replace(/_/g, " ")}</span>
                      <span className="stat-value">{value}</span>
                    </div>
                  ))}
                </div>

                <div className="ranking-layout">
                  <div className="ranking-panel">
                    <h3 className="ranking-title">Top predictors</h3>
                    <FeatureRankingChart
                      rankings={activeResult.feature_rankings}
                      metricLabel={metricLabel}
                    />
                  </div>

                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Feature</th>
                          <th>Score</th>
                          <th>Interpretation</th>
                          {modelFamily === "statistical" && (
                            <>
                              <th>p-value</th>
                              <th>Significant</th>
                            </>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {activeResult.feature_rankings?.map((row) => (
                          <tr key={row.feature}>
                            <td className="city-cell">{row.feature}</td>
                            <td className="num-cell">{row.score}</td>
                            <td className="interpretation-cell">{row.description}</td>
                            {modelFamily === "statistical" && (
                              <>
                                <td className="num-cell">{row.p_value}</td>
                                <td>{row.significant ? "Yes" : "No"}</td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      )}
    </>
  );
}
