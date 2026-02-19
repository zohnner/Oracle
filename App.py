from flask import Flask, request, jsonify, send_from_directory
import ollama
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
import threading

load_dotenv()

app = Flask(__name__, static_folder="static")

MODEL = "llama3.1:8b"
HISTORY_FILE = "chat_history.json"
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
POLYMARKET_API = "https://gamma-api.polymarket.com"

_context_cache = {"prompt": None, "markets": [], "headlines": [], "last_updated": None}
_context_lock = threading.Lock()


# ── Polymarket ────────────────────────────────────────────────────────────────

def get_polymarket_top(limit=10):
    try:
        resp = requests.get(
            f"{POLYMARKET_API}/markets",
            params={"limit": limit, "order": "volume24hr", "ascending": False, "active": True},
            timeout=8
        )
        markets = resp.json()
        results = []
        for m in markets:
            outcomes = m.get("outcomes", "[]")
            if isinstance(outcomes, str):
                try: outcomes = json.loads(outcomes)
                except: outcomes = []
            prices = m.get("outcomePrices", "[]")
            if isinstance(prices, str):
                try: prices = json.loads(prices)
                except: prices = []

            pairs = []
            if outcomes and prices:
                pairs = [{"label": o, "prob": round(float(p) * 100, 1)} for o, p in zip(outcomes, prices)]

            results.append({
                "question": m.get("question", "N/A"),
                "volume24h": float(m.get("volume24hr", 0)),
                "pairs": pairs,
                "slug": m.get("slug", ""),
            })
        return results
    except Exception as e:
        return []


def search_polymarket(query, limit=5):
    try:
        resp = requests.get(
            f"{POLYMARKET_API}/markets",
            params={"limit": limit, "q": query, "active": True},
            timeout=8
        )
        markets = resp.json()
        results = []
        for m in markets:
            outcomes = m.get("outcomes", "[]")
            if isinstance(outcomes, str):
                try: outcomes = json.loads(outcomes)
                except: outcomes = []
            prices = m.get("outcomePrices", "[]")
            if isinstance(prices, str):
                try: prices = json.loads(prices)
                except: prices = []

            pairs = []
            if outcomes and prices:
                pairs = [{"label": o, "prob": round(float(p) * 100, 1)} for o, p in zip(outcomes, prices)]

            results.append({
                "question": m.get("question", "N/A"),
                "volume24h": float(m.get("volume24hr", 0)),
                "pairs": pairs,
                "slug": m.get("slug", ""),
            })
        return results
    except Exception as e:
        return []


# ── News ──────────────────────────────────────────────────────────────────────

def get_top_headlines():
    try:
        resp = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"country": "us", "pageSize": 8, "apiKey": NEWS_API_KEY},
            timeout=8
        )
        data = resp.json()
        articles = data.get("articles", [])
        return [{"title": a["title"], "source": a["source"]["name"],
                 "url": a["url"], "publishedAt": a.get("publishedAt", "")[:10]} for a in articles]
    except:
        return []


def search_news(query):
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "pageSize": 6, "sortBy": "publishedAt", "apiKey": NEWS_API_KEY},
            timeout=8
        )
        data = resp.json()
        articles = data.get("articles", [])
        return [{"title": a["title"], "source": a["source"]["name"],
                 "url": a["url"], "publishedAt": a.get("publishedAt", "")[:10]} for a in articles]
    except:
        return []


# ── Context ───────────────────────────────────────────────────────────────────

def build_context():
    headlines = get_top_headlines()
    markets = get_polymarket_top(8)
    now = datetime.now().strftime("%A, %B %d %Y %H:%M")

    headlines_str = "\n".join([f"- {h['title']} ({h['source']})" for h in headlines]) or "Unavailable"
    markets_str = "\n".join([
        f"- {m['question']}\n  " + " | ".join([f"{p['label']}: {p['prob']}%" for p in m['pairs']]) + f" | 24h Vol: ${m['volume24h']:,.0f}"
        for m in markets
    ]) or "Unavailable"

    prompt = f"""You are a sharp, well-informed personal assistant with real-time awareness of current events and prediction markets. Be concise, direct, and analytical.

Today is {now}.

## Top Headlines Right Now
{headlines_str}

## Top Polymarket Markets (by 24h volume)
{markets_str}

Use this live data to inform your answers. If asked about something not in the data, say so and offer to search."""

    with _context_lock:
        _context_cache["prompt"] = prompt
        _context_cache["markets"] = markets
        _context_cache["headlines"] = headlines
        _context_cache["last_updated"] = datetime.now().isoformat()

    return prompt, markets, headlines


# ── History ───────────────────────────────────────────────────────────────────

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/init", methods=["GET"])
def api_init():
    prompt, markets, headlines = build_context()
    history = load_history()
    return jsonify({
        "markets": markets,
        "headlines": headlines,
        "history": history,
        "last_updated": _context_cache["last_updated"]
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    prompt, markets, headlines = build_context()
    return jsonify({
        "markets": markets,
        "headlines": headlines,
        "last_updated": _context_cache["last_updated"]
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json
    user_input = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    with _context_lock:
        system_prompt = _context_cache.get("prompt") or build_context()[0]

    history.append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        response = ollama.chat(model=MODEL, messages=messages)
        reply = response["message"]["content"]
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    history.append({"role": "assistant", "content": reply})
    save_history(history)

    return jsonify({"reply": reply, "history": history})


@app.route("/api/markets", methods=["GET"])
def api_markets():
    q = request.args.get("q", "").strip()
    if q:
        return jsonify(search_polymarket(q))
    return jsonify(get_polymarket_top(12))


@app.route("/api/news", methods=["GET"])
def api_news():
    q = request.args.get("q", "").strip()
    if q:
        return jsonify(search_news(q))
    return jsonify(get_top_headlines())


@app.route("/api/clear", methods=["POST"])
def api_clear():
    save_history([])
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("⏳ Building initial context...")
    build_context()
    print("✅ Ready! Open http://localhost:5000")
    app.run(debug=False, port=5000)