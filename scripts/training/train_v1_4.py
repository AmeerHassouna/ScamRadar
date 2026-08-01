"""
═══════════════════════════════════════════════════════════════════════════════
  ARCHIVED RESEARCH ARTEFACT — REJECTED EXPERIMENT
═══════════════════════════════════════════════════════════════════════════════
  This script documents the v1.4 experiment which was EVALUATED AND REJECTED.
  It will NOT run against the current production codebase — it depends on the
  following v1.4 additions that were reverted after the experiment concluded:

    * config.NUMERICAL_FEATURES_V6            (= NUMERICAL_FEATURES_V5 + ['url_free_hosting'])
    * config.FREE_HOSTING_DOMAINS             (frozen set of ~25 hosts)
    * src._02_feature_engineering.compute_url_free_hosting(text) -> int
    * src._02_feature_engineering.normalise_for_tfidf(text) -> str
    * src._02_feature_engineering.add_features() — adds 'url_free_hosting' column

  Outcome (from outputs/eval/v1.4_candidate_external.json):
    Δ F1 external:  v1.3 = 0.8734  →  v1.4 = 0.8737  (+0.0003)
    Ship criterion (≥ +1.0 F1 pt): FAILED. v1.3 retained as final model.

  See outputs/eval/v1.4_candidate.json and v1.4_candidate_external.json for
  the full evaluation record and outputs/intervention_log.md for context.

  To reproduce: apply the v1.4 additions listed above (recoverable from git
  history at commit HEAD around the "docs: align repo..." commit period)
  before running this script.
═══════════════════════════════════════════════════════════════════════════════

Train v1.4_candidate — literature-justified generalisation improvements over v1.3.

Two changes only, both independently justified from external literature (never
from inspection of the external evaluation set):

1. TF-IDF text normalisation
   URLs, emails, phones, currency amounts and standalone digits replaced with
   placeholder tokens (URLTOKEN, EMAILTOKEN, ...) BEFORE TF-IDF fitting.
   Refs: Sebastiani (2002); Chandrasekaran et al. (2006); Fette et al. (2007);
   Manning et al. (2008) §2.

2. url_free_hosting feature
   Binary flag for URLs on well-known free-hosting platforms abused by
   phishing kits (github.io, vercel.app, ipfs.io, ...). List sourced from
   APWG Phishing Activity Trends Reports 2023-2024 and MITRE ATT&CK T1583.008.
   Signal is orthogonal to url_suspicious_tld — the .io TLD is legitimate.

All other choices copied directly from v1.3:
* Same corpus (46,360 DB + 1,133 external additions -> 22,546 dedup clusters)
* Same group-aware cluster split (outputs/split_v1.json)
* Same train-only fitting of TF-IDF/scaler/FAISS
* Same v1.2 hyperparameters (n_estimators=200, max_depth=None,
  min_samples_leaf=1, max_features='sqrt', class_weight=None)
* Same calibration + threshold procedure (on X_cal, a val slice of X_train)

External 400-item evaluation set is not touched during training.
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
from config import DB_PATH, NUMERICAL_FEATURES_V6
from src._00_dedup import add_cluster_ids, dedup_by_cluster
from src._02_feature_engineering import add_features, normalise_for_tfidf
from src._05_model_training import calibrate_model, find_optimal_threshold

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_DIR  = os.path.join(BASE_DIR, 'models', 'v1.4_candidate')
SPLIT_PATH     = os.path.join(BASE_DIR, 'outputs', 'split_v1.json')
EXTERNAL_CSV   = os.path.join(BASE_DIR, 'data', 'external_training', 'external_train.csv')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

V1_2_HYPERPARAMS = {
    'n_estimators':     200,
    'max_depth':        None,
    'min_samples_leaf': 1,
    'max_features':     'sqrt',
    'class_weight':     None,
    'random_state':     42,
    'n_jobs':           -1,
}


# STEP 1 — Load + external additions + dedup + split (identical to v1.3)
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
print(f"  Combined raw corpus: {len(df):,}", flush=True)

df = add_cluster_ids(df)
df = dedup_by_cluster(df, strategy='longest')
print(f"  After dedup: {len(df):,} clusters", flush=True)


# STEP 2 — Feature engineering (v1.4: add_features now also computes url_free_hosting)
print("\nSTEP 2: FEATURE ENGINEERING (v1.4 — includes url_free_hosting)", flush=True)
df = add_features(df)
# Sanity check: url_free_hosting column is present with a distribution
n_free_host = int(df['url_free_hosting'].sum())
print(f"  url_free_hosting=1 count: {n_free_host:,} / {len(df):,} "
      f"({n_free_host/len(df)*100:.2f}%)", flush=True)


# STEP 3 — Load v1.3 split (extended to include new clusters as train)
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


# STEP 4 — Embeddings + train-only FAISS (identical to v1.3)
print("\nSTEP 4: EMBEDDINGS + TRAIN-ONLY FAISS", flush=True)
from src._04_vector_proximity import (
    load_sentence_model, build_faiss_index, build_legit_faiss_index,
    compute_proximity_scores,
)
import faiss

st_model = load_sentence_model()
embeddings = st_model.encode(df['raw_text'].fillna('').tolist(),
                             batch_size=128, show_progress_bar=False,
                             convert_to_numpy=True)
scam_index  = build_faiss_index(embeddings[train_mask],  df.loc[train_mask, 'label'].values)
legit_index = build_legit_faiss_index(embeddings[train_mask], df.loc[train_mask, 'label'].values)
prox_scam, prox_legit, prox_delta = compute_proximity_scores(embeddings, scam_index, legit_index)
df['proximity_scam_score']  = prox_scam * 0.5
df['legit_proximity_score'] = prox_legit
df['proximity_delta']       = prox_delta

faiss.write_index(scam_index,  os.path.join(CANDIDATE_DIR, 'scam_faiss.index'))
faiss.write_index(legit_index, os.path.join(CANDIDATE_DIR, 'legit_faiss.index'))
np.save(os.path.join(CANDIDATE_DIR, 'embeddings.npy'), embeddings)


# STEP 5 — TF-IDF fit on train, with v1.4 text normalisation (Intervention A)
print("\nSTEP 5: TF-IDF FIT ON TRAIN SLICE (v1.4 — with normalise_for_tfidf)", flush=True)
train_texts_raw = df.loc[train_mask, 'raw_text'].fillna('').values
test_texts_raw  = df.loc[test_mask,  'raw_text'].fillna('').values

# v1.4 change: apply normalisation BEFORE TF-IDF fitting
train_texts = [normalise_for_tfidf(t) for t in train_texts_raw]
test_texts  = [normalise_for_tfidf(t) for t in test_texts_raw]
print(f"  Applied normalise_for_tfidf to {len(train_texts):,} train + {len(test_texts):,} test texts", flush=True)

tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2),
                        stop_words='english', sublinear_tf=True)
X_tfidf_train = tfidf.fit_transform(train_texts)
X_tfidf_test  = tfidf.transform(test_texts)
print(f"  Word TF-IDF vocab size: {len(tfidf.get_feature_names_out()):,} "
      f"(v1.3 was also 5,000 max)", flush=True)

char_tfidf = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                             max_features=3000, sublinear_tf=True)
X_char_train = char_tfidf.fit_transform(train_texts)
X_char_test  = char_tfidf.transform(test_texts)


# STEP 6 — Scaler fit on train (with url_free_hosting in V6 feature set)
print("\nSTEP 6: STANDARDSCALER FIT ON TRAIN SLICE (V6 features)", flush=True)
X_num_train = df.loc[train_mask, NUMERICAL_FEATURES_V6].fillna(0).values
X_num_test  = df.loc[test_mask,  NUMERICAL_FEATURES_V6].fillna(0).values
scaler = StandardScaler()
X_num_train_s = scaler.fit_transform(X_num_train)
X_num_test_s  = scaler.transform(X_num_test)
print(f"  Numerical features: {len(NUMERICAL_FEATURES_V6)} (v1.3 had {len(NUMERICAL_FEATURES_V6)-1})", flush=True)

pickle.dump(tfidf,      open(os.path.join(CANDIDATE_DIR, 'tfidf_vectorizer.pkl'), 'wb'))
pickle.dump(char_tfidf, open(os.path.join(CANDIDATE_DIR, 'char_vectorizer.pkl'),  'wb'))
pickle.dump(scaler,     open(os.path.join(CANDIDATE_DIR, 'scaler.pkl'),           'wb'))

X_train = hstack([X_tfidf_train, X_char_train, csr_matrix(X_num_train_s)])
X_test  = hstack([X_tfidf_test,  X_char_test,  csr_matrix(X_num_test_s)])
y_train = df.loc[train_mask, 'label'].values
y_test  = df.loc[test_mask,  'label'].values
print(f"  Combined — train: {X_train.shape}   test: {X_test.shape}", flush=True)


# STEP 7 — Train + calibrate + threshold (all on train-side data only)
print("\nSTEP 7: TRAIN + CALIBRATE + THRESHOLD", flush=True)
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=42, stratify=y_train
)
rf = RandomForestClassifier(**V1_2_HYPERPARAMS)
t0 = time.time()
rf.fit(X_tr2, y_tr2)
print(f"  RF fit in {time.time()-t0:.1f}s", flush=True)

calibrated = calibrate_model(rf, X_cal, y_cal)
opt_thresh, _ = find_optimal_threshold(calibrated, X_cal, y_cal)


# STEP 8 — Internal test measurement
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

print(f"\n  Internal test — v1.4 (threshold={opt_thresh:.2f}):")
for k, v in final.items():
    print(f"    {k:10s}  {v:.4f}", flush=True)
print(f"    Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}", flush=True)
print(classification_report(y_test, y_pred_cal, target_names=['Legit','Scam']), flush=True)


# STEP 9 — Save
model_payload = {
    'model': calibrated,
    'threshold': float(opt_thresh),
    'hyperparameters': V1_2_HYPERPARAMS,
    'intervention': 'v1.4 — text normalisation + url_free_hosting',
    'numerical_features': NUMERICAL_FEATURES_V6,
    'requires_tfidf_normalisation': True,
}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))
print(f"\n✅ Saved to {CANDIDATE_DIR}/  (threshold={opt_thresh:.2f})", flush=True)

expected = ['scamradar_model.pkl', 'tfidf_vectorizer.pkl', 'char_vectorizer.pkl',
            'scaler.pkl', 'scam_faiss.index', 'legit_faiss.index', 'embeddings.npy']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing artefacts: {missing}")
print(f"✅ All 7 artefacts present", flush=True)
