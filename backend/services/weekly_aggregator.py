"""Convert heterogeneous epidemiological data to a common weekly timeline."""

from __future__ import annotations

from typing import Any

import pandas as pd

# User-defined preprocessing rules for Phase 1
AGGREGATION_RULES: dict[str, dict[str, Any]] = {
    "wastewater": {
        "label": "Waste Water",
        "description": "Waste Water -> weekly mean / max / min",
        "numeric_ops": {"mean": "mean", "max": "max", "min": "min"},
    },
    "air_pollution": {
        "label": "Air Pollution",
        "description": "Air Pollution -> weekly mean / max / variance",
        "numeric_ops": {"mean": "mean", "max": "max", "variance": "var"},
    },
    "mobility_data": {
        "label": "Mobility Data",
        "description": "Mobility Data -> weekly average",
        "numeric_ops": {"mean": "mean"},
    },
    "climate_data": {
        "label": "Climate Data",
        "description": "Climate Data -> forward-fill / interpolate, then weekly",
        "resample": "monthly_to_weekly",
        "numeric_ops": {"mean": "mean"},
    },
    "digital_information": {
        "label": "Digital Information",
        "description": "Digital Information -> weekly count / sentiment mean / topic frequency",
        "numeric_ops": {"count": "count", "mean": "mean", "sum": "sum"},
    },
    "clinical_data": {
        "label": "Clinical Data",
        "description": "Clinical Data -> map public health units to 16 Ontario areas, weekly sum of cases",
        "numeric_ops": {"sum": "sum"},
    },
}

DATA_TYPE_ALIASES: dict[str, str] = {
    "hourly_air_pollution": "air_pollution",
    "daily_mobility": "mobility_data",
    "monthly_climate": "climate_data",
    "social_media": "digital_information",
    "outbreak": "clinical_data",
    "auto": "wastewater",
}


def resolve_data_type(data_type: str) -> str:
    return DATA_TYPE_ALIASES.get(data_type, data_type)


def _find_disease_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        lower = col.lower().strip()
        if lower in {"disease", "pathogen", "syndrome"} or lower == "disease":
            return col
        if "disease" in lower:
            return col
    return None


def _clinical_metric_columns(df: pd.DataFrame) -> list[str]:
    metrics: list[str] = []
    for col in df.columns:
        lower = col.lower()
        if any(
            token in lower
            for token in (
                "population",
                "per 100",
                "per100",
                "rate",
                "surveillance week",
                "surveillance period",
            )
        ):
            continue
        if "case" in lower and pd.api.types.is_numeric_dtype(df[col]):
            metrics.append(col)
    return metrics


def _numeric_columns(df: pd.DataFrame, data_type: str = "wastewater") -> list[str]:
    if resolve_data_type(data_type) == "clinical_data":
        clinical_metrics = _clinical_metric_columns(df)
        if clinical_metrics:
            return clinical_metrics

    exclude = {
        "year",
        "week",
        "event_date",
        "location_confidence",
        "EpiYear",
        "EpiWeek",
        "pruid",
    }
    cols = []
    for col in df.columns:
        if col in exclude or col.startswith("matched_") or col.startswith("location_"):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            cols.append(col)
    return cols


def _group_columns(data_type: str, df: pd.DataFrame) -> list[str]:
    base = ["matched_city", "matched_region", "year", "week"]
    if resolve_data_type(data_type) == "clinical_data":
        disease_col = _find_disease_column(df)
        if disease_col:
            return base + [disease_col]
    return base


def _monthly_to_weekly(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    work = df.copy()
    work = work.sort_values("event_date")
    work = work.set_index("event_date")
    weekly_index = pd.date_range(work.index.min(), work.index.max(), freq="W-MON")
    expanded = work.reindex(work.index.union(weekly_index)).sort_index()
    for col in numeric_cols:
        expanded[col] = expanded[col].interpolate(method="time").ffill()
    expanded = expanded.loc[weekly_index]
    iso = expanded.index.isocalendar()
    expanded["year"] = iso.year
    expanded["week"] = iso.week
    expanded["event_date"] = expanded.index
    return expanded.reset_index(drop=True)


def aggregate_weekly(df: pd.DataFrame, data_type: str = "wastewater", frequency: str = "auto") -> pd.DataFrame:
    if "event_date" not in df.columns:
        raise ValueError("Dataframe must include event_date before weekly aggregation.")

    resolved_type = resolve_data_type(data_type)
    rules = AGGREGATION_RULES.get(resolved_type, AGGREGATION_RULES["wastewater"])
    numeric_cols = _numeric_columns(df, data_type=resolved_type)

    if not numeric_cols:
        raise ValueError("No numeric metric columns found for weekly aggregation.")

    if resolved_type == "climate_data" or frequency == "monthly":
        df = _monthly_to_weekly(df, numeric_cols)

    group_cols = _group_columns(resolved_type, df)
    for col in group_cols:
        if col not in df.columns:
            df[col] = None

    grouped = df.groupby(group_cols, dropna=False)
    frames: list[pd.DataFrame] = []

    for op_name, pandas_op in rules["numeric_ops"].items():
        if pandas_op == "count":
            agg = grouped.size().rename(f"weekly_{op_name}").reset_index()
        elif pandas_op == "var":
            agg = grouped[numeric_cols].var().add_prefix(f"weekly_{op_name}_").reset_index()
        else:
            agg = grouped[numeric_cols].agg(pandas_op).add_prefix(f"weekly_{op_name}_").reset_index()
        frames.append(agg)

    result = frames[0]
    for frame in frames[1:]:
        result = result.merge(frame, on=group_cols, how="outer")

    week_starts = (
        df.groupby(group_cols, dropna=False)["event_date"]
        .min()
        .reset_index()
        .rename(columns={"event_date": "week_start"})
    )
    result = result.merge(week_starts, on=group_cols, how="left")
    result = result.sort_values(["matched_city", "year", "week"]).reset_index(drop=True)
    return result
