"""
api/news.py — NewsAPI integration.
"""
import requests
import config
from api.cache import TTLCache
from api.logger import get_logger

log   = get_logger("news")
cache = TTLCache(default_ttl=config.CACHE_TTL_SEC)


def _normalize(a: dict) -> dict:
    return {
        "title":       a.get("title", ""),
        "source":      a.get("source", {}).get("name", ""),
        "url":         a.get("url", ""),
        "publishedAt": (a.get("publishedAt") or "")[:10],
    }


def get_top_headlines(page_size: int = 10) -> list[dict]:
    if not config.NEWS_API_KEY:
        log.warning("NEWS_API_KEY not set — skipping headlines")
        return []

    key = f"headlines_{page_size}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{config.NEWS_API}/top-headlines",
            params={"country": "us", "pageSize": page_size, "apiKey": config.NEWS_API_KEY},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = [_normalize(a) for a in r.json().get("articles", [])]
        cache.set(key, result)
        log.info("News: fetched %d headlines", len(result))
        return result
    except Exception as e:
        log.error("Headlines fetch failed: %s", e)
        return []


def search_news(query: str, page_size: int = 6) -> list[dict]:
    if not config.NEWS_API_KEY:
        log.warning("NEWS_API_KEY not set — skipping news search")
        return []

    key = f"news_search_{query}_{page_size}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{config.NEWS_API}/everything",
            params={"q": query, "pageSize": page_size,
                    "sortBy": "publishedAt", "apiKey": config.NEWS_API_KEY},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = [_normalize(a) for a in r.json().get("articles", [])]
        cache.set(key, result)
        log.info("News: search '%s' → %d results", query, len(result))
        return result
    except Exception as e:
        log.error("News search failed ('%s'): %s", query, e)
        return []
