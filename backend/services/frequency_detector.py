"""Detect temporal frequency in messy epidemiological CSV files."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

DATE_CANDIDATES = [
    "date",
    "datetime",
    "timestamp",
    "time",
    "weekstart",
    "week_start",
    "epiweek",
    "epiyear",
    "year_month",
    "month",
]

WEEK_NUMBER_HINTS = ("surveillance week", "epiweek", "week number", "week_num")


def _find_date_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        lower = col.lower()
        if lower in DATE_CANDIDATES or "date" in lower or "time" in lower or "week" in lower:
            cols.append(col)
    return cols


def _parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=False)


def _is_week_number_column(col: str) -> bool:
    lower = col.lower().strip()
    if lower in {"week", "surveillance week", "epiweek", "week number"}:
        return True
    return lower.endswith(" week") and "date" not in lower and "start" not in lower and "end" not in lower


def _pick_best_date_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    scored: list[tuple[float, str]] = []
    for col in candidates:
        lower = col.lower()
        score = 1.0
        if _is_week_number_column(col):
            score = 0.05
        elif "start date" in lower or lower in {"date", "event_date", "week_start", "weekstart"}:
            score = 10.0
        elif "end date" in lower:
            score = 8.0
        elif "date" in lower:
            score = 6.0
        elif "time" in lower:
            score = 4.0

        parsed = _parse_dates(df[col]).dropna()
        if len(parsed) >= 3:
            score += 2.0
        elif len(parsed) == 0:
            score = 0.0

        if score > 0:
            scored.append((score, col))

    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]


def detect_frequency(df: pd.DataFrame) -> dict[str, Any]:
    lower_cols = {c.lower(): c for c in df.columns}

    if {"epiyear", "epiweek"}.issubset(lower_cols):
        week_col = lower_cols.get("weekstart")
        return {
            "frequency": "weekly",
            "date_column": week_col or lower_cols["epiweek"],
            "notes": "Detected epidemiological week columns.",
        }

    if "surveillance week" in lower_cols:
        start_col = next((c for c in df.columns if "start date" in c.lower()), None)
        end_col = next((c for c in df.columns if "end date" in c.lower()), None)
        date_col = start_col or end_col or lower_cols["surveillance week"]
        return {
            "frequency": "weekly",
            "date_column": date_col,
            "notes": "Detected surveillance week reporting (already weekly).",
        }

    if {"EpiYear", "EpiWeek"}.issubset(df.columns):
        week_col = next((c for c in df.columns if c.lower() == "weekstart"), None)
        return {
            "frequency": "weekly",
            "date_column": week_col or "EpiWeek",
            "notes": "Detected epidemiological week columns.",
        }

    date_cols = _find_date_columns(df)
    if not date_cols:
        return {"frequency": "unknown", "date_column": None, "notes": "No date column detected."}

    primary = _pick_best_date_column(df, date_cols)
    if primary is None:
        return {"frequency": "unknown", "date_column": None, "notes": "No parseable date column found."}

    if _is_week_number_column(primary):
        return {
            "frequency": "weekly",
            "date_column": primary,
            "notes": "Detected week-number column; treating input as weekly.",
        }

    parsed = _parse_dates(df[primary]).dropna().sort_values()
    if len(parsed) < 3:
        return {"frequency": "unknown", "date_column": primary, "notes": "Too few valid dates."}

    diffs = parsed.diff().dropna()
    median_days = diffs.dt.total_seconds().median() / 86400

    if median_days <= 1.5 / 24:
        freq = "hourly"
    elif median_days <= 2:
        freq = "daily"
    elif 6 <= median_days <= 8:
        freq = "weekly"
    elif 25 <= median_days <= 35:
        freq = "monthly"
    else:
        freq = "irregular"

    return {
        "frequency": freq,
        "date_column": primary,
        "median_interval_days": round(float(median_days), 3),
        "notes": f"Inferred from median interval of {median_days:.2f} days.",
    }


def build_datetime_index(df: pd.DataFrame, detection: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()

    if detection["frequency"] == "weekly" and {"EpiYear", "EpiWeek"}.issubset(out.columns):
        out["event_date"] = pd.to_datetime(out.get("weekstart"), errors="coerce")
        missing = out["event_date"].isna()
        if missing.any():
            out.loc[missing, "event_date"] = (
                pd.to_datetime(out.loc[missing, "EpiYear"].astype(str) + "-1", format="%G-%V-%u", errors="coerce")
            )
        out["year"] = out["EpiYear"]
        out["week"] = out["EpiWeek"]
        return out

    date_col = detection["date_column"]
    if date_col is None:
        raise ValueError("Cannot build weekly timeline without a date column.")

    if _is_week_number_column(date_col):
        week_values = pd.to_numeric(out[date_col], errors="coerce")
        start_col = next((c for c in out.columns if "start date" in c.lower()), None)
        if start_col:
            out["event_date"] = _parse_dates(out[start_col])
        else:
            period_col = next((c for c in out.columns if "surveillance period" in c.lower()), None)
            if period_col:
                years = out[period_col].astype(str).str.extract(r"(\d{4})")[0]
                out["event_date"] = pd.to_datetime(
                    years + "-W" + week_values.astype("Int64").astype(str).str.zfill(2) + "-1",
                    format="%G-W%V-%u",
                    errors="coerce",
                )
            else:
                out["event_date"] = pd.NaT
        out["week"] = week_values
        out["year"] = out["event_date"].dt.isocalendar().year
        missing_year = out["year"].isna()
        if missing_year.any() and "surveillance period" in {c.lower() for c in out.columns}:
            period_col = next(c for c in out.columns if "surveillance period" in c.lower())
            out.loc[missing_year, "year"] = (
                out.loc[missing_year, period_col].astype(str).str.extract(r"(\d{4})")[0]
            )
        return out

    out["event_date"] = _parse_dates(out[date_col])
    iso = out["event_date"].dt.isocalendar()
    out["year"] = iso.year
    out["week"] = iso.week
    return out
