"""
api/health.py — checks status of Ollama, API keys, and data freshness.
"""
import requests
import ollama
import config
from api.logger import get_logger

log = get_logger("health")


def check_ollama() -> dict:
    try:
        models = ollama.list()
        names  = [m["name"] for m in models.get("models", [])]
        model_available = any(config.OLLAMA_MODEL in n for n in names)
        return {
            "ok":              True,
            "model":           config.OLLAMA_MODEL,
            "model_available": model_available,
            "available_models": names,
        }
    except Exception as e:
        log.warning("Ollama health check failed: %s", e)
        return {"ok": False, "error": str(e)}


def check_news_api() -> dict:
    if not config.NEWS_API_KEY:
        return {"ok": False, "error": "NEWS_API_KEY not set"}
    try:
        r = requests.get(
            f"{config.NEWS_API}/top-headlines",
            params={"country": "us", "pageSize": 1, "apiKey": config.NEWS_API_KEY},
            timeout=5,
        )
        if r.status_code == 200:
            return {"ok": True}
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        log.warning("NewsAPI health check failed: %s", e)
        return {"ok": False, "error": str(e)}


def check_polymarket() -> dict:
    try:
        r = requests.get(
            f"{config.POLYMARKET_API}/markets",
            params={"limit": 1, "active": True},
            timeout=5,
        )
        return {"ok": r.status_code == 200}
    except Exception as e:
        log.warning("Polymarket health check failed: %s", e)
        return {"ok": False, "error": str(e)}


def check_kalshi() -> dict:
    try:
        h = {"accept": "application/json"}
        if config.KALSHI_API_KEY:
            h["Authorization"] = f"Bearer {config.KALSHI_API_KEY}"
        r = requests.get(
            f"{config.KALSHI_API}/markets",
            params={"limit": 1, "status": "open"},
            headers=h, timeout=5,
        )
        return {"ok": r.status_code in (200, 401),   # 401 = reachable but unauthed
                "authenticated": bool(config.KALSHI_API_KEY)}
    except Exception as e:
        log.warning("Kalshi health check failed: %s", e)
        return {"ok": False, "error": str(e)}


def full_health() -> dict:
    return {
        "ollama":     check_ollama(),
        "news_api":   check_news_api(),
        "polymarket": check_polymarket(),
        "kalshi":     check_kalshi(),
    }
