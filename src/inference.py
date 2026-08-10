"""Deployed inference dispatcher.

Thin bridge between the FastAPI layer (`api/main.py`) and the actual
model loader / predictor in `src/e5_inference.py`. Exposes two functions
plus two URL-safety helpers.

  * `load_pipeline()`    — called once at API startup; returns a 6-tuple
                           whose first element is the loaded model bundle
                           and whose remaining five positions are `None`
                           (the deployed E8-P9 pipeline is a
                           self-contained bundle, so the extra positions
                           kept for backwards compatibility carry no
                           artifacts).
  * `predict_message()`  — called per request; forwards to `predict_e5`
                           after unpacking the bundle. Threshold defaults
                           to `config.E5_THRESHOLD` (0.59).
  * `is_all_trusted_domains(urls)` and
    `check_url_google_safebrowsing(url, api_key)` — URL-safety helpers
                           imported by `src/e5_inference.py` inside its
                           request-time code paths.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import E5_THRESHOLD, TRUSTED_DOMAINS


# ─── URL-safety helpers ──────────────────────────────────────────────────

def is_all_trusted_domains(urls: list) -> bool:
    """True iff every URL in the list resolves to an exact trusted domain
    or a real subdomain of one. Empty list returns False.

    Uses urlparse for hostname extraction; never uses substring matching.
    """
    if not urls:
        return False
    for url in urls:
        hostname = urlparse(url).netloc.lower().split(':')[0]
        if hostname.startswith('www.'):
            hostname = hostname[4:]
        matched = any(
            hostname == trusted or hostname.endswith('.' + trusted)
            for trusted in TRUSTED_DOMAINS
        )
        if not matched:
            return False
    return True


def check_url_google_safebrowsing(url: str, api_key: str):
    """Query the Google Safe Browsing v4 API for a single URL.

    Returns (flagged: bool, threat_type: str | None). If `api_key` is
    empty or the API errors, returns (False, None) — i.e. treated as
    clean rather than failing the request.
    """
    import requests

    if not api_key:
        return False, None
    endpoint = (
        f'https://safebrowsing.googleapis.com/v4/threatMatches:find'
        f'?key={api_key}'
    )
    payload = {
        'client': {'clientId': 'scamradar', 'clientVersion': '1.0'},
        'threatInfo': {
            'threatTypes': [
                'MALWARE', 'SOCIAL_ENGINEERING',
                'UNWANTED_SOFTWARE', 'POTENTIALLY_HARMFUL_APPLICATION',
            ],
            'platformTypes':    ['ANY_PLATFORM'],
            'threatEntryTypes': ['URL'],
            'threatEntries':    [{'url': url}],
        },
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'matches' in data:
                return True, data['matches'][0].get('threatType', 'THREAT')
        return False, None
    except Exception:
        return False, None


# ─── Bundle loader + predictor ───────────────────────────────────────────

from src.e5_inference import (                                # noqa: E402
    load_e5_pipeline as _load_e5_pipeline,
    predict_e5 as _predict_e5,
)


def load_pipeline():
    """Load the deployed model bundle.

    Returns `(model, None, None, None, None, None)` — a 6-tuple whose
    first element is the loaded classifier bundle and whose remaining
    positions are placeholders retained for the FastAPI layer's
    unpacking contract.
    """
    bundle = _load_e5_pipeline()
    return (bundle['model'], None, None, None, None, None)


def predict_message(text: str, model, tfidf=None, char_tfidf=None,
                    scaler=None, scam_idx=None, st_model=None,
                    threshold: float | None = None,
                    vt_api_key: str | None = None,
                    gsb_api_key: str | None = None,
                    **_ignored_kwargs) -> dict:
    """Predict a single message via the deployed pipeline.

    All positional arguments past `model` are accepted for backwards
    compatibility with the FastAPI layer and are ignored — the deployed
    bundle is self-contained.

    `threshold` defaults to `config.E5_THRESHOLD` (0.59).
    """
    pipe = {
        'model':     model,
        'threshold': float(threshold) if threshold is not None else float(E5_THRESHOLD),
    }
    return _predict_e5(
        text, pipe,
        threshold=pipe['threshold'],
        vt_api_key=vt_api_key,
        gsb_api_key=gsb_api_key,
    )
