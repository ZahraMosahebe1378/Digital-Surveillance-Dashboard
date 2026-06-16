"""End-to-end Phase 1 preprocessing pipeline."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd

from .date_coverage import compute_date_coverage
from .frequency_detector import build_datetime_index, detect_frequency
from .geo_columns import is_clinical_pipeline
from .location_matcher import match_dataframe_locations
from .ontario_filter import filter_ontario_rows
from .preprocessing_steps import build_preprocessing_steps
from .weekly_aggregator import AGGREGATION_RULES, aggregate_weekly, resolve_data_type


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}


def load_tabular_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = Path(filename or "").suffix.lower()
    buffer = io.BytesIO(file_bytes)

    if ext == ".csv":
        return pd.read_csv(buffer)
    if ext in {".xlsx", ".xlsm"}:
        return pd.read_excel(buffer, engine="openpyxl")

    allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise ValueError(f"Unsupported file type '{ext or '(none)'}'. Upload one of: {allowed}.")


def infer_data_type(frequency: str, filename: str = "") -> str:
    name = filename.lower()
    if "wastewater" in name or "waste water" in name:
        return "wastewater"
    if "mobility" in name:
        return "mobility_data"
    if "climate" in name or frequency == "monthly":
        return "climate_data"
    if "pollution" in name or "air" in name or frequency == "hourly":
        return "air_pollution"
    if any(token in name for token in ["clinical", "outbreak", "hospital", "mmr", "vaccine", "cases"]):
        return "clinical_data"
    if any(token in name for token in ["social", "news", "reddit", "twitter", "topic", "sentiment", "digital"]):
        return "digital_information"
    if frequency == "daily":
        return "mobility_data"
    if frequency == "weekly":
        return "wastewater"
    return "wastewater"


def preprocess_csv(
    file_bytes: bytes,
    filename: str = "upload.csv",
    data_type: str | None = None,
    min_location_confidence: float = 0.55,
    ontario_only: bool = True,
) -> dict[str, Any]:
    df = load_tabular_file(file_bytes, filename)
    original_rows = len(df)
    is_clinical = is_clinical_pipeline(data_type, filename)

    ontario_filter_stats: dict[str, int | str] = {}
    if is_clinical:
        ontario_filter_stats = {
            "skipped": original_rows,
            "reason": "clinical_ontario_phu_source",
        }
        matched_df = match_dataframe_locations(df, min_confidence=min_location_confidence)
        matched_df = matched_df[matched_df["location_matched"]].copy()
    else:
        if ontario_only:
            df, ontario_filter_stats = filter_ontario_rows(df)

        matched_df = match_dataframe_locations(df, min_confidence=min_location_confidence)
        matched_df = matched_df[matched_df["location_matched"]].copy()

    detection = detect_frequency(matched_df)
    timeline_df = build_datetime_index(matched_df, detection)
    resolved_type = resolve_data_type(
        data_type or infer_data_type(detection["frequency"], filename)
    )
    if is_clinical:
        resolved_type = "clinical_data"

    weekly_df = aggregate_weekly(
        timeline_df,
        data_type=resolved_type,
        frequency=detection["frequency"],
    )
    date_coverage = compute_date_coverage(timeline_df, weekly_df)

    preview = weekly_df.head(20).replace({pd.NA: None}).to_dict(orient="records")

    location_summary = (
        matched_df.groupby(["matched_city", "matched_region"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values("rows", ascending=False)
        .head(20)
        .to_dict(orient="records")
    )
    match_method_summary = (
        matched_df["location_match_method"]
        .value_counts()
        .rename_axis("method")
        .reset_index(name="rows")
        .to_dict(orient="records")
    )
    type_meta = AGGREGATION_RULES.get(resolved_type, AGGREGATION_RULES["wastewater"])
    preprocessing_steps = build_preprocessing_steps(
        filename=filename,
        original_rows=original_rows,
        rows_after_filter=len(df) if not is_clinical else original_rows,
        rows_after_location=len(matched_df),
        weekly_rows=len(weekly_df),
        data_type=resolved_type,
        data_type_label=type_meta.get("label", resolved_type),
        is_clinical=is_clinical,
        ontario_only=ontario_only,
        ontario_filter_stats=ontario_filter_stats,
        frequency_detection=detection,
        aggregation_rule=type_meta["description"],
    )

    return {
        "filename": filename,
        "original_rows": original_rows,
        "ontario_rows_after_filter": len(df) if not is_clinical else original_rows,
        "ontario_rows": len(matched_df),
        "weekly_rows": len(weekly_df),
        "ontario_filter_stats": ontario_filter_stats,
        "frequency_detection": detection,
        "data_type": resolved_type,
        "data_type_label": type_meta.get("label", resolved_type),
        "aggregation_rule": type_meta["description"],
        "location_summary": location_summary,
        "match_method_summary": match_method_summary,
        "date_coverage": date_coverage,
        "preview": preview,
        "weekly_csv": weekly_df.to_csv(index=False),
        "skip_geography": False,
        "preprocessing_steps": preprocessing_steps,
    }
