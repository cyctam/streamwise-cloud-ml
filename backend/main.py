from __future__ import annotations

import json
import logging
import os
import pickle
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data/raw"))
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", ROOT / "artifacts"))
FRONTEND_DIST = ROOT / "frontend/dist"
LOGGER = logging.getLogger("streamwise.api")

app = FastAPI(
    title="Streamwise API",
    version="2.1.0",
    description="Dataset exploration and hybrid streaming recommendation API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_model: Any | None = None
_metrics: dict[str, Any] = {}


class ScoreRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    content_id: str = Field(min_length=1, max_length=64)


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"Dataset file is missing: {name}")
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        LOGGER.exception("Unable to read dataset %s", name)
        raise HTTPException(status_code=503, detail=f"Dataset cannot be read: {name}") from exc


def _datasets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        _read_csv("user_profiles.csv"),
        _read_csv("content_catalog.csv"),
        _read_csv("user_interactions.csv"),
    )


def _load_model() -> None:
    global _model, _metrics
    model_path = ARTIFACT_DIR / "hybrid_recommender.pkl"
    metrics_path = ARTIFACT_DIR / "metrics.json"
    _model = None
    _metrics = {}
    try:
        if os.getenv("MODEL_BUCKET"):
            import boto3

            ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            client = boto3.client("s3")
            if not model_path.is_file():
                client.download_file(
                    os.environ["MODEL_BUCKET"],
                    os.getenv("MODEL_KEY", "models/hybrid_recommender.pkl"),
                    str(model_path),
                )
            if not metrics_path.is_file():
                client.download_file(
                    os.environ["MODEL_BUCKET"],
                    os.getenv("METRICS_KEY", "models/metrics.json"),
                    str(metrics_path),
                )
        if not model_path.is_file():
            LOGGER.warning("Model artifact not found at %s", model_path)
            return
        with model_path.open("rb") as stream:
            candidate = pickle.load(stream)
        if not getattr(candidate, "is_fitted", False):
            raise ValueError("Model artifact is not fitted")
        _model = candidate
        if metrics_path.is_file():
            _metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        else:
            _metrics = candidate.metrics()
    except Exception as exc:
        LOGGER.exception("Unable to load model artifact")
        _metrics = {"load_error": str(exc)}


_load_model()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "dataset_available": all((DATA_DIR / name).is_file() for name in (
            "user_profiles.csv", "content_catalog.csv", "user_interactions.csv"
        )),
        "api_version": app.version,
    }


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    dataset_available = all((DATA_DIR / name).is_file() for name in (
        "user_profiles.csv", "content_catalog.csv", "user_interactions.csv"
    ))
    if not dataset_available or _model is None:
        raise HTTPException(
            status_code=503,
            detail={"dataset_available": dataset_available, "model_loaded": _model is not None},
        )
    return {"status": "ready", "model_loaded": True, "dataset_available": True}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    users, content, interactions = _datasets()
    interactions = interactions.copy()
    interactions["timestamp"] = pd.to_datetime(interactions["timestamp"], errors="coerce", utc=True)
    positive = interactions[interactions.interaction_type.isin(["play", "complete", "like", "add_to_watchlist"])]
    daily = (
        positive.dropna(subset=["timestamp"])
        .assign(day=lambda frame: frame.timestamp.dt.strftime("%Y-%m-%d"))
        .groupby("day").size().tail(30)
    )
    genre_mix = (
        interactions.merge(content[["content_id", "genre"]], on="content_id", how="inner")
        .groupby("genre").size().sort_values(ascending=False)
    )
    event_mix = interactions.interaction_type.value_counts()
    return {
        "dataset_label": "Synthetic benchmark",
        "dataset_note": "Generated data for reproducible experiments; not production user telemetry.",
        "kpis": {
            "users": int(users.user_id.nunique()),
            "content": int(content.content_id.nunique()),
            "interactions": int(len(interactions)),
            "positive_events": int(len(positive)),
            "unique_user_content_pairs": int(interactions[["user_id", "content_id"]].drop_duplicates().shape[0]),
        },
        "daily_activity": [{"date": str(key), "events": int(value)} for key, value in daily.items()],
        "genre_distribution": [{"genre": str(key), "interactions": int(value)} for key, value in genre_mix.items()],
        "event_distribution": [{"event": str(key), "count": int(value)} for key, value in event_mix.items()],
        "model": {"loaded": _model is not None, **_metrics},
    }


