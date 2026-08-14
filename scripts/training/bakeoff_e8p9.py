"""
E8-P9 final classifier bake-off — raw-classifier comparison on the deployed
E8-P9 training corpus.

Purpose
-------
Demonstrate that Logistic Regression (the deployed E8-P9 classifier) was
selected as the winner over reasonable alternatives on the *final* E8-P9
training corpus, not only on the earlier E3 comparison corpus. The deployed
pipeline is unchanged.

Experimental design
-------------------
The classifier is the ONLY variable across experiments. Everything else is
byte-identical to the deployed E8-P9 pipeline:

  * partitions       — the split column baked into
                       data/interim/e7_p1_features_e8p9.parquet
                       (train / val / test / external)
  * preprocessing    — the `text` column in the parquet (already normalised by
                       the DP pipeline, consumed as-is by every TF-IDF)
  * word TF-IDF      — TfidfVectorizer(**E5_WORD_PARAMS), fit on train only
  * char TF-IDF      — TfidfVectorizer(**E5_CHAR_PARAMS), fit on train only
  * numerical block  — the 25 features from src/features,
                       computed by scripts.training.train_e7_p1
  * scaling          — StandardScaler, fit on train only
  * feature fusion   — hstack([Xw, Xc, csr_matrix(Xn)])
  * evaluation set   — the full 25,306-row external benchmark (features
                       recomputed once; every classifier scores the same rows)
  * thresholds       — reported at BOTH the deployed threshold (0.59) AND
                       each classifier's validation-optimal F1 threshold

Candidates
----------
  * LogisticRegression       — exact deployed E8-P9 configuration
  * LinearSVC + CalibratedClassifierCV(FrozenEstimator, method='sigmoid')
                             — LinearSVC fit on train, then wrapped in
                               sklearn.frozen.FrozenEstimator (sklearn >=1.6
                               replacement for the deprecated cv='prefit');
                               sigmoid calibrator fit on val, base not refit.
  * SGDClassifier(loss='log_loss')

Exclusions and why
------------------
  * ComplementNB: requires non-negative inputs; the StandardScaler'd numerical
    block contains negatives. Including it would force a different
    preprocessing pipeline for one classifier and violate the fairness
    principle. Dropped rather than special-cased.

  * RandomForest: memory-prohibitive on the ~500k-dim sparse fused matrix.

  * HistGradientBoostingClassifier: does not accept sparse input in sklearn.

Raw-classifier evaluation
-------------------------
No rule engine, no OTP rule, no safety net. Those belong to the deployed
inference pipeline and are classifier-agnostic; folding them in would add
correlated noise across every row rather than distinguishing classifiers.

Outputs
-------
  outputs/eval/e8p9_bakeoff_results.json
  outputs/eval/e8p9_bakeoff_results.csv
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.frozen import FrozenEstimator  # sklearn >=1.6 replaces cv='prefit'
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, roc_auc_score, average_precision_score,
                              confusion_matrix)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.training.train_e7_p1 import (
    E5_LR_PARAMS, E5_WORD_PARAMS, E5_CHAR_PARAMS, ALL_NUMERICAL,
    compute_features_for_df,
)

# ─── Paths ───────────────────────────────────────────────────────────────────
FEAT_PARQUET = os.path.join(_ROOT, 'data', 'interim',
                            'e7_p1_features_e8p9.parquet')
EXT_BENCHMARK = os.path.join(_ROOT, 'data', 'canonical', 'external_benchmark.parquet')

OUT_DIR = os.path.join(_ROOT, 'outputs', 'eval')
OUT_JSON = os.path.join(OUT_DIR, 'e8p9_bakeoff_results.json')
OUT_CSV = os.path.join(OUT_DIR, 'e8p9_bakeoff_results.csv')
CACHE_DIR = os.path.join(OUT_DIR, '_bakeoff_cache')

DEPLOYED_THRESHOLD = 0.59  # E5's F1-max — inherited by E8-P9 as-deployed
N_LATENCY_TRIALS = 50
N_LATENCY_WARMUP = 5


# ─── Candidate factories ─────────────────────────────────────────────────────
def _make_lr():
    """Exact deployed E8-P9 configuration."""
    return LogisticRegression(**E5_LR_PARAMS)


def _make_linear_svc():
    """LinearSVC with class_weight='balanced' and random_state=42.

    Wrapped in CalibratedClassifierCV(cv='prefit') downstream so the
    validation split can supply probability calibration without re-fitting
    the base model.
    """
    return LinearSVC(
        C=1.0, class_weight='balanced', random_state=42,
        max_iter=1000, tol=1e-4, dual='auto',
    )


def _make_sgd():
    return SGDClassifier(
        loss='log_loss', class_weight='balanced', random_state=42,
        max_iter=200, tol=1e-4, alpha=1e-4,
    )


CANDIDATES = [
    ('logistic_regression',       _make_lr,        'sklearn.linear_model.LogisticRegression'),
    ('linear_svc_calibrated',     _make_linear_svc,'sklearn.svm.LinearSVC + CalibratedClassifierCV(FrozenEstimator, sigmoid)'),
    ('sgd_log_loss',              _make_sgd,       "sklearn.linear_model.SGDClassifier(loss='log_loss')"),
]


# ─── Shared preprocessing (fit once, reused across every classifier) ─────────
def build_shared_pipeline(combined: pd.DataFrame, ext_df: pd.DataFrame):
    """Fit word TF-IDF, char TF-IDF, StandardScaler on train only, then
    transform train/val/test/external. Returns X blocks + y vectors.

    ext_df must already carry the 25 numerical feature columns.
    """
    train = combined[combined.split == 'train'].reset_index(drop=True)
    val   = combined[combined.split == 'val'  ].reset_index(drop=True)
    test  = combined[combined.split == 'test' ].reset_index(drop=True)
    ext   = ext_df.reset_index(drop=True)

    print(f'  train={len(train):,}  val={len(val):,}  test={len(test):,}  '
          f'external={len(ext):,}')

    # Word TF-IDF — fit on train.text only
    print('  fit word TF-IDF (E5 params)...')
    word_vec = TfidfVectorizer(**E5_WORD_PARAMS)
    Xw_tr = word_vec.fit_transform(train.text)
    Xw_va = word_vec.transform(val.text)
    Xw_te = word_vec.transform(test.text)
    Xw_ex = word_vec.transform(ext.text)
    print(f'    word features: {Xw_tr.shape[1]:,}')

    # Char TF-IDF — fit on train.text only
    print('  fit char TF-IDF (E5 params)...')
    char_vec = TfidfVectorizer(**E5_CHAR_PARAMS)
    Xc_tr = char_vec.fit_transform(train.text)
    Xc_va = char_vec.transform(val.text)
    Xc_te = char_vec.transform(test.text)
    Xc_ex = char_vec.transform(ext.text)
    print(f'    char features: {Xc_tr.shape[1]:,}')

    # Numerical block — StandardScaler fit on train only
    print(f'  fit StandardScaler over {len(ALL_NUMERICAL)} numerical features...')
    scaler = StandardScaler()
    Xn_tr = scaler.fit_transform(train[ALL_NUMERICAL].values.astype(np.float64))
    Xn_va = scaler.transform(val[ALL_NUMERICAL].values.astype(np.float64))
    Xn_te = scaler.transform(test[ALL_NUMERICAL].values.astype(np.float64))
    Xn_ex = scaler.transform(ext[ALL_NUMERICAL].values.astype(np.float64))

    # Fuse
    X_tr = hstack([Xw_tr, Xc_tr, csr_matrix(Xn_tr)]).tocsr()
    X_va = hstack([Xw_va, Xc_va, csr_matrix(Xn_va)]).tocsr()
    X_te = hstack([Xw_te, Xc_te, csr_matrix(Xn_te)]).tocsr()
    X_ex = hstack([Xw_ex, Xc_ex, csr_matrix(Xn_ex)]).tocsr()
    print(f'  fused X shape: train={X_tr.shape}  external={X_ex.shape}')

    y_tr = train.label.values.astype(int)
    y_va = val.label.values.astype(int)
    y_te = test.label.values.astype(int)
    y_ex = ext.label.values.astype(int)

    return {
        'X_tr': X_tr, 'y_tr': y_tr,
        'X_va': X_va, 'y_va': y_va,
        'X_te': X_te, 'y_te': y_te,
        'X_ex': X_ex, 'y_ex': y_ex,
        'word_vec': word_vec, 'char_vec': char_vec, 'scaler': scaler,
    }


# ─── Metric helpers ──────────────────────────────────────────────────────────
def _ece(y, p, n_bins: int = 10) -> float:
    y = np.asarray(y).astype(int)
    p = np.asarray(p)
    bins = np.linspace(0, 1, n_bins + 1)
    e = 0.0
    for i in range(n_bins):
        mask = (p >= bins[i]) & (p < bins[i + 1])
        if mask.sum() == 0:
            continue
        conf = p[mask].mean()
        acc = y[mask].mean()
        e += (mask.sum() / len(y)) * abs(conf - acc)
    return float(e)


def score_at_threshold(y, p, threshold: float) -> dict:
    y = np.asarray(y).astype(int)
    p = np.asarray(p)
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    out = {
        'threshold':  round(float(threshold), 4),
        'n':          int(len(y)),
        'accuracy':   round(float(accuracy_score(y, yhat)), 4),
        'precision':  round(float(precision_score(y, yhat, zero_division=0)), 4),
        'recall':     round(float(recall_score(y, yhat, zero_division=0)), 4),
        'f1':         round(float(f1_score(y, yhat, zero_division=0)), 4),
        'confusion':  {'tn': int(tn), 'fp': int(fp),
                       'fn': int(fn), 'tp': int(tp)},
    }
    if len(set(y)) > 1:
        out['roc_auc'] = round(float(roc_auc_score(y, p)), 4)
        out['pr_auc']  = round(float(average_precision_score(y, p)), 4)
        out['ece']     = round(_ece(y, p), 4)
    return out


def find_f1_max_threshold(y, p) -> tuple[float, float]:
    y = np.asarray(y).astype(int)
    thresholds = np.linspace(0.05, 0.95, 91)
    best_t, best_f1 = 0.5, 0.0
    for t in thresholds:
        f1 = f1_score(y, (p >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return float(best_t), float(best_f1)


# ─── Latency + size measurement ──────────────────────────────────────────────
def measure_latency_ms(clf, X_ext) -> float:
    """Median batch=1 predict_proba latency, warm."""
    n = X_ext.shape[0]
    idxs = np.linspace(0, n - 1, N_LATENCY_TRIALS + N_LATENCY_WARMUP,
                       dtype=int)
    # warmup
    for i in idxs[:N_LATENCY_WARMUP]:
        clf.predict_proba(X_ext[i:i + 1])
    times = []
    for i in idxs[N_LATENCY_WARMUP:]:
        t0 = time.perf_counter()
        clf.predict_proba(X_ext[i:i + 1])
        times.append((time.perf_counter() - t0) * 1000.0)
    return float(np.median(times))


def measure_size_mb(clf) -> float:
    """Serialise the classifier alone (vectorisers + scaler are shared and
    identical across every candidate) and return MB on disk."""
    tmp = os.path.join(OUT_DIR, '_bakeoff_tmp_clf.joblib')
    joblib.dump(clf, tmp, compress=3)
    mb = os.path.getsize(tmp) / 1e6
    try:
        os.remove(tmp)
    except OSError:
        pass
    return float(mb)


# ─── Data loading ────────────────────────────────────────────────────────────
def load_combined_and_external() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the E8-P9 features parquet (train/val/test/external splits with
    precomputed numerical features), and the full 25,306-row external
    benchmark with its numerical features recomputed on the fly.

    We deliberately do NOT reuse the parquet's `split=='external'` slice for
    the external evaluation — the full benchmark parquet is 25,306 rows
    (matches the official E8-P9 headline), whereas the parquet's external
    split is a 24,841-row subset. All four models see the same 25,306 rows.
    """
    print(f'Loading E8-P9 features parquet:  {FEAT_PARQUET}')
    combined = pd.read_parquet(FEAT_PARQUET)
    print(f'  shape={combined.shape}  splits={combined.split.value_counts().to_dict()}')

    print(f'Loading full external benchmark: {EXT_BENCHMARK}')
    ext = pd.read_parquet(EXT_BENCHMARK)
    print(f'  external benchmark: n={len(ext):,}  '
          f'scam={int((ext.label == 1).sum()):,}  '
          f'legit={int((ext.label == 0).sum()):,}')

    print('Recomputing 25 numerical features for the external benchmark '
          '(same helper used at training time)...')
    ext_feats = compute_features_for_df(ext[['text']], text_col='text')
    ext = pd.concat([ext[['text', 'label', 'category']].reset_index(drop=True),
                     ext_feats.reset_index(drop=True)], axis=1)
    return combined, ext


