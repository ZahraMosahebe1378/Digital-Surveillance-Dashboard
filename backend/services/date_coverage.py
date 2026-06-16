"""Compute available date ranges after preprocessing stages."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _to_timestamp(value) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts)


def _iso_week_start(year: int, week: int) -> pd.Timestamp | None:
    try:
        return pd.to_datetime(f"{int(year)}-W{int(week):02d}-1", format="%G-W%V-%u")
    except (ValueError, TypeError):
        return None


def _range_from_dates(dates: pd.Series) -> dict[str, Any] | None:
    parsed = pd.to_datetime(dates, errors="coerce").dropna()
    if parsed.empty:
        return None
    start = parsed.min()
    end = parsed.max()
    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "start_display": start.strftime("%b %d, %Y"),
        "end_display": end.strftime("%b %d, %Y"),
        "span_days": int((end - start).days),
    }


def compute_date_coverage(
    matched_timeline_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> dict[str, Any]:
    input_range = None
    if "event_date" in matched_timeline_df.columns:
        input_range = _range_from_dates(matched_timeline_df["event_date"])

    weekly_range = None
    total_weeks = 0
    cities = 0

    if not weekly_df.empty:
        if "week_start" in weekly_df.columns:
            weekly_range = _range_from_dates(weekly_df["week_start"])
        elif {"year", "week"}.issubset(weekly_df.columns):
            week_dates = [
                _iso_week_start(row.year, row.week)
                for row in weekly_df[["year", "week"]].drop_duplicates().itertuples(index=False)
            ]
            week_dates = [d for d in week_dates if d is not None]
            if week_dates:
                start = min(week_dates)
                end = max(week_dates)
                weekly_range = {
                    "start": start.strftime("%Y-%m-%d"),
                    "end": end.strftime("%Y-%m-%d"),
                    "start_display": start.strftime("%b %d, %Y"),
                    "end_display": end.strftime("%b %d, %Y"),
                    "span_days": int((end - start).days),
                }

        if {"year", "week"}.issubset(weekly_df.columns):
            total_weeks = int(weekly_df[["year", "week"]].drop_duplicates().shape[0])

        if "matched_city" in weekly_df.columns:
            cities = int(weekly_df["matched_city"].dropna().nunique())

    summary_label = "Date range unavailable"
    if weekly_range:
        summary_label = f"{weekly_range['start_display']} → {weekly_range['end_display']}"

    return {
        "summary": summary_label,
        "after_cleaning": weekly_range,
        "before_weekly_aggregation": input_range,
        "total_weeks": total_weeks,
        "cities_with_data": cities,
    }
