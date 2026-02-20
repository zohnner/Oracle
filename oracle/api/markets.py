"""
api/markets.py — Polymarket and Kalshi data fetching.
Returns normalised market dicts; all external I/O is isolated here.
"""
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import config
from api.cache import TTLCache
from api.logger import get_logger

log   = get_logger("markets")
cache = TTLCache(default_ttl=config.CACHE_TTL_SEC)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json_field(val, default=None):
    if default is None:
        default = []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            pass
    return default


def fmt_vol(v) -> str:
    v = float(v or 0)
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.1f}K"
    return f"${v:.0f}"


# ── Polymarket ────────────────────────────────────────────────────────────────

def _normalize_poly(m: dict) -> dict:
    outcomes = _parse_json_field(m.get("outcomes"))
    prices   = _parse_json_field(m.get("outcomePrices"))
    pairs = [
        {"label": o, "prob": round(float(p) * 100, 1)}
        for o, p in zip(outcomes, prices)
    ] if outcomes and prices else []
    return {
        "source":    "polymarket",
        "question":  m.get("question", "N/A"),
        "volume24h": float(m.get("volume24hr") or 0),
        "pairs":     pairs,
        "slug":      m.get("slug", ""),
        "id":        m.get("id", ""),
    }


def get_polymarket_top(limit: int = 12) -> list[dict]:
    key = f"poly_top_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{config.POLYMARKET_API}/markets",
            params={"limit": limit, "order": "volume24hr", "ascending": False, "active": True},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = [_normalize_poly(m) for m in r.json()]
        cache.set(key, result)
        log.info("Polymarket: fetched %d top markets", len(result))
        return result
    except Exception as e:
        log.error("Polymarket top fetch failed: %s", e)
        return []


def search_polymarket(query: str, limit: int = 6) -> list[dict]:
    key = f"poly_search_{query}_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{config.POLYMARKET_API}/markets",
            params={"limit": limit, "q": query, "active": True},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = [_normalize_poly(m) for m in r.json()]
        cache.set(key, result)
        log.info("Polymarket: search '%s' → %d results", query, len(result))
        return result
    except Exception as e:
        log.error("Polymarket search failed ('%s'): %s", query, e)
        return []


# ── Kalshi ────────────────────────────────────────────────────────────────────

def _kalshi_headers() -> dict:
    h = {"accept": "application/json"}
    if config.KALSHI_API_KEY:
        h["Authorization"] = f"Bearer {config.KALSHI_API_KEY}"
    return h


def _normalize_kalshi(m: dict) -> dict:
    yes_ask  = float(m.get("yes_ask")  or 0) * 100
    yes_bid  = float(m.get("yes_bid")  or 0) * 100
    yes_prob = round((yes_ask + yes_bid) / 2, 1) if (yes_ask or yes_bid) else None
    pairs = (
        [{"label": "Yes", "prob": yes_prob},
         {"label": "No",  "prob": round(100 - yes_prob, 1)}]
        if yes_prob is not None else []
    )
    return {
        "source":    "kalshi",
        "question":  m.get("title", m.get("question", "N/A")),
        "volume24h": float(m.get("volume") or 0),
        "pairs":     pairs,
        "slug":      m.get("ticker", ""),
        "id":        m.get("id", ""),
    }


def get_kalshi_top(limit: int = 8) -> list[dict]:
    key = f"kalshi_top_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{config.KALSHI_API}/markets",
            params={"limit": limit, "status": "open"},
            headers=_kalshi_headers(),
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = [_normalize_kalshi(m) for m in r.json().get("markets", [])]
        cache.set(key, result)
        log.info("Kalshi: fetched %d top markets", len(result))
        return result
    except Exception as e:
        log.error("Kalshi top fetch failed: %s", e)
        return []


def search_kalshi(query: str, limit: int = 5) -> list[dict]:
    key = f"kalshi_search_{query}_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{config.KALSHI_API}/markets",
            params={"limit": limit, "status": "open", "search": query},
            headers=_kalshi_headers(),
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = [_normalize_kalshi(m) for m in r.json().get("markets", [])]
        cache.set(key, result)
        log.info("Kalshi: search '%s' → %d results", query, len(result))
        return result
    except Exception as e:
        log.error("Kalshi search failed ('%s'): %s", query, e)
        return []


# ── Parallel fetch ────────────────────────────────────────────────────────────

def fetch_all_markets() -> tuple[list, list]:
    """Fetch Polymarket and Kalshi simultaneously. Returns (poly, kalshi)."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_poly   = ex.submit(get_polymarket_top, 12)
        f_kalshi = ex.submit(get_kalshi_top, 8)
        poly   = f_poly.result()
        kalshi = f_kalshi.result()
    return poly, kalshi
