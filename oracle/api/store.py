"""
api/store.py — persistent JSON storage for history, alerts, and watchlist.
All file I/O lives here so the rest of the app never touches disk directly.
"""
import json
import os
import time
from datetime import datetime
from typing import Any

import config
from api.logger import get_logger

log = get_logger("store")


# ── Generic helpers ───────────────────────────────────────────────────────────

def _read(path: str, default: Any = None) -> Any:
    if default is None:
        default = []
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        log.error("Failed to read %s: %s", path, e)
        return default


def _write(path: str, data: Any) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error("Failed to write %s: %s", path, e)


# ── Chat history ──────────────────────────────────────────────────────────────

def load_history() -> list[dict]:
    return _read(config.HISTORY_FILE, default=[])


def save_history(history: list[dict]) -> None:
    # Trim to keep the last MAX_HISTORY_MSGS messages (preserve whole exchanges)
    if len(history) > config.MAX_HISTORY_MSGS:
        trimmed = history[-config.MAX_HISTORY_MSGS:]
        log.info(
            "History trimmed from %d to %d messages",
            len(history), len(trimmed)
        )
        history = trimmed
    _write(config.HISTORY_FILE, history)


def clear_history() -> None:
    _write(config.HISTORY_FILE, [])
    log.info("Chat history cleared")


def export_history_markdown() -> str:
    """Return the full conversation as a markdown string."""
    history = load_history()
    if not history:
        return "_No conversation history._"
    lines = [f"# ORACLE Chat Export\n_{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"]
    for msg in history:
        role  = "**You**" if msg["role"] == "user" else "**ORACLE**"
        lines.append(f"{role}\n\n{msg['content']}\n\n---\n")
    return "\n".join(lines)


# ── Alerts ────────────────────────────────────────────────────────────────────

def load_alerts() -> list[dict]:
    return _read(config.ALERTS_FILE, default=[])


def save_alerts(alerts: list[dict]) -> None:
    _write(config.ALERTS_FILE, alerts)


def add_alert(slug: str, label: str, threshold: float, direction: str) -> dict:
    alerts = load_alerts()
    alert = {
        "id":        str(int(time.time() * 1000)),
        "slug":      slug,
        "label":     label,
        "threshold": threshold,
        "direction": direction,
        "fired":     False,
        "created":   datetime.now().isoformat(),
    }
    alerts.append(alert)
    save_alerts(alerts)
    log.info("Alert added: %s %s %s %.1f%%", slug, label, direction, threshold)
    return alert


def delete_alert(alert_id: str) -> None:
    alerts = [a for a in load_alerts() if a.get("id") != alert_id]
    save_alerts(alerts)
    log.info("Alert deleted: %s", alert_id)


def check_alerts(all_markets: list[dict]) -> list[dict]:
    """Check all active alerts against current market data. Returns fired list."""
    alerts  = load_alerts()
    fired   = []
    updated = False

    for alert in alerts:
        if alert.get("fired"):
            continue
        slug      = alert.get("slug", "").lower()
        label     = alert.get("label", "").lower()
        thresh    = float(alert.get("threshold", 0))
        direction = alert.get("direction", "above")

        for m in all_markets:
            market_slug = (m.get("slug") or m.get("question") or "").lower()
            if slug and slug not in market_slug:
                continue
            for p in m.get("pairs", []):
                if label and label.lower() not in p["label"].lower():
                    continue
                prob = p["prob"]
                hit  = (direction == "above" and prob >= thresh) or \
                       (direction == "below" and prob <= thresh)
                if hit:
                    log.warning(
                        "ALERT FIRED: %s | %s | %.1f%% (threshold %s %.1f%%)",
                        m["question"], p["label"], prob, direction, thresh
                    )
                    alert["fired"] = True
                    updated = True
                    fired.append({**alert, "current_prob": prob, "market": m["question"]})

    if updated:
        save_alerts(alerts)

    return fired


# ── Watchlist ─────────────────────────────────────────────────────────────────

def load_watchlist() -> list[dict]:
    return _read(config.WATCHLIST_FILE, default=[])


def save_watchlist(watchlist: list[dict]) -> None:
    _write(config.WATCHLIST_FILE, watchlist)


def add_to_watchlist(slug: str, question: str, source: str) -> dict:
    wl = load_watchlist()
    # Deduplicate by slug
    if any(w["slug"] == slug for w in wl):
        log.debug("Watchlist: %s already pinned", slug)
        return next(w for w in wl if w["slug"] == slug)
    entry = {"slug": slug, "question": question, "source": source,
             "pinned_at": datetime.now().isoformat()}
    wl.append(entry)
    save_watchlist(wl)
    log.info("Watchlist: pinned %s (%s)", slug, source)
    return entry


def remove_from_watchlist(slug: str) -> None:
    wl = [w for w in load_watchlist() if w["slug"] != slug]
    save_watchlist(wl)
    log.info("Watchlist: unpinned %s", slug)
