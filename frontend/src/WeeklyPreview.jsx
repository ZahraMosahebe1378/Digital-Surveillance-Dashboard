import { Fragment, useEffect, useMemo, useState } from "react";

const PRIMARY_PREFIX = {
  wastewater: "weekly_mean_",
  air_pollution: "weekly_mean_",
  mobility_data: "weekly_mean_",
  climate_data: "weekly_mean_",
  digital_information: "weekly_mean_",
  clinical_data: "weekly_sum_",
};

const DETAIL_PREFIXES = {
  wastewater: ["weekly_max_", "weekly_min_"],
  air_pollution: ["weekly_max_", "weekly_variance_"],
  mobility_data: [],
  climate_data: [],
  digital_information: ["weekly_count_", "weekly_sum_"],
  clinical_data: [],
};

const ID_KEYS = new Set([
  "matched_city",
  "matched_region",
  "location",
  "year",
  "week",
  "week_start",
  "Disease",
  "disease",
]);

function humanizeColumn(key) {
  return key
    .replace(/^weekly_(mean|max|min|sum|count|variance)_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatWeekLabel(row) {
  if (row.week_start) {
    const d = new Date(row.week_start);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    }
  }
  if (row.year != null && row.week != null) {
    return `${row.year} · W${String(row.week).padStart(2, "0")}`;
  }
  return "—";
}

function formatValue(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (Math.abs(n) >= 1) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (n === 0) return "0";
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function collectMetricColumns(rows, prefix) {
  if (!rows?.length || !prefix) return [];
  const keys = new Set();
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (key.startsWith(prefix) && !ID_KEYS.has(key)) keys.add(key);
    }
  }
  return [...keys].sort();
}

function buildDetailGroups(rows, prefixes) {
  return prefixes
    .map((prefix) => ({
      label: prefix.replace(/^weekly_/, "").replace(/_$/, ""),
      columns: collectMetricColumns(rows, prefix),
    }))
    .filter((g) => g.columns.length > 0);
}

