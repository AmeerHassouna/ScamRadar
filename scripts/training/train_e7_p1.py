"""
E7 Phase 1 — Numerical feature fusion (5 ablation variants + E5 reference).

CONTROLLED EXPERIMENT: everything is E5's exact recipe. The only variable that
changes is which subset of the 25 already-implemented numerical features
(from src/features.py) is concatenated with the word + char
TF-IDF representation.

Variants trained:
  E7-P1-tone      : E5 features + 4 tone features
  E7-P1-url       : E5 features + 5 URL structural features
  E7-P1-phrase    : E5 features + 3 phrase / impersonation features
  E7-P1-textstats : E5 features + 13 text-statistics features
  E7-P1-full      : E5 features + all 25 numerical features

The `proximity_scam_score` feature is EXCLUDED — requires FAISS + Sentence
Transformers, which the user explicitly forbade in Phase 1.

Bundles saved to models/e7_p1_variants/*.joblib.
"""
from __future__ import annotations

import os
import re
import sys
import time
import json
import joblib
import warnings
import numpy as np
import pandas as pd

from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.features import (
    preprocess_text, compute_tone_features, compute_url_features,
    compute_new_features, extract_urls,
)

BASE_A = _ROOT
OUT_DIR = os.path.join(BASE_A, 'models', 'e7_p1_variants')
FEAT_PARQUET = os.path.join(BASE_A, 'data', 'interim', 'e7_p1_features.parquet')
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(FEAT_PARQUET), exist_ok=True)

# ─── E5 EXACT RECIPE ───────────────────────────────────────────────────────────
E5_LR_PARAMS = dict(
    C=5.968425624989058, penalty='l2', class_weight='balanced',
    max_iter=3000, solver='liblinear', tol=1e-4, fit_intercept=True,
    random_state=42,
)
E5_WORD_PARAMS = dict(
    ngram_range=(1, 2), min_df=3, max_df=0.9462114758401128,
    max_features=200000, sublinear_tf=True, lowercase=True,
)
E5_CHAR_PARAMS = dict(
    analyzer='char_wb', ngram_range=(3, 6), min_df=4, max_df=1.0,
    max_features=300000, sublinear_tf=True, lowercase=True,
)

# ─── FEATURE GROUP DEFINITIONS ─────────────────────────────────────────────────
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
ALL_NUMERICAL = FEATURE_GROUPS['tone'] + FEATURE_GROUPS['url'] + \
                FEATURE_GROUPS['phrase'] + FEATURE_GROUPS['textstats']

VARIANTS = {
    'e7_p1_tone':      FEATURE_GROUPS['tone'],
    'e7_p1_url':       FEATURE_GROUPS['url'],
    'e7_p1_phrase':    FEATURE_GROUPS['phrase'],
    'e7_p1_textstats': FEATURE_GROUPS['textstats'],
    'e7_p1_full':      ALL_NUMERICAL,
}


# ─── SELF-CONTAINED NUMERICAL FEATURE COMPUTATION ──────────────────────────────
_URL_RE = re.compile(r'https?://\S+|www\.\S+', re.I)


