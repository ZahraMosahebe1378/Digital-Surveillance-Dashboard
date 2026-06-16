import { useState } from "react";
import FeatureSelectionPage from "./FeatureSelectionPage";
import PreprocessingSteps from "./PreprocessingSteps";
import WeeklyPreview from "./WeeklyPreview";

const PIPELINE_STEPS = [
  { id: "preprocessing", label: "Data preprocessing" },
  { id: "feature_relevance", label: "Feature relevance" },
];

const DATA_TYPES = [
  { value: "wastewater", label: "Waste Water" },
  { value: "air_pollution", label: "Air Pollution" },
  { value: "mobility_data", label: "Mobility Data" },
  { value: "climate_data", label: "Climate Data" },
  { value: "digital_information", label: "Digital Information" },
  { value: "clinical_data", label: "Clinical Data" },
];

const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xlsm"];

function isAcceptedFile(file) {
  if (!file?.name) return false;
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function weeklyCsvFilename(originalName) {
  const base = (originalName || "upload").replace(/\.[^.]+$/, "");
  return `weekly_${base}.csv`;
}

const LOADING_LINES = [
  "Sprinting through messy Ontario rows…",
  "Chasing Peel Region down the 401…",
  "Teaching Toronto it is not Mississauga…",
  "Converting hourly chaos to weekly calm…",
  "Almost at the finish line…",
];

function formatType(value, labelFromApi) {
  if (labelFromApi) return labelFromApi;
  return DATA_TYPES.find((t) => t.value === value)?.label ?? value;
}

function StatCard({ label, value, accent }) {
  return (
    <div className="stat-card" style={{ "--accent": accent }}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value?.toLocaleString?.() ?? value}</span>
    </div>
  );
}

