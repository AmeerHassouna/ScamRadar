"""
Train v1.7_local_experiment — data-augmentation experiment (LOCAL ONLY).

Purpose:
  Test whether targeted augmentation with (a) mined model errors and
  (b) synthetic subtle-tone scam + hard-legit samples improves per-category
  performance vs the current localhost model (11866bb) and the deployed
  production model (v1.3).

Isolation guarantees:
  * READS baseline `data/db 4.db` but never modifies it.
  * READS augmentation JSONLs from `data/v1.7_augmentation/` — never modifies them.
  * WRITES model artifacts ONLY to `models/v1.7_local_experiment/`.
  * Does NOT swap the currently-loaded localhost model.
  * Does NOT touch v1.3 or any deployed artifact.

Architecture:
  Identical to v1.3 recipe (per user approval):
    - RandomForest (v1.2's winning hyperparams)
    - Isotonic calibration on 20% held-out slice of train
    - F1-max threshold sweep on same held-out slice
    - Same TF-IDF (word+char) + StandardScaler + FAISS indices
    - Same cluster-aware split (extends v1.3's split with new-cluster train tag)

Augmentation sources (loaded from data/v1.7_augmentation/ only at run time):
  * mined_errors/errors.jsonl                  — 156 items (FP/FN from prior experiments)
  * synthetic/hard_legit_*.jsonl               — hard-legit training additions
  * synthetic/subtle_scam_*.jsonl              — subtle-scam training additions

Everything remains local. No git commits. No deployment.
"""
import os
import sys
import sqlite3
import pickle
import json
import time
import glob

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             precision_score, recall_score, confusion_matrix)
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

BASE_DIR         = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_DIR    = os.path.join(BASE_DIR, 'models', 'v1.7_local_experiment')
SPLIT_PATH       = os.path.join(BASE_DIR, 'outputs', 'split_v1.json')
AUGMENT_DIR      = os.path.join(BASE_DIR, 'data', 'v1.7_augmentation')
MINED_ERRORS     = os.path.join(AUGMENT_DIR, 'mined_errors', 'errors.jsonl')
SYNTHETIC_GLOB   = os.path.join(AUGMENT_DIR, 'synthetic', '*.jsonl')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

# v1.2/v1.3 winning hyperparameters — kept unchanged per user's "keep existing
# architecture unless strong evidence to change" directive.
V1_2_HYPERPARAMS = {
    'n_estimators':     200,
    'max_depth':        None,
    'min_samples_leaf': 1,
    'max_features':     'sqrt',
    'class_weight':     None,
    'random_state':     42,
    'n_jobs':           -1,
}

RANDOM_SEED = 42


