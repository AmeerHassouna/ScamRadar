"""
ScamRadar+ hold-out evaluation.

Loads the same 20% test split the model was originally evaluated on
(random_state=42, stratified), samples N messages, runs the FULL pipeline
(with all overrides + fixes), and reports proper metrics.

Compare against the reported 98.1% F1 on the raw model to see if the pipeline
changes preserved or hurt performance.

    python tests/holdout_eval.py [N]        # N = sample size, default 1000
"""
import sys, os, time, sqlite3, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, confusion_matrix, classification_report)

from src._09_prediction_pipeline import load_pipeline, predict_message
from config import DB_PATH, DEFAULT_THRESHOLD

SAMPLE_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = 42

# ── 1. Load data (same query as app.py) ────────────────────────────────────
print("Loading data from SQLite…")
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT m.message_id, m.raw_text, m.label, c.type AS channel
    FROM Message m
    JOIN Channel c ON m.channel_id = c.channel_id
    ORDER BY m.message_id
""", conn)
conn.close()
df['raw_text'] = df['raw_text'].fillna('')
print(f"Total: {len(df):,}   Legit: {(df.label==0).sum():,}   Scam: {(df.label==1).sum():,}")

# ── 2. Reproduce the exact same 20% test split (stratified, random_state=42) ─
idx_train, idx_test = train_test_split(
    np.arange(len(df)),
    test_size=0.20, random_state=SEED, stratify=df['label'].values,
)
test_df = df.iloc[idx_test].reset_index(drop=True)
print(f"Test split: {len(test_df):,}   Legit: {(test_df.label==0).sum():,}   Scam: {(test_df.label==1).sum():,}")

# ── 3. Stratified sample from the test split ───────────────────────────────
n_per_class = SAMPLE_SIZE // 2
legit_pool = test_df[test_df.label == 0]
scam_pool  = test_df[test_df.label == 1]
random.seed(SEED)
np.random.seed(SEED)
sample = pd.concat([
    legit_pool.sample(n=min(n_per_class, len(legit_pool)), random_state=SEED),
    scam_pool.sample(n=min(n_per_class, len(scam_pool)),  random_state=SEED),
], ignore_index=True)
# Skip messages under the pipeline's minimum length (they return TOO_SHORT)
sample = sample[sample['raw_text'].str.strip().str.len() >= 20].reset_index(drop=True)
print(f"Sample: {len(sample):,} messages (~{n_per_class} per class after length filter)\n")

# ── 4. Load pipeline once ──────────────────────────────────────────────────
print("Loading pipeline (post-fix)…")
model, tfidf, char_tfidf, scaler, scam_idx, st_model = load_pipeline()

# ── 5. Run predictions ─────────────────────────────────────────────────────
print(f"\nPredicting {len(sample):,} messages…")
predictions, verdicts, confidences = [], [], []
t0 = time.time()

for i, row in enumerate(sample.itertuples()):
    if i and i % 100 == 0:
        elapsed = time.time() - t0
        rate    = i / elapsed
        eta     = (len(sample) - i) / rate
        print(f"  {i}/{len(sample)}  ({rate:.1f} msg/s, ETA {eta:.0f}s)")
    r = predict_message(row.raw_text, model, tfidf, char_tfidf, scaler,
                        scam_idx, st_model,
                        threshold=DEFAULT_THRESHOLD,
                        vt_api_key=None, gsb_api_key=None)
    v = r['verdict']
    verdicts.append(v)
    confidences.append(r['confidence'])
    # Binary prediction: SCAM or SUSPICIOUS → 1, LEGIT → 0
    predictions.append(1 if v in ('SCAM', 'SUSPICIOUS') else 0)

print(f"\nTotal time: {time.time()-t0:.1f}s   ({len(sample)/(time.time()-t0):.1f} msg/s)\n")

# ── 6. Metrics ─────────────────────────────────────────────────────────────
y_true = sample['label'].values
y_pred = np.array(predictions)

acc  = accuracy_score(y_true, y_pred)
prec = precision_score(y_true, y_pred, zero_division=0)
rec  = recall_score(y_true, y_pred, zero_division=0)
f1   = f1_score(y_true, y_pred, zero_division=0)
cm   = confusion_matrix(y_true, y_pred)
tn, fp, fn, tp = cm.ravel()

print("═" * 70)
print(f"HOLD-OUT EVALUATION — {len(sample):,} messages (post-fix pipeline)")
print("═" * 70)
print(f"  Accuracy       : {acc:.4f}")
print(f"  Precision      : {prec:.4f}   (of what we flagged, how many were real scams)")
print(f"  Recall         : {rec:.4f}   (of real scams, how many we caught)")
print(f"  F1             : {f1:.4f}   (reported model F1: 0.9811)")
print()
print(f"  Confusion matrix:")
print(f"                       predicted")
print(f"                    LEGIT    SCAM/SUS")
print(f"    actual LEGIT   {tn:>6d}   {fp:>6d}   ← {fp} false positives")
print(f"    actual SCAM    {fn:>6d}   {tp:>6d}   ← {fn} false negatives")
print()

# Also report LEGIT-only accuracy (three-tier: how often we get exact tier right)
scam_flagged   = (np.array(verdicts) == 'SCAM').sum()
sus_flagged    = (np.array(verdicts) == 'SUSPICIOUS').sum()
legit_flagged  = (np.array(verdicts) == 'LEGIT').sum()
print(f"  Verdict distribution:")
print(f"    SCAM       : {scam_flagged:>5d} ({scam_flagged/len(sample)*100:.1f}%)")
print(f"    SUSPICIOUS : {sus_flagged:>5d} ({sus_flagged/len(sample)*100:.1f}%)")
print(f"    LEGIT      : {legit_flagged:>5d} ({legit_flagged/len(sample)*100:.1f}%)")
print()
print(classification_report(y_true, y_pred, target_names=['LEGIT', 'SCAM']))

# ── 7. Error analysis — show samples of each error type ────────────────────
sample = sample.copy()
sample['verdict']    = verdicts
sample['confidence'] = confidences
sample['pred']       = y_pred

fp_msgs = sample[(sample.label == 0) & (sample.pred == 1)].sort_values('confidence', ascending=False)
fn_msgs = sample[(sample.label == 1) & (sample.pred == 0)].sort_values('confidence')

print("─" * 70)
print(f"TOP 10 FALSE POSITIVES  (legit messages we flagged as scam/suspicious):")
print("─" * 70)
for _, r in fp_msgs.head(10).iterrows():
    txt = r['raw_text'][:150].replace('\n', ' ')
    print(f"  [{r['verdict']:<10} {r['confidence']:>5.1f}%]  {txt}…")

print()
print("─" * 70)
print(f"TOP 10 FALSE NEGATIVES  (scam messages we missed):")
print("─" * 70)
for _, r in fn_msgs.head(10).iterrows():
    txt = r['raw_text'][:150].replace('\n', ' ')
    print(f"  [{r['verdict']:<10} {r['confidence']:>5.1f}%]  {txt}…")

print()
