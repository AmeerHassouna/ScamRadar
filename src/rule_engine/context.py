"""RuleContext builder — parses URLs, hostnames, tone, and other pre-derived
signals into a single immutable object the rules read from.

Called once per prediction from `predict_e5` before the rule engine runs.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from src.rule_engine.base import RuleContext

# Regex used only inside context building
_STRIP_PORT_RE = re.compile(r':\d+$')


def _hostname_of(url: str) -> str:
    """Return lowercased eTLD+1-ish hostname (bare or www-stripped)."""
    try:
        parsed = urlparse(url if '://' in url else 'https://' + url)
        host = (parsed.netloc or '').lower()
        host = _STRIP_PORT_RE.sub('', host)
        if host.startswith('www.'):
            host = host[4:]
        return host
    except Exception:
        return ''


def build_context(
    text: str,
    ml_probability: float,
    ml_threshold: float,
    *,
    text_norm: str | None = None,
    urls: list | None = None,
    tone: tuple = (0, 0, 0, 0),
    scam_phrase_score: int = 0,
    sender_impersonation_score: int = 0,
    scam_type: str = 'general_spam',
    gsb_flagged: bool = False,
    gsb_threat_type: str | None = None,
    vt_malicious: int = 0,
    vt_suspicious: int = 0,
    trusted_domains: set | None = None,
    extras: dict | None = None,
) -> RuleContext:
    """Assemble a RuleContext from already-computed signals.

    The caller (predict_e5) has already computed most of these during
    its ancillary analysis; we just pass them through so no work is
    duplicated. Anything omitted defaults to a neutral value.
    """
    if trusted_domains is None:
        from config import TRUSTED_DOMAINS
        trusted_domains = TRUSTED_DOMAINS

    if urls is None:
        # Only lazy-import extract_urls if the caller didn't supply URLs
        from src.features import extract_urls
        urls = extract_urls(text) or []

    if text_norm is None:
        from src.features import preprocess_text
        text_norm = preprocess_text(text) if text else ''

    hostnames = [h for h in (_hostname_of(u) for u in urls) if h]

    return RuleContext(
        text=text or '',
        text_norm=text_norm or '',
        text_lower=(text or '').lower(),
        urls=list(urls),
        hostnames=hostnames,
        trusted_domains=set(trusted_domains),
        gsb_flagged=bool(gsb_flagged),
        gsb_threat_type=gsb_threat_type,
        vt_malicious=int(vt_malicious or 0),
        vt_suspicious=int(vt_suspicious or 0),
        tone_urgency=int(tone[0] if len(tone) > 0 else 0),
        tone_fear=int(tone[1]    if len(tone) > 1 else 0),
        tone_reward=int(tone[2]  if len(tone) > 2 else 0),
        tone_threat=int(tone[3]  if len(tone) > 3 else 0),
        scam_phrase_score=int(scam_phrase_score or 0),
        sender_impersonation_score=int(sender_impersonation_score or 0),
        scam_type=str(scam_type or 'general_spam'),
        ml_probability=float(ml_probability),
        ml_threshold=float(ml_threshold),
        extras=extras or {},
    )
