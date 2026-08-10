"""
E7-P3 evaluation — E5 vs E7-P1-full vs E7-P3 (adds FAISS proximity).

Scores each model on:
  - E5 external benchmark (n=25,306)
  - Manual acceptance test (n=32)
  - E6 authentic corpus (n=97)

For E7-P3 evaluation: proximity features are already precomputed for
external + train/val/test in data/interim/e7_p3_features.parquet.
For acceptance test and E6 authentic corpus, we compute proximity
on the fly using the FAISS indices in models/e7_p3_faiss/.

Reports:
  outputs/e7_p3_report.md — full comparison
  outputs/eval/e7_p3_results.json — raw metrics
"""
from __future__ import annotations

import os, sys, json, warnings, time
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, roc_auc_score, average_precision_score,
                              confusion_matrix, brier_score_loss)
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BASE_A = _ROOT
BASE_B = '/Users/ameer/Downloads/scamradar2'
VARIANTS_DIR = os.path.join(BASE_A, 'models', 'e7_p1_variants')
FAISS_DIR = os.path.join(BASE_A, 'models', 'e7_p3_faiss')
FEAT_PARQUET = os.path.join(BASE_A, 'data', 'interim', 'e7_p3_features.parquet')

# Lazy globals — loaded once per process
_MINILM = None
_SCAM_IDX = None
_LEGIT_IDX = None
_NORM_FACTOR = None


def _ensure_faiss_loaded():
    global _MINILM, _SCAM_IDX, _LEGIT_IDX, _NORM_FACTOR
    if _MINILM is None:
        import faiss
        from sentence_transformers import SentenceTransformer
        _MINILM = SentenceTransformer('all-MiniLM-L6-v2')
        _SCAM_IDX = faiss.read_index(f'{FAISS_DIR}/scam_index.faiss')
        _LEGIT_IDX = faiss.read_index(f'{FAISS_DIR}/legit_index.faiss')
        _NORM_FACTOR = float(np.sqrt(_MINILM.get_sentence_embedding_dimension()))


def compute_proximity_features(texts, k=10):
    """Returns list of dicts with proximity_{scam,legit,delta}_score."""
    _ensure_faiss_loaded()
    embs = _MINILM.encode(texts, batch_size=64, show_progress_bar=False,
                           convert_to_numpy=True).astype(np.float32)
    scam_d, _ = _SCAM_IDX.search(embs, k)
    legit_d, _ = _LEGIT_IDX.search(embs, k)
    scam_sim  = 1.0 - (scam_d.mean(axis=1)  / _NORM_FACTOR)
    legit_sim = 1.0 - (legit_d.mean(axis=1) / _NORM_FACTOR)
    delta = scam_sim - legit_sim
    return [{'proximity_scam_score': float(s),
             'proximity_legit_score': float(l),
             'proximity_delta': float(d)}
            for s, l, d in zip(scam_sim, legit_sim, delta)]


# ─── Bundle loaders (three types) ─────────────────────────────────────────────
def load_e5():
    b = joblib.load(f'{BASE_A}/models/e5_bundle.joblib')
    return {'name': 'e5', 'model': b['model'], 'threshold': 0.59, 'kind': 'e5'}


def load_e7_p1_full():
    b = joblib.load(f'{VARIANTS_DIR}/e7_p1_full.joblib')
    return {
        'name': 'e7_p1_full',
        'lr': b['lr'], 'word_vec': b['word_vec'], 'char_vec': b['char_vec'],
        'scaler': b['scaler'], 'feature_cols': b['feature_cols'],
        'threshold': b.get('threshold', 0.59), 'kind': 'e7_p1',
    }


def load_e7_p3():
    b = joblib.load(f'{VARIANTS_DIR}/e7_p3_proximity.joblib')
    return {
        'name': 'e7_p3_proximity',
        'lr': b['lr'], 'word_vec': b['word_vec'], 'char_vec': b['char_vec'],
        'scaler': b['scaler'], 'feature_cols': b['feature_cols'],
        'threshold': b.get('threshold', 0.59), 'kind': 'e7_p3',
    }


