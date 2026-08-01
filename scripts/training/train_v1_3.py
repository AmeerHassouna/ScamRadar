"""
Train v1.3_candidate — Intervention 4 (External Real-World Phishing Data Expansion).

Change from v1.2: **one variable only** — training corpus is augmented with
data/external_training/*.csv (1,133 items: 633 zefang-liu phishing + 500 Reddit legit).

Everything else is v1.2's exact procedure:
  * Deduplication (SHA-1 on normalise_text)
  * Split via cluster IDs → group-aware train/test (external items added to train side)
  * Train-only TF-IDF + StandardScaler + FAISS
  * Same v1.2 hyperparameters
    (n_estimators=200, max_depth=None, min_samples_leaf=1,
     max_features='sqrt', class_weight=None, calibration + threshold sweep)

Split assignment for new items: all training additions go to the train side (they
were vetted for zero overlap with existing training AND with the reserved external
eval set). New items still get cluster_ids from add_cluster_ids — they will not
match anything already in outputs/split_v1.json because they were overlap-verified,
so they extend the train-cluster set cleanly.

Outputs: models/v1.3_candidate/ (7 artefacts). v1.0 / v1.2 baselines untouched.
"""
import os, sys, sqlite3, pickle, json, time, csv
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
CANDIDATE_DIR  = os.path.join(BASE_DIR, 'models', 'v1.3_candidate')
SPLIT_PATH     = os.path.join(BASE_DIR, 'outputs', 'split_v1.json')
EXTERNAL_CSV   = os.path.join(BASE_DIR, 'data', 'external_training', 'external_train.csv')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

