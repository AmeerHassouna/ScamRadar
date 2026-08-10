"""
E7-P3 — Train E7-P1-full + 3 FAISS proximity features.

Same recipe as E7-P1-full (E5 LR hyperparams, E5 TF-IDF params, seed 42),
only variable changed: numerical features go from 25 → 28 (added
proximity_scam_score, proximity_legit_score, proximity_delta).

Saves bundle to models/e7_p1_variants/e7_p3_proximity.joblib.
"""
from __future__ import annotations

import os, sys, time, joblib, warnings
import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

BASE_A = _ROOT
OUT_DIR = os.path.join(BASE_A, 'models', 'e7_p1_variants')
FEAT_PARQUET = os.path.join(BASE_A, 'data', 'interim', 'e7_p3_features.parquet')

# E5 recipe with reduced max_iter (same as e7_p1_full)
LR_PARAMS = dict(
    C=5.968425624989058, penalty='l2', class_weight='balanced',
    max_iter=500, solver='liblinear', tol=1e-4, fit_intercept=True,
    random_state=42,
)
WORD = dict(ngram_range=(1,2), min_df=3, max_df=0.9462114758401128,
            max_features=200000, sublinear_tf=True, lowercase=True)
CHAR = dict(analyzer='char_wb', ngram_range=(3,6), min_df=4, max_df=1.0,
            max_features=300000, sublinear_tf=True, lowercase=True)

# E7-P1-full's 25 features + 3 new proximity features = 28
ALL_NUMERICAL = [
    # Tone (4)
    'tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat',
    # URL (5)
    'has_url', 'url_count', 'url_suspicious_tld',
    'url_suspicious_keyword', 'url_has_ip',
    # Phrase (3)
    'scam_phrase_score', 'sender_impersonation_score', 'legit_phrase_score',
    # Text stats (13)
    'text_length', 'word_count', 'exclamation_count', 'uppercase_ratio',
    'digit_ratio', 'urgency_score', 'avg_word_length',
    'capitalized_word_count', 'punctuation_density',
    'question_mark_count', 'currency_symbol_count',
    'readability_score', 'unique_word_ratio',
    # Proximity (3) - NEW
    'proximity_scam_score', 'proximity_legit_score', 'proximity_delta',
]


def main():
    print('=== E7-P3: train with FAISS proximity features ===', flush=True)
    print(f'Loading precomputed features from {FEAT_PARQUET}...', flush=True)
    combined = pd.read_parquet(FEAT_PARQUET)
    train = combined[combined.split == 'train'].reset_index(drop=True)
    print(f'  train={len(train):,}  scam={int(train.label.sum()):,}', flush=True)

    print('\nFitting word TF-IDF...', flush=True)
    word_vec = TfidfVectorizer(**WORD)
    Xw = word_vec.fit_transform(train.text)
    print(f'  {Xw.shape[1]:,} features', flush=True)

    print('Fitting char TF-IDF...', flush=True)
    char_vec = TfidfVectorizer(**CHAR)
    Xc = char_vec.fit_transform(train.text)
    print(f'  {Xc.shape[1]:,} features', flush=True)

    print(f'Standardising {len(ALL_NUMERICAL)} numerical features...', flush=True)
    Xn_raw = train[ALL_NUMERICAL].values.astype(np.float64)
    scaler = StandardScaler()
    Xn = scaler.fit_transform(Xn_raw)
    print(f'  z-score range: [{Xn.min():.2f}, {Xn.max():.2f}]', flush=True)
    Xn = np.clip(Xn, -8.0, 8.0)  # matches E7-P1-full training hygiene

    X = hstack([Xw, Xc, csr_matrix(Xn)]).tocsr()
    y = train.label.values.astype(int)
    print(f'\nCombined X: {X.shape} sparse nnz={X.nnz:,}', flush=True)
    print('Freeing intermediates...', flush=True)
    del Xw, Xc, Xn, Xn_raw
    import gc; gc.collect()

    print(f'Fitting LR (max_iter=500)...', flush=True)
    t0 = time.time()
    clf = LogisticRegression(**LR_PARAMS)
    clf.fit(X, y)
    print(f'  fit in {time.time()-t0:.1f}s', flush=True)

    # Save bundle
    bundle = {
        'variant': 'e7_p3_proximity',
        'lr': clf, 'word_vec': word_vec, 'char_vec': char_vec, 'scaler': scaler,
        'feature_cols': ALL_NUMERICAL,
        'threshold': 0.59,
        'lr_params': LR_PARAMS,
        'note': ('E7-P1-full recipe + 3 FAISS proximity features (proximity_scam_score, '
                 'proximity_legit_score, proximity_delta). Proximity features require '
                 'MiniLM + FAISS indices at inference time.'),
    }
    out = os.path.join(OUT_DIR, 'e7_p3_proximity.joblib')
    joblib.dump(bundle, out)
    print(f'Saved {out} ({os.path.getsize(out)/1e6:.1f} MB)', flush=True)


if __name__ == '__main__':
    main()
