"""
═══════════════════════════════════════════════════════════════════════════════
  ARCHIVED RESEARCH ARTEFACT — REJECTED EXPERIMENT
═══════════════════════════════════════════════════════════════════════════════
  v1.5 was designed as a single-variable ablation testing whether frozen
  MiniLM sentence embeddings would outperform word TF-IDF for scam detection.
  It was evaluated once on the reserved external 400-item set and REJECTED
  per the pre-committed ship criterion.

  Outcome (from outputs/eval/v1.5_candidate_external.json):
    External F1:  v1.3 = 0.8734  →  v1.5 = 0.8703   (Δ = −0.0031)
    Ship criterion (≥ +1.0 F1 pt): FAILED. v1.3 retained as final model.

  Interpretation: for this corpus, semantic MiniLM embeddings and surface-token
  TF-IDF produce statistically-equivalent scam-detection signal. The OOD gap
  is not driven by text-representation limitations. See intervention_log.md.

  This script requires the (deleted) models/v1.5_candidate/ directory. To
  reproduce: re-run this script — it will re-create the directory from scratch.
═══════════════════════════════════════════════════════════════════════════════

Train v1.5_candidate — frozen MiniLM sentence embeddings replace word TF-IDF.

Single controlled variable vs v1.3:
  * word TF-IDF (5,000 sparse features)  →  MiniLM sentence embeddings (384 dense features)

Unchanged from v1.3:
  * Same corpus (46,360 DB rows + 1,133 external additions → 22,546 dedup clusters)
  * Same cluster-aware split (outputs/split_v1.json)
  * Same train-only fitting of char_tfidf / scaler / FAISS
  * Same char TF-IDF (3,000 features)
  * Same 26 numerical features (NUMERICAL_FEATURES_V5)
  * Same FAISS proximity feature
  * Same RF hyperparameters (n_estimators=200, max_depth=None, ...)
  * Same isotonic calibration procedure
  * Same threshold sweep (F1-maximising) on the training-side val slice
  * Same random seed = 42

No production code changes. This is a purely offline experiment.
External 400-item set is not touched during training.
"""
import os, sys, sqlite3, pickle, json, time, csv, hashlib, shutil
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             precision_score, recall_score, classification_report,
                             confusion_matrix)
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DB_PATH, NUMERICAL_FEATURES_V5
from src._00_dedup import add_cluster_ids, dedup_by_cluster
from src._02_feature_engineering import add_features
from src._05_model_training import calibrate_model, find_optimal_threshold

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_DIR  = os.path.join(BASE_DIR, 'models', 'v1.5_candidate')
SPLIT_PATH     = os.path.join(BASE_DIR, 'outputs', 'split_v1.json')
EXTERNAL_CSV   = os.path.join(BASE_DIR, 'data', 'external_training', 'external_train.csv')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