# v1.2's winning hyperparameters (from Intervention 3)
V1_2_HYPERPARAMS = {
    'n_estimators':     200,
    'max_depth':        None,
    'min_samples_leaf': 1,
    'max_features':     'sqrt',
    'class_weight':     None,
    'random_state':     42,
    'n_jobs':           -1,
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: LOAD DB DATA
# ══════════════════════════════════════════════════════════════════════════════
print("STEP 1: LOAD DB CORPUS", flush=True)
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
print(f"  DB corpus: {len(df):,} rows", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: LOAD EXTERNAL TRAINING ADDITIONS
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2: LOAD EXTERNAL TRAINING ADDITIONS", flush=True)
ext_rows = []
with open(EXTERNAL_CSV, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        ext_rows.append({
            'raw_text':          r['raw_text'],
            'label':             int(r['label']),
            'source':            r['source'],
            'channel':           'email' if 'phishing' in r['source'] else 'reddit',
            # placeholder DB features — will be overwritten by add_features() below
            'text_length':       0, 'word_count': 0, 'has_url': 0, 'url_count': 0,
            'exclamation_count': 0, 'uppercase_ratio': 0.0,
            'digit_ratio':       0.0, 'urgency_score': 0.0,
        })
ext_df = pd.DataFrame(ext_rows)
# Assign synthetic message_ids beyond existing range
next_id = int(df['message_id'].max() or 0) + 1
ext_df['message_id'] = np.arange(next_id, next_id + len(ext_df))
print(f"  External items: {len(ext_df):,}  ({(ext_df.label==1).sum()} scam + {(ext_df.label==0).sum()} legit)", flush=True)

# Combined corpus
df = pd.concat([df, ext_df], ignore_index=True)
print(f"  Combined corpus: {len(df):,} rows", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: DEDUP (same as v1.2)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3: DEDUP", flush=True)
df = add_cluster_ids(df)
before = len(df)
df = dedup_by_cluster(df, strategy='longest')
print(f"  {before:,} → {len(df):,} clusters ({(1-len(df)/before)*100:.1f}% removed)", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: FEATURE ENGINEERING (unchanged)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 4: FEATURE ENGINEERING", flush=True)
df = add_features(df)
# Recompute DB features for external items (add_features overwrites some; ensure the rest are computed)
for col in ['text_length', 'word_count']:
    df[col] = df['raw_text'].fillna('').apply(lambda t: len(t) if col == 'text_length' else len(t.split()))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: SPLIT ASSIGNMENT — extend v1.2's split with new-cluster train tag
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5: SPLIT ASSIGNMENT", flush=True)
with open(SPLIT_PATH) as f:
    split_map = dict(json.load(f))

new_train_clusters = 0
for cid in df['cluster_id']:
    if cid not in split_map:
        split_map[cid] = 'train'   # all new items → train side
        new_train_clusters += 1
df['split'] = df['cluster_id'].map(split_map)
print(f"  Added {new_train_clusters:,} new clusters as train side", flush=True)

train_mask = (df['split'] == 'train').values
test_mask  = (df['split'] == 'test').values
print(f"  Train: {train_mask.sum():,}   Test: {test_mask.sum():,}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: EMBEDDINGS + TRAIN-ONLY FAISS (same as v1.2)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 6: EMBEDDINGS + TRAIN-ONLY FAISS", flush=True)
from src._04_vector_proximity import (
    load_sentence_model, build_faiss_index, build_legit_faiss_index,
    compute_proximity_scores,
)
import faiss

st_model = load_sentence_model()
embeddings = st_model.encode(df['raw_text'].fillna('').tolist(),
                             batch_size=128, show_progress_bar=False,
                             convert_to_numpy=True)
scam_index  = build_faiss_index(embeddings[train_mask], df.loc[train_mask, 'label'].values)
legit_index = build_legit_faiss_index(embeddings[train_mask], df.loc[train_mask, 'label'].values)
prox_scam, prox_legit, prox_delta = compute_proximity_scores(embeddings, scam_index, legit_index)
df['proximity_scam_score']  = prox_scam * 0.5
df['legit_proximity_score'] = prox_legit
df['proximity_delta']       = prox_delta

faiss.write_index(scam_index,  os.path.join(CANDIDATE_DIR, 'scam_faiss.index'))
faiss.write_index(legit_index, os.path.join(CANDIDATE_DIR, 'legit_faiss.index'))
np.save(os.path.join(CANDIDATE_DIR, 'embeddings.npy'), embeddings)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: TRAIN-ONLY TF-IDF + SCALER (same as v1.2)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 7: TRAIN-ONLY TF-IDF + SCALER", flush=True)
train_texts = df.loc[train_mask, 'raw_text'].fillna('').values
test_texts  = df.loc[test_mask,  'raw_text'].fillna('').values

tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2),
                        stop_words='english', sublinear_tf=True)
X_tfidf_train = tfidf.fit_transform(train_texts)
X_tfidf_test  = tfidf.transform(test_texts)

char_tfidf = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                             max_features=3000, sublinear_tf=True)
X_char_train = char_tfidf.fit_transform(train_texts)
X_char_test  = char_tfidf.transform(test_texts)

X_num_train = df.loc[train_mask, NUMERICAL_FEATURES_V5].fillna(0).values
X_num_test  = df.loc[test_mask,  NUMERICAL_FEATURES_V5].fillna(0).values
scaler = StandardScaler()
X_num_train_s = scaler.fit_transform(X_num_train)
X_num_test_s  = scaler.transform(X_num_test)

pickle.dump(tfidf,      open(os.path.join(CANDIDATE_DIR, 'tfidf_vectorizer.pkl'), 'wb'))
pickle.dump(char_tfidf, open(os.path.join(CANDIDATE_DIR, 'char_vectorizer.pkl'),  'wb'))
pickle.dump(scaler,     open(os.path.join(CANDIDATE_DIR, 'scaler.pkl'),           'wb'))

X_train = hstack([X_tfidf_train, X_char_train, csr_matrix(X_num_train_s)])
X_test  = hstack([X_tfidf_test,  X_char_test,  csr_matrix(X_num_test_s)])
y_train = df.loc[train_mask, 'label'].values
y_test  = df.loc[test_mask,  'label'].values
print(f"  Combined — train: {X_train.shape}   test: {X_test.shape}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: TRAIN v1.2 HYPERPARAMETERS ON X_TRAIN (via X_tr2 + X_cal split)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 8: TRAIN + CALIBRATE + THRESHOLD (v1.2 hyperparameters)", flush=True)
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=42, stratify=y_train
)
rf = RandomForestClassifier(**V1_2_HYPERPARAMS)
t0 = time.time()
rf.fit(X_tr2, y_tr2)
print(f"  RF fit in {time.time()-t0:.1f}s", flush=True)

calibrated = calibrate_model(rf, X_cal, y_cal)
opt_thresh, _ = find_optimal_threshold(calibrated, X_cal, y_cal)

y_prob_cal = calibrated.predict_proba(X_test)[:, 1]
y_pred_cal = (y_prob_cal >= opt_thresh).astype(int)
final = {
    'Accuracy':  accuracy_score(y_test, y_pred_cal),
    'Precision': precision_score(y_test, y_pred_cal, zero_division=0),
    'Recall':    recall_score(y_test, y_pred_cal, zero_division=0),
    'F1':        f1_score(y_test, y_pred_cal, zero_division=0),
    'AUC':       roc_auc_score(y_test, y_prob_cal),
}
tn, fp, fn, tp = confusion_matrix(y_test, y_pred_cal).ravel()

print(f"\n  Internal test — v1.3_candidate (threshold={opt_thresh:.2f}):")
for k, v in final.items():
    print(f"    {k:10s}  {v:.4f}", flush=True)
print(f"    Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: SAVE
# ══════════════════════════════════════════════════════════════════════════════
model_payload = {
    'model': calibrated,
    'threshold': float(opt_thresh),
    'hyperparameters': V1_2_HYPERPARAMS,
    'intervention': 'v1.3 External Real-World Phishing Data Expansion',
}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))
print(f"\n✅ Saved to {CANDIDATE_DIR}/  (threshold={opt_thresh:.2f})", flush=True)

expected = ['scamradar_model.pkl', 'tfidf_vectorizer.pkl', 'char_vectorizer.pkl',
            'scaler.pkl', 'scam_faiss.index', 'legit_faiss.index', 'embeddings.npy']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing artefacts: {missing}")
print(f"✅ All 7 artefacts present", flush=True)
