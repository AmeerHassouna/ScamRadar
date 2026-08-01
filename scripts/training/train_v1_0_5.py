"""
Train v1.0.5_candidate — LEAKAGE FIXES ONLY (no deduplication).

Purpose: ablation isolating the effect of removing train/test fitting leakage
from the effect of deduplication. Same corpus and same split methodology as
v1.0; only the fitting-order changes:

  1. Split BEFORE fitting any statistic (row-level, seed=42, stratified — same
     split rows as v1.0's original training).
  2. Fit TF-IDF word + char vectorizers on train slice only, transform test.
  3. Fit StandardScaler on train slice only, transform test.
  4. Build scam + legit FAISS indices from train-slice embeddings only.

DIFFERS FROM v1.1: no deduplication step. Trains on the full 46,360-row corpus.

All artefacts → models/v1.0.5_candidate/. models/*.pkl untouched.

Usage:
    python scripts/train_v1_0_5.py
"""

import os, sys, sqlite3, pickle, time
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             precision_score, recall_score, classification_report,
                             confusion_matrix)
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DB_PATH, NUMERICAL_FEATURES_V5
from src._00_dedup import add_cluster_ids   # used only to preserve cluster_id column for eval bucketing
from src._02_feature_engineering import add_features

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_DIR  = os.path.join(BASE_DIR, 'models', 'v1.0.5_candidate')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 1: LOAD DATA (full 46K corpus — no dedup)")
print("="*72)

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT m.message_id, m.raw_text, m.label,
           c.type AS channel, ds.name AS source,
           mf.text_length, mf.word_count, mf.has_url, mf.url_count,
           mf.exclamation_count, mf.uppercase_ratio, mf.digit_ratio, mf.urgency_score
    FROM Message m
    JOIN Channel c ON m.channel_id = c.channel_id
    JOIN DataSource ds ON m.source_id = ds.source_id
    JOIN MessageFeatures mf ON m.message_id = mf.message_id
    ORDER BY m.message_id
