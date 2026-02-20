"""
api/shifts.py — detects and persists significant probability shifts.
A "shift" is when any market outcome moves >= SHIFT_THRESHOLD points in one refresh cycle.
"""
import os
import json
from datetime import datetime
from api.logger import get_logger
from api.store import _read, _write
import config

log = get_logger("shifts")

SHIFT_THRESHOLD = float(os.getenv("SHIFT_THRESHOLD", "5"))   # points
SHIFTS_FILE     = os.path.join(config.DATA_DIR, "shifts.json")
MAX_SHIFTS      = 100   # rolling window


def detect_shifts(all_markets: list[dict]) -> list[dict]:
    """
    Scan markets (which already have delta values from context.py) for big moves.
    Returns list of new shift events detected this cycle.
    """
    new_shifts = []
    now = datetime.now().isoformat()

    for m in all_markets:
        for p in m.get("pairs", []):
            delta = p.get("delta")
            if delta is None:
                continue
            if abs(delta) >= SHIFT_THRESHOLD:
                direction = "up" if delta > 0 else "down"
                shift = {
                    "timestamp":  now,
                    "market":     m.get("question", ""),
                    "slug":       m.get("slug", ""),
                    "source":     m.get("source", ""),
                    "label":      p["label"],
                    "prob":       p["prob"],
                    "delta":      delta,
                    "direction":  direction,
                }
                log.warning(
                    "SHIFT DETECTED: %s | %s %s%.1f%% → %.1f%%",
                    m["question"], p["label"], "▲" if delta > 0 else "▼",
                    abs(delta), p["prob"]
                )
                new_shifts.append(shift)

    if new_shifts:
        _persist_shifts(new_shifts)

    return new_shifts


def _persist_shifts(new_shifts: list[dict]) -> None:
    existing = _read(SHIFTS_FILE, default=[])
    combined = new_shifts + existing          # newest first
    combined = combined[:MAX_SHIFTS]          # rolling window
    _write(SHIFTS_FILE, combined)


def load_shifts(limit: int = 20) -> list[dict]:
    """Return most recent shift events."""
    return _read(SHIFTS_FILE, default=[])[:limit]


def clear_shifts() -> None:
    _write(SHIFTS_FILE, [])