function PreprocessingPage() {
  const [file, setFile] = useState(null);
  const [dataType, setDataType] = useState("wastewater");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingLine, setLoadingLine] = useState(0);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) {
      setError("Please choose a CSV or Excel (.xlsx) file.");
      return;
    }
    if (!isAcceptedFile(file)) {
      setError("Unsupported file type. Please upload a .csv or .xlsx file.");
      return;
    }

    setLoading(true);
    setLoadingLine(0);
    setError("");
    setResult(null);
    const lineTimer = setInterval(() => {
      setLoadingLine((n) => (n + 1) % LOADING_LINES.length);
    }, 2200);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("data_type", dataType);
    formData.append("min_location_confidence", "0.55");
    formData.append("ontario_only", "true");
    formData.append("download", "false");

    try {
      const response = await fetch("/api/preprocess", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      const json = await response.json();
      setResult(json);
    } catch (err) {
      setError(err.message);
    } finally {
      clearInterval(lineTimer);
      setLoading(false);
    }
  }

  async function handleDownload() {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("data_type", dataType);
    formData.append("download", "true");

    try {
      const response = await fetch("/api/preprocess", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      const csvText = await response.text();
      const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = weeklyCsvFilename(file.name);
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  const maxRows = result?.location_summary?.length
    ? Math.max(...result.location_summary.map((r) => r.rows))
    : 1;

  return (
    <>
      <header className="hero">
        <div className="hero-badge">preprocessing step</div>
        <h1>Data Preprocessing Pipeline</h1>
        <p>Ontario filtering and weekly alignment for epidemiological modeling.</p>
      </header>

      <form className="card upload-card" onSubmit={handleSubmit}>
        <h2 className="card-title">Upload & configure</h2>

        <label className="file-drop">
          <span className="file-drop-icon" aria-hidden="true">📄</span>
          <span className="file-drop-text">
            {file ? file.name : "Choose a CSV or Excel file"}
          </span>
          <span className="file-drop-hint">Ontario rows only · weekly output</span>
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>

        <label className="field">
          <span className="field-label">Data type</span>
          <select value={dataType} onChange={(e) => setDataType(e.target.value)}>
            {DATA_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>

        <div className="actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "On it…" : "Run preprocessing"}
          </button>
          {result && (
            <button type="button" className="btn btn-secondary" onClick={handleDownload}>
              ↓ Download weekly CSV
            </button>
          )}
        </div>
        {error && <p className="alert alert-error">{error}</p>}

        {loading && (
          <div className="runner-panel" role="status" aria-live="polite">
            <p className="runner-caption">{LOADING_LINES[loadingLine]}</p>
            <div className="runner-track">
              <div className="runner-dust" aria-hidden="true" />
              <div className="runner-sprite" aria-hidden="true">
                <span className="runner-body">🏃‍♀️</span>
                <span className="runner-legs">💨</span>
              </div>
              <div className="runner-finish">📊 weekly</div>
            </div>
          </div>
        )}
      </form>

      {result && (
        <section className="results">
          <div className="card">
            <h2 className="card-title">Summary</h2>
            <div className="stat-grid">
              <StatCard label="Original rows" value={result.original_rows} accent="#4477AA" />
              <StatCard label="Rows matched" value={result.ontario_rows} accent="#009E73" />
              <StatCard label="Weekly output" value={result.weekly_rows} accent="#D55E00" />
            </div>

            <div className="meta-chips">
              <span className="chip">
                <strong>File</strong> {result.filename}
              </span>
              <span className="chip">
                <strong>Frequency</strong> {result.frequency_detection?.frequency}
              </span>
              <span className="chip">
                <strong>Type</strong> {formatType(result.data_type, result.data_type_label)}
              </span>
            </div>
            <p className="rule-text">{result.aggregation_rule}</p>

            {result.date_coverage?.after_cleaning && (
              <div className="coverage-card">
                <div className="coverage-header">
                  <span className="coverage-icon" aria-hidden="true">📅</span>
                  <div>
                    <h3 className="coverage-title">Data available after cleaning</h3>
                    <p className="coverage-range">{result.date_coverage.summary}</p>
                  </div>
                </div>
                <div className="coverage-details">
                  <div className="coverage-item">
                    <span className="coverage-label">From</span>
                    <span className="coverage-value">
                      {result.date_coverage.after_cleaning.start_display}
                    </span>
                    <span className="coverage-sub">{result.date_coverage.after_cleaning.start}</span>
                  </div>
                  <div className="coverage-arrow" aria-hidden="true">→</div>
                  <div className="coverage-item">
                    <span className="coverage-label">To</span>
                    <span className="coverage-value">
                      {result.date_coverage.after_cleaning.end_display}
                    </span>
                    <span className="coverage-sub">{result.date_coverage.after_cleaning.end}</span>
                  </div>
                </div>
                <div className="coverage-meta">
                  <span className="chip">
                    <strong>{result.date_coverage.total_weeks}</strong> weekly periods
                  </span>
                  {result.date_coverage.cities_with_data > 0 && (
                    <span className="chip">
                      <strong>{result.date_coverage.cities_with_data}</strong> areas with data
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {result.preprocessing_steps?.length > 0 && (
            <div className="card">
              <h2 className="card-title">Preprocessing steps</h2>
              <PreprocessingSteps steps={result.preprocessing_steps} />
            </div>
          )}

          {result.location_summary?.length > 0 && (
            <div className="card">
              <h2 className="card-title">Matched areas (16 Ontario regions)</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>City</th>
                      <th>Region</th>
                      <th>Rows</th>
                      <th className="bar-col">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.location_summary.map((row) => (
                      <tr key={`${row.matched_city}-${row.matched_region}`}>
                        <td className="city-cell">{row.matched_city}</td>
                        <td>{row.matched_region}</td>
                        <td className="num-cell">{row.rows.toLocaleString()}</td>
                        <td className="bar-col">
                          <div className="bar-track">
                            <div
                              className="bar-fill"
                              style={{ width: `${(row.rows / maxRows) * 100}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card">
            <h2 className="card-title">Weekly preview</h2>
            <WeeklyPreview
              preview={result.preview}
              dataType={result.data_type}
              totalRows={result.weekly_rows}
            />
          </div>
        </section>
      )}
    </>
  );
}

export default function App() {
  const [pipelineStep, setPipelineStep] = useState("preprocessing");

  return (
    <div className="app-shell">
      <div className="bg-shape bg-shape-a" aria-hidden="true" />
      <div className="bg-shape bg-shape-b" aria-hidden="true" />

      <main className="page">
        <nav className="pipeline-nav" aria-label="Pipeline steps">
          {PIPELINE_STEPS.map((step) => (
            <button
              key={step.id}
              type="button"
              className={`pipeline-nav-btn ${pipelineStep === step.id ? "is-active" : ""}`}
              onClick={() => setPipelineStep(step.id)}
            >
              {step.label}
            </button>
          ))}
        </nav>

        {pipelineStep === "preprocessing" ? <PreprocessingPage /> : <FeatureSelectionPage />}
      </main>
    </div>
  );
}
