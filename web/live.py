"""Live backend: proxies to the Lambda functions behind API Gateway."""
import os
from datetime import date, timedelta

import requests


class UpstreamError(RuntimeError):
    """The AWS backend is missing, unreachable, or returned something unusable."""


def _post(url_env, path, payload):
    base = os.getenv(url_env, "").rstrip("/")
    if not base:
        raise UpstreamError(f"{url_env} is not configured")
    try:
        resp = requests.post(
            f"{base}{path}", json=payload, timeout=float(os.getenv("REQUEST_TIMEOUT", "10")),
            headers={"x-api-key": os.getenv("API_GATEWAY_KEY", ""), "Content-Type": "application/json"},
        )
    except requests.RequestException as exc:
        raise UpstreamError("Backend unreachable") from exc
    if resp.status_code != 200:
        raise UpstreamError(f"Backend returned HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise UpstreamError("Backend returned invalid JSON") from exc


def predict(user_id, content_id, state):
    return _post("PREDICTION_API_URL", "/predict",
                 {"user_id": user_id, "content_id": content_id, "context": {"user_state": state}})


def forecast(content_id, periods, method):
    res = _post("FORECAST_API_URL", "/forecast",
                {"content_id": content_id, "periods": periods, "method": method})
    try:
        values = [round(v) for v in res["forecast"]]
        summ = res["summary"]
        band = 1.28 * summ.get("std_deviation", 0)
        start = date.today() + timedelta(days=1)
        dates = res.get("forecast_dates") or [(start + timedelta(days=k)).isoformat() for k in range(len(values))]
        return {
            "method": res.get("method", method),
            "forecast": {"dates": dates, "values": values,
                         "lower": [max(0, round(v - band)) for v in values],
                         "upper": [round(v + band) for v in values]},
            "summary": {"total": round(summ["total_forecast"]), "average": round(summ["average_daily"]),
                        "min": round(summ["min_daily"]), "max": round(summ["max_daily"])},
        }
    except (KeyError, TypeError) as exc:
        raise UpstreamError("Unexpected backend response") from exc