# ─── Prediction ────────────────────────────────────────────────────────────────
def predict_proba(bundle, texts, numerical_df=None):
    if bundle['kind'] == 'e5':
        return bundle['model'].predict_proba(texts)[:, 1]
    # E7 variants
    Xw = bundle['word_vec'].transform(texts)
    Xc = bundle['char_vec'].transform(texts)
    if numerical_df is None:
        raise ValueError('need numerical features for E7 variant')
    Xn = numerical_df[bundle['feature_cols']].values.astype(np.float64)
    Xn = bundle['scaler'].transform(Xn)
    Xn = np.clip(Xn, -8.0, 8.0)
    X = hstack([Xw, Xc, csr_matrix(Xn)]).tocsr()
    return bundle['lr'].predict_proba(X)[:, 1]


# ─── Metric helper ─────────────────────────────────────────────────────────────
def score(y, p, threshold=0.59):
    y = np.asarray(y).astype(int); p = np.asarray(p)
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0,1]).ravel()
    m = {
        'n': int(len(y)),
        'accuracy':  round(float(accuracy_score(y, yhat)), 4),
        'precision': round(float(precision_score(y, yhat, zero_division=0)), 4),
        'recall':    round(float(recall_score(y, yhat, zero_division=0)), 4),
        'f1':        round(float(f1_score(y, yhat, zero_division=0)), 4),
        'confusion': {'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},
    }
    if len(set(y)) > 1:
        m['roc_auc'] = round(float(roc_auc_score(y, p)), 4)
        m['pr_auc']  = round(float(average_precision_score(y, p)), 4)
    return m


def per_category(y, p, cats, mode, threshold=0.59):
    y = np.asarray(y).astype(int); p = np.asarray(p)
    yhat = (p >= threshold).astype(int)
    out = {}
    arr = np.asarray(cats)
    for c in sorted(set(cats)):
        m = arr == c
        if m.sum() == 0: continue
        y_c, yhat_c = y[m], yhat[m]
        if mode == 'recall':
            if y_c.sum() == 0: continue
            out[c] = {'n': int(m.sum()),
                      'recall': round(float(recall_score(y_c, yhat_c, zero_division=0)), 4)}
        else:
            if (y_c==0).sum() == 0: continue
            fpr = ((yhat_c==1)&(y_c==0)).sum() / (y_c==0).sum()
            out[c] = {'n': int(m.sum()), 'fp_rate': round(float(fpr), 4)}
    return out


# ─── Data loaders ──────────────────────────────────────────────────────────────
def load_all():
    print('Loading features parquet + eval sets...', flush=True)
    feats = pd.read_parquet(FEAT_PARQUET)
    ext_full = pd.read_parquet(f'{BASE_B}/data/external_benchmark/benchmark.parquet')

    from tests.manual_acceptance_test import TESTS
    acc = pd.DataFrame([{'text': t, 'label': 0, 'category': c} for c, t in TESTS])

    e6 = pd.read_parquet(f'{BASE_A}/data/interim/e6/e6_augmentation.parquet')[
        ['text','label','category']].reset_index(drop=True)

    # For acceptance + e6, compute numerical features (E7-P1 + proximity)
    from scripts.training.train_e7_p1 import compute_all_numerical
    def add_e7_p1(df):
        rows = df['text'].apply(compute_all_numerical)
        return pd.concat([df, pd.DataFrame(list(rows.values), index=df.index)], axis=1)

    def add_proximity(df):
        prox = compute_proximity_features(df['text'].tolist())
        return pd.concat([df, pd.DataFrame(prox, index=df.index)], axis=1)

    print('  computing E7-P1 features on acceptance + E6...', flush=True)
    acc = add_e7_p1(acc); e6 = add_e7_p1(e6)
    print('  computing proximity features on acceptance + E6...', flush=True)
    acc = add_proximity(acc); e6 = add_proximity(e6)

    # External benchmark: features + proximity are in the parquet
    ext_feats = feats[feats.split == 'external'].reset_index(drop=True)
    ext_feats = ext_feats.merge(ext_full[['text','category']], on='text', how='left')

    return feats, ext_full, ext_feats, acc, e6


def main():
    feats, ext_full, ext_feats, acc_df, e6_df = load_all()

    bundles = [load_e5(), load_e7_p1_full(), load_e7_p3()]
    print(f'Bundles: {[b["name"] for b in bundles]}\n', flush=True)

    results = {}
    probs   = {}

    for b in bundles:
        print(f'=== {b["name"]} ===', flush=True)
        results[b['name']] = {}
        probs[b['name']]   = {}

        # External
        p_ext = predict_proba(b, ext_full.text.tolist(),
                              numerical_df=ext_feats if b['kind'] != 'e5' else None)
        probs[b['name']]['external'] = p_ext
        results[b['name']]['external'] = score(ext_full.label.values, p_ext)
        results[b['name']]['external']['per_scam_recall'] = per_category(
            ext_full.label.values, p_ext, ext_full.category.values, 'recall')
        results[b['name']]['external']['per_legit_fp'] = per_category(
            ext_full.label.values, p_ext, ext_full.category.values, 'fp_rate')

        # Acceptance test
        p_acc = predict_proba(b, acc_df.text.tolist(),
                              numerical_df=acc_df if b['kind'] != 'e5' else None)
        probs[b['name']]['acceptance'] = p_acc
        m = score(acc_df.label.values, p_acc)
        m['fp_rate'] = round(float(((p_acc >= 0.59).sum()) / len(p_acc)), 4)
        results[b['name']]['acceptance'] = m

        # E6 authentic
        p_e6 = predict_proba(b, e6_df.text.tolist(),
                             numerical_df=e6_df if b['kind'] != 'e5' else None)
        probs[b['name']]['e6'] = p_e6
        results[b['name']]['e6'] = score(e6_df.label.values, p_e6)

        ext = results[b['name']]['external']
        acc = results[b['name']]['acceptance']
        print(f'  external:   F1={ext["f1"]}  P={ext["precision"]}  R={ext["recall"]}  '
              f'PR-AUC={ext.get("pr_auc","-")}', flush=True)
        print(f'  acceptance: FP={acc["fp_rate"]*100:.1f}% ({acc["confusion"]["fp"]}/{acc["n"]})', flush=True)
        print(f'  e6:         F1={results[b["name"]]["e6"]["f1"]}', flush=True)

    # ── Coefficient inspection for proximity features specifically
    print('\n=== Proximity coefficient inspection (e7_p3) ===', flush=True)
    e7p3 = [b for b in bundles if b['name'] == 'e7_p3_proximity'][0]
    n_word = len(e7p3['word_vec'].vocabulary_)
    n_char = len(e7p3['char_vec'].vocabulary_)
    num_coefs = e7p3['lr'].coef_[0][n_word + n_char:]
    coef_dict = {fc: float(c) for fc, c in zip(e7p3['feature_cols'], num_coefs)}
    for fc in ['proximity_scam_score', 'proximity_legit_score', 'proximity_delta']:
        print(f'  {fc:24s} coef={coef_dict[fc]:+.4f}', flush=True)

    # Save results
    out_json = f'{BASE_A}/outputs/eval/e7_p3_results.json'
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    # Convert numpy scalars → python
    def _pyify(x):
        if isinstance(x, dict): return {k: _pyify(v) for k,v in x.items()}
        if isinstance(x, list): return [_pyify(v) for v in x]
        if isinstance(x, (np.integer, np.floating)): return float(x)
        return x
    with open(out_json, 'w') as f:
        json.dump({
            'results': _pyify(results),
            'proximity_coefficients': coef_dict,
        }, f, indent=2)
    print(f'\nSaved {out_json}', flush=True)


if __name__ == '__main__':
    main()