def compute_all_numerical(text: str) -> dict:
    """Compute every one of the 25 numerical features for a single message.
    Uses only the existing helpers from src/features.py."""
    t_raw = str(text) if text is not None else ''
    t_pre = preprocess_text(t_raw)

    # --- DB-derived features (computed inline, not from db) ---
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

    # --- Tone (via existing helper) ---
    urg, fear, reward, threat = compute_tone_features(t_pre)

    # --- URL structural (via existing helper) ---
    url_susp_tld, url_susp_kw, url_has_ip = compute_url_features(t_pre)

    # --- Phrase / impersonation / textstats (via existing helper) ---
    new = compute_new_features(t_pre)

    return {
        # DB-inline
        'text_length': text_length, 'word_count': word_count,
        'has_url': has_url, 'url_count': url_count,
        'exclamation_count': exclamation_count,
        'uppercase_ratio': uppercase_ratio, 'digit_ratio': digit_ratio,
        'urgency_score': urgency_score,
        # Tone
        'tone_urgency': urg, 'tone_fear': fear,
        'tone_reward': reward, 'tone_threat': threat,
        # URL
        'url_suspicious_tld': url_susp_tld,
        'url_suspicious_keyword': url_susp_kw,
        'url_has_ip': url_has_ip,
        # New engineered
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


def compute_features_for_df(df: pd.DataFrame, text_col: str = 'text') -> pd.DataFrame:
    print(f'  computing 25 numerical features for {len(df):,} rows...')
    t0 = time.time()
    feats = df[text_col].apply(compute_all_numerical)
    fdf = pd.DataFrame(list(feats.values), index=df.index)
    print(f'  done in {time.time()-t0:.1f}s')
    return fdf


# ─── LOAD DATA + PRECOMPUTE FEATURES ───────────────────────────────────────────
def load_or_compute_features():
    if os.path.exists(FEAT_PARQUET):
        print(f'Loading precomputed features from {FEAT_PARQUET}')
        combined = pd.read_parquet(FEAT_PARQUET)
        return combined

    print('Loading E5 training data (from canonical in-repo copy)...')
    CANONICAL = os.path.join(BASE_A, 'data', 'canonical')
    train = pd.read_parquet(f'{CANONICAL}/train.parquet')[['text', 'label', 'cluster_id']]
    val   = pd.read_parquet(f'{CANONICAL}/val.parquet')[['text', 'label', 'cluster_id']]
    test  = pd.read_parquet(f'{CANONICAL}/test.parquet')[['text', 'label', 'cluster_id']]
    ext   = pd.read_parquet(f'{CANONICAL}/external_benchmark.parquet')[['text', 'label']]
    train['split'] = 'train'; val['split'] = 'val'
    test['split']  = 'test';  ext['split'] = 'external'
    ext['cluster_id'] = -1  # external has no cluster id in this schema

    combined = pd.concat([train, val, test, ext], ignore_index=True)
    print(f'  train={len(train):,}  val={len(val):,}  test={len(test):,}  ext={len(ext):,}')

    fdf = compute_features_for_df(combined, text_col='text')
    combined = pd.concat([combined, fdf], axis=1)

    combined.to_parquet(FEAT_PARQUET, index=False)
    print(f'Saved {FEAT_PARQUET}')
    return combined


# ─── TRAINING ONE VARIANT ──────────────────────────────────────────────────────
def train_variant(variant_name: str, feature_cols: list[str],
                  combined: pd.DataFrame, out_dir: str):
    print(f'\n{"="*70}\nTRAINING VARIANT: {variant_name}  ({len(feature_cols)} numerical features)\n{"="*70}')

    train = combined[combined.split == 'train'].reset_index(drop=True)
    print(f'  train={len(train):,}  scam={int(train.label.sum()):,}  legit={int((train.label==0).sum()):,}')

    # 1. Fit vectorizers on train text (matching E5 exactly)
    print('  fitting word TF-IDF...')
    word_vec = TfidfVectorizer(**E5_WORD_PARAMS)
    Xw_tr = word_vec.fit_transform(train.text)
    print(f'    word: {Xw_tr.shape[1]:,} features')

    print('  fitting char TF-IDF...')
    char_vec = TfidfVectorizer(**E5_CHAR_PARAMS)
    Xc_tr = char_vec.fit_transform(train.text)
    print(f'    char: {Xc_tr.shape[1]:,} features')

    # 2. Numerical block
    Xn_tr_raw = train[feature_cols].values.astype(np.float64)
    scaler = StandardScaler()
    Xn_tr = scaler.fit_transform(Xn_tr_raw)
    print(f'    numerical: {Xn_tr.shape[1]} features (standardised)')

    # 3. Combine
    X_tr = hstack([Xw_tr, Xc_tr, csr_matrix(Xn_tr)]).tocsr()
    y_tr = train.label.values.astype(int)
    print(f'  combined X: {X_tr.shape}')

    # 4. Fit LR (E5's exact params)
    print('  fitting LogisticRegression...')
    t0 = time.time()
    clf = LogisticRegression(**E5_LR_PARAMS)
    clf.fit(X_tr, y_tr)
    print(f'    fit in {time.time()-t0:.1f}s')

    # 5. Save bundle
    bundle = {
        'variant': variant_name,
        'lr':             clf,
        'word_vec':       word_vec,
        'char_vec':       char_vec,
        'scaler':         scaler,
        'feature_cols':   feature_cols,
        'e5_recipe':      {'lr': E5_LR_PARAMS, 'word': E5_WORD_PARAMS, 'char': E5_CHAR_PARAMS},
        'threshold':      0.59,  # E5's F1-max — used as PRIMARY threshold in eval
    }
    out_path = os.path.join(out_dir, f'{variant_name}.joblib')
    joblib.dump(bundle, out_path)
    print(f'  saved {out_path}  ({os.path.getsize(out_path)/1e6:.1f} MB)')
    return bundle


def main():
    combined = load_or_compute_features()

    for variant_name, feature_cols in VARIANTS.items():
        train_variant(variant_name, feature_cols, combined, OUT_DIR)

    print('\n' + '='*70)
    print('ALL 5 VARIANTS TRAINED. Ready for evaluation.')
    print('='*70)
    print(f'Bundles: {OUT_DIR}/')
    for v in VARIANTS:
        p = os.path.join(OUT_DIR, f'{v}.joblib')
        if os.path.exists(p):
            print(f'  {v}: {os.path.getsize(p)/1e6:.1f} MB')


if __name__ == '__main__':
    main()