V1_3_HYPERPARAMS = {
    'n_estimators':     200,
    'max_depth':        None,
    'min_samples_leaf': 1,
    'max_features':     'sqrt',
    'class_weight':     None,
    'random_state':     42,
    'n_jobs':           -1,
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — LOAD + DEDUP + SPLIT (identical to v1.3)
# ══════════════════════════════════════════════════════════════════════════════
print("STEP 1: LOAD + DEDUP + SPLIT (identical to v1.3)", flush=True)
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
ext_rows = []
with open(EXTERNAL_CSV, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        ext_rows.append({
            'raw_text':          r['raw_text'],
            'label':             int(r['label']),
            'source':            r['source'],
            'channel':           'email' if 'phishing' in r['source'] else 'reddit',
            'text_length':       0, 'word_count': 0, 'has_url': 0, 'url_count': 0,
            'exclamation_count': 0, 'uppercase_ratio': 0.0,
            'digit_ratio':       0.0, 'urgency_score': 0.0,
        })
ext_df = pd.DataFrame(ext_rows)
next_id = int(df['message_id'].max() or 0) + 1
ext_df['message_id'] = np.arange(next_id, next_id + len(ext_df))
df = pd.concat([df, ext_df], ignore_index=True)

df = add_cluster_ids(df)
df = dedup_by_cluster(df, strategy='longest')
print(f"  Corpus after dedup: {len(df):,} clusters", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — FEATURE ENGINEERING (identical to v1.3, produces V5 features)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2: FEATURE ENGINEERING (V5, identical to v1.3)", flush=True)
df = add_features(df)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SPLIT ASSIGNMENT (identical to v1.3)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3: SPLIT ASSIGNMENT (from outputs/split_v1.json, extended for new clusters)", flush=True)
with open(SPLIT_PATH) as f:
    split_map = dict(json.load(f))
for cid in df['cluster_id']:
    if cid not in split_map:
        split_map[cid] = 'train'
df['split'] = df['cluster_id'].map(split_map)
train_mask = (df['split'] == 'train').values
test_mask  = (df['split'] == 'test').values
print(f"  Train: {train_mask.sum():,}   Test: {test_mask.sum():,}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — EMBEDDINGS (MiniLM) + TRAIN-ONLY FAISS (identical to v1.3)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 4: MINILM EMBEDDINGS + TRAIN-ONLY FAISS", flush=True)
from src._04_vector_proximity import (
    load_sentence_model, build_faiss_index, build_legit_faiss_index,
    compute_proximity_scores,
)
import faiss

st_model = load_sentence_model()
t0 = time.time()
print(f"  Encoding {len(df):,} clusters via all-MiniLM-L6-v2 (CPU)…", flush=True)
embeddings = st_model.encode(df['raw_text'].fillna('').tolist(),
                             batch_size=128, show_progress_bar=False,
                             convert_to_numpy=True)
print(f"  Embedding shape: {embeddings.shape}  ({time.time()-t0:.1f}s)", flush=True)

# Save a raw (un-normalised) copy for reproducibility — same as v1.3
np.save(os.path.join(CANDIDATE_DIR, 'embeddings.npy'), embeddings)

# Build FAISS from train slice only (for proximity_scam_score numerical feature)
scam_idx  = build_faiss_index(embeddings[train_mask],  df.loc[train_mask, 'label'].values)
legit_idx = build_legit_faiss_index(embeddings[train_mask], df.loc[train_mask, 'label'].values)
prox_scam, prox_legit, prox_delta = compute_proximity_scores(embeddings, scam_idx, legit_idx)
df['proximity_scam_score']  = prox_scam * 0.5   # scale identical to v1.3
df['legit_proximity_score'] = prox_legit
df['proximity_delta']       = prox_delta

faiss.write_index(scam_idx,  os.path.join(CANDIDATE_DIR, 'scam_faiss.index'))
faiss.write_index(legit_idx, os.path.join(CANDIDATE_DIR, 'legit_faiss.index'))

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — CHAR TF-IDF FIT ON TRAIN SLICE (identical to v1.3)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5: CHAR TF-IDF FIT ON TRAIN SLICE (word TF-IDF DROPPED per v1.5 spec)", flush=True)
train_texts = df.loc[train_mask, 'raw_text'].fillna('').values
test_texts  = df.loc[test_mask,  'raw_text'].fillna('').values

char_tfidf = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                             max_features=3000, sublinear_tf=True)
X_char_train = char_tfidf.fit_transform(train_texts)
X_char_test  = char_tfidf.transform(test_texts)
pickle.dump(char_tfidf, open(os.path.join(CANDIDATE_DIR, 'char_vectorizer.pkl'), 'wb'))
print(f"  Char TF-IDF: train {X_char_train.shape}, test {X_char_test.shape}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — NUMERICAL FEATURES SCALED ON TRAIN SLICE (V5, identical to v1.3)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 6: NUMERICAL FEATURES (V5, 26 features)", flush=True)
X_num_train = df.loc[train_mask, NUMERICAL_FEATURES_V5].fillna(0).values
X_num_test  = df.loc[test_mask,  NUMERICAL_FEATURES_V5].fillna(0).values
scaler = StandardScaler()
X_num_train_s = scaler.fit_transform(X_num_train)
X_num_test_s  = scaler.transform(X_num_test)
pickle.dump(scaler, open(os.path.join(CANDIDATE_DIR, 'scaler.pkl'), 'wb'))
print(f"  Numerical: train {X_num_train_s.shape}, test {X_num_test_s.shape}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — v1.5 FEATURE MATRIX = [MiniLM, char_tfidf, numerical_scaled]
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 7: BUILD v1.5 FEATURE MATRIX", flush=True)
E_train = embeddings[train_mask]   # (n_train, 384)  — dense
E_test  = embeddings[test_mask]    # (n_test,  384)
print(f"  MiniLM: train {E_train.shape}, test {E_test.shape}", flush=True)

# hstack expects sparse-or-dense mix; convert MiniLM to sparse to concat with char_tfidf
X_train = hstack([csr_matrix(E_train), X_char_train, csr_matrix(X_num_train_s)])
X_test  = hstack([csr_matrix(E_test),  X_char_test,  csr_matrix(X_num_test_s)])
y_train = df.loc[train_mask, 'label'].values
y_test  = df.loc[test_mask,  'label'].values
print(f"  Combined — train: {X_train.shape}   test: {X_test.shape}", flush=True)
assert X_train.shape[1] == X_test.shape[1] == 384 + 3000 + 26 == 3410, \
    f"Feature dim mismatch: expected 3410, got train={X_train.shape[1]}, test={X_test.shape[1]}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — TRAIN + CALIBRATE + THRESHOLD (identical procedure to v1.3)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 8: TRAIN + CALIBRATE + THRESHOLD (v1.3 hyperparameters)", flush=True)
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=42, stratify=y_train
)
rf = RandomForestClassifier(**V1_3_HYPERPARAMS)
t0 = time.time()
rf.fit(X_tr2, y_tr2)
print(f"  RF fit in {time.time()-t0:.1f}s", flush=True)

calibrated = calibrate_model(rf, X_cal, y_cal)
opt_thresh, _ = find_optimal_threshold(calibrated, X_cal, y_cal)
print(f"  Optimal threshold: {opt_thresh}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — INTERNAL TEST MEASUREMENT
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 9: INTERNAL TEST", flush=True)
y_prob_cal = calibrated.predict_proba(X_test)[:, 1]
y_pred_cal = (y_prob_cal >= opt_thresh).astype(int)
final = {
    'Accuracy':  float(accuracy_score(y_test, y_pred_cal)),
    'Precision': float(precision_score(y_test, y_pred_cal, zero_division=0)),
    'Recall':    float(recall_score(y_test, y_pred_cal, zero_division=0)),
    'F1':        float(f1_score(y_test, y_pred_cal, zero_division=0)),
    'AUC':       float(roc_auc_score(y_test, y_prob_cal)),
}
tn, fp, fn, tp = confusion_matrix(y_test, y_pred_cal).ravel()
print(f"  Internal test (threshold={opt_thresh:.2f}):")
for k, v in final.items():
    print(f"    {k:10s}  {v:.4f}", flush=True)
print(f"    Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 10 — SAVE
# ══════════════════════════════════════════════════════════════════════════════
model_payload = {
    'model':             calibrated,
    'threshold':         float(opt_thresh),
    'hyperparameters':   V1_3_HYPERPARAMS,
    'intervention':      'v1.5 — frozen MiniLM sentence embeddings replace word TF-IDF',
    'numerical_features': NUMERICAL_FEATURES_V5,
    'text_representation': 'sentence-transformers/all-MiniLM-L6-v2 (384-dim)',
    'feature_matrix_shape': [384, 3000, 26],
    'feature_matrix_total': 3410,
}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))

# Marker file — no tfidf_vectorizer.pkl since word TF-IDF is dropped
with open(os.path.join(CANDIDATE_DIR, 'text_representation.txt'), 'w') as f:
    f.write("v1.5 uses frozen MiniLM sentence embeddings (sentence-transformers/all-MiniLM-L6-v2)\n"
            "in place of word TF-IDF. Embedding dimension: 384.\n"
            "See scripts/train_v1_5.py and scripts/eval_v1_5.py for details.\n"
            "There is intentionally no tfidf_vectorizer.pkl in this directory.\n")

print(f"\n✅ Saved to {CANDIDATE_DIR}/  (threshold={opt_thresh:.2f})", flush=True)
expected = ['scamradar_model.pkl', 'char_vectorizer.pkl', 'scaler.pkl',
            'scam_faiss.index', 'legit_faiss.index', 'embeddings.npy',
            'text_representation.txt']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing artefacts: {missing}")
print(f"✅ All artefacts present ({len(expected)} files)", flush=True)
