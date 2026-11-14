"""Streamwise web app: the UI plus a small JSON API.

APP_MODE=demo (default) serves deterministic synthetic results.
APP_MODE=live proxies to the AWS Lambda backend through API Gateway.
"""
import logging
import os
import re
import time

from flask import Flask, g, jsonify, render_template, request

from . import demo, live

MODE = "live" if os.getenv("APP_MODE", "demo").lower() == "live" else "demo"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
STATES = ("browsing", "searching", "returning")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("streamwise")
app = Flask(__name__)


class BadRequest(ValueError):
    """Client sent invalid input (HTTP 400)."""


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Request body must be a JSON object")
    return data


def _ident(data, key):
    value = str(data.get(key, "")).strip()
    if not ID_RE.match(value):
        raise BadRequest(f"{key} must be 1-64 characters: letters, digits, _ or -")
    return value


@app.context_processor
def _inject():
    return {"mode": MODE}


@app.before_request
def _start_timer():
    g.t0 = time.perf_counter()


@app.after_request
def _finish(resp):
    ms = (time.perf_counter() - g.get("t0", time.perf_counter())) * 1000
    log.info("%s %s -> %s %.1fms", request.method, request.path, resp.status_code, ms)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.errorhandler(BadRequest)
def _bad_request(exc):
    return jsonify(error=str(exc)), 400


@app.errorhandler(live.UpstreamError)
def _upstream(exc):
    log.error("upstream failure: %s", exc)
    return jsonify(error=str(exc)), 502


@app.get("/")
def index():
    return render_template("index.html", page="home")


@app.get("/prediction")
def prediction():
    return render_template("prediction.html", page="prediction", states=STATES)


@app.get("/forecasting")
def forecasting():
    return render_template("forecasting.html", page="forecasting", methods=demo.METHODS)


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", mode=MODE)


@app.post("/api/predict")
def api_predict():
    data = _body()
    user_id, content_id = _ident(data, "user_id"), _ident(data, "content_id")
    ctx = data.get("context")
    state = ctx.get("user_state", "browsing") if isinstance(ctx, dict) else "browsing"
    if state not in STATES:
        raise BadRequest(f"user_state must be one of: {', '.join(STATES)}")
    backend = live if MODE == "live" else demo
    return jsonify({**backend.predict(user_id, content_id, state), "mode": MODE})


@app.post("/api/forecast")
def api_forecast():
    data = _body()
    content_id = _ident(data, "content_id")
    try:
        periods = int(data.get("periods", 30))
    except (TypeError, ValueError):
        raise BadRequest("periods must be an integer") from None
    if not 1 <= periods <= 365:
        raise BadRequest("periods must be between 1 and 365")
    method = data.get("method", "moving_average")
    if method not in demo.METHODS:
        raise BadRequest(f"method must be one of: {', '.join(demo.METHODS)}")
    backend = live if MODE == "live" else demo
    return jsonify({**backend.forecast(content_id, periods, method), "mode": MODE})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8000")),
            debug=os.getenv("FLASK_DEBUG") == "1")
