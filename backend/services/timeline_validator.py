"""Validate that uploaded modeling data uses a consistent weekly timeline."""

from __future__ import annotations

from typing import Any

import pandas as pd

WEEKLY_GAP_DAYS = (5.5, 8.5)
DAILY_GAP_MAX = 2.5


def _parse_week_starts(df: pd.DataFrame) -> pd.Series:
    if "week_start" in df.columns:
        parsed = pd.to_datetime(df["week_start"], errors="coerce")
        if parsed.notna().sum() >= 3:
            return parsed

    if {"year", "week"}.issubset(df.columns):
        years = pd.to_numeric(df["year"], errors="coerce")
        weeks = pd.to_numeric(df["week"], errors="coerce")
        built = pd.to_datetime(
            years.astype("Int64").astype(str) + "-W" + weeks.astype("Int64").astype(str).str.zfill(2) + "-1",
            format="%G-W%V-%u",
            errors="coerce",
        )
        if built.notna().sum() >= 3:
            return built

    for col in df.columns:
        lower = col.lower()
        if "start date" in lower or lower in {"date", "event_date"}:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() >= 3:
                return parsed

    return pd.Series(dtype="datetime64[ns]")


def validate_weekly_timeline(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "valid": False,
            "frequency": "unknown",
            "error": "Uploaded file is empty.",
            "week_count": 0,
        }

    week_dates = _parse_week_starts(df)
    if week_dates.notna().sum() < 3:
        return {
            "valid": False,
            "frequency": "unknown",
            "error": (
                "Could not detect a weekly timeline. Expected columns like year + week, "
                "week_start, or a parseable start date column."
            ),
            "week_count": int(week_dates.notna().sum()),
        }

    unique_weeks = week_dates.dropna().drop_duplicates().sort_values()
    week_count = len(unique_weeks)

    if week_count < 3:
        return {
            "valid": False,
            "frequency": "unknown",
            "error": "Need at least 3 weekly periods for feature relevance analysis.",
            "week_count": week_count,
            "timeline_start": unique_weeks.min().strftime("%Y-%m-%d") if week_count else None,
            "timeline_end": unique_weeks.max().strftime("%Y-%m-%d") if week_count else None,
        }

    gaps = unique_weeks.diff().dropna().dt.total_seconds() / 86400
    median_gap = float(gaps.median()) if not gaps.empty else 0.0

    if median_gap <= DAILY_GAP_MAX:
        return {
            "valid": False,
            "frequency": "daily",
            "error": (
                f"Data appears daily (median gap {median_gap:.1f} days), not weekly. "
                "Run the preprocessing step first to align to a weekly grid."
            ),
            "week_count": week_count,
            "median_gap_days": round(median_gap, 2),
        }

    if not (WEEKLY_GAP_DAYS[0] <= median_gap <= WEEKLY_GAP_DAYS[1]):
        return {
            "valid": False,
            "frequency": "irregular",
            "error": (
                f"Timeline is not consistently weekly (median gap {median_gap:.1f} days). "
                "All feature and outcome rows must share the same weekly periods."
            ),
            "week_count": week_count,
            "median_gap_days": round(median_gap, 2),
        }

    # Check alignment: each modeling row should map to one weekly bucket
    bucket_cols = [c for c in ("matched_city", "year", "week") if c in df.columns]
    if bucket_cols:
        dupes = df.duplicated(subset=bucket_cols, keep=False).sum()
        if dupes > len(df) * 0.5 and "Disease" not in df.columns and "disease" not in {c.lower() for c in df.columns}:
            return {
                "valid": False,
                "frequency": "weekly",
                "error": (
                    "Multiple rows share the same area/week without a disease dimension. "
                    "Merge or pivot outcomes before feature relevance analysis."
                ),
                "week_count": week_count,
                "median_gap_days": round(median_gap, 2),
            }

    return {
        "valid": True,
        "frequency": "weekly",
        "error": None,
        "week_count": week_count,
        "median_gap_days": round(median_gap, 2),
        "timeline_start": unique_weeks.min().strftime("%Y-%m-%d"),
        "timeline_end": unique_weeks.max().strftime("%Y-%m-%d"),
    }
