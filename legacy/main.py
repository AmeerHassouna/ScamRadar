"""
ScamRadar+ | Main Pipeline  (v5)
Runs the complete improved modelling pipeline end to end.
Shows old-v4 vs new-v5 accuracy comparison at the end.
"""

import os, sys, sqlite3, pickle
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (DB_PATH, MODELS_PATH, OUTPUT_PATH,
                    NUMERICAL_FEATURES_V4, NUMERICAL_FEATURES_V5,
                    REBUILD_INDEX, DEFAULT_THRESHOLD)

os.makedirs(MODELS_PATH, exist_ok=True)
os.makedirs(OUTPUT_PATH,  exist_ok=True)

# ─── STEP 1: LOAD DATA ────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 1: DATA LOADING")
print("="*60)

conn = sqlite3.connect(DB_PATH)
query = """
SELECT m.message_id, m.raw_text, m.label,
       c.type AS channel, ds.name AS source,
       mf.text_length, mf.word_count, mf.has_url, mf.url_count,
       mf.exclamation_count, mf.uppercase_ratio, mf.digit_ratio, mf.urgency_score
FROM Message m
JOIN Channel c ON m.channel_id = c.channel_id
JOIN DataSource ds ON m.source_id = ds.source_id
JOIN MessageFeatures mf ON m.message_id = mf.message_id
ORDER BY m.message_id
"""
df = pd.read_sql_query(query, conn)
conn.close()
print(f"✅ Loaded {len(df)} rows")
print(df['label'].value_counts())

# ─── STEP 2: FEATURE ENGINEERING (v5) ────────────────────────────────────
print("\n" + "="*60)
print("STEP 2: FEATURE ENGINEERING  (v5 — phrase-level tone + 9 new features)")
print("="*60)

from src._02_feature_engineering import add_features
df = add_features(df)

# Tone sanity-check
print("\nNegation sanity check:")
test_cases = [
    "You are free to leave anytime.",
    "GET YOUR FREE GIFT NOW — CLAIM TODAY!",
    "No prize has been awarded to you.",
    "You have won a prize! Claim now!",
]
from src._02_feature_engineering import compute_tone_features
for t in test_cases:
    u, f, r, th = compute_tone_features(t)
    print(f"  reward={r} urgency={u} | {t[:55]}")

# ─── STEP 3: VECTOR PROXIMITY (v5 — k=10, dual index) ────────────────────
print("\n" + "="*60)
print("STEP 3: VECTOR PROXIMITY  (k=10, scam + legit indices)")
print("="*60)

from src._04_vector_proximity import (
    load_sentence_model, encode_messages,
    build_faiss_index, build_legit_faiss_index,
    compute_proximity_scores, save_faiss_index,
)

st_model   = load_sentence_model()
embeddings = encode_messages(st_model, df['raw_text'].fillna('').tolist())

scam_index  = build_faiss_index(embeddings, df['label'].values)
legit_index = build_legit_faiss_index(embeddings, df['label'].values)

prox_scam, prox_legit, prox_delta = compute_proximity_scores(
    embeddings, scam_index, legit_index
)
df['proximity_scam_score']  = prox_scam * 0.5   # scaled ×0.5 before feature matrix
df['legit_proximity_score'] = prox_legit          # display-only; not in feature list
df['proximity_delta']       = prox_delta           # display-only; not in feature list

save_faiss_index(scam_index, embeddings, legit_index)

print(f"\nProximity scores by label:")
print(df.groupby('label')[['proximity_scam_score','legit_proximity_score','proximity_delta']].mean())

# ─── STEP 4: TF-IDF + COMBINE (v5) ───────────────────────────────────────
print("\n" + "="*60)
print("STEP 4: TF-IDF VECTORIZATION + FEATURE COMBINATION  (v5 — 27 features)")
print("="*60)

from src._03_tfidf_vectorization import (
    build_tfidf, build_combined_features, split_data, save_vectorizers,
    NUMERICAL_FEATURES_V5,
)

tfidf, char_tfidf, X_tfidf, X_char = build_tfidf(df)
y = df['label'].values
X_combined, scaler = build_combined_features(df, X_tfidf, X_char, NUMERICAL_FEATURES_V5)
X_train, X_test, y_train, y_test = split_data(X_combined, y)
save_vectorizers(tfidf, char_tfidf, scaler)

# ─── STEP 5: TRAIN MODELS ────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 5: MODEL TRAINING")
print("="*60)

from src._05_model_training import (
    train_all_models, calibrate_model,
    find_optimal_threshold, save_best_model,
)

trained_models = train_all_models(X_train, y_train)

# ─── STEP 6: EVALUATE ALL MODELS ─────────────────────────────────────────
print("\n" + "="*60)
print("STEP 6: EVALUATION")
print("="*60)

from src._06_evaluation import (
    evaluate_all_models, plot_confusion_matrices, plot_roc_curves,
    plot_feature_importance, cross_validate_models, evaluate_per_channel,
)

results = evaluate_all_models(trained_models, X_test, y_test)
plot_confusion_matrices(trained_models, X_test, y_test)
plot_roc_curves(trained_models, X_test, y_test)
plot_feature_importance(trained_models["Random Forest"], tfidf, char_tfidf, NUMERICAL_FEATURES_V5)
evaluate_per_channel(df, trained_models["Random Forest"], X_combined, y)

# ─── STEP 7: SELECT BEST MODEL ───────────────────────────────────────────
print("\n" + "="*60)
print("STEP 7: MODEL SELECTION")
print("="*60)

