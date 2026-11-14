"""Deterministic synthetic backend, used when APP_MODE=demo (no AWS needed).

Same inputs always give the same outputs, so a demo deployment behaves
predictably and tests can assert on it.
"""
import hashlib
import math
import random
from datetime import date, timedelta
from statistics import mean, pstdev

METHODS = ("moving_average", "exponential_smoothing", "linear_trend", "seasonal")
FACTORS = (
    "frequent_streamer", "genre_affinity", "popular_title",
    "recent_activity", "premium_plan", "similar_users_completed",
)
_STATE_BOOST = {"browsing": 0.0, "searching": 0.05, "returning": 0.10}


def _rng(*parts):
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def predict(user_id, content_id, state="browsing"):
    rng = _rng("predict", user_id, content_id)
    score = min(rng.uniform(0.04, 0.97) + _STATE_BOOST.get(state, 0.0), 0.99)
    pct = round(score * 100, 1)
    gap = abs(pct - 50)
    if pct >= 60:
        rec = "Feature on the home row"
    elif pct >= 35:
        rec = "Add to the similar-titles shelf"
    else:
        rec = "Do not promote"
    return {
        "prediction_percentage": pct,
        "confidence": "high" if gap > 30 else "medium" if gap > 12 else "low",
        "factors": rng.sample(FACTORS, 3),
        "recommendation": rec,
    }


def _history(content_id, days=120):
    rng = _rng("history", content_id)
    base, trend = rng.uniform(40, 400), rng.uniform(-0.002, 0.006)
    amp, phase = rng.uniform(0.10, 0.35), rng.uniform(0, 2 * math.pi)
    return [
        max(0, round(base * (1 + trend * i)
                     * (1 + amp * math.sin(2 * math.pi * (i % 7) / 7 + phase))
                     * rng.uniform(0.9, 1.1)))
        for i in range(days)
    ]


def _project(hist, periods, method):
    n = len(hist)
    if method == "moving_average":
        return [mean(hist[-14:])] * periods
    if method == "exponential_smoothing":
        level = hist[0]
        for v in hist[1:]:
            level = 0.3 * v + 0.7 * level
        return [level] * periods
    if method == "linear_trend":
        ys = hist[-60:]
        xm, ym = (len(ys) - 1) / 2, mean(ys)
        slope = (sum((i - xm) * (y - ym) for i, y in enumerate(ys))
                 / sum((i - xm) ** 2 for i in range(len(ys))))
        return [ym + slope * (len(ys) - 1 - xm + k + 1) for k in range(periods)]
    return [mean(hist[n - 7 * w + (k % 7)] for w in range(1, 9)) for k in range(periods)]


def forecast(content_id, periods=30, method="moving_average"):
    hist = _history(content_id)
    sigma = pstdev(hist[-28:]) * 0.5
    values = [max(0.0, v) for v in _project(hist, periods, method)]
    start = date.today() + timedelta(days=1)
    spread = [1.28 * sigma * math.sqrt(1 + k / 7) for k in range(periods)]
    vals = [round(v) for v in values]
    return {
        "method": method,
        "forecast": {
            "dates": [(start + timedelta(days=k)).isoformat() for k in range(periods)],
            "values": vals,
            "lower": [max(0, round(v - s)) for v, s in zip(values, spread, strict=False)],
            "upper": [round(v + s) for v, s in zip(values, spread, strict=False)],
        },
        "summary": {"total": sum(vals), "average": round(mean(vals)),
                    "min": min(vals), "max": max(vals)},
    }
