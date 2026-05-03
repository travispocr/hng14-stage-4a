#!/usr/bin/env python3
"""
SwiftDeploy API Service
Supports stable and canary modes via MODE env var.
"""

import os
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, g

app = Flask(__name__)

# ── Config from environment ───────────────────────────────────
MODE        = os.environ.get("MODE", "stable").lower()
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT    = int(os.environ.get("APP_PORT", 3000))
START_TIME  = time.time()

# ── Chaos state (canary only) ─────────────────────────────────
chaos_lock  = threading.Lock()
chaos_state = {"mode": None, "duration": None, "rate": None}


def apply_chaos():
    """Apply active chaos before handling a request. Returns error response or None."""
    with chaos_lock:
        state = chaos_state.copy()

    if state["mode"] == "slow":
        time.sleep(state["duration"] or 1)

    elif state["mode"] == "error":
        rate = state["rate"] or 0.5
        if random.random() < rate:
            return jsonify({"error": "chaos-induced error", "mode": "error"}), 500

    return None


def add_mode_header(response):
    """Add X-Mode: canary header on every response in canary mode."""
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    return response


app.after_request(add_mode_header)


# ── Routes ────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    if MODE == "canary":
        err = apply_chaos()
        if err:
            return err

    return jsonify({
        "message": f"Welcome to SwiftDeploy API",
        "mode": MODE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": "hngstage4a"
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)

@app.route("/api", methods=["GET"])
def api():
    return jsonify({
        "message": "HNGI14 Stage 0",
        "track": "DevOps",
        "username": "hngstage4a"
    }), 200
