"""Build human-readable preprocessing step summaries for the API and UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .weekly_aggregator import AGGREGATION_RULES, resolve_data_type

Step = dict[str, Any]


def _file_format_label(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in {".xlsx", ".xlsm"}:
        return "Excel"
    if ext == ".csv":
        return "CSV"
    return ext.lstrip(".") or "file"


def _aggregation_detail(data_type: str, frequency: str) -> str:
    resolved = resolve_data_type(data_type)
    rules = AGGREGATION_RULES.get(resolved, AGGREGATION_RULES["wastewater"])
    ops = " / ".join(rules["numeric_ops"].keys())
    base = f"Applied weekly {ops} aggregation for {rules['label']}."
    if resolved == "climate_data" or frequency == "monthly":
        base += " Monthly values were forward-filled and interpolated to a weekly grid first."
    elif resolved == "clinical_data":
        if frequency == "weekly":
            base += " Input was already weekly; case counts were summed per area and week."
        elif frequency == "daily":
            base += " Daily case counts were rolled up into weekly sums per area."
        else:
            base += " Case metrics were aligned to a weekly timeline and summed per area."
    return base


def build_preprocessing_steps(
    *,
    filename: str,
    original_rows: int,
    rows_after_filter: int,
    rows_after_location: int,
    weekly_rows: int,
    data_type: str,
    data_type_label: str,
    is_clinical: bool,
    ontario_only: bool,
    ontario_filter_stats: dict[str, Any],
    frequency_detection: dict[str, Any],
    aggregation_rule: str,
) -> list[Step]:
    steps: list[Step] = []
    step_num = 1
    fmt = _file_format_label(filename)
    freq = frequency_detection.get("frequency", "unknown")
    date_col = frequency_detection.get("date_column")

    steps.append(
        {
            "step": step_num,
            "title": "Load file",
            "detail": f"Read {fmt} file '{filename}' ({original_rows:,} rows).",
        }
    )
    step_num += 1

    if is_clinical:
        steps.append(
            {
                "step": step_num,
                "title": "Skip Ontario boundary filter",
                "detail": (
                    "Clinical source data is already Ontario public-health reporting; "
                    "no province or coordinate filter was applied."
                ),
            }
        )
        step_num += 1

        dropped = max(original_rows - rows_after_location, 0)
        steps.append(
            {
                "step": step_num,
                "title": "Map public health units to 16 Ontario areas",
                "detail": (
                    f"Matched health-unit names to the 16 Ontario modeling areas; "
                    f"{rows_after_location:,} rows kept ({dropped:,} unmatched)."
                    if dropped
                    else f"Matched health-unit names to the 16 Ontario modeling areas; "
                    f"all {rows_after_location:,} rows mapped."
                ),
            }
        )
        step_num += 1
    else:
        if ontario_only:
            kept = rows_after_filter
            removed = max(original_rows - kept, 0)
            filter_bits = []
            for key, value in ontario_filter_stats.items():
                if isinstance(value, int) and value > 0:
                    filter_bits.append(f"{key.replace('_', ' ')}: {value:,}")
            extra = f" ({'; '.join(filter_bits)})" if filter_bits else ""
            steps.append(
                {
                    "step": step_num,
                    "title": "Filter to Ontario rows",
                    "detail": (
                        f"Kept {kept:,} of {original_rows:,} rows inside Ontario boundaries"
                        f"{extra}."
                        if removed
                        else f"All {kept:,} rows were already within Ontario."
                    ),
                }
            )
            step_num += 1

        dropped = max(rows_after_filter - rows_after_location, 0)
        steps.append(
            {
                "step": step_num,
                "title": "Match Ontario health boundaries",
                "detail": (
                    f"Fuzzy-matched locations to 16 Ontario cities; {rows_after_location:,} rows "
                    f"matched ({dropped:,} rows dropped below confidence threshold)."
                    if dropped
                    else f"Fuzzy-matched locations to 16 Ontario cities; all {rows_after_location:,} rows matched."
                ),
            }
        )
        step_num += 1

    date_note = f" using column '{date_col}'" if date_col else ""
    steps.append(
        {
            "step": step_num,
            "title": "Detect temporal frequency",
            "detail": (
                f"Detected {freq} cadence{date_note}. "
                f"{frequency_detection.get('notes', '')}".strip()
            ),
        }
    )
    step_num += 1

    steps.append(
        {
            "step": step_num,
            "title": "Align to weekly timeline",
            "detail": (
                "Parsed week start dates into ISO year/week and built event_date "
                "for the common weekly modeling grid."
            ),
        }
    )
    step_num += 1

    steps.append(
        {
            "step": step_num,
            "title": "Aggregate to weekly metrics",
            "detail": _aggregation_detail(data_type, freq),
        }
    )
    step_num += 1

    steps.append(
        {
            "step": step_num,
            "title": "Prepare output",
            "detail": (
                f"Produced {weekly_rows:,} weekly rows for {data_type_label}. "
                f"Rule: {aggregation_rule}."
            ),
        }
    )

    return steps