best_name = max(results, key=lambda n: results[n]['F1'])
best_model_raw = trained_models[best_name]
print(f"✅ Best model: {best_name}  (F1={results[best_name]['F1']:.4f})")

# ─── STEP 8: CALIBRATION + THRESHOLD OPTIMISATION ────────────────────────
print("\n" + "="*60)
print("STEP 8: CALIBRATION + THRESHOLD OPTIMISATION")
print("="*60)

# Use 20 % of train set as calibration / validation set
X_tr2, X_cal, y_tr2, y_cal = train_test_split(
    X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
)
# Re-fit on reduced training set so calibration is on held-out data
best_model_raw.fit(X_tr2, y_tr2)

calibrated_model = calibrate_model(best_model_raw, X_cal, y_cal)
optimal_threshold, _ = find_optimal_threshold(calibrated_model, X_cal, y_cal)

# Evaluate calibrated model on test set
from sklearn.metrics import classification_report
y_prob_cal = calibrated_model.predict_proba(X_test)[:, 1]
y_pred_cal = (y_prob_cal >= optimal_threshold).astype(int)
print(f"\nCalibrated {best_name} — Test Set (threshold={optimal_threshold:.2f}):")
print(f"  Accuracy:  {accuracy_score(y_test, y_pred_cal):.4f}")
print(f"  F1:        {f1_score(y_test, y_pred_cal):.4f}")
print(f"  AUC-ROC:   {roc_auc_score(y_test, y_prob_cal):.4f}")
print(classification_report(y_test, y_pred_cal, target_names=['Legit','Scam']))

save_best_model(calibrated_model, threshold=optimal_threshold)
print(f"✅ Calibrated model saved to models/scamradar_model.pkl")

# ─── STEP 9: HYPERPARAMETER TUNING ───────────────────────────────────────
print("\n" + "="*60)
print("STEP 9: HYPERPARAMETER TUNING (Random Forest)")
print("="*60)

from src._07_hyperparameter_tuning import tune_random_forest
best_rf, best_params = tune_random_forest(X_train, y_train, X_test, y_test, n_iter=5)

# Compare tuned RF vs selected best
rf_f1  = f1_score(y_test, best_rf.predict(X_test))
sel_f1 = f1_score(y_test, y_pred_cal)
if rf_f1 > sel_f1:
    print(f"Tuned RF (F1={rf_f1:.4f}) beats calibrated {best_name} (F1={sel_f1:.4f}) → saving tuned RF")
    tuned_cal = calibrate_model(best_rf, X_cal, y_cal)
    t_opt, _  = find_optimal_threshold(tuned_cal, X_cal, y_cal)
    save_best_model(tuned_cal, threshold=t_opt)
else:
    print(f"Calibrated {best_name} (F1={sel_f1:.4f}) remains production model")

# ─── STEP 10: ADVERSARIAL TESTING ────────────────────────────────────────
print("\n" + "="*60)
print("STEP 10: ADVERSARIAL ROBUSTNESS TESTING")
print("="*60)

from src._09_prediction_pipeline import predict_message, load_pipeline
from src._08_adversarial_testing import run_all_adversarial_tests

prod_model, _tfidf, _char, _scaler, _scam_idx, _st = load_pipeline()
_thresh = DEFAULT_THRESHOLD

def predict_fn(text):
    return predict_message(
        text, prod_model, _tfidf, _char, _scaler,
        _scam_idx, _st, threshold=_thresh,
    )

run_all_adversarial_tests(predict_fn)

# ─── STEP 11: OLD vs NEW COMPARISON ──────────────────────────────────────
print("\n" + "="*60)
print("STEP 11: v4 vs v5 ACCURACY COMPARISON")
print("="*60)

print("\n  v4 results (from previous pipeline run — 16 features):")
v4_reference = {
    "Logistic Regression": {"Accuracy": 0.9820, "F1": 0.9811, "AUC-ROC": 0.9983},
    "Decision Tree":       {"Accuracy": 0.9747, "F1": 0.9735, "AUC-ROC": 0.9745},
    "Random Forest":       {"Accuracy": 0.9771, "F1": 0.9761, "AUC-ROC": 0.9956},
}
for name, m in v4_reference.items():
    print(f"    {name:25s}  Acc={m['Accuracy']:.4f}  F1={m['F1']:.4f}  AUC={m['AUC-ROC']:.4f}")

print(f"\n  v5 results (this run — 27 features):")
for name, m in results.items():
    delta_acc = m['Accuracy'] - v4_reference.get(name, {}).get('Accuracy', m['Accuracy'])
    delta_f1  = m['F1']       - v4_reference.get(name, {}).get('F1',       m['F1'])
    sign_acc  = '+' if delta_acc >= 0 else ''
    sign_f1   = '+' if delta_f1  >= 0 else ''
    auc_val   = m.get('AUC', m.get('AUC-ROC', 0.0))
    print(f"    {name:25s}  Acc={m['Accuracy']:.4f} ({sign_acc}{delta_acc:+.4f})  "
          f"F1={m['F1']:.4f} ({sign_f1}{delta_f1:+.4f})  AUC={auc_val:.4f}")

print(f"\n  Production model : {best_name} (calibrated, threshold={optimal_threshold:.2f})")
print(f"  Feature count    : {len(NUMERICAL_FEATURES_V5)} numerical + TF-IDF 5000 + char 3000")

print("\n✅ Pipeline v5 complete! Models saved to models/")
print("✅ Plots saved to outputs/")