# ─── Per-classifier trainer + evaluator ──────────────────────────────────────
def train_and_evaluate(name: str, make_clf, description: str,
                       shared: dict) -> dict:
    print(f'\n{"=" * 72}\n  {name}  ({description})\n{"=" * 72}')

    X_tr, y_tr = shared['X_tr'], shared['y_tr']
    X_va, y_va = shared['X_va'], shared['y_va']
    X_te, y_te = shared['X_te'], shared['y_te']
    X_ex, y_ex = shared['X_ex'], shared['y_ex']

    # ── Fit (with per-classifier disk cache) ──
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f'{name}.joblib')
    base = make_clf()
    base_params = base.get_params(deep=False)

    clf = None
    fit_seconds = None
    if os.path.exists(cache_path):
        print(f'  ⟳ loading cached fitted classifier from {cache_path}')
        cached = joblib.load(cache_path)
        cand_clf = cached['clf']
        cand_dim = None
        if hasattr(cand_clf, 'coef_'):
            cand_dim = cand_clf.coef_.shape[1]
        elif hasattr(cand_clf, 'calibrated_classifiers_'):
            inner = cand_clf.calibrated_classifiers_[0].estimator
            if hasattr(inner, 'coef_'):
                cand_dim = inner.coef_.shape[1]
        expected_dim = X_tr.shape[1]
        if cand_dim is not None and cand_dim != expected_dim:
            print(f'    !! cached clf dim {cand_dim} != current pipeline dim '
                  f'{expected_dim} — invalidating cache and refitting')
            os.remove(cache_path)
        else:
            clf = cand_clf
            fit_seconds = cached['fit_seconds']
            print(f'    (originally fit in {fit_seconds:.1f}s)')

    if clf is None:
        t0 = time.time()
        if name == 'linear_svc_calibrated':
            print('  fit LinearSVC on train...')
            base.fit(X_tr, y_tr)
            print(f'    LinearSVC fit in {time.time() - t0:.1f}s')
            t1 = time.time()
            print('  fit sigmoid calibrator on val (FrozenEstimator, cv=5)...')
            clf = CalibratedClassifierCV(
                FrozenEstimator(base), method='sigmoid',
            )
            clf.fit(X_va, y_va)
            print(f'    calibrator fit in {time.time() - t1:.1f}s')
        else:
            print(f'  fit {name} on train...')
            clf = base
            clf.fit(X_tr, y_tr)
            print(f'    fit in {time.time() - t0:.1f}s')
        fit_seconds = time.time() - t0
        joblib.dump({'clf': clf, 'fit_seconds': fit_seconds}, cache_path,
                    compress=3)
        print(f'  cached fitted classifier → {cache_path}')

    # ── Score every split ──
    print('  predict_proba on val / test / external...')
    p_va = clf.predict_proba(X_va)[:, 1]
    p_te = clf.predict_proba(X_te)[:, 1]
    p_ex = clf.predict_proba(X_ex)[:, 1]

    val_opt_t, val_opt_f1 = find_f1_max_threshold(y_va, p_va)
    print(f'  val-optimal F1 threshold: {val_opt_t:.3f}  (val F1={val_opt_f1:.4f})')

    ext_deployed = score_at_threshold(y_ex, p_ex, DEPLOYED_THRESHOLD)
    ext_optimal  = score_at_threshold(y_ex, p_ex, val_opt_t)
    val_at_opt   = score_at_threshold(y_va, p_va, val_opt_t)
    test_deployed = score_at_threshold(y_te, p_te, DEPLOYED_THRESHOLD)
    test_optimal  = score_at_threshold(y_te, p_te, val_opt_t)

    # ── Ops metrics ──
    lat_ms = measure_latency_ms(clf, X_ex)
    size_mb = measure_size_mb(clf)
    print(f'  latency (batch=1, median of {N_LATENCY_TRIALS} warm calls): '
          f'{lat_ms:.2f} ms')
    print(f'  classifier size on disk (joblib compress=3):    {size_mb:.2f} MB')

    # ── Headline summary ──
    print(f'  external @ 0.59:  F1={ext_deployed["f1"]}  '
          f'P={ext_deployed["precision"]}  R={ext_deployed["recall"]}  '
          f'PR-AUC={ext_deployed.get("pr_auc")}  ECE={ext_deployed.get("ece")}')
    print(f'  external @ {val_opt_t:.2f}: F1={ext_optimal["f1"]}  '
          f'P={ext_optimal["precision"]}  R={ext_optimal["recall"]}')

    return {
        'model':                     name,
        'description':               description,
        'hyperparameters':           {k: (v if not hasattr(v, '__name__')
                                          else v.__name__)
                                      for k, v in base_params.items()},
        'fit_seconds':               round(fit_seconds, 2),
        'classifier_size_mb':        round(size_mb, 3),
        'latency_batch1_ms_median':  round(lat_ms, 3),
        'val_optimal_threshold':     round(val_opt_t, 4),
        'val_at_optimal_threshold':  val_at_opt,
        'external_at_deployed_0.59': ext_deployed,
        'external_at_val_optimal':   ext_optimal,
        'test_at_deployed_0.59':     test_deployed,
        'test_at_val_optimal':       test_optimal,
    }


