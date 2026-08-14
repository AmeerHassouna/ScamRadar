"""
Canonical evaluation for the deployed E8-P9 pipeline.

Computes headline metrics + confusion matrix + error analysis on the
frozen 25,306-row external benchmark. Reproduces the canonical values
declared in `src.canonical.HEADLINE_METRICS`.

There are two modes:

  * `evaluate_raw_classifier(...)` — the classifier alone, no rule engine.
    Yields the "raw classifier" block of HEADLINE_METRICS.

  * `evaluate_with_rule_engine(...)` — the deployed pipeline (classifier
    + 19-rule engine). Yields the "with_rule_engine" block.

Both take an already-loaded model callable (bundle from
`src.model.load_deployed_bundle()`) and a benchmark DataFrame (from
`src.data.load_external_benchmark()`). This keeps the evaluation
functions pure and testable — no path fiddling, no environment vars.

For side-by-side FP/FN error analysis with textual samples, see
`scripts/evaluation/analyze_e8p9_errors.py` — the fuller reporting script
uses these primitives.
"""
from __future__ import annotations

import os
import sys
import warnings
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)

from src.canonical import OPERATING_THRESHOLD


# ─── Metric primitives ───────────────────────────────────────────────────

def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray,
                    threshold: float = OPERATING_THRESHOLD) -> dict:
    """Compute the standard headline metric set at a given threshold."""
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return {
            'accuracy':  float(accuracy_score(y_true, y_pred)),
            'precision': float(precision_score(y_true, y_pred, zero_division=0)),
            'recall':    float(recall_score(y_true, y_pred, zero_division=0)),
            'f1':        float(f1_score(y_true, y_pred, zero_division=0)),
            'roc_auc':   float(roc_auc_score(y_true, y_prob)),
            'pr_auc':    float(average_precision_score(y_true, y_prob)),
            'brier':     float(brier_score_loss(y_true, y_prob)),
            'ece':       expected_calibration_error(y_true, y_prob),
            'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
            'n':         int(len(y_true)),
            'threshold': float(threshold),
        }


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray,
                                 n_bins: int = 15) -> float:
    """15-bin equal-width ECE, matches the training-time convention."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.digitize(y_prob, bins) - 1
    idx = np.clip(idx, 0, n_bins - 1)
    n = len(y_true)
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        acc_b = float(y_true[mask].mean())
        conf_b = float(y_prob[mask].mean())
        ece += (mask.sum() / n) * abs(acc_b - conf_b)
    return float(ece)


# ─── High-level evaluators ───────────────────────────────────────────────

def score_batch(bundle: dict, texts: list[str]) -> np.ndarray:
    """Return raw classifier probabilities for a list of texts.

    Uses the same adapter path as production inference so numbers match
    byte-for-byte.
    """
    from src.e5_inference import _E7P1Adapter
    model = _E7P1Adapter(bundle)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        proba = model.predict_proba(texts)
    return proba[:, 1]


def evaluate_raw_classifier(bundle: dict, benchmark: pd.DataFrame,
                             threshold: float = OPERATING_THRESHOLD) -> dict:
    """Score the classifier alone (no rule engine) on a benchmark."""
    texts = benchmark['text'].astype(str).tolist()
    y_true = benchmark['label'].astype(int).values
    y_prob = score_batch(bundle, texts)
    return compute_metrics(y_true, y_prob, threshold)


def evaluate_with_rule_engine(bundle: dict, benchmark: pd.DataFrame,
                               threshold: float = OPERATING_THRESHOLD
                               ) -> tuple[dict, pd.DataFrame]:
    """Score the deployed pipeline (classifier + 19 rules).

    Returns (metrics_dict, per_item_df). The per-item frame includes the
    ml probability, final probability, verdict, and any triggered rules.
    """
    from src.e5_inference import predict_e5

    pipe = {'model': _wrap_for_predict_e5(bundle), 'threshold': threshold}

    rows = []
    for i, r in enumerate(benchmark.itertuples(index=False), 1):
        text = str(r.text)
        try:
            res = predict_e5(text, pipe, threshold=threshold,
                              vt_api_key=None, gsb_api_key=None)
        except Exception:
            res = {'verdict': 'LEGIT', 'confidence': 0.0,
                   'ml_probability': 0.0, 'final_probability': 0.0,
                   'urls_found': [], 'rule_engine': None}
        pred = 1 if res.get('verdict') in ('SCAM', 'SUSPICIOUS') else 0
        re_out = res.get('rule_engine') or {}
        rows.append({
            'text':        text,
            'category':    getattr(r, 'category', None),
            'label':       int(r.label),
            'pred':        pred,
            'confidence':  float(res.get('confidence', 0)),
            'ml_prob':     float(res.get('ml_probability') or 0),
            'final_prob':  float(res.get('final_probability') or 0),
            'triggered':   ','.join(t['rule_id'] for t in (re_out.get('triggered_rules') or [])),
            'forced_scam': bool(re_out.get('forced_scam')),
            'has_url':     1 if (res.get('urls_found') or []) else 0,
            'char_len':    len(text),
        })
        if i % 2000 == 0:
            print(f'  scored {i:>6}/{len(benchmark)}')

    per_df = pd.DataFrame(rows)
    y_true = per_df['label'].values
    y_prob = per_df['final_prob'].values
    metrics = compute_metrics(y_true, y_prob, threshold)
    metrics['n_fp'] = int(((per_df.label == 0) & (per_df.pred == 1)).sum())
    metrics['n_fn'] = int(((per_df.label == 1) & (per_df.pred == 0)).sum())
    return metrics, per_df


def _wrap_for_predict_e5(bundle: dict):
    """The predict_e5 code path expects `pipe['model'].predict_proba(texts)`.
    Wrap the E8-P9 bundle in the adapter that provides that interface."""
    from src.e5_inference import _E7P1Adapter
    return _E7P1Adapter(bundle)


# ─── Error analysis (grouping only — for full report see scripts/) ──────

def fp_fn_by_category(per_df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """FP counts per category and FN counts per (scam) category."""
    fps = per_df[(per_df.label == 0) & (per_df.pred == 1)]
    fns = per_df[(per_df.label == 1) & (per_df.pred == 0)]
    return fps.category.value_counts(), fns.category.value_counts()


def rule_engagement(per_df: pd.DataFrame) -> dict:
    """How the rule engine engaged with the residual errors."""
    fps = per_df[(per_df.label == 0) & (per_df.pred == 1)]
    fns = per_df[(per_df.label == 1) & (per_df.pred == 0)]

    def _rule_hits(rows) -> Counter:
        c: Counter = Counter()
        for s in rows.triggered:
            for r in (s or '').split(','):
                if r:
                    c[r] += 1
        return c

    return {
        'fp_touched':   int((fps.n_rules > 0).sum()) if 'n_rules' in fps.columns else int((fps.triggered.str.len() > 0).sum()),
        'fp_forced':    int(fps.forced_scam.sum()) if 'forced_scam' in fps.columns else 0,
        'fp_rule_hits': dict(_rule_hits(fps).most_common()),
        'fn_touched':   int((fns.triggered.str.len() > 0).sum()),
        'fn_rule_hits': dict(_rule_hits(fns).most_common()),
    }


__all__ = [
    'compute_metrics', 'expected_calibration_error',
    'score_batch', 'evaluate_raw_classifier', 'evaluate_with_rule_engine',
    'fp_fn_by_category', 'rule_engagement',
]
