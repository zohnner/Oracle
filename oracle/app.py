"""
app.py — ORACLE Flask application. Thin routing layer only.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

import config
from api.context import build_context, get_context, start_background_refresh
from api.health import full_health
from api.logger import get_logger
from api.markets import search_polymarket, search_kalshi, get_polymarket_top, get_kalshi_top
from api.news import get_top_headlines, search_news
from api.reddit import get_multi_sub_feed, search_reddit, get_market_sentiment
from api.rss import get_all_feeds, search_feeds
from api.calendar import get_all_events, get_upcoming_events, search_events
from api.shifts import load_shifts
from api.store import (
    add_alert, add_to_watchlist, clear_history, delete_alert,
    export_history_markdown, load_alerts, load_history, load_watchlist,
    remove_from_watchlist, save_history,
)

log = get_logger("app")
app = Flask(__name__, static_folder="static")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/init")
def api_init():
    build_context()
    ctx = get_context()
    return jsonify({
        **ctx,
        "history":        load_history(),
        "alerts":         load_alerts(),
        "watchlist":      load_watchlist(),
        "shifts":         load_shifts(20),
        "upcoming_events": get_upcoming_events(30),
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    build_context()
    ctx = get_context()
    return jsonify({**ctx, "shifts": load_shifts(20)})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data       = request.json or {}
    user_input = (data.get("message") or "").strip()
    history    = data.get("history", [])
    do_stream  = data.get("stream", True)
    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    ctx        = get_context()
    sys_prompt = ctx["prompt"] or ""
    history.append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": sys_prompt}] + history
    log.info("Chat: %d chars, history_len=%d", len(user_input), len(history))

    if do_stream:
        def generate():
            full = ""
            try:
                for chunk in ollama.chat(model=config.OLLAMA_MODEL, messages=messages, stream=True):
                    token = chunk["message"]["content"]
                    full += token
                    yield f"data: {json.dumps({'token': token})}\n\n"
                history.append({"role": "assistant", "content": full})
                save_history(history)
                yield f"data: {json.dumps({'done': True, 'history': history})}\n\n"
            except Exception as e:
                log.error("Stream error: %s", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return Response(stream_with_context(generate()),
                        mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    try:
        resp  = ollama.chat(model=config.OLLAMA_MODEL, messages=messages)
        reply = resp["message"]["content"]
    except Exception as e:
        log.error("Chat error: %s", e)
        return jsonify({"error": str(e)}), 500

    history.append({"role": "assistant", "content": reply})
    save_history(history)
    return jsonify({"reply": reply, "history": history})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    clear_history()
    return jsonify({"ok": True})


@app.route("/api/export")
def api_export():
    md = export_history_markdown()
    return Response(md, mimetype="text/markdown",
                    headers={"Content-Disposition": "attachment; filename=oracle-chat.md"})


@app.route("/api/markets")
def api_markets():
    q      = (request.args.get("q") or "").strip()
    source = request.args.get("source", "all")
    poly, kalshi = [], []
    if source in ("poly", "all"):
        poly   = search_polymarket(q) if q else get_polymarket_top(12)
    if source in ("kalshi", "all"):
        kalshi = search_kalshi(q)     if q else get_kalshi_top(8)
    return jsonify({"poly": poly, "kalshi": kalshi})


@app.route("/api/news")
def api_news():
    q = (request.args.get("q") or "").strip()
    return jsonify(search_news(q) if q else get_top_headlines())


@app.route("/api/rss")
def api_rss():
    q = (request.args.get("q") or "").strip()
    return jsonify(search_feeds(q) if q else get_all_feeds(4))


@app.route("/api/reddit")
def api_reddit():
    q = (request.args.get("q") or "").strip()
    if q:
        return jsonify(search_reddit(q))
    return jsonify(get_multi_sub_feed())


@app.route("/api/reddit/sentiment")
def api_reddit_sentiment():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "q parameter required"}), 400
    return jsonify(get_market_sentiment(q))


@app.route("/api/calendar")
def api_calendar():
    q    = (request.args.get("q") or "").strip()
    days = int(request.args.get("days", 60))
    if q:
        return jsonify(search_events(q))
    return jsonify(get_all_events(days_back=7, days_ahead=days))


@app.route("/api/shifts")
def api_shifts():
    limit = int(request.args.get("limit", 20))
    return jsonify(load_shifts(limit))


# ── Rabbit Hole — multi-source briefing for a single market ──────────────────
@app.route("/api/rabbithole")
def api_rabbithole():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "q parameter required"}), 400

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_reddit   = ex.submit(get_market_sentiment, q)
        f_rss      = ex.submit(search_feeds, q, 4)
        f_calendar = ex.submit(search_events, q)
        f_news     = ex.submit(search_news, q)
        reddit   = f_reddit.result()
        rss      = f_rss.result()
        calendar = f_calendar.result()
        news     = f_news.result()

    return jsonify({
        "query":    q,
        "reddit":   reddit,
        "rss":      rss[:8],
        "calendar": calendar[:5],
        "news":     news[:6],
    })


@app.route("/api/alerts", methods=["GET"])
def api_get_alerts():
    return jsonify(load_alerts())


@app.route("/api/alerts", methods=["POST"])
def api_add_alert():
    d = request.json or {}
    if not all(k in d for k in ("slug", "label", "threshold", "direction")):
        return jsonify({"error": "Missing fields"}), 400
    try:
        threshold = float(d["threshold"])
    except (ValueError, TypeError):
        return jsonify({"error": "threshold must be a number"}), 400
    return jsonify(add_alert(d["slug"], d["label"], threshold, d["direction"])), 201


@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
def api_delete_alert(alert_id):
    delete_alert(alert_id)
    return jsonify({"ok": True})


@app.route("/api/watchlist", methods=["GET"])
def api_get_watchlist():
    return jsonify(load_watchlist())


@app.route("/api/watchlist", methods=["POST"])
def api_add_watchlist():
    d = request.json or {}
    if not d.get("slug"):
        return jsonify({"error": "slug required"}), 400
    return jsonify(add_to_watchlist(d["slug"], d.get("question", ""), d.get("source", ""))), 201


@app.route("/api/watchlist/<path:slug>", methods=["DELETE"])
def api_remove_watchlist(slug):
    remove_from_watchlist(slug)
    return jsonify({"ok": True})


@app.route("/api/health")
def api_health():
    return jsonify(full_health())


if __name__ == "__main__":
    os.makedirs(config.DATA_DIR, exist_ok=True)
    log.info("ORACLE starting...")
    build_context()
    start_background_refresh()
    log.info("Ready -> http://localhost:5000")
    app.run(debug=False, port=5000, threaded=True)
