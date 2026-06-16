"""Geographic column helpers for province-wide clinical preprocessing."""

from __future__ import annotations

import pandas as pd

CLINICAL_TYPE_ALIASES = {
    "outbreak": "clinical_data",
    "clinical": "clinical_data",
}

GEO_COLUMN_NAMES = {
    "province",
    "pruid",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "lng",
    "long",
    "lat_dd",
    "latitude_dd",
    "lon_dd",
    "longitude_dd",
    "x",
    "y",
    "city",
    "location",
    "site",
    "region",
    "municipality",
    "area",
    "health_unit",
    "geography",
    "place",
    "matched_city",
    "matched_region",
    "location_matched",
    "location_confidence",
    "location_match_method",
    "location_raw",
}

CLINICAL_DEFAULT_LOCATION = "Toronto"

CLINICAL_FILENAME_TOKENS = ("clinical", "outbreak", "hospital", "mmr", "vaccine")


def is_geographic_column(name: str) -> bool:
    lower = name.lower()
    if lower in GEO_COLUMN_NAMES:
        return True
    return lower.startswith("matched_") or lower.startswith("location_")


def drop_geographic_columns(df: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [col for col in df.columns if is_geographic_column(col)]
    if not drop_cols:
        return df
    return df.drop(columns=drop_cols)


def resolve_clinical_type(data_type: str) -> str:
    key = data_type.strip().lower().replace(" ", "_")
    return CLINICAL_TYPE_ALIASES.get(key, key)


def is_clinical_pipeline(data_type: str | None, filename: str = "") -> bool:
    if data_type:
        return resolve_clinical_type(data_type) == "clinical_data"
    name = filename.lower()
    return any(token in name for token in CLINICAL_FILENAME_TOKENS)
