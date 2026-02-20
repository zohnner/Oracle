"""
config.py — centralised configuration for ORACLE.
All env vars and constants live here; import from other modules.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Model ─────────────────────────────────────────────────────────────────────
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# ── API keys ──────────────────────────────────────────────────────────────────
NEWS_API_KEY     = os.getenv("NEWS_API_KEY", "")
KALSHI_API_KEY   = os.getenv("KALSHI_API_KEY", "")

# ── External API base URLs ────────────────────────────────────────────────────
POLYMARKET_API   = "https://gamma-api.polymarket.com"
KALSHI_API       = "https://api.elections.kalshi.com/trade-api/v2"
NEWS_API         = "https://newsapi.org/v2"

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR         = os.getenv("DATA_DIR", "data")
HISTORY_FILE     = os.path.join(DATA_DIR, "chat_history.json")
ALERTS_FILE      = os.path.join(DATA_DIR, "alerts.json")
WATCHLIST_FILE   = os.path.join(DATA_DIR, "watchlist.json")
LOG_FILE         = os.path.join(DATA_DIR, "oracle.log")

# ── Behaviour ─────────────────────────────────────────────────────────────────
AUTO_REFRESH_SEC = int(os.getenv("AUTO_REFRESH_SEC", "300"))   # background refresh
CACHE_TTL_SEC    = int(os.getenv("CACHE_TTL_SEC", "60"))       # min seconds between external calls
MAX_HISTORY_MSGS = int(os.getenv("MAX_HISTORY_MSGS", "100"))   # trim after this many messages
HTTP_TIMEOUT     = 8                                            # seconds per external request
