"""
api/context.py — builds the AI system prompt from live data.
Maintains a background refresh thread and tracks odds movement for sparklines.
"""
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import config
from api.markets import fetch_all_markets, fmt_vol
from api.news import get_top_headlines
from api.rss import get_all_feeds
from api.calendar import calendar_context_str
from api.shifts import detect_shifts
from api.store import check_alerts, load_watchlist
from api.logger import get_logger

log = get_logger("context")

_ctx: dict = {
    "prompt":         None,
    "poly_markets":   [],
    "kalshi_markets": [],
    "headlines":      [],
    "rss_feed":       [],
    "fired_alerts":   [],
    "shifts":         [],
    "last_updated":   None,
    "prev_probs":     {},
}
_ctx_lock = threading.Lock()


def _attach_deltas(markets, prev_probs):
    for m in markets:
        slug = m.get("slug", "")
        prev = prev_probs.get(slug, {})
        for p in m.get("pairs", []):
            old = prev.get(p["label"])
            p["delta"] = round(p["prob"] - old, 1) if old is not None else None
    return markets


def _snapshot_probs(markets):
    snap = {}
    for m in markets:
        slug = m.get("slug", "")
        if slug:
            snap[slug] = {p["label"]: p["prob"] for p in m.get("pairs", [])}
    return snap


def _pin_watchlist(poly, kalshi):
    wl_slugs = {w["slug"] for w in load_watchlist()}
    if not wl_slugs:
        return poly, kalshi
    def reorder(mkts):
        pinned   = [m for m in mkts if m.get("slug") in wl_slugs]
        unpinned = [m for m in mkts if m.get("slug") not in wl_slugs]
        for m in pinned: m["pinned"] = True
        return pinned + unpinned
    return reorder(poly), reorder(kalshi)


def build_context():
    log.info("Building context...")
    t0 = time.monotonic()

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_markets   = ex.submit(fetch_all_markets)
        f_headlines = ex.submit(get_top_headlines, 8)
        f_rss       = ex.submit(get_all_feeds, 3)
        poly, kalshi = f_markets.result()
        headlines    = f_headlines.result()
        rss_feed     = f_rss.result()

    all_markets = poly + kalshi

    with _ctx_lock:
        prev = _ctx["prev_probs"].copy()

    poly   = _attach_deltas(poly,   prev)
    kalshi = _attach_deltas(kalshi, prev)
    shifts = detect_shifts(all_markets)
    poly, kalshi = _pin_watchlist(poly, kalshi)
    fired = check_alerts(all_markets)
    cal_str = calendar_context_str(days_ahead=14)

    now    = datetime.now().strftime("%A, %B %d %Y %H:%M")
    hl_str = "\n".join(f"- {h['title']} ({h['source']})" for h in headlines) or "Unavailable"
    mk_str = "\n".join(
        f"- [{m['source'].upper()}] {m['question']}\n  " +
        " | ".join(f"{p['label']}: {p['prob']}%" for p in m.get("pairs", [])) +
        f"  | 24h Vol: {fmt_vol(m['volume24h'])}"
        for m in all_markets
    ) or "Unavailable"

    shift_str = ""
    if shifts:
        shift_str = "\n\n## Significant Moves This Cycle\n" + "\n".join(
            f"- {'up' if s['direction']=='up' else 'down'} {s['market']} | "
            f"{s['label']}: {s['prob']}% ({'+' if s['delta']>0 else ''}{s['delta']}pts)"
            for s in shifts
        )

    prompt = (
        f"You are ORACLE — a sharp, analytical personal assistant with real-time "
        f"awareness of current events, Polymarket, Kalshi prediction markets, "
        f"Reddit sentiment, and the economic calendar. Be concise and data-driven.\n\n"
        f"Today is {now}.\n\n"
        f"## Upcoming High-Impact Events\n{cal_str}\n\n"
        f"## Top News Headlines\n{hl_str}\n\n"
        f"## Live Prediction Markets\n{mk_str}"
        f"{shift_str}\n\n"
        f"Ground your answers in this data. When asked about a market, consider "
        f"upcoming calendar events. Flag when something is not in context and offer to search."
    )

    elapsed = time.monotonic() - t0
    log.info("Context built in %.2fs — poly=%d kalshi=%d rss=%d shifts=%d",
             elapsed, len(poly), len(kalshi), len(rss_feed), len(shifts))

    with _ctx_lock:
        _ctx["prompt"]         = prompt
        _ctx["poly_markets"]   = poly
        _ctx["kalshi_markets"] = kalshi
        _ctx["headlines"]      = headlines
        _ctx["rss_feed"]       = rss_feed
        _ctx["fired_alerts"]   = fired
        _ctx["shifts"]         = shifts
        _ctx["last_updated"]   = datetime.now().isoformat()
        _ctx["prev_probs"]     = _snapshot_probs(all_markets)


def get_context():
    with _ctx_lock:
        return {
            "prompt":         _ctx["prompt"],
            "poly_markets":   list(_ctx["poly_markets"]),
            "kalshi_markets": list(_ctx["kalshi_markets"]),
            "headlines":      list(_ctx["headlines"]),
            "rss_feed":       list(_ctx["rss_feed"]),
            "fired_alerts":   list(_ctx["fired_alerts"]),
            "shifts":         list(_ctx["shifts"]),
            "last_updated":   _ctx["last_updated"],
        }


def _refresh_loop():
    while True:
        time.sleep(config.AUTO_REFRESH_SEC)
        try:
            build_context()
        except Exception as e:
            log.error("Background refresh failed: %s", e)


def start_background_refresh():
    t = threading.Thread(target=_refresh_loop, daemon=True, name="context-refresh")
    t.start()
    log.info("Background refresh started (every %ds)", config.AUTO_REFRESH_SEC)