""", conn)
conn.close()
print(f"✅ Loaded {len(df):,} rows (no dedup applied)")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: FEATURE ENGINEERING (unchanged from main.py)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 2: FEATURE ENGINEERING")
print("="*72)
df = add_features(df)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: ROW-LEVEL SPLIT (SAME METHODOLOGY AS v1.0)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 3: ROW-LEVEL SPLIT (seed=42, stratified — same as v1.0)")
print("="*72)

train_idx, test_idx = train_test_split(
    np.arange(len(df)), test_size=0.20, random_state=42,
    stratify=df['label'].values,
)
train_mask = np.zeros(len(df), dtype=bool); train_mask[train_idx] = True
test_mask  = ~train_mask
print(f"✅ Train: {train_mask.sum():,}   Test: {test_mask.sum():,}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: EMBED ALL, BUILD FAISS FROM TRAIN ONLY
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 4: SENTENCE-TRANSFORMER ENCODING + TRAIN-ONLY FAISS INDICES")
print("="*72)

from src._04_vector_proximity import (
    load_sentence_model, build_faiss_index, build_legit_faiss_index,
    compute_proximity_scores,
)
import faiss

st_model = load_sentence_model()
print(f"Encoding {len(df):,} messages …")
t0 = time.time()
embeddings = st_model.encode(
    df['raw_text'].fillna('').tolist(),
    batch_size=128, show_progress_bar=True, convert_to_numpy=True,
)
print(f"✅ Embeddings shape: {embeddings.shape}  (in {time.time()-t0:.1f}s)")

train_embeddings = embeddings[train_mask]
train_labels     = df.loc[train_mask, 'label'].values

scam_index  = build_faiss_index(train_embeddings, train_labels)
legit_index = build_legit_faiss_index(train_embeddings, train_labels)

prox_scam, prox_legit, prox_delta = compute_proximity_scores(
    embeddings, scam_index, legit_index
)
df['proximity_scam_score']  = prox_scam * 0.5
df['legit_proximity_score'] = prox_legit
df['proximity_delta']       = prox_delta

faiss.write_index(scam_index,  os.path.join(CANDIDATE_DIR, 'scam_faiss.index'))
faiss.write_index(legit_index, os.path.join(CANDIDATE_DIR, 'legit_faiss.index'))
np.save(os.path.join(CANDIDATE_DIR, 'embeddings.npy'), embeddings)
print(f"✅ FAISS indices saved to {CANDIDATE_DIR}/")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: TF-IDF FIT ON TRAIN, TRANSFORM TEST
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 5: TF-IDF FIT ON TRAIN SLICE")
print("="*72)

train_texts = df.loc[train_mask, 'raw_text'].fillna('').values
test_texts  = df.loc[test_mask,  'raw_text'].fillna('').values

tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2),
                        stop_words='english', sublinear_tf=True)
X_tfidf_train = tfidf.fit_transform(train_texts)
X_tfidf_test  = tfidf.transform(test_texts)
print(f"✅ Word TF-IDF — train: {X_tfidf_train.shape}   test: {X_tfidf_test.shape}")

char_tfidf = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                             max_features=3000, sublinear_tf=True)
X_char_train = char_tfidf.fit_transform(train_texts)
X_char_test  = char_tfidf.transform(test_texts)
print(f"✅ Char TF-IDF — train: {X_char_train.shape}   test: {X_char_test.shape}")

pickle.dump(tfidf,      open(os.path.join(CANDIDATE_DIR, 'tfidf_vectorizer.pkl'), 'wb'))
pickle.dump(char_tfidf, open(os.path.join(CANDIDATE_DIR, 'char_vectorizer.pkl'),  'wb'))
print(f"✅ TF-IDF vectorizers saved")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: STANDARDSCALER FIT ON TRAIN
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 6: STANDARDSCALER FIT ON TRAIN SLICE")
print("="*72)

X_num_train = df.loc[train_mask, NUMERICAL_FEATURES_V5].fillna(0).values
X_num_test  = df.loc[test_mask,  NUMERICAL_FEATURES_V5].fillna(0).values

scaler = StandardScaler()
X_num_train_s = scaler.fit_transform(X_num_train)
X_num_test_s  = scaler.transform(X_num_test)
print(f"✅ Numerical — train: {X_num_train_s.shape}   test: {X_num_test_s.shape}")
pickle.dump(scaler, open(os.path.join(CANDIDATE_DIR, 'scaler.pkl'), 'wb'))
print(f"✅ Scaler saved")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: BUILD COMBINED FEATURE MATRICES
# ══════════════════════════════════════════════════════════════════════════════
X_train = hstack([X_tfidf_train, X_char_train, csr_matrix(X_num_train_s)])
X_test  = hstack([X_tfidf_test,  X_char_test,  csr_matrix(X_num_test_s)])
y_train = df.loc[train_mask, 'label'].values
y_test  = df.loc[test_mask,  'label'].values
print(f"\n✅ Combined — train: {X_train.shape}   test: {X_test.shape}")
assert X_train.shape[1] == X_test.shape[1], "Train/test feature dim mismatch"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: TRAIN + PICK BEST BY F1
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 8: TRAIN + EVALUATE")
print("="*72)

from src._05_model_training import (
    train_all_models, calibrate_model, find_optimal_threshold,
)
trained = train_all_models(X_train, y_train)

results = {}
for name, m in trained.items():
    y_pred = m.predict(X_test)
    y_prob = m.predict_proba(X_test)[:, 1]
    results[name] = {
        'Accuracy':  accuracy_score(y_test, y_pred),
        'Precision': precision_score(y_test, y_pred, zero_division=0),
        'Recall':    recall_score(y_test, y_pred, zero_division=0),
        'F1':        f1_score(y_test, y_pred, zero_division=0),
        'AUC':       roc_auc_score(y_test, y_prob),
    }
    print(f"\n{name}:")
    for k, v in results[name].items():
        print(f"  {k:10s}  {v:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: CALIBRATE + PICK THRESHOLD
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("STEP 9: CALIBRATION + THRESHOLD OPTIMISATION")
print("="*72)

best_name = max(results, key=lambda n: results[n]['F1'])
best_raw  = trained[best_name]
print(f"Best raw: {best_name} (F1={results[best_name]['F1']:.4f})")

X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=42, stratify=y_train
)
best_raw.fit(X_tr2, y_tr2)
calibrated = calibrate_model(best_raw, X_cal, y_cal)
opt_thresh, _ = find_optimal_threshold(calibrated, X_cal, y_cal)

y_prob_cal = calibrated.predict_proba(X_test)[:, 1]
y_pred_cal = (y_prob_cal >= opt_thresh).astype(int)
final_metrics = {
    'Accuracy':  accuracy_score(y_test, y_pred_cal),
    'Precision': precision_score(y_test, y_pred_cal, zero_division=0),
    'Recall':    recall_score(y_test, y_pred_cal, zero_division=0),
    'F1':        f1_score(y_test, y_pred_cal, zero_division=0),
    'AUC':       roc_auc_score(y_test, y_prob_cal),
}
tn, fp, fn, tp = confusion_matrix(y_test, y_pred_cal).ravel()

print(f"\nCalibrated {best_name} — internal test (threshold={opt_thresh:.2f}):")
for k, v in final_metrics.items():
    print(f"  {k:10s}  {v:.4f}")
print(f"  Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}")
print(classification_report(y_test, y_pred_cal, target_names=['Legit','Scam']))

# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: SAVE
# ══════════════════════════════════════════════════════════════════════════════
model_payload = {'model': calibrated, 'threshold': float(opt_thresh)}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))
print(f"\n✅ Model saved to {CANDIDATE_DIR}/scamradar_model.pkl (threshold={opt_thresh:.2f})")

expected = ['scamradar_model.pkl', 'tfidf_vectorizer.pkl', 'char_vectorizer.pkl',
            'scaler.pkl', 'scam_faiss.index', 'legit_faiss.index', 'embeddings.npy']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing candidate artefacts: {missing}")
print(f"\n✅ All 7 artefacts present in {CANDIDATE_DIR}/")
print(f"\nDone — internal test F1={final_metrics['F1']:.4f}")
