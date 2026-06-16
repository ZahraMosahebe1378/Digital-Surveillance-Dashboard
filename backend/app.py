from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from services.feature_selection import MODEL_FAMILIES, run_feature_selection
from services.preprocessing import preprocess_csv
from services.weekly_aggregator import AGGREGATION_RULES

app = FastAPI(title="Ontario Data Preprocessing API", version="0.1.0")


def weekly_csv_filename(filename: str) -> str:
    stem = Path(filename or "upload").stem
    return f"weekly_{stem}.csv"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/rules")
def rules() -> dict:
    return {
        "aggregation_rules": {
            key: value["description"] for key, value in AGGREGATION_RULES.items()
        }
    }


@app.get("/feature-selection/models")
def feature_selection_models() -> dict:
    return {"model_families": MODEL_FAMILIES}


@app.post("/feature-selection")
async def feature_selection(
    file: UploadFile = File(...),
    model_family: str = Form(...),
    outcome_file: UploadFile | None = File(default=None),
):
    content = await file.read()
    outcome_content = await outcome_file.read() if outcome_file else None
    try:
        return run_feature_selection(
            file_bytes=content,
            filename=file.filename or "upload.csv",
            model_family=model_family,
            outcome_file_bytes=outcome_content,
            outcome_filename=outcome_file.filename if outcome_file else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/preprocess")
async def preprocess(
    file: UploadFile = File(...),
    data_type: str | None = Form(default=None),
    min_location_confidence: float = Form(default=0.55),
    ontario_only: bool = Form(default=True),
    download: bool = Form(default=False),
):
    content = await file.read()
    try:
        result = preprocess_csv(
            file_bytes=content,
            filename=file.filename or "upload.csv",
            data_type=data_type or None,
            min_location_confidence=min_location_confidence,
            ontario_only=ontario_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if download:
        download_name = weekly_csv_filename(file.filename or "upload.csv")
        return Response(
            content=result["weekly_csv"],
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    return {
        "filename": result["filename"],
        "original_rows": result["original_rows"],
        "ontario_rows_after_filter": result["ontario_rows_after_filter"],
        "ontario_rows": result["ontario_rows"],
        "weekly_rows": result["weekly_rows"],
        "ontario_filter_stats": result["ontario_filter_stats"],
        "frequency_detection": result["frequency_detection"],
        "data_type": result["data_type"],
        "data_type_label": result["data_type_label"],
        "aggregation_rule": result["aggregation_rule"],
        "location_summary": result["location_summary"],
        "match_method_summary": result["match_method_summary"],
        "date_coverage": result["date_coverage"],
        "preview": result["preview"],
        "preprocessing_steps": result.get("preprocessing_steps", []),
    }
