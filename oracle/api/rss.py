"""
api/rss.py — RSS feed aggregator for high-signal news sources.
No API key needed. Replaces Twitter as a real-time breaking news signal.
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

import requests
from api.cache import TTLCache
from api.logger import get_logger
import config

log   = get_logger("rss")
cache = TTLCache(default_ttl=config.CACHE_TTL_SEC)

# Curated high-signal RSS feeds — fast, authoritative, low-noise
FEEDS = {
    "Reuters":        "https://feeds.reuters.com/reuters/topNews",
    "AP News":        "https://feeds.apnews.com/rss/apf-topnews",
    "Politico":       "https://rss.politico.com/politics-news.xml",
    "The Hill":       "https://thehill.com/news/feed/",
    "FT":             "https://www.ft.com/rss/home/us",
    "Axios":          "https://api.axios.com/feed/",
    "BBC":            "https://feeds.bbci.co.uk/news/world/rss.xml",
}


def _parse_date(raw: str) -> str:
    """Parse RSS date string to ISO format, return raw on failure."""
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw[:16] if raw else ""


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_feed(name: str, url: str, limit: int) -> list[dict]:
    key = f"rss_{name}_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(url, timeout=config.HTTP_TIMEOUT,
                         headers={"User-Agent": "ORACLE/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)

        # Handle both RSS <item> and Atom <entry>
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        results = []
        for item in items[:limit]:
            def t(tag):
                el = item.find(tag) or item.find(f"atom:{tag}", ns)
                return el.text if el is not None else ""

            link = t("link")
            # Atom feeds sometimes store link in href attribute
            if not link:
                el = item.find("atom:link", ns)
                link = el.get("href", "") if el is not None else ""

            results.append({
                "title":       _strip_tags(t("title")),
                "source":      name,
                "url":         link,
                "publishedAt": _parse_date(t("pubDate") or t("published") or t("updated")),
            })

        cache.set(key, results)
        log.info("RSS %s: fetched %d items", name, len(results))
        return results
    except Exception as e:
        log.error("RSS %s fetch failed: %s", name, e)
        return []


def get_all_feeds(limit_each: int = 4) -> list[dict]:
    """Fetch all configured feeds in parallel and merge by date."""
    with ThreadPoolExecutor(max_workers=len(FEEDS)) as ex:
        futures = {ex.submit(_fetch_feed, name, url, limit_each): name
                   for name, url in FEEDS.items()}
        all_items = []
        for f in futures:
            all_items.extend(f.result())

    # Sort by date descending (ISO strings sort correctly)
    all_items.sort(key=lambda x: x["publishedAt"], reverse=True)
    return all_items


def search_feeds(query: str, limit_each: int = 4) -> list[dict]:
    """Fetch all feeds and filter items matching the query."""
    q = query.lower()
    all_items = get_all_feeds(limit_each)
    matched = [i for i in all_items if q in i["title"].lower()]
    return matched or all_items  # fallback to all if no match
