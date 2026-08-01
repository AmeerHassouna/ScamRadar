"""
═══════════════════════════════════════════════════════════════════════════════
  ARCHIVED RESEARCH ARTEFACT — REJECTED EXPERIMENT
═══════════════════════════════════════════════════════════════════════════════
  v1.6 was designed as a follow-up to v1.5 to test whether the RandomForest
  classifier was the limiting factor for frozen MiniLM embeddings, by
  swapping RF → LogisticRegression (with L2-normalised MiniLM as standard
  SBERT-linear-probe practice).

  Outcome (from outputs/eval/v1.6_candidate_external.json):
    External F1:  v1.3 = 0.8734  →  v1.6 = 0.8367   (Δ = −0.0367)
    Ship criterion (≥ +1.0 F1 pt): FAILED. v1.3 retained as final model.

  Interpretation: neither the embedding representation (tested in v1.5) nor
  the classifier choice (tested in v1.6) was the limiting factor. Both
  MiniLM+RF (v1.5) and MiniLM+LR (v1.6) failed to beat v1.3's TF-IDF+RF
  on the external benchmark under identical protocol. This converging
  evidence suggests the OOD gap is dominated by training-distribution
  coverage rather than representation or classifier architecture.

  To reproduce: re-run this script — it will re-create the v1.6_candidate
  directory from scratch. See scripts/eval_v1_6.py for the corresponding
  evaluator.
═══════════════════════════════════════════════════════════════════════════════

Train v1.6_candidate — MiniLM sentence embeddings + Logistic Regression.

Follow-up to v1.5 (which used MiniLM + RandomForest) that tests whether
the classifier choice was the limiting factor for MiniLM embeddings.

Two changes vs v1.5, both technically justified for LR:

  1. Classifier: RandomForestClassifier(n_estimators=200) →
     LogisticRegression(penalty='l2', solver='lbfgs', C=1.0,
                        max_iter=1000, class_weight=None, random_state=42)

  2. MiniLM embedding preprocessing: encode(normalize_embeddings=True) so
     embeddings are L2-normalised (unit vectors). Standard SBERT-linear-
     probe protocol per Reimers & Gurevych (2019) — aligns with the model's
     cosine-similarity training objective and is consistent with the FAISS
     pipeline which already L2-normalises the same embeddings.

Everything else identical to v1.5:
  * Same corpus (46,360 DB rows + 1,133 external additions → 22,546 dedup clusters)
  * Same cluster-aware split (outputs/split_v1.json)
  * Same char TF-IDF (3,000 features, TfidfVectorizer default norm='l2')
  * Same 26 numerical features (V5), same StandardScaler
  * Same FAISS proximity feature (train-only indices)
  * Same isotonic calibration + F1-max threshold sweep on the val slice
  * Same random seed = 42

No production code changes. External 400-item set is not touched during training.
"""
import os, sys, sqlite3, pickle, json, time, csv, warnings
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             precision_score, recall_score, classification_report,
                             confusion_matrix)
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DB_PATH, NUMERICAL_FEATURES_V5
from src._00_dedup import add_cluster_ids, dedup_by_cluster
from src._02_feature_engineering import add_features
from src._05_model_training import calibrate_model, find_optimal_threshold

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_DIR  = os.path.join(BASE_DIR, 'models', 'v1.6_candidate')
SPLIT_PATH     = os.path.join(BASE_DIR, 'outputs', 'split_v1.json')
EXTERNAL_CSV   = os.path.join(BASE_DIR, 'data', 'external_training', 'external_train.csv')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

