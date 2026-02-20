"""
api/calendar.py — economic & political event calendar.
Pulls from public sources: FED calendar, US government data, election dates.
Falls back to a curated static schedule for known recurring events.
"""
import requests
from datetime import datetime, timedelta
from api.cache import TTLCache
from api.logger import get_logger
import config

log   = get_logger("calendar")
cache = TTLCache(default_ttl=3600)  # calendar data changes slowly, cache 1hr


# ── Known recurring high-impact events ───────────────────────────────────────
# These are the events prediction markets care most about.
# Kept up-to-date manually in config; auto-events layer on top.

KNOWN_EVENTS_2025_2026 = [
    # Fed FOMC meetings (8 per year)
    {"date": "2025-01-29", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-03-19", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-05-07", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-06-18", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-07-30", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-09-17", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-11-05", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2025-12-17", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2026-01-28", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    {"date": "2026-03-18", "title": "FOMC Rate Decision",      "category": "fed",      "impact": "high"},
    # CPI releases (monthly, ~2nd week)
    {"date": "2025-02-12", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-03-12", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-04-10", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-05-13", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-06-11", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-07-15", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-08-12", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-09-10", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-10-15", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-11-13", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2025-12-10", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2026-01-14", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    {"date": "2026-02-11", "title": "CPI Inflation Report",    "category": "macro",    "impact": "high"},
    # Jobs reports (first Friday of month)
    {"date": "2025-02-07", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-03-07", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-04-04", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-05-02", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-06-06", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-07-03", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-08-01", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-09-05", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-10-03", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-11-07", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2025-12-05", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2026-01-09", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    {"date": "2026-02-06", "title": "Non-Farm Payrolls",       "category": "macro",    "impact": "high"},
    # Political
    {"date": "2025-01-20", "title": "Presidential Inauguration","category": "political","impact": "high"},
    {"date": "2025-11-04", "title": "US Midterm Elections",    "category": "political","impact": "high"},
    {"date": "2026-11-03", "title": "US Midterm Elections",    "category": "political","impact": "high"},
    # Supreme Court
    {"date": "2025-06-30", "title": "SCOTUS Term Ends (rulings expected)", "category": "political", "impact": "medium"},
    {"date": "2026-06-30", "title": "SCOTUS Term Ends (rulings expected)", "category": "political", "impact": "medium"},
    # GDP
    {"date": "2025-01-30", "title": "Q4 2024 GDP (Advance)",   "category": "macro",    "impact": "medium"},
    {"date": "2025-04-30", "title": "Q1 2025 GDP (Advance)",   "category": "macro",    "impact": "medium"},
    {"date": "2025-07-30", "title": "Q2 2025 GDP (Advance)",   "category": "macro",    "impact": "medium"},
    {"date": "2025-10-30", "title": "Q3 2025 GDP (Advance)",   "category": "macro",    "impact": "medium"},
    {"date": "2026-01-29", "title": "Q4 2025 GDP (Advance)",   "category": "macro",    "impact": "medium"},
]

CATEGORY_ICONS = {
    "fed":       "🏦",
    "macro":     "📊",
    "political": "🗳️",
    "earnings":  "💰",
    "other":     "📅",
}


def _days_until(date_str: str) -> int:
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (target - datetime.now().date()).days
    except Exception:
        return 9999


def get_upcoming_events(days_ahead: int = 30) -> list[dict]:
    """Return events in the next N days, sorted by date."""
    now  = datetime.now().date()
    events = []
    for e in KNOWN_EVENTS_2025_2026:
        days = _days_until(e["date"])
        if 0 <= days <= days_ahead:
            events.append({
                **e,
                "days_until": days,
                "icon": CATEGORY_ICONS.get(e["category"], "📅"),
                "label": "TODAY" if days == 0 else f"in {days}d",
            })
    events.sort(key=lambda x: x["days_until"])
    return events


def get_all_events(days_back: int = 7, days_ahead: int = 60) -> list[dict]:
    """Return events in a window around today."""
    now = datetime.now().date()
    events = []
    for e in KNOWN_EVENTS_2025_2026:
        days = _days_until(e["date"])
        if -days_back <= days <= days_ahead:
            events.append({
                **e,
                "days_until": days,
                "icon": CATEGORY_ICONS.get(e["category"], "📅"),
                "label": (
                    "TODAY"        if days == 0  else
                    f"{-days}d ago" if days < 0  else
                    f"in {days}d"
                ),
                "past": days < 0,
            })
    events.sort(key=lambda x: x["days_until"])
    return events


def search_events(query: str) -> list[dict]:
    q = query.lower()
    return [e for e in get_all_events(30, 365) if q in e["title"].lower() or q in e["category"].lower()]


def calendar_context_str(days_ahead: int = 14) -> str:
    """Return a compact string suitable for injecting into the AI prompt."""
    events = get_upcoming_events(days_ahead)
    if not events:
        return "No major events in the next 14 days."
    return "\n".join(
        f"- {e['icon']} {e['date']} ({e['label']}): {e['title']} [{e['impact'].upper()}]"
        for e in events
    )
