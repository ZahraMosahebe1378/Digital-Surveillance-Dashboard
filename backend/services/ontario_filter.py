"""Keep only Ontario rows during preprocessing."""

from __future__ import annotations

from typing import Any

import pandas as pd

FilterStats = dict[str, Any]

ONTARIO_PROVINCE_VALUES = {"ontario", "on", "ont", "ca-on"}
ONTARIO_PRUID = 35
ONTARIO_BBOX = {
    "min_lat": 41.0,
    "max_lat": 57.5,
    "min_lon": -95.5,
    "max_lon": -74.0,
}

LAT_COLUMNS = ["latitude", "lat", "y", "lat_dd", "latitude_dd"]
LON_COLUMNS = ["longitude", "lon", "lng", "long", "x", "lon_dd", "longitude_dd"]


def detect_lat_lon_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    lower_map = {c.lower(): c for c in df.columns}
    lat_col = next((lower_map[c] for c in LAT_COLUMNS if c in lower_map), None)
    lon_col = next((lower_map[c] for c in LON_COLUMNS if c in lower_map), None)
    return lat_col, lon_col


def _in_ontario_bbox(lat: float, lon: float) -> bool:
    return (
        ONTARIO_BBOX["min_lat"] <= lat <= ONTARIO_BBOX["max_lat"]
        and ONTARIO_BBOX["min_lon"] <= lon <= ONTARIO_BBOX["max_lon"]
    )


def filter_ontario_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, FilterStats]:
    work = df.copy()
    original = len(work)
    flags = pd.Series(False, index=work.index)
    reasons: FilterStats = {}

    if "province" in work.columns:
        province_mask = work["province"].astype(str).str.strip().str.lower().isin(ONTARIO_PROVINCE_VALUES)
        province_mask |= work["province"].astype(str).str.contains("ontario", case=False, na=False)
        flags |= province_mask
        reasons["province_match"] = int(province_mask.sum())

    if "pruid" in work.columns:
        pruid_mask = pd.to_numeric(work["pruid"], errors="coerce") == ONTARIO_PRUID
        flags |= pruid_mask
        reasons["pruid_match"] = int(pruid_mask.sum())

    lat_col, lon_col = detect_lat_lon_columns(work)
    if lat_col and lon_col:
        lat = pd.to_numeric(work[lat_col], errors="coerce")
        lon = pd.to_numeric(work[lon_col], errors="coerce")
        bbox_mask = pd.Series(
            [
                _in_ontario_bbox(a, b) if pd.notna(a) and pd.notna(b) else False
                for a, b in zip(lat, lon)
            ],
            index=work.index,
        )
        geo_mask = lat.notna() & lon.notna() & bbox_mask
        flags |= geo_mask
        reasons["ontario_coordinates"] = int(geo_mask.sum())

    if flags.any():
        kept = work[flags].copy()
        reasons["rows_kept"] = len(kept)
        reasons["rows_dropped"] = original - len(kept)
        return kept, reasons

    # No Ontario metadata columns: downstream city matching will decide.
    reasons["rows_kept"] = original
    reasons["rows_dropped"] = 0
    reasons["note"] = "No province or coordinate columns found; Ontario filtering deferred to city matching."
    return work, reasons
