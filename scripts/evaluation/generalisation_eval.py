"""
Rung-1 evaluation: leaked-vs-unseen bucketed F1 on a shared row-level test set.

Usage:
    python scripts/generalisation_eval.py --models-dir models/v1.0_frozen
    python scripts/generalisation_eval.py --models-dir models/v1.1_candidate \
                                          --training-clusters-json outputs/split_v1.json

Design:
  * SHARED TEST SET: 20% row-level stratified split (seed=42) of the FULL corpus.
    This is v1.0's original test set — used unchanged so v1.0's numbers are
    reproducible and v1.1 is measured on the same rows for direct comparison.
  * BUCKETING: each test row is 'leaked' if its cluster_id is in the model's
    training set, 'unseen' otherwise.
      - For v1.0_frozen: training clusters = clusters of all v1.0 training rows
        (derived from the row-level split — same seed=42).
      - For v1.1_candidate: training clusters = the 'train'-labelled clusters
        in outputs/split_v1.json (must be passed via --training-clusters-json).
  * SAMPLE: stratified — 250 rows per (bucket × label) cell = up to 1,000 rows.
  * OUTPUT: JSON with leaked/unseen/overall metrics, per-source F1, per-
    scam-type F1, and a small sample of leaked/unseen false positives/negatives.

The 'shared test set' choice keeps v1.0 and v1.1 directly comparable — same
9,272 rows evaluated by both, only the bucket definition changes per model.
"""

import argparse, json, os, sys, time, sqlite3, pickle, re
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, confusion_matrix)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src._00_dedup import add_cluster_ids
from src._09_prediction_pipeline import predict_message
from src._02_feature_engineering import classify_scam_type
from config import DEFAULT_THRESHOLD

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'db 4.db')
EVAL_DIR = os.path.join(BASE_DIR, 'outputs', 'eval')
os.makedirs(EVAL_DIR, exist_ok=True)


# ── Model loading (bypass load_pipeline; use any folder) ────────────────────
def load_pipeline_from(models_dir: str):
    """Load model + vectorizers + FAISS + st_model from an arbitrary folder."""
    import faiss
    from sentence_transformers import SentenceTransformer

    payload    = pickle.load(open(os.path.join(models_dir, 'scamradar_model.pkl'),   'rb'))
    tfidf      = pickle.load(open(os.path.join(models_dir, 'tfidf_vectorizer.pkl'),  'rb'))
    char_tfidf = pickle.load(open(os.path.join(models_dir, 'char_vectorizer.pkl'),   'rb'))
    scaler     = pickle.load(open(os.path.join(models_dir, 'scaler.pkl'),            'rb'))
    scam_idx   = faiss.read_index(os.path.join(models_dir, 'scam_faiss.index'))
    st_model   = SentenceTransformer('all-MiniLM-L6-v2')

    model = payload['model'] if isinstance(payload, dict) else payload
    threshold = payload.get('threshold', DEFAULT_THRESHOLD) if isinstance(payload, dict) else DEFAULT_THRESHOLD
    return model, tfidf, char_tfidf, scaler, scam_idx, st_model, threshold


# ── Frozen v1.0 training-cluster derivation ─────────────────────────────────
def derive_frozen_training_clusters(df_full):
    """
    v1.0 was trained with train_test_split(seed=42, stratify=label) at row level.
    Its training clusters = the set of cluster_ids appearing in that training half.
    """
    idx_tr, _ = train_test_split(np.arange(len(df_full)),
                                 test_size=0.20, random_state=42,
                                 stratify=df_full['label'].values)
    return set(df_full.iloc[idx_tr]['cluster_id'].tolist())


