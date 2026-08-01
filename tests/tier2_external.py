"""
Tier 2 — external validation on the Deysi/spam-detection-dataset test split.

This dataset was NEVER seen by the model:
  • Modern synthetic spam (iPhone X ads, weight loss, emoji spam, GET RICH QUICK)
  • Real Reddit-style questions as non-spam
  • Completely different domain than Enron/SpamAssassin/UCI-SMS/PhishTank

If the model performs well here, it means the fixes generalise to real modern
messages users would actually paste — not just to the hold-out.

    python tests/tier2_external.py [N]        # N = sample size, default 1000
"""
import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datasets import load_dataset
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, confusion_matrix, classification_report)

from src._09_prediction_pipeline import load_pipeline, predict_message
from config import DEFAULT_THRESHOLD

SAMPLE_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = 42

# ── 1. Load external dataset ───────────────────────────────────────────────
print("Loading Deysi/spam-detection-dataset (test split)…")
ds = load_dataset("Deysi/spam-detection-dataset", split="test")
texts = ds['text']
labels = [1 if l == 'spam' else 0 for l in ds['label']]
print(f"Total: {len(texts):,}   Spam: {sum(labels):,}   Not-spam: {len(labels)-sum(labels):,}")

# ── 2. Filter min length + stratified sample ───────────────────────────────
valid_idx = [i for i, t in enumerate(texts) if t and len(t.strip()) >= 20]
spam_idx    = [i for i in valid_idx if labels[i] == 1]
notspam_idx = [i for i in valid_idx if labels[i] == 0]
random.seed(SEED)
n_per_class = SAMPLE_SIZE // 2
sample_idx = (random.sample(spam_idx,    min(n_per_class, len(spam_idx))) +
              random.sample(notspam_idx, min(n_per_class, len(notspam_idx))))
random.shuffle(sample_idx)
print(f"Sample: {len(sample_idx):,} messages\n")

# ── 3. Load pipeline ───────────────────────────────────────────────────────
print("Loading pipeline (post-fix)…")
model, tfidf, char_tfidf, scaler, scam_idx, st_model = load_pipeline()

# ── 4. Predict ─────────────────────────────────────────────────────────────
print(f"\nPredicting {len(sample_idx):,} messages…")
predictions, verdicts, confs, sample_texts, sample_labels = [], [], [], [], []
t0 = time.time()
for i, idx in enumerate(sample_idx):
    if i and i % 100 == 0:
        rate = i / (time.time() - t0)
        eta  = (len(sample_idx) - i) / rate
        print(f"  {i}/{len(sample_idx)}  ({rate:.1f} msg/s, ETA {eta:.0f}s)")
    txt = texts[idx]
    r = predict_message(txt, model, tfidf, char_tfidf, scaler,
                        scam_idx, st_model,
                        threshold=DEFAULT_THRESHOLD,
                        vt_api_key=None, gsb_api_key=None)
    verdicts.append(r['verdict'])
    confs.append(r['confidence'])
    predictions.append(1 if r['verdict'] in ('SCAM', 'SUSPICIOUS') else 0)
    sample_texts.append(txt)
    sample_labels.append(labels[idx])

print(f"\nTotal time: {time.time()-t0:.1f}s\n")

# ── 5. Metrics ─────────────────────────────────────────────────────────────
y_true = np.array(sample_labels)
y_pred = np.array(predictions)

acc  = accuracy_score(y_true, y_pred)
prec = precision_score(y_true, y_pred, zero_division=0)
rec  = recall_score(y_true, y_pred, zero_division=0)
f1   = f1_score(y_true, y_pred, zero_division=0)
cm   = confusion_matrix(y_true, y_pred)
tn, fp, fn, tp = cm.ravel()

print("═" * 70)
print(f"TIER 2 — EXTERNAL DATASET (Deysi, model has never seen it)")
print(f"        {len(sample_idx):,} messages")
print("═" * 70)
print(f"  Accuracy       : {acc:.4f}")
print(f"  Precision      : {prec:.4f}")
print(f"  Recall         : {rec:.4f}")
print(f"  F1             : {f1:.4f}")
print()
print(f"  Confusion matrix:")
print(f"                          predicted")
print(f"                    NOT-SPAM     SPAM/SUS")
print(f"    actual NOT-SPAM {tn:>6d}      {fp:>6d}   ← {fp} false positives")
print(f"    actual SPAM     {fn:>6d}      {tp:>6d}   ← {fn} false negatives")
print()

scam_n = sum(1 for v in verdicts if v == 'SCAM')
sus_n  = sum(1 for v in verdicts if v == 'SUSPICIOUS')
leg_n  = sum(1 for v in verdicts if v == 'LEGIT')
print(f"  Verdict distribution:")
print(f"    SCAM       : {scam_n:>5d} ({scam_n/len(sample_idx)*100:.1f}%)")
print(f"    SUSPICIOUS : {sus_n:>5d} ({sus_n/len(sample_idx)*100:.1f}%)")
print(f"    LEGIT      : {leg_n:>5d} ({leg_n/len(sample_idx)*100:.1f}%)")
print()
print(classification_report(y_true, y_pred, target_names=['NOT-SPAM', 'SPAM']))

# ── 6. Error samples ───────────────────────────────────────────────────────
fp_pairs = [(i, sample_texts[i], verdicts[i], confs[i])
            for i in range(len(sample_idx))
            if sample_labels[i] == 0 and predictions[i] == 1]
fn_pairs = [(i, sample_texts[i], verdicts[i], confs[i])
            for i in range(len(sample_idx))
            if sample_labels[i] == 1 and predictions[i] == 0]
fp_pairs.sort(key=lambda x: -x[3])
fn_pairs.sort(key=lambda x:  x[3])

print("─" * 70)
print(f"TOP 10 FALSE POSITIVES  (non-spam we called scam):")
print("─" * 70)
for i, txt, v, c in fp_pairs[:10]:
    print(f"  [{v:<10} {c:>5.1f}%]  {txt[:140].strip()}…")

print()
print("─" * 70)
print(f"TOP 10 FALSE NEGATIVES  (spam we missed):")
print("─" * 70)
for i, txt, v, c in fn_pairs[:10]:
    print(f"  [{v:<10} {c:>5.1f}%]  {txt[:140].strip()}…")
print()
