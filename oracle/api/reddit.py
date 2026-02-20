"""
api/reddit.py — Reddit sentiment via the public JSON API (no auth required).
Fetches top posts from relevant subreddits and scores them for sentiment.
"""
import re
import requests
from api.cache import TTLCache
from api.logger import get_logger
import config

log   = get_logger("reddit")
cache = TTLCache(default_ttl=config.CACHE_TTL_SEC)

# High-signal subreddits for market/news research
DEFAULT_SUBS = [
    "politics", "worldnews", "Economics",
    "PredictIt", "PolymarketUsers", "investing",
]

HEADERS = {
    "User-Agent": "ORACLE/1.0 (local research tool)",
}


def _score_sentiment(text: str) -> str:
    """Naive keyword sentiment — good enough for a quick signal."""
    text = text.lower()
    pos = len(re.findall(
        r"\b(win|surge|rise|up|gain|likely|strong|positive|bullish|leads|ahead)\b", text
    ))
    neg = len(re.findall(
        r"\b(lose|fall|drop|down|crash|unlikely|weak|negative|bearish|behind|unlikely)\b", text
    ))
    if pos > neg:   return "bullish"
    if neg > pos:   return "bearish"
    return "neutral"


def _normalize_post(post: dict, sub: str) -> dict:
    d = post.get("data", {})
    title = d.get("title", "")
    return {
        "title":     title,
        "subreddit": d.get("subreddit", sub),
        "score":     d.get("score", 0),
        "comments":  d.get("num_comments", 0),
        "url":       "https://reddit.com" + d.get("permalink", ""),
        "sentiment": _score_sentiment(title + " " + d.get("selftext", "")[:200]),
        "created":   d.get("created_utc", 0),
    }


def get_subreddit_top(sub: str, limit: int = 5) -> list[dict]:
    key = f"reddit_{sub}_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"https://www.reddit.com/r/{sub}/hot.json",
            params={"limit": limit},
            headers=HEADERS,
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        posts = r.json().get("data", {}).get("children", [])
        result = [_normalize_post(p, sub) for p in posts]
        cache.set(key, result)
        log.info("Reddit r/%s: fetched %d posts", sub, len(result))
        return result
    except Exception as e:
        log.error("Reddit r/%s fetch failed: %s", sub, e)
        return []


def search_reddit(query: str, limit: int = 8) -> list[dict]:
    """Search Reddit across all subs for a topic."""
    key = f"reddit_search_{query}_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "hot", "limit": limit, "type": "link"},
            headers=HEADERS,
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        posts = r.json().get("data", {}).get("children", [])
        result = [_normalize_post(p, "search") for p in posts]
        cache.set(key, result)
        log.info("Reddit search '%s': %d results", query, len(result))
        return result
    except Exception as e:
        log.error("Reddit search failed ('%s'): %s", query, e)
        return []


def get_market_sentiment(market_question: str) -> dict:
    """
    Given a market question, extract keywords and search Reddit.
    Returns posts + an overall sentiment summary.
    """
    # Strip common filler words to get a clean search query
    stopwords = {"will", "the", "a", "an", "in", "of", "to", "be", "by", "or", "win", "who"}
    words  = [w for w in re.sub(r"[?']", "", market_question).split() if w.lower() not in stopwords]
    query  = " ".join(words[:5])
    posts  = search_reddit(query, limit=6)

    counts   = {"bullish": 0, "bearish": 0, "neutral": 0}
    for p in posts:
        counts[p["sentiment"]] += 1

    dominant = max(counts, key=lambda k: counts[k]) if posts else "neutral"
    return {
        "query":     query,
        "posts":     posts,
        "sentiment": dominant,
        "counts":    counts,
    }


def get_multi_sub_feed(subs: list[str] = None, limit_each: int = 3) -> list[dict]:
    """Fetch from multiple subreddits and merge by score."""
    subs   = subs or DEFAULT_SUBS
    all_posts = []
    for sub in subs:
        all_posts.extend(get_subreddit_top(sub, limit_each))
    all_posts.sort(key=lambda p: p["score"], reverse=True)
    return all_posts
