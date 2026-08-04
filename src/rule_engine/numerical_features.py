"""Runtime-only extraction of the 25-feature numerical block used by the
E7-P1 / E8 model bundles. This is a small subset of scripts/training/
train_e7_p1.py — just the parts inference needs, so the deployed image
doesn't have to include the training script.

Both `ALL_NUMERICAL` (the ordered list of column names the scaler was
fit on) and `compute_all_numerical(text)` must stay byte-for-byte
identical to the training-time versions in scripts/training/train_e7_p1.py,
or the scaler's z-scores will drift silently.
"""
from __future__ import annotations

import re

from src._02_feature_engineering import (
    preprocess_text,
    compute_tone_features,
    compute_url_features,
    compute_new_features,
)


FEATURE_GROUPS = {
    'tone': ['tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat'],
    'url': ['has_url', 'url_count', 'url_suspicious_tld',
            'url_suspicious_keyword', 'url_has_ip'],
    'phrase': ['scam_phrase_score', 'sender_impersonation_score', 'legit_phrase_score'],
    'textstats': ['text_length', 'word_count', 'exclamation_count', 'uppercase_ratio',
                  'digit_ratio', 'urgency_score', 'avg_word_length',
                  'capitalized_word_count', 'punctuation_density',
                  'question_mark_count', 'currency_symbol_count',
                  'readability_score', 'unique_word_ratio'],
}
ALL_NUMERICAL = (FEATURE_GROUPS['tone'] + FEATURE_GROUPS['url']
                 + FEATURE_GROUPS['phrase'] + FEATURE_GROUPS['textstats'])


_URL_RE = re.compile(r'https?://\S+|www\.\S+', re.I)


def compute_all_numerical(text: str) -> dict:
    """Compute every one of the 25 numerical features for a single message.
    Uses only the existing helpers from src/_02_feature_engineering.py."""
    t_raw = str(text) if text is not None else ''
    t_pre = preprocess_text(t_raw)

    urls = _URL_RE.findall(t_pre)
    text_length = len(t_pre)
    word_count = len(t_pre.split())
    has_url = int(len(urls) > 0)
    url_count = len(urls)
    exclamation_count = t_pre.count('!')
    uppercase_ratio = (sum(c.isupper() for c in t_pre) / max(len(t_pre), 1))
    digit_ratio = (sum(c.isdigit() for c in t_pre) / max(len(t_pre), 1))
    urgency_score = float(sum(1 for w in ['urgent', 'immediately', 'now', 'today', 'asap']
                               if w in t_pre.lower()))

    urg, fear, reward, threat = compute_tone_features(t_pre)
    url_susp_tld, url_susp_kw, url_has_ip = compute_url_features(t_pre)
    new = compute_new_features(t_pre)

    return {
        'text_length': text_length, 'word_count': word_count,
        'has_url': has_url, 'url_count': url_count,
        'exclamation_count': exclamation_count,
        'uppercase_ratio': uppercase_ratio, 'digit_ratio': digit_ratio,
        'urgency_score': urgency_score,
        'tone_urgency': urg, 'tone_fear': fear,
        'tone_reward': reward, 'tone_threat': threat,
        'url_suspicious_tld': url_susp_tld,
        'url_suspicious_keyword': url_susp_kw,
        'url_has_ip': url_has_ip,
        'scam_phrase_score':          new.get('scam_phrase_score', 0),
        'sender_impersonation_score': new.get('sender_impersonation_score', 0),
        'legit_phrase_score':         new.get('legit_phrase_score', 0),
        'avg_word_length':            new.get('avg_word_length', 0.0),
        'capitalized_word_count':     new.get('capitalized_word_count', 0),
        'punctuation_density':        new.get('punctuation_density', 0.0),
        'question_mark_count':        new.get('question_mark_count', 0),
        'currency_symbol_count':      new.get('currency_symbol_count', 0),
        'readability_score':          new.get('readability_score', 0.0),
        'unique_word_ratio':          new.get('unique_word_ratio', 0.0),
    }