# ─── Reporting ───────────────────────────────────────────────────────────────
def rank_and_write(results: list[dict], shared_meta: dict):
    # Ranking: primary = external PR-AUC (threshold-independent, matches E3),
    # tiebreaker = external F1 at deployed threshold.
    def sort_key(r):
        pr = r['external_at_deployed_0.59'].get('pr_auc', 0.0) or 0.0
        f1 = r['external_at_deployed_0.59'].get('f1', 0.0) or 0.0
        return (-pr, -f1)

    ranked = sorted(results, key=sort_key)
    winner = ranked[0]['model']

    payload = {
        'experiment':          'E8-P9 final classifier bake-off',
        'purpose':             ('Confirm that the deployed classifier '
                                '(LogisticRegression) remains the winner on '
                                'the E8-P9 corpus, not only on the earlier '
                                'E3 comparison corpus.'),
        'primary_metric':      'external PR-AUC at deployed threshold 0.59',
        'tiebreak_metric':     'external F1 at deployed threshold 0.59',
        'shared_pipeline':     shared_meta,
        'deployed_threshold':  DEPLOYED_THRESHOLD,
        'excluded_candidates': {
            'ComplementNB':                  'requires non-negative input; '
                                              'incompatible with StandardScaler '
                                              'output. Dropped rather than '
                                              'given a different preprocessing '
                                              'pipeline.',
            'RandomForest':                  'memory-prohibitive on the '
                                              '~500k-dim sparse fused matrix.',
            'HistGradientBoostingClassifier':'does not accept sparse input '
                                              'in scikit-learn.',
        },
        'notes': [
            'Rule engine / safety net / OTP rule are DISABLED for this '
            'evaluation. Bake-off measures raw classifier behaviour.',
            'The deployed E8-P9 headline number is LR + rule engine; expect '
            'the LR row here to differ from that headline for that reason.',
            'LinearSVC is calibrated via CalibratedClassifierCV wrapping '
            'sklearn.frozen.FrozenEstimator (sklearn >=1.6 replacement for the '
            'deprecated cv="prefit"). The calibrator is fit on the validation '
            'split; the base LinearSVC is not refit.',
        ],
        'ranked':              [{'model': r['model'],
                                 'external_pr_auc':
                                     r['external_at_deployed_0.59'].get('pr_auc'),
                                 'external_f1_at_0.59':
                                     r['external_at_deployed_0.59'].get('f1'),
                                 'external_f1_at_val_optimal':
                                     r['external_at_val_optimal'].get('f1'),
                                 'external_ece':
                                     r['external_at_deployed_0.59'].get('ece'),
                                 'classifier_size_mb': r['classifier_size_mb'],
                                 'latency_batch1_ms_median':
                                     r['latency_batch1_ms_median']}
                                for r in ranked],
        'winner':              winner,
        'results':             results,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, 'w') as f:
        json.dump(payload, f, indent=2)
    print(f'\nSaved {OUT_JSON}  ({os.path.getsize(OUT_JSON) / 1024:.1f} KB)')

    # CSV flat table
    csv_cols = ['rank', 'model', 'ext_pr_auc', 'ext_roc_auc',
                'ext_f1_at_0.59', 'ext_precision_at_0.59', 'ext_recall_at_0.59',
                'ext_accuracy_at_0.59', 'ext_ece_at_0.59',
                'val_optimal_threshold',
                'ext_f1_at_val_optimal', 'ext_precision_at_val_optimal',
                'ext_recall_at_val_optimal',
                'test_f1_at_0.59', 'test_f1_at_val_optimal',
                'classifier_size_mb', 'latency_batch1_ms_median',
                'fit_seconds']
    with open(OUT_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=csv_cols)
        w.writeheader()
        for i, r in enumerate(ranked, 1):
            d = r['external_at_deployed_0.59']
            o = r['external_at_val_optimal']
            t = r['test_at_deployed_0.59']
            to = r['test_at_val_optimal']
            w.writerow({
                'rank':                     i,
                'model':                    r['model'],
                'ext_pr_auc':               d.get('pr_auc'),
                'ext_roc_auc':              d.get('roc_auc'),
                'ext_f1_at_0.59':           d.get('f1'),
                'ext_precision_at_0.59':    d.get('precision'),
                'ext_recall_at_0.59':       d.get('recall'),
                'ext_accuracy_at_0.59':     d.get('accuracy'),
                'ext_ece_at_0.59':          d.get('ece'),
                'val_optimal_threshold':    r['val_optimal_threshold'],
                'ext_f1_at_val_optimal':    o.get('f1'),
                'ext_precision_at_val_optimal': o.get('precision'),
                'ext_recall_at_val_optimal':    o.get('recall'),
                'test_f1_at_0.59':          t.get('f1'),
                'test_f1_at_val_optimal':   to.get('f1'),
                'classifier_size_mb':       r['classifier_size_mb'],
                'latency_batch1_ms_median': r['latency_batch1_ms_median'],
                'fit_seconds':              r['fit_seconds'],
            })
    print(f'Saved {OUT_CSV}  ({os.path.getsize(OUT_CSV) / 1024:.1f} KB)')

    print(f'\n{"=" * 72}\n  RANKING  (primary = external PR-AUC @ 0.59)\n{"=" * 72}')
    for i, r in enumerate(ranked, 1):
        d = r['external_at_deployed_0.59']
        o = r['external_at_val_optimal']
        print(f'  {i}. {r["model"]:26s}  '
              f'PR-AUC={d.get("pr_auc")}  '
              f'F1@0.59={d.get("f1")}  '
              f'F1@val-opt={o.get("f1")}  '
              f'ECE={d.get("ece")}  '
              f'size={r["classifier_size_mb"]}MB  '
              f'lat={r["latency_batch1_ms_median"]}ms')
    print(f'\n  Winner: {winner}')


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    print('╔══════════════════════════════════════════════════════════════════════╗')
    print('║  E8-P9 FINAL CLASSIFIER BAKE-OFF                                     ║')
    print('║  raw-classifier comparison on the deployed E8-P9 training corpus     ║')
    print('╚══════════════════════════════════════════════════════════════════════╝')

    combined, ext = load_combined_and_external()

    print('\n─── Fitting shared preprocessing (once, reused across all candidates) ───')
    shared = build_shared_pipeline(combined, ext)

    shared_meta = {
        'feature_matrix_dim':     int(shared['X_tr'].shape[1]),
        'word_tfidf_params':      dict(E5_WORD_PARAMS),
        'char_tfidf_params':      dict(E5_CHAR_PARAMS),
        'n_numerical_features':   len(ALL_NUMERICAL),
        'numerical_features':     list(ALL_NUMERICAL),
        'scaler':                 'StandardScaler (fit on train)',
        'external_benchmark':     EXT_BENCHMARK,
        'external_benchmark_n':   int(shared['X_ex'].shape[0]),
        'train_n':                int(shared['X_tr'].shape[0]),
        'val_n':                  int(shared['X_va'].shape[0]),
        'test_n':                 int(shared['X_te'].shape[0]),
    }

    results = []
    for name, factory, description in CANDIDATES:
        results.append(train_and_evaluate(name, factory, description, shared))

    rank_and_write(results, shared_meta)


if __name__ == '__main__':
    main()