def _dataset_frames() -> dict[str, tuple[pd.DataFrame, str]]:
    users, content, interactions = _datasets()
    return {
        "user_profiles": (users, "User attributes and declared genre preference"),
        "content_catalog": (content, "Streaming catalog metadata and content attributes"),
        "user_interactions": (interactions, "Timestamped playback and engagement events"),
    }


@app.get("/api/datasets")
def datasets() -> dict[str, Any]:
    frames = _dataset_frames()
    result = []
    for name, (frame, description) in frames.items():
        duplicate_count = int(frame.duplicated().sum())
        result.append({
            "name": name,
            "description": description,
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "missing_values": int(frame.isna().sum().sum()),
            "duplicate_rows": duplicate_count,
            "fields": list(frame.columns),
        })
    return {"label": "Synthetic benchmark", "datasets": result}


@app.get("/api/datasets/{name}/preview")
def dataset_preview(name: str, limit: int = Query(12, ge=1, le=50)) -> dict[str, Any]:
    frames = _dataset_frames()
    if name not in frames:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    frame = frames[name][0].head(limit).astype(object).where(pd.notna(frames[name][0].head(limit)), None)
    return {"name": name, "columns": list(frame.columns), "rows": frame.to_dict(orient="records")}


@app.get("/api/datasets/{name}/profile")
def dataset_profile(name: str) -> dict[str, Any]:
    frames = _dataset_frames()
    if name not in frames:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    frame = frames[name][0]
    columns = []
    for column in frame.columns:
        series = frame[column]
        missing = int(series.isna().sum())
        unique = int(series.nunique(dropna=True))
        item: dict[str, Any] = {
            "name": str(column),
            "dtype": str(series.dtype),
            "missing": missing,
            "missing_pct": round(missing / max(len(frame), 1) * 100, 2),
            "unique": unique,
        }
        if pd.api.types.is_numeric_dtype(series):
            values = pd.to_numeric(series, errors="coerce").dropna()
            item["statistics"] = {
                "min": round(float(values.min()), 3) if not values.empty else None,
                "median": round(float(values.median()), 3) if not values.empty else None,
                "mean": round(float(values.mean()), 3) if not values.empty else None,
                "max": round(float(values.max()), 3) if not values.empty else None,
            }
        else:
            item["top_values"] = [
                {"value": str(value), "count": int(count)}
                for value, count in series.value_counts(dropna=True).head(5).items()
            ]
        columns.append(item)
    return {
        "name": name,
        "rows": int(len(frame)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "columns": columns,
    }


@app.get("/api/users")
def users(search: str = Query("", max_length=64), limit: int = Query(50, ge=1, le=100)) -> dict[str, Any]:
    frame = _read_csv("user_profiles.csv")
    if search:
        frame = frame[frame.user_id.astype(str).str.contains(search, case=False, regex=False)]
    return {"items": frame.head(limit)[["user_id", "preferred_genre", "customer_segment"]].to_dict(orient="records")}


@app.get("/api/content")
def content(search: str = Query("", max_length=100), limit: int = Query(100, ge=1, le=250)) -> dict[str, Any]:
    frame = _read_csv("content_catalog.csv")
    if search:
        mask = frame.title.astype(str).str.contains(search, case=False, regex=False)
        frame = frame[mask]
    fields = [field for field in ("content_id", "title", "genre", "content_type") if field in frame]
    return {"items": frame.head(limit)[fields].to_dict(orient="records")}


@app.get("/api/model/status")
def model_status() -> dict[str, Any]:
    return {"loaded": _model is not None, "metrics": _metrics}


@app.get("/api/model/metrics")
def model_metrics() -> dict[str, Any]:
    if _model is None:
        raise HTTPException(status_code=503, detail="Model artifact unavailable. Train it with `python -m backend.ml.train` and restart the API.")
    return _metrics


@app.get("/api/recommendations/{user_id}")
def recommendations(user_id: str, limit: int = Query(10, ge=1, le=30)) -> dict[str, Any]:
    if _model is None:
        raise HTTPException(status_code=503, detail="Model artifact unavailable. Train it with `python -m backend.ml.train` and restart the API.")
    try:
        items = _model.recommend(user_id, limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "user_id": user_id,
        "items": items,
        "score_semantics": "Relative ranking score; not a calibrated probability.",
    }


@app.post("/api/recommendations/score")
def recommendation_score(body: ScoreRequest) -> dict[str, Any]:
    if _model is None:
        raise HTTPException(status_code=503, detail="Model artifact unavailable. Train it with `python -m backend.ml.train` and restart the API.")
    try:
        return _model.score(body.user_id, body.content_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/forecast/{content_id}")
def forecast(
    content_id: str,
    periods: int = Query(14, ge=1, le=60),
    method: str = Query("moving_average", pattern="^(moving_average|linear_trend|seasonal_naive)$"),
) -> dict[str, Any]:
    _, catalog, interactions = _datasets()
    if content_id not in set(catalog.content_id.astype(str)):
        raise HTTPException(status_code=404, detail="Content not found")
    events = interactions[
        (interactions.content_id.astype(str) == content_id)
        & interactions.interaction_type.isin(["play", "complete"])
    ].copy()
    if events.empty:
        raise HTTPException(status_code=422, detail="No observed play history for this title; forecasting is unavailable.")
    events["day"] = pd.to_datetime(events.timestamp, errors="coerce", utc=True).dt.date
    history = events.dropna(subset=["day"]).groupby("day").size().sort_index()
    if history.empty:
        raise HTTPException(status_code=422, detail="The title has no valid timestamped play history.")
    end = history.index.max()
    start = end - timedelta(days=29)
    history_dates = [start + timedelta(days=index) for index in range(30)]
    values = np.asarray([float(history.get(day, 0)) for day in history_dates], dtype=float)
    if method == "moving_average":
        window = values[-7:]
        predictions = [float(window.mean())] * periods
    elif method == "linear_trend":
        slope, intercept = np.polyfit(np.arange(len(values)), values, 1)
        predictions = [max(0.0, float(intercept + slope * (len(values) + step))) for step in range(periods)]
    else:
        predictions = []
        for step in range(periods):
            weekday_slot = (len(values) + step) % 7
            seasonal_values = values[weekday_slot::7]
            predictions.append(float(seasonal_values.mean()) if seasonal_values.size else float(values.mean()))
    residual_scale = float(np.std(values[-14:] - np.mean(values[-14:]))) if len(values) >= 14 else float(np.std(values))
    forecast_dates = [end + timedelta(days=index + 1) for index in range(periods)]
    catalog_row = catalog.loc[catalog.content_id.astype(str) == content_id].iloc[0]
    return {
        "content_id": content_id,
        "title": str(catalog_row.title),
        "method": method,
        "history_end_date": end.isoformat(),
        "method_label": {
            "moving_average": "7-day moving average baseline",
            "linear_trend": "Linear trend baseline",
            "seasonal_naive": "Day-of-week seasonal naive baseline",
        }[method],
        "history": [{"date": day.isoformat(), "actual": int(value)} for day, value in zip(history_dates, values, strict=True)],
        "forecast": [
            {
                "date": day.isoformat(),
                "value": round(max(0.0, value), 2),
                "lower": round(max(0.0, value - 1.28 * residual_scale), 2),
                "upper": round(max(0.0, value + 1.28 * residual_scale), 2),
            }
            for day, value in zip(forecast_dates, predictions, strict=True)
        ],
        "interval_note": "Illustrative variability band based on recent observed daily counts; not a calibrated prediction interval.",
    }


if FRONTEND_DIST.is_dir():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
