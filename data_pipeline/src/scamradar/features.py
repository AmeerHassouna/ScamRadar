"""Stage 3 — feature engineering as experiments (spec §4).

Feature sets are named F1..F6 and built as sklearn transformers so any model
can consume any set under identical conditions.
"""
from __future__ import annotations

import re

import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

URL = re.compile(r"https?://\S+|www\.\S+", re.I)
SHORTENER = re.compile(r"\b(bit\.ly|tinyurl|t\.co|goo\.gl|is\.gd|cutt\.ly|rb\.gy|shorturl)\b", re.I)
IP_URL = re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}", re.I)
PHONE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
MONEY = re.compile(r"[$€£₪]|(\b(usd|eur|ils|btc|eth|usdt|crypto|bitcoin)\b)", re.I)
URGENCY = re.compile(r"\b(urgent|immediately|now|expires?|suspend(ed)?|verify|confirm|"
                     r"limited|act now|final notice|last chance|24 hours|asap|"
                     r"click here|winner|congratulations|prize|free|refund)\b", re.I)
CRED = re.compile(r"\b(password|login|log in|ssn|otp|pin code|credentials|account "
                  r"(number|details)|social security)\b", re.I)
GREET_ANON = re.compile(r"^(dear (customer|user|sir|madam|friend|beneficiary))", re.I)
RISKY_TLD = re.compile(r"\.(xyz|top|club|icu|live|online|buzz|rest|click|link|work)\b", re.I)


class SecurityFeatures(BaseEstimator, TransformerMixin):
    """F5 — ~20 handcrafted security/linguistic features."""
    NAMES = ["n_urls", "has_shortener", "has_ip_url", "risky_tld", "n_phones",
             "money_hits", "urgency_hits", "cred_hits", "anon_greeting",
             "len_chars", "len_words", "caps_ratio", "digit_ratio", "punct_ratio",
             "exclam_count", "question_count", "avg_word_len", "max_word_len",
             "nonascii_ratio", "newline_count"]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for t in X:
            t = str(t)
            words = t.split() or [""]
            n = max(len(t), 1)
            rows.append([
                len(URL.findall(t)), int(bool(SHORTENER.search(t))),
                int(bool(IP_URL.search(t))), int(bool(RISKY_TLD.search(t))),
                len(PHONE.findall(t)), len(MONEY.findall(t)),
                len(URGENCY.findall(t)), len(CRED.findall(t)),
                int(bool(GREET_ANON.search(t))),
                len(t), len(words),
                sum(c.isupper() for c in t) / n,
                sum(c.isdigit() for c in t) / n,
                sum(not c.isalnum() and not c.isspace() for c in t) / n,
                t.count("!"), t.count("?"),
                float(np.mean([len(w) for w in words])),
                float(max(len(w) for w in words)),
                sum(ord(c) > 127 for c in t) / n,
                t.count("\n"),
            ])
        return np.asarray(rows, dtype=np.float64)


def _word_tfidf(**kw):
    return TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2,
                           max_features=200_000, **kw)


def _char_tfidf(**kw):
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
                           min_df=2, max_features=300_000, **kw)


def _scaled_security():
    return Pipeline([("sec", SecurityFeatures()),
                     ("scale", StandardScaler())])


def build(feature_set: str):
    """Return an unfitted transformer for the named feature set."""
    fs = feature_set.upper()
    if fs == "F1":
        return _word_tfidf()
    if fs == "F2":
        return _char_tfidf()
    if fs == "F3":
        return FeatureUnion([("w", _word_tfidf()), ("c", _char_tfidf())])
    if fs == "F5":
        return _scaled_security()
    if fs == "F6":
        return FeatureUnion([("w", _word_tfidf()), ("c", _char_tfidf()),
                             ("s", _scaled_security())])
    if fs == "F4":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise SystemExit("F4 needs `pip install sentence-transformers`") from e

        class STEmb(BaseEstimator, TransformerMixin):
            def __init__(self):
                self.m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            def fit(self, X, y=None): return self
            def transform(self, X):
                return self.m.encode(list(X), batch_size=64, show_progress_bar=False)
        return STEmb()
    raise ValueError(f"unknown feature set {feature_set}")


FEATURE_SETS = ["F1", "F2", "F3", "F5", "F6"]  # F4 opt-in (heavy dependency)
