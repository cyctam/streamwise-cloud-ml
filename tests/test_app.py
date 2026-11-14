from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import DATA_DIR, app

client = TestClient(app)


def test_health_reports_dataset_and_model_state() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dataset_available"] is True
    assert body["model_loaded"] is True
    assert client.get("/readyz").status_code == 200


def test_overview_uses_dataset_counts_and_benchmark_label() -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_label"] == "Synthetic benchmark"
    assert body["kpis"]["users"] == 500
    assert body["kpis"]["content"] == 240
    assert body["kpis"]["interactions"] > 0
    assert body["daily_activity"]
    assert body["genre_distribution"]


def test_dataset_explorer_exposes_preview_and_profile() -> None:
    summary = client.get("/api/datasets")
    assert summary.status_code == 200
    names = {item["name"] for item in summary.json()["datasets"]}
    assert names == {"user_profiles", "content_catalog", "user_interactions"}

    preview = client.get("/api/datasets/content_catalog/preview?limit=5")
    assert preview.status_code == 200
    assert len(preview.json()["rows"]) == 5

    profile = client.get("/api/datasets/user_interactions/profile")
    assert profile.status_code == 200
    fields = {item["name"] for item in profile.json()["columns"]}
    assert {"user_id", "content_id", "interaction_type", "timestamp"}.issubset(fields)


def test_recommendations_are_ranked_and_exclude_seen_titles() -> None:
    response = client.get("/api/recommendations/user_00042?limit=8")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 8
    assert [item["rank"] for item in items] == list(range(1, 9))
    assert all(0 <= item["hybrid_score"] <= 1 for item in items)
    assert all(item["score_type"] == "relative_ranking_score_not_probability" for item in items)
    assert len({item["content_id"] for item in items}) == len(items)
    interactions = pd.read_csv(DATA_DIR / "user_interactions.csv")
    seen = set(interactions.loc[interactions.user_id == "user_00042", "content_id"].astype(str))
    assert not seen.intersection(item["content_id"] for item in items)


def test_recommendation_rejects_unknown_user() -> None:
    response = client.get("/api/recommendations/not_a_real_user")
    assert response.status_code == 404


def test_recommendation_score_exposes_both_model_components() -> None:
    response = client.post("/api/recommendations/score", json={
        "user_id": "user_00042",
        "content_id": "content_00001",
    })
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["content_score"] <= 1
    assert 0 <= body["collaborative_score"] <= 1
    assert body["hybrid_score"] == round(0.45 * body["content_score"] + 0.55 * body["collaborative_score"], 4)


def test_forecast_uses_observed_history_without_random_fallback() -> None:
    catalog = client.get("/api/content").json()["items"]
    chosen = None
    for item in catalog:
        response = client.get(f"/api/forecast/{item['content_id']}?periods=7&method=moving_average")
        if response.status_code == 200:
            chosen = response.json()
            break
    assert chosen is not None
    assert len(chosen["history"]) == 30
    assert len(chosen["forecast"]) == 7
    assert chosen["method"] == "moving_average"
    assert chosen["history_end_date"] == chosen["history"][-1]["date"]
    assert "not a calibrated" in chosen["interval_note"]
    assert all(row["lower"] <= row["value"] <= row["upper"] for row in chosen["forecast"])


def test_forecast_validates_method_and_horizon() -> None:
    assert client.get("/api/forecast/content_00001?method=random").status_code == 422
    assert client.get("/api/forecast/content_00001?periods=0").status_code == 422


def test_users_and_content_catalog_endpoints() -> None:
    users = client.get("/api/users?search=user_0004")
    assert users.status_code == 200
    assert users.json()["items"]
    content = client.get("/api/content?limit=10")
    assert content.status_code == 200
    assert len(content.json()["items"]) == 10


def test_model_metrics_include_holdout_and_popularity_baseline() -> None:
    response = client.get("/api/model/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["evaluated_users"] > 0
    assert body["hybrid"]["ndcg_at_k"] is not None
    assert body["popularity_baseline"]["ndcg_at_k"] is not None
    assert body["dataset_label"] == "synthetic benchmark"


def test_forecast_supports_each_documented_baseline() -> None:
    for method in ("moving_average", "linear_trend", "seasonal_naive"):
        response = client.get(f"/api/forecast/content_00001?periods=5&method={method}")
        assert response.status_code == 200
        assert len(response.json()["forecast"]) == 5
