"""
Prediction and URL-reputation caches.

All public functions are thread-safe — safe to call from asyncio.to_thread
workers as well as the main event loop.
"""
import hashlib
import threading
from cachetools import TTLCache

# ── Prediction cache ───────────────────────────────────────────────────────
# Keyed by SHA-256(normalised text).  TTL=1h so stale scam intel rotates out.
_predict_cache: TTLCache = TTLCache(maxsize=10_000, ttl=3_600)
_predict_lock  = threading.Lock()

# ── URL reputation cache ───────────────────────────────────────────────────
# Keyed by URL string. 24h TTL — domain reputation doesn't change by the minute.
_url_cache: TTLCache = TTLCache(maxsize=50_000, ttl=86_400)
_url_lock   = threading.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────

def _text_key(text: str) -> str:
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()


# ── Prediction cache API ────────────────────────────────────────────────────

def get_prediction(text: str) -> dict | None:
    with _predict_lock:
        return _predict_cache.get(_text_key(text))


def set_prediction(text: str, result: dict) -> None:
    with _predict_lock:
        _predict_cache[_text_key(text)] = result


# ── URL reputation cache API ────────────────────────────────────────────────

def get_url_rep(url: str) -> tuple | None:
    """Returns (gsb_flagged, threat_type, vt_malicious, vt_suspicious) or None."""
    with _url_lock:
        return _url_cache.get(url)


def set_url_rep(url: str, value: tuple) -> None:
    with _url_lock:
        _url_cache[url] = value


# ── Stats ──────────────────────────────────────────────────────────────────

def cache_info() -> dict:
    with _predict_lock, _url_lock:
        return {
            'predict_cached':  len(_predict_cache),
            'predict_maxsize': _predict_cache.maxsize,
            'predict_ttl_s':   _predict_cache.ttl,
            'url_cached':      len(_url_cache),
            'url_maxsize':     _url_cache.maxsize,
            'url_ttl_s':       _url_cache.ttl,
        }
