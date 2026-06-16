"""Feature relevance analysis for weekly epidemiological modeling data."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor

from .preprocessing import load_tabular_file
from .timeline_validator import validate_weekly_timeline

MODEL_FAMILIES = {
    "ai_based": {
        "label": "AI-based models",
        "model_name": "Decision Tree",
        "description": "Non-linear decision tree feature importance for each outcome.",
    },
    "statistical": {
        "label": "Statistical models",
        "model_name": "Negative Binomial Regression",
        "description": "GLM negative binomial coefficients and significance for count outcomes.",
    },
    "heuristic": {
        "label": "Heuristic models",
        "model_name": "Not available yet",
        "description": "Rule-based heuristics will be added in a future release.",
    },
}

OUTCOME_CASE_COLUMNS = (
    "number of cases",
    "number of cases column",
    "weekly_sum_number of cases",
    "cases",
)

OUTCOME_PATTERNS = {
    "covid_cases": [r"covid", r"sars-cov"],
    "influenza_cases": [r"influenza", r"flu"],
    "rsv_cases": [r"rsv", r"respiratory syncytial"],
}

PREFERRED_WASTEWATER_FEATURE = "weekly_mean_w_avg"

ID_COLUMNS = {
    "matched_city",
    "matched_region",
    "location",
    "year",
    "week",
    "week_start",
    "event_date",
    "disease",
    "surveillance period",
    "surveillance week",
}

NON_FEATURE_HINTS = ("population", "per 100", "per100", "rate", "confidence", "distance")


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _find_disease_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col.lower().strip() == "disease":
            return col
    return None


def _find_case_value_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        normalized = _normalize_label(col).replace("weekly_sum_", "")
        if normalized in {_normalize_label(name) for name in OUTCOME_CASE_COLUMNS}:
            if pd.api.types.is_numeric_dtype(df[col]):
                return col

    for col in df.columns:
        lower = col.lower()
        if ("case" in lower or lower.startswith("weekly_sum_")) and pd.api.types.is_numeric_dtype(df[col]):
            if "100" not in lower and "rate" not in lower and "population" not in lower:
                return col
    return None


def _classify_disease_value(value: str) -> str | None:
    lower = str(value).lower()
    if re.search(r"covid|sars-cov", lower):
        return "covid_cases"
    if re.search(r"influenza|\bflu\b", lower):
        return "influenza_cases"
    if re.search(r"rsv|respiratory syncytial", lower):
        return "rsv_cases"
    return None


def _classify_outcome_column(name: str) -> str | None:
    lower = name.lower()
    for outcome, patterns in OUTCOME_PATTERNS.items():
        if any(re.search(p, lower) for p in patterns):
            return outcome
    return None


def _pivot_disease_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    disease_col = _find_disease_column(df)
    if not disease_col:
        return df

    case_col = _find_case_value_column(df)
    if not case_col:
        raise ValueError("Disease column found but no numeric case count column detected.")

    index_cols = [c for c in ["matched_city", "matched_region", "year", "week", "week_start"] if c in df.columns]
    if not index_cols:
        raise ValueError("Need year/week (or week_start) plus optional area columns to pivot disease outcomes.")

    feature_cols = [
        c
        for c in df.columns
        if c not in index_cols + [disease_col, case_col]
        and pd.api.types.is_numeric_dtype(df[c])
        and not _classify_outcome_column(c)
    ]

    grouped = df.groupby(index_cols + [disease_col], dropna=False)
    outcome_wide = grouped[case_col].sum().unstack(disease_col)
    outcome_wide.columns = [
        _classify_disease_value(str(col))
        or _classify_outcome_column(str(col))
        or f"{_normalize_label(col)}_cases"
        for col in outcome_wide.columns
    ]
    if outcome_wide.columns.duplicated().any():
        outcome_wide = outcome_wide.T.groupby(level=0).sum().T

    if feature_cols:
        features = grouped[feature_cols].mean().reset_index()
        wide = features.merge(outcome_wide.reset_index(), on=index_cols, how="left")
    else:
        wide = outcome_wide.reset_index()

    return wide


def _detect_outcome_columns(df: pd.DataFrame) -> list[str]:
    outcomes: list[str] = []
    for col in df.columns:
        if _classify_outcome_column(col):
            outcomes.append(col)
        elif col in {"covid_cases", "influenza_cases", "rsv_cases"}:
            outcomes.append(col)
    return sorted(set(outcomes))


def _detect_feature_columns(df: pd.DataFrame, outcome_cols: list[str]) -> list[str]:
    if PREFERRED_WASTEWATER_FEATURE in df.columns:
        return [PREFERRED_WASTEWATER_FEATURE]

    features: list[str] = []
    for col in df.columns:
        lower = col.lower()
        if col in outcome_cols:
            continue
        if lower in {c.lower() for c in ID_COLUMNS}:
            continue
        if any(hint in lower for hint in NON_FEATURE_HINTS):
            continue
        if _classify_outcome_column(col):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            features.append(col)
    return features


def _merge_keys(predictors: pd.DataFrame, outcomes: pd.DataFrame) -> list[str]:
    for candidate in (
        ["matched_city", "matched_region", "year", "week"],
        ["matched_city", "year", "week"],
        ["year", "week"],
    ):
        if all(col in predictors.columns and col in outcomes.columns for col in candidate):
            return candidate
    return []


def _prepare_outcome_frame(outcome_file_bytes: bytes, outcome_filename: str) -> pd.DataFrame:
    from .preprocessing import preprocess_csv

    result = preprocess_csv(
        file_bytes=outcome_file_bytes,
        filename=outcome_filename,
        data_type="clinical_data",
    )
    return pd.read_csv(io.StringIO(result["weekly_csv"]))


def _merge_predictors_with_outcomes(predictors: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    keys = _merge_keys(predictors, outcomes)
    if not keys:
        raise ValueError(
            "Could not align outcome and predictor files on shared weekly keys "
            "(matched_city + year + week)."
        )

    predictor_cols = list(keys)
    if PREFERRED_WASTEWATER_FEATURE in predictors.columns:
        predictor_cols.append(PREFERRED_WASTEWATER_FEATURE)
    else:
        predictor_cols.extend(
            c
            for c in predictors.columns
            if c not in keys
            and c not in outcomes.columns
            and pd.api.types.is_numeric_dtype(predictors[c])
            and not _classify_outcome_column(c)
        )

    outcome_cols = keys + [c for c in outcomes.columns if c not in keys]
    merged = predictors[predictor_cols].merge(outcomes[outcome_cols], on=keys, how="inner")
    if merged.empty:
        raise ValueError(
            "No overlapping weekly rows between the Cases outcome file and wastewater predictors. "
            "Check that both cover the same areas and weeks."
        )
    return merged


def _modeling_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    work = _pivot_disease_outcomes(df.copy())
    outcomes = _detect_outcome_columns(work)

    if not outcomes:
        case_col = _find_case_value_column(work)
        if case_col:
            renamed = case_col
            classified = _classify_outcome_column(case_col)
            if classified:
                work = work.rename(columns={case_col: classified})
                outcomes = [classified]
            else:
                outcomes = [renamed]

    if not outcomes:
        raise ValueError(
            "No outcome columns found. Upload your Cases file (Number of cases + Disease) "
            "together with wastewater predictors, or provide a merged weekly dataset."
        )

    features = _detect_feature_columns(work, outcomes)
    if not features:
        raise ValueError(
            "No predictor feature columns found. Upload preprocessed data that includes "
            "weekly predictor variables alongside case outcomes."
        )

    bucket = [c for c in ["matched_city", "year", "week"] if c in work.columns]
    if bucket:
        work = work.groupby(bucket, dropna=False)[features + outcomes].mean().reset_index()

    return work, outcomes, features


OUTCOME_LABELS = {
    "covid_cases": "COVID-19 cases",
    "influenza_cases": "Influenza cases",
    "rsv_cases": "RSV cases",
}


def _outcome_label(key: str) -> str:
    return OUTCOME_LABELS.get(key, key.replace("_", " "))


def _interpret_ai_feature(feature: str, importance: float, outcome: str) -> str:
    if importance >= 0.5:
        strength = "highly"
    elif importance >= 0.25:
        strength = "moderately"
    elif importance >= 0.1:
        strength = "weakly"
    else:
        strength = "minimally"
    if importance >= 0.1:
        return (
            f"{feature} is {strength} associated with {outcome} "
            f"(decision-tree importance {importance:.2f})."
        )
    return f"{feature} shows minimal association with {outcome} in this model."


def _interpret_stat_feature(feature: str, coef: float, p_value: float, outcome: str) -> str:
    if p_value < 0.05:
        direction = "positively" if coef > 0 else "negatively"
        if abs(coef) >= 0.5:
            strength = "strongly"
        elif abs(coef) >= 0.1:
            strength = "moderately"
        else:
            strength = "weakly"
        return (
            f"{feature} is {strength} and statistically {direction} associated with {outcome} "
            f"(coefficient {coef:+.3f}, p={p_value:.4f})."
        )
    return (
        f"{feature} does not show a statistically reliable association with {outcome} "
        f"(p={p_value:.4f})."
    )


def _build_outcome_summary(
    model_family: str,
    metrics: dict[str, Any],
    top_feature: str | None,
    outcome: str,
) -> str:
    predictor = top_feature or "The predictor"
    if model_family == "ai_based":
        r2 = float(metrics.get("r2", 0))
        if r2 >= 0.6:
            fit = "a strong"
        elif r2 >= 0.3:
            fit = "a moderate"
        else:
            fit = "a limited"
        return (
            f"{predictor} is the strongest driver of {outcome} in this tree model. "
            f"Together, the selected variables explain {r2 * 100:.0f}% of weekly variation ({fit} fit)."
        )

    pseudo_r2 = float(metrics.get("pseudo_r2", 0))
    if pseudo_r2 >= 0.3:
        fit = "substantial"
    elif pseudo_r2 >= 0.1:
        fit = "moderate"
    else:
        fit = "limited"
    return (
        f"{predictor} shows the strongest statistical link to {outcome}. "
        f"Model pseudo-R² is {pseudo_r2:.2f}, indicating {fit} explanatory power for weekly case counts."
    )


def _attach_interpretations(result: dict[str, Any], model_family: str, outcome_key: str) -> dict[str, Any]:
    label = _outcome_label(outcome_key)
    rankings = result.get("feature_rankings", [])
    for row in rankings:
        if model_family == "ai_based":
            row["description"] = _interpret_ai_feature(row["feature"], row["abs_score"], label)
        else:
            row["description"] = _interpret_stat_feature(
                row["feature"],
                row["score"],
                float(row.get("p_value", 1.0)),
                label,
            )

    top = rankings[0]["feature"] if rankings else None
    result["summary"] = _build_outcome_summary(model_family, result.get("metrics", {}), top, label)
    return result


def _rank_scores(scores: dict[str, float], limit: int = 12) -> list[dict[str, Any]]:
    ordered = sorted(scores.items(), key=lambda item: abs(item[1]), reverse=True)[:limit]
    return [
        {
            "feature": name,
            "score": round(float(value), 4),
            "abs_score": round(abs(float(value)), 4),
        }
        for name, value in ordered
    ]


def _run_decision_tree(X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
    mask = y.notna() & X.notna().any(axis=1)
    X_fit = X.loc[mask].fillna(0.0).reset_index(drop=True)
    y_fit = y.loc[mask].fillna(0.0).reset_index(drop=True)

    if len(X_fit) < 5:
        raise ValueError("Not enough complete weekly rows to train a decision tree.")

    model = DecisionTreeRegressor(max_depth=4, random_state=42)
    model.fit(X_fit, y_fit)
    importances = dict(zip(X.columns, model.feature_importances_))
    pred = model.predict(X_fit)
    ss_res = float(np.sum((y_fit - pred) ** 2))
    ss_tot = float(np.sum((y_fit - y_fit.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "metrics": {
            "r2": round(r2, 4),
            "mae": round(float(np.mean(np.abs(y_fit - pred))), 4),
            "rows_used": int(len(X_fit)),
        },
        "feature_rankings": _rank_scores(importances),
    }


def _run_negative_binomial(X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
    import statsmodels.api as sm

    mask = y.notna()
    X_fit = X.loc[mask].fillna(0.0).reset_index(drop=True)
    y_fit = y.loc[mask].fillna(0.0).clip(lower=0).reset_index(drop=True)
    y_fit = np.round(y_fit).astype(int)

    if len(X_fit) < 8:
        raise ValueError("Not enough complete weekly rows for negative binomial regression.")

    X_const = sm.add_constant(X_fit, has_constant="add")
    model = sm.GLM(y_fit, X_const, family=sm.families.NegativeBinomial())
    result = model.fit(maxiter=100, disp=False)

    scores: dict[str, float] = {}
    p_values: dict[str, float] = {}
    for name, coef, pval in zip(X_const.columns, result.params, result.pvalues):
        if name == "const":
            continue
        scores[name] = float(coef)
        p_values[name] = float(pval)

    return {
        "metrics": {
            "pseudo_r2": round(float(result.pseudo_rsquared()), 4),
            "aic": round(float(result.aic), 2),
            "rows_used": int(len(X_fit)),
        },
        "feature_rankings": [
            {
                **row,
                "p_value": round(p_values.get(row["feature"], 1.0), 4),
                "significant": p_values.get(row["feature"], 1.0) < 0.05,
            }
            for row in _rank_scores(scores)
        ],
    }


def run_feature_selection(
    file_bytes: bytes,
    filename: str,
    model_family: str,
    outcome_file_bytes: bytes | None = None,
    outcome_filename: str | None = None,
) -> dict[str, Any]:
    if model_family not in MODEL_FAMILIES:
        raise ValueError(f"Unknown model family '{model_family}'.")

    meta = MODEL_FAMILIES[model_family]
    if model_family == "heuristic":
        return {
            "model_family": model_family,
            "model_label": meta["label"],
            "model_name": meta["model_name"],
            "available": False,
            "message": "Heuristic models are not implemented yet. Choose AI-based or Statistical.",
        }

    df = load_tabular_file(file_bytes, filename)

    if outcome_file_bytes:
        outcomes_df = _prepare_outcome_frame(outcome_file_bytes, outcome_filename or "Cases.xlsx")
        df = _merge_predictors_with_outcomes(df, outcomes_df)
    elif _find_case_value_column(df) is None and _find_disease_column(df) is None:
        raise ValueError(
            "Upload your Cases outcome file (Cases.xlsx) using the outcome upload box. "
            "The wastewater file supplies weekly_mean_w_avg predictors; "
            "Cases supplies Number of cases outcomes (COVID, Influenza, RSV)."
        )

    timeline = validate_weekly_timeline(df)
    if not timeline["valid"]:
        raise ValueError(timeline["error"])

    modeling_df, outcomes, features = _modeling_frame(df)
    X = modeling_df[features]
    results_by_outcome: dict[str, Any] = {}

    for outcome in outcomes:
        y = modeling_df[outcome]
        if model_family == "ai_based":
            outcome_result = _run_decision_tree(X, y)
        else:
            outcome_result = _run_negative_binomial(X, y)
        results_by_outcome[outcome] = _attach_interpretations(
            outcome_result, model_family, outcome
        )

    return {
        "filename": filename,
        "outcome_filename": outcome_filename,
        "outcome_column": _find_case_value_column(df) or "Number of cases",
        "predictor_column": PREFERRED_WASTEWATER_FEATURE
        if PREFERRED_WASTEWATER_FEATURE in features
        else (features[0] if features else None),
        "model_family": model_family,
        "model_label": meta["label"],
        "model_name": meta["model_name"],
        "available": True,
        "timeline_validation": timeline,
        "outcomes": outcomes,
        "features_analyzed": features,
        "weekly_rows": len(modeling_df),
        "results_by_outcome": results_by_outcome,
    }
