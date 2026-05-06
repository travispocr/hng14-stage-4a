#!/usr/bin/env python3
"""
SwiftDeploy API Service
Supports stable and canary modes via MODE env var.
Exposes /metrics in Prometheus text format.
"""

import os
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# ── Config from environment ───────────────────────────────────
MODE        = os.environ.get("MODE", "stable").lower()
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT    = int(os.environ.get("APP_PORT", 3000))
START_TIME  = time.time()

# ── Chaos state (canary only) ─────────────────────────────────
chaos_lock  = threading.Lock()
chaos_state = {"mode": None, "duration": None, "rate": None}

# ── Metrics state ─────────────────────────────────────────────
metrics_lock = threading.Lock()

# http_requests_total{method, path, status_code}
request_counts = {}

# http_request_duration_seconds histogram
BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
duration_buckets = {}   # key=(method,path) -> {bucket: count}
duration_sum     = {}   # key=(method,path) -> float
duration_count   = {}   # key=(method,path) -> int


def record_request(method, path, status_code, duration):
    key_count = (method, path, str(status_code))
    hist_key  = (method, path)

    with metrics_lock:
        # Counter
        request_counts[key_count] = request_counts.get(key_count, 0) + 1

        # Histogram
        if hist_key not in duration_buckets:
            duration_buckets[hist_key] = {b: 0 for b in BUCKETS}
            duration_sum[hist_key]     = 0.0
            duration_count[hist_key]   = 0

        for b in BUCKETS:
            if duration <= b:
                duration_buckets[hist_key][b] += 1
        duration_sum[hist_key]   += duration
        duration_count[hist_key] += 1


# ── Request timing middleware ─────────────────────────────────
@app.before_request
def start_timer():
    request._start_time = time.time()


@app.after_request
def record_metrics(response):
    # Skip /metrics itself to avoid self-referential noise
    if request.path == "/metrics":
        return response
    duration = time.time() - getattr(request, "_start_time", time.time())
    record_request(request.method, request.path, response.status_code, duration)
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    return response


def apply_chaos():
    with chaos_lock:
        state = chaos_state.copy()
    if state["mode"] == "slow":
        time.sleep(state["duration"] or 1)
    elif state["mode"] == "error":
        rate = state["rate"] or 0.5
        if random.random() < rate:
            return jsonify({"error": "chaos-induced error", "mode": "error"}), 500
    return None


# ── Routes ────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    if MODE == "canary":
        err = apply_chaos()
        if err:
            return err
    return jsonify({
        "message": "Welcome to SwiftDeploy API",
        "mode": MODE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": "hngstage4b"
    }), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    uptime = round(time.time() - START_TIME, 2)
    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime,
        "mode": MODE,
        "version": APP_VERSION
    }), 200


@app.route("/api", methods=["GET"])
def api():
    return jsonify({
        "message": "HNGI14 Stage 4",
        "track": "DevOps",
        "username": "hngstage4b"
    }), 200


@app.route("/chaos", methods=["POST"])
def chaos():
    if MODE != "canary":
        return jsonify({
            "error": "chaos endpoint only available in canary mode",
            "current_mode": MODE
        }), 403

    body = request.get_json(silent=True) or {}
    chaos_mode = body.get("mode")

    if chaos_mode == "slow":
        duration = int(body.get("duration", 1))
        with chaos_lock:
            chaos_state.update({"mode": "slow", "duration": duration, "rate": None})
        return jsonify({"ok": True, "chaos": "slow", "duration": duration}), 200

    elif chaos_mode == "error":
        rate = float(body.get("rate", 0.5))
        with chaos_lock:
            chaos_state.update({"mode": "error", "rate": rate, "duration": None})
        return jsonify({"ok": True, "chaos": "error", "rate": rate}), 200

    elif chaos_mode == "recover":
        with chaos_lock:
            chaos_state.update({"mode": None, "duration": None, "rate": None})
        return jsonify({"ok": True, "chaos": "recovered"}), 200

    else:
        return jsonify({
            "error": "invalid chaos mode",
            "valid_modes": ["slow", "error", "recover"]
        }), 400


@app.route("/metrics", methods=["GET"])
def metrics():
    uptime = time.time() - START_TIME
    mode_val = 1 if MODE == "canary" else 0

    with chaos_lock:
        cs = chaos_state.copy()
    if cs["mode"] == "slow":
        chaos_val = 1
    elif cs["mode"] == "error":
        chaos_val = 2
    else:
        chaos_val = 0

    lines = []

    # ── app_uptime_seconds ────────────────────────────────────
    lines.append("# HELP app_uptime_seconds Time in seconds since app started")
    lines.append("# TYPE app_uptime_seconds gauge")
    lines.append(f"app_uptime_seconds {uptime:.3f}")

    # ── app_mode ─────────────────────────────────────────────
    lines.append("# HELP app_mode Current deployment mode (0=stable, 1=canary)")
    lines.append("# TYPE app_mode gauge")
    lines.append(f'app_mode {mode_val}')

    # ── chaos_active ─────────────────────────────────────────
    lines.append("# HELP chaos_active Active chaos mode (0=none, 1=slow, 2=error)")
    lines.append("# TYPE chaos_active gauge")
    lines.append(f"chaos_active {chaos_val}")

    # ── http_requests_total ───────────────────────────────────
    lines.append("# HELP http_requests_total Total HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    with metrics_lock:
        counts_snap    = dict(request_counts)
        buckets_snap   = {k: dict(v) for k, v in duration_buckets.items()}
        sum_snap       = dict(duration_sum)
        count_snap     = dict(duration_count)

    for (method, path, status_code), count in counts_snap.items():
        lines.append(
            f'http_requests_total{{method="{method}",path="{path}",status_code="{status_code}"}} {count}'
        )

    # ── http_request_duration_seconds ─────────────────────────
    lines.append("# HELP http_request_duration_seconds HTTP request latency histogram")
    lines.append("# TYPE http_request_duration_seconds histogram")
    for (method, path), bkts in buckets_snap.items():
        for le, count in bkts.items():
            lines.append(
                f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{le}"}} {count}'
            )
        lines.append(
            f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {count_snap.get((method,path),0)}'
        )
        lines.append(
            f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {sum_snap.get((method,path),0.0):.6f}'
        )
        lines.append(
            f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count_snap.get((method,path),0)}'
        )

    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)