def load_jsonl(path):
    """Read a JSONL file — one JSON object per line."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def augmentation_row_to_df_row(row, source_tag, next_id):
    """Convert a JSONL augmentation record to the same shape as db-loaded rows."""
    return {
        'message_id':        next_id,
        'raw_text':          row['text'],
        'label':             int(row['label']),
        'source':            source_tag,
        'channel':           row.get('channel', 'email'),
        'text_length':       0, 'word_count': 0, 'has_url': 0, 'url_count': 0,
        'exclamation_count': 0, 'uppercase_ratio': 0.0,
        'digit_ratio':       0.0, 'urgency_score':  0.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: LOAD BASELINE DB (read-only)
# ══════════════════════════════════════════════════════════════════════════════
print("STEP 1: LOAD BASELINE DB (read-only)", flush=True)
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
print(f"  Baseline corpus: {len(df):,} rows", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: LOAD AUGMENTATION (mined errors + synthetic)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2: LOAD v1.7 AUGMENTATION", flush=True)
augment_rows = []
next_id = int(df['message_id'].max() or 0) + 1

# Mined errors
mined = load_jsonl(MINED_ERRORS)
for r in mined:
    row = augmentation_row_to_df_row(r, source_tag=f"v1.7_mined_error", next_id=next_id)
    row['channel'] = 'email'
    augment_rows.append(row)
    next_id += 1
print(f"  Mined errors: {len(mined):,}")

# Synthetic files
synthetic_files = sorted(glob.glob(SYNTHETIC_GLOB))
synth_counts = {}
for path in synthetic_files:
    name = os.path.basename(path).replace('.jsonl', '')
    items = load_jsonl(path)
    synth_counts[name] = len(items)
    for r in items:
        row = augmentation_row_to_df_row(r, source_tag=f"v1.7_synthetic_{name}",
                                          next_id=next_id)
        row['channel'] = 'chat' if 'social' in name or 'gaming' in name else 'email'
        augment_rows.append(row)
        next_id += 1

for k, v in synth_counts.items():
    print(f"  Synthetic {k}: {v:,}")

if augment_rows:
    aug_df = pd.DataFrame(augment_rows)
    aug_scam  = int((aug_df.label == 1).sum())
    aug_legit = int((aug_df.label == 0).sum())
    print(f"  TOTAL augmentation: {len(aug_df):,}  ({aug_scam} scam + {aug_legit} legit)", flush=True)
    df = pd.concat([df, aug_df], ignore_index=True)
else:
    print("  WARN: no augmentation loaded", flush=True)

print(f"  Combined corpus: {len(df):,} rows", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: DEDUP (cluster-aware SHA-1)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3: DEDUP", flush=True)
df = add_cluster_ids(df)
before = len(df)
df = dedup_by_cluster(df, strategy='longest')
print(f"  {before:,} → {len(df):,} clusters ({(1-len(df)/before)*100:.1f}% removed)", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 4: FEATURE ENGINEERING", flush=True)
df = add_features(df)
# ensure text_length/word_count recomputed for augmentation rows
df['text_length'] = df['raw_text'].fillna('').apply(len)
df['word_count']  = df['raw_text'].fillna('').apply(lambda t: len(t.split()))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: SPLIT ASSIGNMENT — extend v1.3's split, all new clusters → train
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5: SPLIT ASSIGNMENT", flush=True)
with open(SPLIT_PATH) as f:
    split_map = dict(json.load(f))

new_train_clusters = 0
for cid in df['cluster_id']:
    if cid not in split_map:
        split_map[cid] = 'train'
        new_train_clusters += 1
df['split'] = df['cluster_id'].map(split_map)
print(f"  Added {new_train_clusters:,} new clusters as train side", flush=True)

train_mask = (df['split'] == 'train').values
test_mask  = (df['split'] == 'test').values
print(f"  Train: {train_mask.sum():,}   Test: {test_mask.sum():,}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: EMBEDDINGS + TRAIN-ONLY FAISS
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
# STEP 7: TRAIN-ONLY TF-IDF + SCALER
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
# STEP 8: TRAIN + CALIBRATE + THRESHOLD (v1.3 recipe)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 8: TRAIN + CALIBRATE + F1-MAX THRESHOLD", flush=True)
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=RANDOM_SEED, stratify=y_train
)
rf = RandomForestClassifier(**V1_2_HYPERPARAMS)
t0 = time.time()
rf.fit(X_tr2, y_tr2)
print(f"  RF fit in {time.time()-t0:.1f}s", flush=True)

calibrated = calibrate_model(rf, X_cal, y_cal)
opt_thresh, thresh_info = find_optimal_threshold(calibrated, X_cal, y_cal)

y_prob_cal = calibrated.predict_proba(X_test)[:, 1]
y_pred_cal = (y_prob_cal >= opt_thresh).astype(int)

metrics = {
    'accuracy':  float(accuracy_score(y_test, y_pred_cal)),
    'precision': float(precision_score(y_test, y_pred_cal, zero_division=0)),
    'recall':    float(recall_score(y_test, y_pred_cal, zero_division=0)),
    'f1':        float(f1_score(y_test, y_pred_cal, zero_division=0)),
    'roc_auc':   float(roc_auc_score(y_test, y_prob_cal)),
}
tn, fp, fn, tp = confusion_matrix(y_test, y_pred_cal).ravel()
print(f"\n  Internal test — v1.7 (threshold={opt_thresh:.3f}):")
for k, v in metrics.items():
    print(f"    {k:10s}  {v:.4f}", flush=True)
print(f"    Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: SAVE
# ══════════════════════════════════════════════════════════════════════════════
augmentation_manifest = {
    'mined_errors_count': len(mined),
    'synthetic_counts':   synth_counts,
    'total_augmentation': len(augment_rows),
    'baseline_size':      before - len(augment_rows) if augment_rows else before,
    'after_dedup':        int(len(df)),
    'new_train_clusters': new_train_clusters,
    'train_size':         int(train_mask.sum()),
    'test_size':          int(test_mask.sum()),
    'threshold':          float(opt_thresh),
    'internal_metrics':   metrics,
    'confusion':          {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    'random_seed':        RANDOM_SEED,
    'hyperparameters':    V1_2_HYPERPARAMS,
    'notes': ('v1.7 = v1.3 pipeline (RF + isotonic + F1-max threshold) + '
              'targeted data augmentation. LOCAL ONLY. Does not swap the '
              'active localhost model. Baseline db and v1.3 remain untouched.'),
}
json.dump(augmentation_manifest,
          open(os.path.join(CANDIDATE_DIR, 'training_manifest.json'), 'w'),
          indent=2)

model_payload = {
    'model':          calibrated,
    'threshold':      float(opt_thresh),
    'hyperparameters': V1_2_HYPERPARAMS,
    'intervention':   'v1.7 Targeted Augmentation (mined errors + synthetic subtle scams + hard-legit)',
}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))
print(f"\nSaved to {CANDIDATE_DIR}/  (threshold={opt_thresh:.3f})", flush=True)

expected = ['scamradar_model.pkl', 'tfidf_vectorizer.pkl', 'char_vectorizer.pkl',
            'scaler.pkl', 'scam_faiss.index', 'legit_faiss.index',
            'embeddings.npy', 'training_manifest.json']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing artefacts: {missing}")
print(f"All {len(expected)} artefacts present. v1.7 training complete.", flush=True)