# ── Metric helpers ──────────────────────────────────────────────────────────
def _metrics(y_true, y_pred):
    if len(y_true) == 0:
        return None
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        'n':         int(len(y_true)),
        'accuracy':  round(float(accuracy_score(y_true, y_pred)), 4),
        'precision': round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        'recall':    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        'f1':        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    }


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models-dir',              required=True,
                    help='Folder with pkls + scam_faiss.index (e.g. models/v1.0_frozen)')
    ap.add_argument('--training-clusters-json',  default=None,
                    help='JSON file with {cluster_id: split}. If omitted, derive from '
                         'row-level seed=42 split (frozen v1.0 methodology).')
    ap.add_argument('--sample-per-cell',         type=int, default=250,
                    help='Rows per (bucket × label). 4 cells → up to 4× this many.')
    ap.add_argument('--output-name',             default=None,
                    help='Output JSON filename. Default: basename of --models-dir.')
    args = ap.parse_args()

    out_name = args.output_name or os.path.basename(os.path.normpath(args.models_dir))
    out_json = os.path.join(EVAL_DIR, f'{out_name}.json')

    # 1. Load full corpus + cluster IDs
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT m.message_id, m.raw_text, m.label, ds.name AS source, c.type AS channel
        FROM Message m
        JOIN DataSource ds ON m.source_id = ds.source_id
        JOIN Channel    c  ON m.channel_id = c.channel_id
        ORDER BY m.message_id
    """, conn)
    conn.close()
    df['raw_text'] = df['raw_text'].fillna('')
    df = add_cluster_ids(df)

    # 2. Determine which clusters were seen by this model during training
    if args.training_clusters_json:
        with open(args.training_clusters_json) as f:
            split_map = json.load(f)
        training_clusters = {cid for cid, s in split_map.items() if s == 'train'}
        print(f"Training clusters from {args.training_clusters_json}: {len(training_clusters):,}")
    else:
        training_clusters = derive_frozen_training_clusters(df)
        print(f"Training clusters derived from seed=42 row-level split: "
              f"{len(training_clusters):,}")

    # 3. Shared test set: row-level seed=42 20% split (same as v1.0)
    _, idx_te = train_test_split(np.arange(len(df)),
                                 test_size=0.20, random_state=42,
                                 stratify=df['label'].values)
    test_df = df.iloc[idx_te].reset_index(drop=True)
    test_df = test_df[test_df['raw_text'].str.strip().str.len() >= 20].reset_index(drop=True)
    test_df['leaked'] = test_df['cluster_id'].isin(training_clusters)
    print(f"Shared test set: {len(test_df):,} rows  "
          f"(leaked={test_df.leaked.sum():,} unseen={(~test_df.leaked).sum():,})")

    # 4. Stratified sample: N per (bucket × label)
    np.random.seed(42)
    buckets = []
    for leaked in [True, False]:
        for lab in [0, 1]:
            sub = test_df[(test_df.leaked == leaked) & (test_df.label == lab)]
            n = min(args.sample_per_cell, len(sub))
            buckets.append(sub.sample(n, random_state=42))
    sample = pd.concat(buckets, ignore_index=True)
    print(f"\nSample composition:")
    for leaked in [True, False]:
        for lab in [0, 1]:
            n = ((sample.leaked == leaked) & (sample.label == lab)).sum()
            print(f"  leaked={leaked} label={lab}  n={n}")

    # 5. Load pipeline + predict
    print(f"\nLoading pipeline from {args.models_dir} …")
    model, tfidf, char_tfidf, scaler, scam_idx, st_model, threshold = \
        load_pipeline_from(args.models_dir)
    print(f"✅ Loaded (threshold={threshold:.2f})")

    print(f"\nPredicting {len(sample)} messages …")
    preds, verdicts, confs, scam_types = [], [], [], []
    t0 = time.time()
    for i, row in enumerate(sample.itertuples()):
        if i and i % 100 == 0:
            rate = i / (time.time() - t0)
            eta  = (len(sample) - i) / rate
            print(f"  {i}/{len(sample)}  ({rate:.1f} msg/s, ETA {eta:.0f}s)")
        r = predict_message(row.raw_text, model, tfidf, char_tfidf, scaler,
                            scam_idx, st_model,
                            threshold=threshold, vt_api_key=None, gsb_api_key=None)
        v = r['verdict']
        verdicts.append(v)
        confs.append(r['confidence'])
        preds.append(1 if v in ('SCAM', 'SUSPICIOUS') else 0)
        scam_types.append(r.get('scam_type') or 'general_spam')

    print(f"\nTotal time: {time.time()-t0:.1f}s")
    sample['pred']       = preds
    sample['verdict']    = verdicts
    sample['confidence'] = confs
    sample['scam_type']  = scam_types

    # 6. Metrics
    result = {
        'models_dir':          args.models_dir,
        'training_clusters_n': len(training_clusters),
        'sample_size':         int(len(sample)),
        'threshold':           float(threshold),
        'leaked':  _metrics(sample[sample.leaked == True]['label'].values,
                            sample[sample.leaked == True]['pred'].values),
        'unseen':  _metrics(sample[sample.leaked == False]['label'].values,
                            sample[sample.leaked == False]['pred'].values),
        'overall': _metrics(sample['label'].values, sample['pred'].values),
    }
    result['gap_leaked_minus_unseen_f1'] = round(
        (result['leaked']['f1'] if result['leaked'] else 0) -
        (result['unseen']['f1'] if result['unseen'] else 0), 4
    )

    # Per-source F1 (on scams — where source is the meaningful stratification)
    per_source = {}
    for src, sub in sample.groupby('source'):
        m = _metrics(sub['label'].values, sub['pred'].values)
        if m:
            per_source[src] = m
    result['per_source'] = per_source

    # Per-scam-type F1 (on scam rows only — legit rows misclassified type is uninformative)
    per_type = {}
    scam_sub = sample[sample.label == 1]
    for stype, sub in scam_sub.groupby('scam_type'):
        y_true = sub['label'].values; y_pred = sub['pred'].values
        # For a scam-only slice, precision is trivially 1 or 0; report recall as the meaningful metric
        per_type[stype] = {
            'n':      int(len(sub)),
            'recall': round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            'caught': int(y_pred.sum()),
        }
    result['per_scam_type_recall'] = per_type

    # 7. Print report + write JSON
    def _fmt(m):
        if m is None: return '  (empty)'
        return (f"  n={m['n']}  acc={m['accuracy']:.4f}  prec={m['precision']:.4f}  "
                f"rec={m['recall']:.4f}  F1={m['f1']:.4f}  "
                f"TN={m['confusion']['tn']} FP={m['confusion']['fp']} "
                f"FN={m['confusion']['fn']} TP={m['confusion']['tp']}")

    print("\n" + "=" * 72)
    print(f"RUNG-1 RESULTS — {out_name}")
    print("=" * 72)
    print(f"LEAKED  (cluster in training)")
    print(_fmt(result['leaked']))
    print(f"UNSEEN  (cluster NOT in training)")
    print(_fmt(result['unseen']))
    print(f"OVERALL")
    print(_fmt(result['overall']))
    print(f"\nGeneralisation gap (leaked F1 − unseen F1): {result['gap_leaked_minus_unseen_f1']:+.4f}")
    print(f"\nPer-source F1:")
    for src, m in per_source.items():
        print(f"  {src:<26}  n={m['n']:>4}  F1={m['f1']:.4f}")
    print(f"\nPer-scam-type recall (on scam rows only):")
    for stype, m in sorted(per_type.items(), key=lambda x: -x[1]['n']):
        print(f"  {stype:<25}  n={m['n']:>3}  caught={m['caught']:>3}  recall={m['recall']:.4f}")

    with open(out_json, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✅ Wrote {out_json}")


if __name__ == '__main__':
    main()
