"""Fuzzy and coordinate-based location matching for Ontario health boundaries."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from .ontario_filter import ONTARIO_BBOX, detect_lat_lon_columns

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ontario_cities.json"
PHU_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "ontario_phu_mapping.json"
LOCATION_CANDIDATE_COLUMNS = [
    "city",
    "location",
    "site",
    "region",
    "municipality",
    "area",
    "health_unit",
    "geography",
    "place",
    "public_health_unit",
    "public health unit",
]
MAX_GEO_MATCH_KM = 120.0


@dataclass
class LocationMatch:
    raw_value: str
    matched_city: str | None
    matched_region: str | None
    confidence: float
    match_method: str
    distance_km: float | None = None


def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s\.\-']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _contains_match(raw: str, alias: str) -> float:
    if not raw or not alias:
        return 0.0
    if alias in raw or raw in alias:
        return 0.92
    raw_tokens = set(raw.split())
    alias_tokens = set(alias.split())
    if alias_tokens and alias_tokens.issubset(raw_tokens):
        return 0.88
    return 0.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _geo_confidence(distance_km: float) -> float:
    if distance_km <= 20:
        return 0.98
    if distance_km <= 40:
        return 0.93
    if distance_km <= 70:
        return 0.85
    if distance_km <= MAX_GEO_MATCH_KM:
        return 0.70
    return 0.0


def load_boundaries() -> list[dict[str, Any]]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_phu_mapping() -> list[dict[str, str]]:
    if not PHU_MAP_PATH.exists():
        return []
    with open(PHU_MAP_PATH, encoding="utf-8") as f:
        return json.load(f)


def _boundary_for_city(city: str, boundaries: list[dict[str, Any]]) -> dict[str, Any] | None:
    city_norm = _normalize(city)
    for entry in boundaries:
        if _normalize(entry["city"]) == city_norm:
            return entry
    return None


def match_phu_to_city(raw_value: str, boundaries: list[dict[str, Any]] | None = None) -> LocationMatch | None:
    boundaries = boundaries or load_boundaries()
    raw_norm = _normalize(raw_value)
    if not raw_norm:
        return None

    best: tuple[float, dict[str, str]] | None = None
    for entry in load_phu_mapping():
        phu_norm = _normalize(entry["phu"])
        if not phu_norm:
            continue
        if phu_norm in raw_norm or raw_norm in phu_norm:
            score = len(phu_norm) / max(len(raw_norm), 1)
            if best is None or score > best[0]:
                best = (score, entry)

    if not best:
        return None

    boundary = _boundary_for_city(best[1]["city"], boundaries)
    if not boundary:
        return None

    return LocationMatch(
        raw_value=str(raw_value),
        matched_city=boundary["city"],
        matched_region=boundary["region"],
        confidence=0.95,
        match_method="phu_to_16_areas",
    )


def match_location_text(raw_value: str, boundaries: list[dict[str, Any]] | None = None) -> LocationMatch:
    boundaries = boundaries or load_boundaries()
    raw_norm = _normalize(raw_value)

    if not raw_norm:
        return LocationMatch(str(raw_value), None, None, 0.0, "empty")

    phu_match = match_phu_to_city(raw_value, boundaries)
    if phu_match:
        return phu_match

    best: LocationMatch | None = None

    for entry in boundaries:
        city = entry["city"]
        region = entry["region"]
        candidates = [_normalize(city), _normalize(region), *[_normalize(a) for a in entry.get("aliases", [])]]

        for candidate in candidates:
            score = max(_similarity(raw_norm, candidate), _contains_match(raw_norm, candidate))
            if score < 0.55:
                continue

            method = "fuzzy_city" if candidate == _normalize(city) else "fuzzy_region_or_alias"
            match = LocationMatch(
                raw_value=str(raw_value),
                matched_city=city,
                matched_region=region,
                confidence=round(score, 3),
                match_method=method,
            )
            if best is None or match.confidence > best.confidence:
                best = match

    if best:
        return best

    return LocationMatch(str(raw_value), None, None, 0.0, "unmatched")


def match_location_coordinates(
    latitude: float,
    longitude: float,
    boundaries: list[dict[str, Any]] | None = None,
) -> LocationMatch:
    boundaries = boundaries or load_boundaries()

    if not (
        ONTARIO_BBOX["min_lat"] <= latitude <= ONTARIO_BBOX["max_lat"]
        and ONTARIO_BBOX["min_lon"] <= longitude <= ONTARIO_BBOX["max_lon"]
    ):
        return LocationMatch(
            raw_value=f"{latitude},{longitude}",
            matched_city=None,
            matched_region=None,
            confidence=0.0,
            match_method="outside_ontario_bbox",
            distance_km=None,
        )

    best: LocationMatch | None = None

    for entry in boundaries:
        distance = _haversine_km(latitude, longitude, entry["latitude"], entry["longitude"])
        confidence = _geo_confidence(distance)
        if confidence <= 0:
            continue

        match = LocationMatch(
            raw_value=f"{latitude},{longitude}",
            matched_city=entry["city"],
            matched_region=entry["region"],
            confidence=confidence,
            match_method="nearest_city_coordinates",
            distance_km=round(distance, 2),
        )
        current_distance = match.distance_km if match.distance_km is not None else 9999.0
        best_distance = best.distance_km if best and best.distance_km is not None else 9999.0
        if best is None or current_distance < best_distance:
            best = match

    if best:
        return best

    return LocationMatch(
        raw_value=f"{latitude},{longitude}",
        matched_city=None,
        matched_region=None,
        confidence=0.0,
        match_method="unmatched_coordinates",
        distance_km=None,
    )


def _pick_best_match(text_match: LocationMatch, geo_match: LocationMatch | None) -> LocationMatch:
    if geo_match is None:
        return text_match
    if text_match.confidence <= 0:
        return geo_match
    if geo_match.confidence <= 0:
        return text_match
  # Prefer coordinates when both are reasonable; coordinates are usually cleaner.
    if geo_match.confidence >= text_match.confidence:
        return geo_match
    return text_match


def detect_location_columns(df: pd.DataFrame) -> list[str]:
    lower_map = {c.lower(): c for c in df.columns}
    found = [lower_map[c] for c in LOCATION_CANDIDATE_COLUMNS if c in lower_map]
    for col in df.columns:
        lower = col.lower()
        if any(token in lower for token in ("health unit", "health_unit", "public health", "phu")):
            if col not in found:
                found.insert(0, col)
    return found


def build_location_field(row: pd.Series, columns: list[str]) -> str:
    parts: list[str] = []
    for col in columns:
        value = row.get(col)
        if pd.notna(value) and str(value).strip():
            parts.append(str(value).strip())
    return " | ".join(parts)


def match_dataframe_locations(df: pd.DataFrame, min_confidence: float = 0.55) -> pd.DataFrame:
    boundaries = load_boundaries()
    loc_columns = detect_location_columns(df)
    lat_col, lon_col = detect_lat_lon_columns(df)
    out = df.copy()

    matches: list[LocationMatch] = []
    for _, row in out.iterrows():
        raw_value = build_location_field(row, loc_columns) if loc_columns else ""
        text_match = match_location_text(raw_value, boundaries) if raw_value else LocationMatch("", None, None, 0.0, "empty")

        geo_match: LocationMatch | None = None
        if lat_col and lon_col:
            lat = pd.to_numeric(row.get(lat_col), errors="coerce")
            lon = pd.to_numeric(row.get(lon_col), errors="coerce")
            if pd.notna(lat) and pd.notna(lon):
                geo_match = match_location_coordinates(float(lat), float(lon), boundaries)

        matches.append(_pick_best_match(text_match, geo_match))

    out["raw_location"] = [m.raw_value for m in matches]
    out["matched_city"] = [m.matched_city for m in matches]
    out["matched_region"] = [m.matched_region for m in matches]
    out["location_confidence"] = [m.confidence for m in matches]
    out["location_match_method"] = [m.match_method for m in matches]
    out["location_distance_km"] = [m.distance_km for m in matches]
    out["location_matched"] = out["location_confidence"] >= min_confidence

    return out