export default function WeeklyPreview({ preview, dataType, totalRows }) {
  const [cityFilter, setCityFilter] = useState("all");
  const [expandedWeek, setExpandedWeek] = useState(null);
  const [visibleCount, setVisibleCount] = useState(10);
  const [showDetails, setShowDetails] = useState(false);

  const primaryPrefix = PRIMARY_PREFIX[dataType] ?? "weekly_mean_";
  const detailPrefixes = DETAIL_PREFIXES[dataType] ?? ["weekly_max_", "weekly_min_"];

  const { cities, primaryColumns, detailGroups, filteredRows } = useMemo(() => {
    const rows = preview ?? [];
    const citySet = new Set();
    for (const row of rows) {
      if (row.matched_city) citySet.add(row.matched_city);
    }
    const cities = [...citySet].sort();
    const primaryColumns = collectMetricColumns(rows, primaryPrefix);
    const detailGroups = buildDetailGroups(rows, detailPrefixes);

    const filtered =
      cityFilter === "all" ? rows : rows.filter((r) => r.matched_city === cityFilter);

    return { cities, primaryColumns, detailGroups, filteredRows: filtered };
  }, [preview, dataType, cityFilter, primaryPrefix, detailPrefixes]);

  useEffect(() => {
    if (!preview?.length) return;
    // #region agent log
    fetch("http://127.0.0.1:7586/ingest/5b59c58d-9b57-4926-acc8-37907a0e0dfa", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "83cec0" },
      body: JSON.stringify({
        sessionId: "83cec0",
        location: "WeeklyPreview.jsx:useEffect",
        message: "Preview columns shaped",
        data: {
          dataType,
          primaryPrefix,
          primaryColumnCount: primaryColumns.length,
          detailGroupCount: detailGroups.length,
          previewRowCount: preview.length,
          cityCount: cities.length,
        },
        timestamp: Date.now(),
        runId: "preview-ui",
        hypothesisId: "H1",
      }),
    }).catch(() => {});
    // #endregion
  }, [preview, dataType, primaryPrefix, primaryColumns.length, detailGroups.length, cities.length]);

  const diseaseKey = useMemo(() => {
    const row = preview?.[0];
    if (!row) return null;
    return Object.keys(row).find((k) => k.toLowerCase() === "disease") ?? null;
  }, [preview]);

  const visibleRows = filteredRows.slice(0, visibleCount);
  const hasMore = visibleCount < filteredRows.length;
  const hasDetails = detailGroups.length > 0;

  function rowKey(row) {
    const disease = row.Disease ?? row.disease ?? "";
    return `${row.matched_city}-${row.year}-${row.week}-${disease}`;
  }

  function toggleRow(key) {
    setExpandedWeek((prev) => (prev === key ? null : key));
  }

  if (!preview?.length) {
    return <p className="preview-empty">No weekly rows to preview.</p>;
  }

  return (
    <div className="weekly-preview">
      <div className="preview-toolbar">
        {cities.length > 0 && (
          <label className="preview-filter">
            <span className="preview-filter-label">City</span>
            <select
              value={cityFilter}
              onChange={(e) => {
                setCityFilter(e.target.value);
                setVisibleCount(10);
                setExpandedWeek(null);
              }}
            >
              <option value="all">All cities ({cities.length})</option>
              {cities.map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </label>
        )}

        {hasDetails && (
          <button
            type="button"
            className={`btn btn-ghost ${showDetails ? "is-active" : ""}`}
            onClick={() => {
              setShowDetails((v) => !v);
              setExpandedWeek(null);
            }}
          >
            {showDetails ? "Hide extra stats" : "Show max / min / other"}
          </button>
        )}

        <span className="preview-count">
          Showing <strong>{Math.min(visibleCount, filteredRows.length)}</strong> of{" "}
          <strong>{filteredRows.length}</strong>
          {totalRows > filteredRows.length ? ` (${totalRows.toLocaleString()} total)` : ""}
        </span>
      </div>

      <div className="table-wrap preview-table-wrap">
        <table className="preview-table">
          <thead>
            <tr>
              {hasDetails && showDetails && <th className="expand-col" aria-label="Expand" />}
              <th>Area</th>
              <th>Week</th>
              {diseaseKey && <th>Disease</th>}
              {primaryColumns.map((col) => (
                <th key={col} className="metric-col">
                  {humanizeColumn(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const key = rowKey(row);
              const isOpen = showDetails && expandedWeek === key;
              return (
                <Fragment key={key}>
                  <tr
                    className={isOpen ? "preview-row is-expanded" : "preview-row"}
                    onClick={hasDetails && showDetails ? () => toggleRow(key) : undefined}
                    style={hasDetails && showDetails ? { cursor: "pointer" } : undefined}
                  >
                    {hasDetails && showDetails && (
                      <td className="expand-col">
                        <span className="expand-icon" aria-hidden="true">
                          {isOpen ? "▼" : "▶"}
                        </span>
                      </td>
                    )}
                    <td className="city-cell">{row.matched_city ?? "—"}</td>
                    <td className="week-cell">{formatWeekLabel(row)}</td>
                    {diseaseKey && <td>{row[diseaseKey] ?? "—"}</td>}
                    {primaryColumns.map((col) => (
                      <td key={col} className="num-cell metric-value">
                        {formatValue(row[col])}
                      </td>
                    ))}
                  </tr>
                  {isOpen && (
                    <tr className="preview-detail-row">
                      <td
                        colSpan={
                          2 + (diseaseKey ? 1 : 0) + primaryColumns.length + (showDetails ? 1 : 0)
                        }
                      >
                        <div className="detail-panels">
                          {detailGroups.map((group) => (
                            <div key={group.label} className="detail-panel">
                              <span className="detail-panel-title">{group.label}</span>
                              <div className="detail-metrics">
                                {group.columns.map((col) => (
                                  <div key={col} className="detail-metric">
                                    <span className="detail-metric-label">{humanizeColumn(col)}</span>
                                    <span className="detail-metric-value">{formatValue(row[col])}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <button
          type="button"
          className="btn btn-secondary preview-more"
          onClick={() => setVisibleCount((n) => n + 10)}
        >
          Show more rows
        </button>
      )}

      <p className="preview-hint">
        Primary weekly values only — download CSV for the full aggregation columns.
      </p>
    </div>
  );
}
