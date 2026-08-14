"""
Canonical E8-P9 model construction, training, and bundle I/O.

Contents:
  * `build_vectorizers()` — the word + char TF-IDF configuration used by
    every E7/E8 variant.
  * `build_classifier()` — Logistic Regression with the frozen E4
    hyperparameters.
  * `compute_numerical_features()` — the 25 engineered numerical features.
  * `train_e8p9_model()` — one-shot end-to-end training that reproduces
    the deployed bundle.
  * `load_deployed_bundle()` — loads `models/e7_p1_variants/e7_p1_full_e8p9.joblib`.
  * `save_bundle()` — serialises a trained bundle in the exact schema the
    inference layer expects.

Reading this module answers "what exactly is the deployed classifier?"
without opening any historical experiment.
"""
from __future__ import annotations

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.canonical import (
    DEPLOYED_MODEL_PATH, LR_HYPERPARAMS, NUMERICAL_FEATURES,
    OPERATING_THRESHOLD, TFIDF_CHAR_PARAMS, TFIDF_WORD_PARAMS,
)
from src.rule_engine.numerical_features import compute_all_numerical


# ─── Configuration builders (thin wrappers over sklearn) ─────────────────

def build_word_vectorizer() -> TfidfVectorizer:
    """Word-level TF-IDF: 1–2 grams, 200k vocab."""
    return TfidfVectorizer(**TFIDF_WORD_PARAMS)


def build_char_vectorizer() -> TfidfVectorizer:
    """Character-level TF-IDF: 3–6 char_wb grams, 300k vocab."""
    return TfidfVectorizer(**TFIDF_CHAR_PARAMS)


def build_classifier() -> LogisticRegression:
    """Logistic Regression with frozen E4 hyperparameters.

    Uncalibrated by design — the E5 calibration study ranked 'none' above
    Platt and isotonic on PR-AUC, ROC-AUC, ECE, and Brier.
    """
    return LogisticRegression(**LR_HYPERPARAMS)


# ─── Feature block: 25 numerical features ────────────────────────────────

def compute_numerical_features(text: str) -> dict[str, float]:
    """Compute the 25 numerical features for a single text.

    Delegates to `src.rule_engine.numerical_features.compute_all_numerical`
    which is the authoritative implementation shared by training and
    inference — guaranteeing parity.
    """
    return compute_all_numerical(text)


def numerical_features_matrix(texts: pd.Series | list[str],
                              scaler: StandardScaler | None = None
                              ) -> tuple[np.ndarray, StandardScaler]:
    """Materialise the 25×n matrix, optionally scaled.

    If `scaler` is None, a new StandardScaler is fit and returned. If
    provided (typically at inference), it is applied without re-fitting.
    Values are clipped to [-8, 8] after scaling — matches training hygiene.
    """
    rows = [compute_numerical_features(t) for t in texts]
    X = np.array(
        [[r.get(c, 0) for c in NUMERICAL_FEATURES] for r in rows],
        dtype=np.float64,
    )
    if scaler is None:
        scaler = StandardScaler().fit(X)
    Xs = np.clip(scaler.transform(X), -8.0, 8.0)
    return Xs, scaler


# ─── Full training pipeline ──────────────────────────────────────────────

def train_e8p9_model(train_df: pd.DataFrame,
                     text_col: str = 'text',
                     label_col: str = 'label') -> dict:
    """Reproduce the deployed E8-P9 bundle from a training corpus.

    Expects `train_df` to be the E8-P9 training corpus loaded via
    `src.data.load_training_corpus_e8p9()`, filtered to `split == 'train'`
    (or the full frame if you want to fit on all rows).

    Returns a bundle dict with the exact schema `_E7P1Adapter` in
    `src.e5_inference` expects — save it via `save_bundle()`.
    """
    texts = train_df[text_col].astype(str).tolist()
    labels = train_df[label_col].astype(int).values

    print(f'[train_e8p9] fitting on n={len(texts):,}')

    print('[train_e8p9] word TF-IDF...')
    word_vec = build_word_vectorizer().fit(texts)
    Xw = word_vec.transform(texts)

    print('[train_e8p9] char TF-IDF...')
    char_vec = build_char_vectorizer().fit(texts)
    Xc = char_vec.transform(texts)

    print('[train_e8p9] numerical features (25)...')
    Xn, scaler = numerical_features_matrix(texts)

    print('[train_e8p9] stacking features...')
    X = hstack([Xw, Xc, csr_matrix(Xn)]).tocsr()

    print(f'[train_e8p9] fitting LogisticRegression (C={LR_HYPERPARAMS["C"]:.4f})')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        lr = build_classifier().fit(X, labels)

    return {
        'variant':      'e7_p1_full_e8p9',
        'lr':           lr,
        'word_vec':     word_vec,
        'char_vec':     char_vec,
        'scaler':       scaler,
        'feature_cols': list(NUMERICAL_FEATURES),
        'threshold':    OPERATING_THRESHOLD,
    }


# ─── Bundle I/O ──────────────────────────────────────────────────────────

def save_bundle(bundle: dict, path: str) -> None:
    """Persist a trained bundle. Uses joblib (matches deployed format)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(bundle, path)
    print(f'[model] saved bundle to {path}  ({os.path.getsize(path)/1e6:.1f} MB)')


def load_deployed_bundle() -> dict:
    """Load the frozen production bundle from disk.

    Returns the raw bundle dict as it was saved. See `src.inference` /
    `src.e5_inference` for the wrapping code that adapts this bundle to
    the API's request-time prediction interface.
    """
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return joblib.load(DEPLOYED_MODEL_PATH)


__all__ = [
    'build_word_vectorizer', 'build_char_vectorizer', 'build_classifier',
    'compute_numerical_features', 'numerical_features_matrix',
    'train_e8p9_model', 'save_bundle', 'load_deployed_bundle',
]
