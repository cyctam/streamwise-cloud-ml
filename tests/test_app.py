import pytest

from web.app import app


@pytest.fixture()
def client():
    return app.test_client()


def test_pages_render(client):
    for path in ("/", "/prediction", "/forecasting", "/healthz"):
        assert client.get(path).status_code == 200


def test_predict_is_deterministic_and_bounded(client):
    body = {"user_id": "user_00001", "content_id": "content_00001"}
    a, b = client.post("/api/predict", json=body).json, client.post("/api/predict", json=body).json
    assert a == b
    assert 0 <= a["prediction_percentage"] <= 100
    assert len(a["factors"]) == 3


@pytest.mark.parametrize("body", [
    {}, {"user_id": "u"}, {"user_id": "<x>", "content_id": "c"},
    {"user_id": "u", "content_id": "c", "context": {"user_state": "nope"}},
])
def test_predict_rejects_bad_input(client, body):
    assert client.post("/api/predict", json=body).status_code == 400


@pytest.mark.parametrize("method", ["moving_average", "exponential_smoothing", "linear_trend", "seasonal"])
def test_forecast_shape(client, method):
    res = client.post("/api/forecast", json={"content_id": "c1", "periods": 14, "method": method}).json
    fc = res["forecast"]
    assert len(fc["dates"]) == len(fc["values"]) == len(fc["lower"]) == len(fc["upper"]) == 14
    assert all(lo <= v <= hi for lo, v, hi in zip(fc["lower"], fc["values"], fc["upper"], strict=False))
    assert res["summary"]["total"] == sum(fc["values"])


@pytest.mark.parametrize("body", [
    {"content_id": "c", "periods": 0}, {"content_id": "c", "periods": 366},
    {"content_id": "c", "periods": "x"}, {"content_id": "c", "method": "magic"},
])
def test_forecast_rejects_bad_input(client, body):
    assert client.post("/api/forecast", json=body).status_code == 400
