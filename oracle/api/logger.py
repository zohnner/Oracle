"""
api/logger.py — shared logger for the whole application.
Writes to both the console and data/oracle.log.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from config import LOG_FILE, DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)

_fmt = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # avoid adding duplicate handlers on reload
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Console handler (INFO+) ──────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(_fmt)
    logger.addHandler(ch)

    # ── Rotating file handler (DEBUG+, 2 MB × 3 files) ──────────────────────
    fh = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_fmt)
    logger.addHandler(fh)

    return logger
