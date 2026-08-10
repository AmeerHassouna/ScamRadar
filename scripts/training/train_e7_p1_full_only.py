"""Train ONLY the e7_p1_full variant with reduced max_iter to avoid the
30-min textstats slowdown. Everything else identical to E5."""
import os, sys, time, joblib, warnings, numpy as np, pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning
warnings.filterwarnings('error', category=ConvergenceWarning)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

BASE_A = _ROOT
OUT_DIR = os.path.join(BASE_A, 'models', 'e7_p1_variants')
FEAT_PARQUET = os.path.join(BASE_A, 'data', 'interim', 'e7_p1_features.parquet')

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

# E5 recipe, only max_iter reduced from 3000 → 500
LR_PARAMS = dict(
    C=5.968425624989058, penalty='l2', class_weight='balanced',
    max_iter=500, solver='liblinear', tol=1e-4, fit_intercept=True,
    random_state=42,
)
WORD = dict(ngram_range=(1,2), min_df=3, max_df=0.9462114758401128,
            max_features=200000, sublinear_tf=True, lowercase=True)
CHAR = dict(analyzer='char_wb', ngram_range=(3,6), min_df=4, max_df=1.0,
            max_features=300000, sublinear_tf=True, lowercase=True)


def main():
    print('Loading precomputed features from parquet...', flush=True)
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

    print('Standardising 25 numerical features...', flush=True)
    Xn_raw = train[ALL_NUMERICAL].values.astype(np.float64)
    scaler = StandardScaler()
    Xn = scaler.fit_transform(Xn_raw)
    print(f'  z-score range: [{Xn.min():.2f}, {Xn.max():.2f}]', flush=True)
    # Clip extreme z-scores to control conditioning (data hygiene, not model change)
    Xn = np.clip(Xn, -8.0, 8.0)
    print(f'  after clip to ±8σ: [{Xn.min():.2f}, {Xn.max():.2f}]', flush=True)

    X = hstack([Xw, Xc, csr_matrix(Xn)]).tocsr()
    y = train.label.values.astype(int)
    print(f'\nCombined X: {X.shape} sparse nnz={X.nnz:,}', flush=True)
    print('Freeing intermediates...', flush=True)
    del Xw, Xc, Xn, Xn_raw
    import gc; gc.collect()

    print(f'Fitting LR (max_iter=500)...', flush=True)
    t0 = time.time()
    converged = True
    try:
        clf = LogisticRegression(**LR_PARAMS)
        clf.fit(X, y)
    except ConvergenceWarning as e:
        print(f'  ⚠ CONVERGENCE WARNING: {e}', flush=True)
        converged = False
        # Re-fit with warnings-as-warnings so we still get the model
        warnings.filterwarnings('default', category=ConvergenceWarning)
        clf = LogisticRegression(**LR_PARAMS)
        clf.fit(X, y)
    print(f'  fit in {time.time()-t0:.1f}s   converged={converged}', flush=True)

    bundle = {
        'variant': 'e7_p1_full',
        'lr': clf, 'word_vec': word_vec, 'char_vec': char_vec, 'scaler': scaler,
        'feature_cols': ALL_NUMERICAL,
        'threshold': 0.59,
        'converged': converged,
        'lr_params': LR_PARAMS,
        'note': 'max_iter=500 (reduced from E5s 3000 due to convergence time on 25-feature block); features clipped to ±8σ post-standardization',
    }
    out = os.path.join(OUT_DIR, 'e7_p1_full.joblib')
    joblib.dump(bundle, out)
    print(f'Saved {out} ({os.path.getsize(out)/1e6:.1f} MB)', flush=True)


if __name__ == '__main__':
    main()