# Approved LR configuration
LR_HYPERPARAMS = {
    'penalty':      'l2',
    'solver':       'lbfgs',
    'C':            1.0,
    'max_iter':     1000,
    'class_weight': None,
    'random_state': 42,
    'n_jobs':       -1,
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — LOAD + DEDUP + SPLIT (identical to v1.5)
# ══════════════════════════════════════════════════════════════════════════════
print("STEP 1: LOAD + DEDUP + SPLIT", flush=True)
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
# STEP 2 — FEATURE ENGINEERING (identical to v1.5)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2: FEATURE ENGINEERING", flush=True)
df = add_features(df)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SPLIT ASSIGNMENT (identical to v1.5)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3: SPLIT ASSIGNMENT", flush=True)
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
# STEP 4 — MINILM EMBEDDINGS (L2-NORMALISED for LR — v1.6 change) + FAISS
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 4: MINILM EMBEDDINGS (L2-normalised) + TRAIN-ONLY FAISS", flush=True)
from src._04_vector_proximity import (
    load_sentence_model, build_faiss_index, build_legit_faiss_index,
    compute_proximity_scores,
)
import faiss

st_model = load_sentence_model()
t0 = time.time()
print(f"  Encoding {len(df):,} clusters via all-MiniLM-L6-v2 with normalize_embeddings=True…", flush=True)
embeddings = st_model.encode(df['raw_text'].fillna('').tolist(),
                             batch_size=128, show_progress_bar=False,
                             convert_to_numpy=True,
                             normalize_embeddings=True)  # v1.6 change vs v1.5
# Sanity check the L2 norms
norms = np.linalg.norm(embeddings, axis=1)
print(f"  Embedding shape: {embeddings.shape}  ({time.time()-t0:.1f}s)", flush=True)
print(f"  L2 norms: min={norms.min():.4f}  max={norms.max():.4f}  mean={norms.mean():.4f}  (should be 1.0)", flush=True)
assert np.allclose(norms, 1.0, atol=1e-5), "MiniLM embeddings not L2-normalised as expected"

np.save(os.path.join(CANDIDATE_DIR, 'embeddings.npy'), embeddings)

# FAISS uses these (already L2-normalised) embeddings — matches v1.5's pipeline
scam_idx  = build_faiss_index(embeddings[train_mask],  df.loc[train_mask, 'label'].values)
legit_idx = build_legit_faiss_index(embeddings[train_mask], df.loc[train_mask, 'label'].values)
prox_scam, prox_legit, prox_delta = compute_proximity_scores(embeddings, scam_idx, legit_idx)
df['proximity_scam_score']  = prox_scam * 0.5
df['legit_proximity_score'] = prox_legit
df['proximity_delta']       = prox_delta

faiss.write_index(scam_idx,  os.path.join(CANDIDATE_DIR, 'scam_faiss.index'))
faiss.write_index(legit_idx, os.path.join(CANDIDATE_DIR, 'legit_faiss.index'))

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — CHAR TF-IDF FIT ON TRAIN SLICE (identical to v1.5)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5: CHAR TF-IDF FIT ON TRAIN SLICE", flush=True)
train_texts = df.loc[train_mask, 'raw_text'].fillna('').values
test_texts  = df.loc[test_mask,  'raw_text'].fillna('').values

char_tfidf = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                             max_features=3000, sublinear_tf=True)
# TfidfVectorizer defaults to norm='l2' — each row L2-normalised
X_char_train = char_tfidf.fit_transform(train_texts)
X_char_test  = char_tfidf.transform(test_texts)
pickle.dump(char_tfidf, open(os.path.join(CANDIDATE_DIR, 'char_vectorizer.pkl'), 'wb'))
print(f"  Char TF-IDF: train {X_char_train.shape}, test {X_char_test.shape}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — NUMERICAL FEATURES SCALED ON TRAIN SLICE (identical to v1.5)
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
# STEP 7 — v1.6 FEATURE MATRIX = [L2-normalised MiniLM, char_tfidf, numerical_scaled]
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 7: BUILD v1.6 FEATURE MATRIX", flush=True)
E_train = embeddings[train_mask]
E_test  = embeddings[test_mask]

X_train = hstack([csr_matrix(E_train), X_char_train, csr_matrix(X_num_train_s)])
X_test  = hstack([csr_matrix(E_test),  X_char_test,  csr_matrix(X_num_test_s)])
y_train = df.loc[train_mask, 'label'].values
y_test  = df.loc[test_mask,  'label'].values
print(f"  Combined — train: {X_train.shape}   test: {X_test.shape}", flush=True)
assert X_train.shape[1] == X_test.shape[1] == 384 + 3000 + 26 == 3410, \
    f"Feature dim mismatch: expected 3410, got train={X_train.shape[1]}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — TRAIN LR + CALIBRATE + THRESHOLD
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 8: TRAIN LOGISTIC REGRESSION + CALIBRATE + THRESHOLD", flush=True)
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=42, stratify=y_train
)
print(f"  Fitting LR({LR_HYPERPARAMS}) on X_tr2 ({X_tr2.shape})…", flush=True)
t0 = time.time()
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    lr = LogisticRegression(**LR_HYPERPARAMS)
    lr.fit(X_tr2, y_tr2)
    conv_warnings = [x for x in w if issubclass(x.category, ConvergenceWarning)]
    if conv_warnings:
        print(f"  ⚠ CONVERGENCE WARNINGS: {len(conv_warnings)} — LR may not have converged fully!", flush=True)
        for warn in conv_warnings[:3]:
            print(f"    {warn.message}", flush=True)
    else:
        print(f"  ✅ LR converged cleanly (no ConvergenceWarning)", flush=True)
print(f"  LR fit in {time.time()-t0:.1f}s  (n_iter_={lr.n_iter_})", flush=True)

calibrated = calibrate_model(lr, X_cal, y_cal)
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
    'model':                calibrated,
    'threshold':            float(opt_thresh),
    'hyperparameters':      LR_HYPERPARAMS,
    'intervention':         'v1.6 — MiniLM (L2-normalised) + Logistic Regression',
    'numerical_features':   NUMERICAL_FEATURES_V5,
    'text_representation':  'sentence-transformers/all-MiniLM-L6-v2 (384-dim, L2-normalised)',
    'feature_matrix_shape': [384, 3000, 26],
    'feature_matrix_total': 3410,
    'classifier':           'LogisticRegression',
    'lr_n_iter':            int(lr.n_iter_[0]) if hasattr(lr.n_iter_, '__len__') else int(lr.n_iter_),
}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))

with open(os.path.join(CANDIDATE_DIR, 'text_representation.txt'), 'w') as f:
    f.write("v1.6 uses L2-normalised MiniLM sentence embeddings (all-MiniLM-L6-v2)\n"
            "in place of word TF-IDF. Classifier: Logistic Regression (lbfgs, L2, C=1.0).\n"
            "Embeddings encoded with normalize_embeddings=True per SBERT linear-probe practice.\n"
            "There is intentionally no tfidf_vectorizer.pkl in this directory.\n"
            "See scripts/train_v1_6.py and scripts/eval_v1_6.py.\n")

print(f"\n✅ Saved to {CANDIDATE_DIR}/  (threshold={opt_thresh:.2f})", flush=True)
expected = ['scamradar_model.pkl', 'char_vectorizer.pkl', 'scaler.pkl',
            'scam_faiss.index', 'legit_faiss.index', 'embeddings.npy',
            'text_representation.txt']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing artefacts: {missing}")
print(f"✅ All artefacts present ({len(expected)} files)", flush=True)
