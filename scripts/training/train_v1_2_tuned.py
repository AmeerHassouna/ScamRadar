"""
Train v1.2_candidate — hyperparameter tuning on v1.1's architecture (TIGHTER SEARCH).

Same procedure as v1.1 (dedup + train-only fitting), only one variable changes:
the RF hyperparameters. Smaller search space than the initial attempt so it
finishes in ~10-15 min while still covering the important region.

Search space:
  n_estimators     ∈ {200, 400}
  max_depth        ∈ {None, 20, 40}
  min_samples_leaf ∈ {1, 2, 5}
  max_features     ∈ {'sqrt', 0.3}
  class_weight     ∈ {None, 'balanced'}
  → 72 combinations, sample 12 via RandomizedSearchCV × 5-fold CV = 60 fits

All artefacts → models/v1.2_candidate/. Deployed pkls untouched.
"""

import os, sys, sqlite3, pickle, json, time
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             precision_score, recall_score, classification_report,
                             confusion_matrix)
from sklearn.model_selection import (train_test_split, RandomizedSearchCV,
                                     StratifiedKFold)
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DB_PATH, NUMERICAL_FEATURES_V5
from src._00_dedup import add_cluster_ids, dedup_by_cluster
from src._02_feature_engineering import add_features
from src._05_model_training import calibrate_model, find_optimal_threshold

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATE_DIR  = os.path.join(BASE_DIR, 'models', 'v1.2_candidate')
SPLIT_PATH     = os.path.join(BASE_DIR, 'outputs', 'split_v1.json')

os.makedirs(CANDIDATE_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEPS 1-7: recreate v1.1's train-slice feature matrix (unchanged procedure)
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
df = add_cluster_ids(df)
df = dedup_by_cluster(df, strategy='longest')
print(f"✅ Deduped: {len(df):,} unique clusters", flush=True)

df = add_features(df)

with open(SPLIT_PATH) as f:
    split_map = json.load(f)
df['split'] = df['cluster_id'].map(split_map)
train_mask = (df['split'] == 'train').values
test_mask  = (df['split'] == 'test').values
print(f"✅ Split: train={train_mask.sum()}  test={test_mask.sum()}", flush=True)

print("\nSTEP 2: EMBEDDINGS + TRAIN-ONLY FAISS", flush=True)
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

print("\nSTEP 3: TRAIN-ONLY TF-IDF + SCALER", flush=True)
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
print(f"✅ Combined — train: {X_train.shape}   test: {X_test.shape}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: RANDOMIZEDSEARCHCV — tighter search (12 candidates × 5-fold = 60 fits)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print("STEP 4: HYPERPARAMETER SEARCH (tight)", flush=True)
print("="*72, flush=True)

param_dist = {
    'n_estimators':     [200, 400],
    'max_depth':        [None, 20, 40],
    'min_samples_leaf': [1, 2, 5],
    'max_features':     ['sqrt', 0.3],
    'class_weight':     [None, 'balanced'],
}

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
rf_base = RandomForestClassifier(random_state=42, n_jobs=-1)
search = RandomizedSearchCV(
    rf_base, param_distributions=param_dist,
    n_iter=12, scoring='f1', cv=skf,
    random_state=42, n_jobs=1,
    verbose=1, refit=False,
)

print(f"Searching 12 candidates × 5-fold CV over: {list(param_dist.keys())}", flush=True)
t0 = time.time()
search.fit(X_train, y_train)
print(f"\n✅ Search complete in {(time.time()-t0)/60:.1f} min", flush=True)
print(f"Best CV F1: {search.best_score_:.4f}", flush=True)
print(f"Best params: {search.best_params_}", flush=True)

results_df = pd.DataFrame(search.cv_results_).sort_values('mean_test_score', ascending=False)
print("\nTop 5 configurations by CV F1:", flush=True)
for i, (_, row) in enumerate(results_df.head(5).iterrows(), 1):
    print(f"  {i}. CV F1={row['mean_test_score']:.4f} ±{row['std_test_score']:.4f}  {row['params']}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: REFIT BEST + CALIBRATE + THRESHOLD
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print("STEP 5: REFIT BEST CONFIG + CALIBRATION + THRESHOLD", flush=True)
print("="*72, flush=True)

best_rf = RandomForestClassifier(**search.best_params_, random_state=42, n_jobs=-1)
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.20, random_state=42, stratify=y_train
)
best_rf.fit(X_tr2, y_tr2)
calibrated = calibrate_model(best_rf, X_cal, y_cal)
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

print(f"\nInternal test — v1.2_candidate (threshold={opt_thresh:.2f}):", flush=True)
for k, v in final.items():
    print(f"  {k:10s}  {v:.4f}", flush=True)
print(f"  Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}", flush=True)
print(classification_report(y_test, y_pred_cal, target_names=['Legit','Scam']), flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: SAVE
# ══════════════════════════════════════════════════════════════════════════════
model_payload = {
    'model': calibrated,
    'threshold': float(opt_thresh),
    'hyperparameters': search.best_params_,
    'cv_score': float(search.best_score_),
}
pickle.dump(model_payload, open(os.path.join(CANDIDATE_DIR, 'scamradar_model.pkl'), 'wb'))
print(f"\n✅ Saved v1.2 to {CANDIDATE_DIR}/  (threshold={opt_thresh:.2f})", flush=True)

expected = ['scamradar_model.pkl', 'tfidf_vectorizer.pkl', 'char_vectorizer.pkl',
            'scaler.pkl', 'scam_faiss.index', 'legit_faiss.index', 'embeddings.npy']
missing = [f for f in expected if not os.path.exists(os.path.join(CANDIDATE_DIR, f))]
if missing:
    raise RuntimeError(f"Missing candidate artefacts: {missing}")
print(f"✅ All 7 artefacts present", flush=True)
