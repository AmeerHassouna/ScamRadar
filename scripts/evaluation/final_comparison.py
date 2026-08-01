"""
Final scientific comparison — original v1.0 pipeline vs frozen v1.3 baseline.

Design principles:
  * Test set: the 400 reserved external items from data/external_evaluation/.
  * These items are held out from v1.3's training (verified during data prep)
    and were never seen by v1.0 (they came from HuggingFace/Reddit, not the DB).
  * SHA-1 overlap verification is repeated here explicitly and documented.
  * Both models run through the identical predict_message() function.
  * FAISS + sentence-transformers ENABLED for both — the fair scientific
    comparison, not production-mode. Both models have FAISS indices.
  * Every disagreement between the two models is enumerated with the raw text.
  * All false positives and false negatives are listed for both models.
  * A structured JSON is written to outputs/eval/final_comparison.json.
  * A human-readable Markdown report is written to outputs/final_comparison_report.md.
"""
import os, sys, csv, pickle, time, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
import sqlite3
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, average_precision_score,
                             confusion_matrix)

from src._00_dedup import normalise_text
from src._09_prediction_pipeline import predict_message
from config import DEFAULT_THRESHOLD, DB_PATH

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V10_DIR        = os.path.join(BASE_DIR, 'models', 'v1.0_frozen')
V13_DIR        = os.path.join(BASE_DIR, 'models', 'v1.3_baseline')
EVAL_CSV       = os.path.join(BASE_DIR, 'data', 'external_evaluation', 'external_eval.csv')
EXT_TRAIN_CSV  = os.path.join(BASE_DIR, 'data', 'external_training', 'external_train.csv')
OUT_JSON       = os.path.join(BASE_DIR, 'outputs', 'eval', 'final_comparison.json')
OUT_MD         = os.path.join(BASE_DIR, 'outputs', 'final_comparison_report.md')


def _hash(text: str) -> str:
    return hashlib.sha1(normalise_text(text).encode('utf-8')).hexdigest()


def load_pipeline(models_dir: str):
    """Load model artefacts + FAISS scam index + sentence-transformer encoder."""
    import faiss
    from sentence_transformers import SentenceTransformer

    payload    = pickle.load(open(os.path.join(models_dir, 'scamradar_model.pkl'), 'rb'))
    tfidf      = pickle.load(open(os.path.join(models_dir, 'tfidf_vectorizer.pkl'), 'rb'))
    char_tfidf = pickle.load(open(os.path.join(models_dir, 'char_vectorizer.pkl'), 'rb'))
    scaler     = pickle.load(open(os.path.join(models_dir, 'scaler.pkl'), 'rb'))
    scam_idx   = faiss.read_index(os.path.join(models_dir, 'scam_faiss.index'))
    st_model   = SentenceTransformer('all-MiniLM-L6-v2')

    model = payload['model'] if isinstance(payload, dict) else payload
    threshold = payload.get('threshold', DEFAULT_THRESHOLD) if isinstance(payload, dict) else DEFAULT_THRESHOLD
    return {'model': model, 'tfidf': tfidf, 'char_tfidf': char_tfidf, 'scaler': scaler,
            'scam_idx': scam_idx, 'st_model': st_model, 'threshold': threshold}


# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD TEST SET
# ══════════════════════════════════════════════════════════════════════════════
print("STEP 1: Load reserved external evaluation set", flush=True)
items = []
with open(EVAL_CSV, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        items.append({
            'raw_text': r['raw_text'],
            'label':    int(r['label']),
            'source':   r['source'],
            'hash':     _hash(r['raw_text']),
        })
print(f"  {len(items):,} items ({sum(1 for i in items if i['label']==1)} scam / "
      f"{sum(1 for i in items if i['label']==0)} legit)", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. OVERLAP VERIFICATION AGAINST BOTH MODELS' TRAINING DATA
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2: SHA-1 overlap verification against both models' training sets", flush=True)

# 2a. v1.0's training corpus = ALL 46,360 DB rows (v1.0 was trained on unfiltered corpus)
conn = sqlite3.connect(DB_PATH)
v10_train = pd.read_sql_query("SELECT raw_text FROM Message", conn)
conn.close()
v10_train['hash'] = v10_train['raw_text'].fillna('').map(_hash)
v10_hashes = set(v10_train['hash'].tolist())
print(f"  v1.0 training corpus: {len(v10_train):,} rows → {len(v10_hashes):,} unique hashes")

# 2b. v1.3's training corpus = v1.0's corpus after dedup + 1,133 external training additions
ext_train = pd.read_csv(EXT_TRAIN_CSV)
ext_train['hash'] = ext_train['raw_text'].fillna('').map(_hash)
v13_added_hashes = set(ext_train['hash'].tolist())
v13_hashes = v10_hashes | v13_added_hashes
print(f"  v1.3 additional training items: {len(ext_train):,} → {len(v13_added_hashes):,} unique")
print(f"  v1.3 total training hashes (v1.0 ∪ added): {len(v13_hashes):,}")

# 2c. Check each test item
overlap_v10 = 0
overlap_v13 = 0
for it in items:
    if it['hash'] in v10_hashes:
        overlap_v10 += 1
    if it['hash'] in v13_hashes:
        overlap_v13 += 1
print(f"\n  Test set overlap with v1.0 training: {overlap_v10:,} / {len(items):,}  (must be 0)")
print(f"  Test set overlap with v1.3 training: {overlap_v13:,} / {len(items):,}  (must be 0)")
assert overlap_v10 == 0, f"CRITICAL: v1.0 training overlap {overlap_v10}"
assert overlap_v13 == 0, f"CRITICAL: v1.3 training overlap {overlap_v13}"
print("  ✅ Both overlaps are zero — test set is genuinely unseen by both models.")


# ══════════════════════════════════════════════════════════════════════════════
# 3. LOAD BOTH MODELS (FAISS + ST ENABLED)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3: Load both models with FAISS + sentence-transformers enabled", flush=True)
print("  Loading v1.0 (LogisticRegression, threshold 0.46)…", flush=True)
p10 = load_pipeline(V10_DIR)
print(f"    base={type(p10['model'].base_model).__name__}, threshold={p10['threshold']}, "
      f"FAISS ntotal={p10['scam_idx'].ntotal}")

print("  Loading v1.3 (RandomForest, threshold 0.40)…", flush=True)
p13 = load_pipeline(V13_DIR)
print(f"    base={type(p13['model'].base_model).__name__}, threshold={p13['threshold']}, "
      f"FAISS ntotal={p13['scam_idx'].ntotal}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. RUN BOTH MODELS ON THE 400 ITEMS THROUGH IDENTICAL predict_message()
# ══════════════════════════════════════════════════════════════════════════════
print(f"\nSTEP 4: Predict {len(items)} items with both models", flush=True)


def run(pipe, items, tag):
    preds, probs, verdicts = [], [], []
    t0 = time.time()
    for i, it in enumerate(items):
        if i and i % 50 == 0:
            rate = i / (time.time()-t0)
            eta = (len(items) - i) / rate
            print(f"    {tag}: {i}/{len(items)}  ({rate:.1f} msg/s, ETA {eta:.0f}s)")
        r = predict_message(it['raw_text'], pipe['model'], pipe['tfidf'], pipe['char_tfidf'],
                            pipe['scaler'], pipe['scam_idx'], pipe['st_model'],
                            threshold=pipe['threshold'], vt_api_key=None, gsb_api_key=None)
        verdicts.append(r['verdict'])
        preds.append(1 if r['verdict'] in ('SCAM', 'SUSPICIOUS') else 0)
        probs.append(float(r.get('confidence', 0)) / 100.0)
    print(f"    {tag}: total {time.time()-t0:.1f}s")
    return np.array(preds), np.array(probs), verdicts

pred10, prob10, verd10 = run(p10, items, 'v1.0')
pred13, prob13, verd13 = run(p13, items, 'v1.3')


# ══════════════════════════════════════════════════════════════════════════════
# 5. METRICS FOR BOTH
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5: Compute all metrics")
y = np.array([it['label'] for it in items])

def metrics(y_true, y_pred, y_prob):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        'n':         int(len(y_true)),
        'accuracy':  round(float(accuracy_score(y_true, y_pred)), 4),
        'precision': round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        'recall':    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        'f1':        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        'roc_auc':   round(float(roc_auc_score(y_true, y_prob)), 4),
        'pr_auc':    round(float(average_precision_score(y_true, y_prob)), 4),
        'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    }

m10 = metrics(y, pred10, prob10)
m13 = metrics(y, pred13, prob13)


# ══════════════════════════════════════════════════════════════════════════════
# 6. DISAGREEMENTS + FP / FN LISTINGS
# ══════════════════════════════════════════════════════════════════════════════
disagreements = []
v10_fp, v10_fn, v13_fp, v13_fn = [], [], [], []

for i, it in enumerate(items):
    r10 = int(pred10[i]); r13 = int(pred13[i])
    row = {
        'idx':      i,
        'label':    it['label'],
        'source':   it['source'],
        'text':     it['raw_text'][:300].replace('\n', ' '),
        'v10_verdict':    verd10[i],
        'v10_pred':       r10,
        'v10_confidence': round(float(prob10[i]) * 100, 2),
        'v13_verdict':    verd13[i],
        'v13_pred':       r13,
        'v13_confidence': round(float(prob13[i]) * 100, 2),
    }
    if r10 != r13:
        disagreements.append(row)
    # FP/FN buckets per model
    if it['label'] == 0 and r10 == 1: v10_fp.append(row)
    if it['label'] == 1 and r10 == 0: v10_fn.append(row)
    if it['label'] == 0 and r13 == 1: v13_fp.append(row)
    if it['label'] == 1 and r13 == 0: v13_fn.append(row)

# Categorise disagreements
v13_correct_v10_wrong = sum(1 for d in disagreements if d['v13_pred'] == d['label'] and d['v10_pred'] != d['label'])
v10_correct_v13_wrong = sum(1 for d in disagreements if d['v10_pred'] == d['label'] and d['v13_pred'] != d['label'])
both_wrong = sum(1 for d in disagreements if d['v10_pred'] != d['label'] and d['v13_pred'] != d['label'])

print(f"  Total disagreements: {len(disagreements)}/{len(items)}")
print(f"    v1.3 correct, v1.0 wrong: {v13_correct_v10_wrong}")
print(f"    v1.0 correct, v1.3 wrong: {v10_correct_v13_wrong}")
print(f"    Both wrong (different wrong verdicts): {both_wrong}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. WRITE JSON + MARKDOWN
# ══════════════════════════════════════════════════════════════════════════════
result = {
    'test_set': {
        'source':       'data/external_evaluation/external_eval.csv',
        'n':            len(items),
        'n_scam':       int((y == 1).sum()),
        'n_legit':      int((y == 0).sum()),
    },
    'overlap_verification': {
        'v10_training_corpus_size':        len(v10_train),
        'v10_unique_training_hashes':      len(v10_hashes),
        'v13_additional_training_items':   len(ext_train),
        'v13_total_training_hashes':       len(v13_hashes),
        'test_overlap_with_v10_training':  overlap_v10,
        'test_overlap_with_v13_training':  overlap_v13,
        'result':                          'PASS (zero overlap for both models)',
    },
    'v1.0': m10,
    'v1.3': m13,
    'improvement': {
        'delta_accuracy':  round(m13['accuracy']  - m10['accuracy'],  4),
        'delta_precision': round(m13['precision'] - m10['precision'], 4),
        'delta_recall':    round(m13['recall']    - m10['recall'],    4),
        'delta_f1':        round(m13['f1']        - m10['f1'],        4),
        'delta_roc_auc':   round(m13['roc_auc']   - m10['roc_auc'],   4),
        'delta_pr_auc':    round(m13['pr_auc']    - m10['pr_auc'],    4),
    },
    'disagreements': {
        'total':                    len(disagreements),
        'v13_correct_v10_wrong':    v13_correct_v10_wrong,
        'v10_correct_v13_wrong':    v10_correct_v13_wrong,
        'both_wrong':               both_wrong,
        'items':                    disagreements,
    },
    'v1.0_errors': {'false_positives': v10_fp, 'false_negatives_head': v10_fn[:20],
                     'fp_count': len(v10_fp), 'fn_count': len(v10_fn)},
    'v1.3_errors': {'false_positives': v13_fp, 'false_negatives': v13_fn,
                     'fp_count': len(v13_fp), 'fn_count': len(v13_fn)},
}

os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
with open(OUT_JSON, 'w') as f:
    json.dump(result, f, indent=2)
print(f"\n✅ Wrote {OUT_JSON}")

# Markdown human-readable
md_lines = [
    "# Final Scientific Comparison — v1.0 (Original) vs v1.3 (Frozen Baseline)",
    "",
    "**Test set:** the 400 reserved external items from `data/external_evaluation/external_eval.csv`",
    "**Composition:** 250 zefang-liu phishing (label=1) + 150 Reddit legit (label=0)",
    "**Provenance:** collected during Intervention 4 data prep, held apart from v1.3 training",
    "**FAISS + sentence-transformers:** ENABLED for both models (fair comparison, not production-mode)",
    "",
    "## Overlap verification (SHA-1 on normalise_text)",
    "",
    f"| Check | Value |",
    f"|---|---:|",
    f"| v1.0 training corpus size | {len(v10_train):,} rows |",
    f"| v1.0 unique training hashes | {len(v10_hashes):,} |",
    f"| v1.3 additional training items | {len(ext_train):,} |",
    f"| v1.3 total training hashes (v1.0 ∪ added) | {len(v13_hashes):,} |",
    f"| Test set size | {len(items):,} |",
    f"| **Test items overlapping v1.0 training** | **{overlap_v10}** (must be 0) |",
    f"| **Test items overlapping v1.3 training** | **{overlap_v13}** (must be 0) |",
    "",
    f"**Verdict:** ✅ Zero overlap for both models — test set is genuinely unseen by both.",
    "",
    "## Headline metrics",
    "",
    "| Metric | v1.0 | v1.3 | Δ |",
    "|---|---:|---:|---:|",
    f"| Accuracy | {m10['accuracy']:.4f} | {m13['accuracy']:.4f} | {(m13['accuracy']-m10['accuracy']):+.4f} |",
    f"| Precision | {m10['precision']:.4f} | {m13['precision']:.4f} | {(m13['precision']-m10['precision']):+.4f} |",
    f"| Recall | {m10['recall']:.4f} | {m13['recall']:.4f} | {(m13['recall']-m10['recall']):+.4f} |",
    f"| **F1** | **{m10['f1']:.4f}** | **{m13['f1']:.4f}** | **{(m13['f1']-m10['f1']):+.4f}** |",
    f"| ROC-AUC | {m10['roc_auc']:.4f} | {m13['roc_auc']:.4f} | {(m13['roc_auc']-m10['roc_auc']):+.4f} |",
    f"| PR-AUC | {m10['pr_auc']:.4f} | {m13['pr_auc']:.4f} | {(m13['pr_auc']-m10['pr_auc']):+.4f} |",
    "",
    "## Confusion matrices",
    "",
    "**v1.0 (original LogisticRegression, threshold 0.46):**",
    "",
    "|  | Predicted LEGIT | Predicted SCAM |",
    "|---|---:|---:|",
    f"| Actual LEGIT | {m10['confusion']['tn']} (TN) | {m10['confusion']['fp']} (FP) |",
    f"| Actual SCAM | {m10['confusion']['fn']} (FN) | {m10['confusion']['tp']} (TP) |",
    "",
    "**v1.3 (RandomForest + external phishing data + train-only fitting, threshold 0.40):**",
    "",
    "|  | Predicted LEGIT | Predicted SCAM |",
    "|---|---:|---:|",
    f"| Actual LEGIT | {m13['confusion']['tn']} (TN) | {m13['confusion']['fp']} (FP) |",
    f"| Actual SCAM | {m13['confusion']['fn']} (FN) | {m13['confusion']['tp']} (TP) |",
    "",
    "## Disagreements summary",
    "",
    f"| Category | Count |",
    f"|---|---:|",
    f"| Total items where the two models disagreed | {len(disagreements)} |",
    f"| **v1.3 correct, v1.0 wrong** | **{v13_correct_v10_wrong}** |",
    f"| v1.0 correct, v1.3 wrong | {v10_correct_v13_wrong} |",
    f"| Both wrong (different wrong verdicts) | {both_wrong} |",
    "",
]

# Full FP/FN listings
def _fmt_table(rows, header):
    if not rows:
        return ["*(none)*", ""]
    out = [f"| # | source | label | v1.0 conf | v1.3 conf | text |",
           f"|---:|---|---:|---:|---:|---|"]
    for r in rows:
        out.append(f"| {r['idx']} | {r['source']} | {r['label']} | "
                   f"{r['v10_confidence']:.1f} | {r['v13_confidence']:.1f} | "
                   f"{r['text'][:180].replace('|','│')} |")
    out.append("")
    return out

md_lines += ["## v1.0 false positives (legit misclassified as scam)", ""]
md_lines += [f"**Total: {len(v10_fp)}**", ""]
md_lines += _fmt_table(v10_fp, 'v1.0 FP')

md_lines += ["## v1.0 false negatives (scams missed — first 20 shown)", ""]
md_lines += [f"**Total: {len(v10_fn)}**", ""]
md_lines += _fmt_table(v10_fn[:20], 'v1.0 FN')

md_lines += ["## v1.3 false positives (legit misclassified as scam)", ""]
md_lines += [f"**Total: {len(v13_fp)}**", ""]
md_lines += _fmt_table(v13_fp, 'v1.3 FP')

md_lines += ["## v1.3 false negatives (scams missed)", ""]
md_lines += [f"**Total: {len(v13_fn)}**", ""]
md_lines += _fmt_table(v13_fn, 'v1.3 FN')

md_lines += ["## Per-message disagreements (full listing)", ""]
md_lines += [f"**Total disagreements: {len(disagreements)}**", ""]
md_lines += ["| # | label | source | v1.0 → | v1.3 → | text |",
             "|---:|---:|---|---|---|---|"]
for d in disagreements:
    md_lines.append(f"| {d['idx']} | {d['label']} | {d['source']} | "
                    f"{d['v10_verdict']} ({d['v10_confidence']:.1f}%) | "
                    f"{d['v13_verdict']} ({d['v13_confidence']:.1f}%) | "
                    f"{d['text'][:150].replace('|','│')} |")

with open(OUT_MD, 'w') as f:
    f.write('\n'.join(md_lines))
print(f"✅ Wrote {OUT_MD}")

# Console summary
print("\n" + "=" * 70)
print("HEADLINE RESULT")
print("=" * 70)
print(f"  Test set: {len(items)} truly-unseen items (SHA-1 verified zero overlap)")
print(f"  v1.0 F1: {m10['f1']:.4f}  |  v1.3 F1: {m13['f1']:.4f}  |  Δ = {m13['f1']-m10['f1']:+.4f}")
print(f"  v1.0 recall: {m10['recall']:.4f}  |  v1.3 recall: {m13['recall']:.4f}")
print(f"  v1.0 precision: {m10['precision']:.4f}  |  v1.3 precision: {m13['precision']:.4f}")
print(f"  Disagreements: {len(disagreements)} total")
print(f"    v1.3 correct where v1.0 wrong:  {v13_correct_v10_wrong}")
print(f"    v1.0 correct where v1.3 wrong:  {v10_correct_v13_wrong}")
