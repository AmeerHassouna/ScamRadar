"""
Rung-3 external evaluation.

Runs a saved model against data/external_evaluation/external_eval.csv (400 items:
250 zefang-liu phishing + 150 Reddit legit — reserved during Intervention 4 data
prep, never seen by any candidate at training time).

    python scripts/external_eval.py --models-dir models/v1.2_baseline
    python scripts/external_eval.py --models-dir models/v1.3_candidate

Outputs:
  * Full metrics (accuracy, precision, recall, F1, ROC-AUC, PR-AUC, confusion)
  * Per-source breakdown (phishing side + Reddit legit side)
  * outputs/eval/<name>_external.json
"""
import argparse, os, sys, csv, pickle, json, time
import numpy as np
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, average_precision_score,
                             confusion_matrix)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src._09_prediction_pipeline import predict_message
from config import DEFAULT_THRESHOLD

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL_CSV = os.path.join(BASE_DIR, 'data', 'external_evaluation', 'external_eval.csv')
OUT_DIR  = os.path.join(BASE_DIR, 'outputs', 'eval')
os.makedirs(OUT_DIR, exist_ok=True)


def load_from_dir(models_dir: str):
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
    return model, tfidf, char_tfidf, scaler, scam_idx, st_model, threshold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models-dir', required=True)
    ap.add_argument('--output-name', default=None)
    args = ap.parse_args()

    name = args.output_name or (os.path.basename(os.path.normpath(args.models_dir)) + '_external')
    out_json = os.path.join(OUT_DIR, f'{name}.json')

    # Load reserved external items
    items = []
    with open(EVAL_CSV, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            items.append({'raw_text': r['raw_text'], 'label': int(r['label']),
                          'source': r['source']})
    print(f'External eval set: {len(items):,} items  '
          f'({sum(1 for i in items if i["label"]==1)} scam / '
          f'{sum(1 for i in items if i["label"]==0)} legit)')

    # Load pipeline
    print(f'Loading pipeline from {args.models_dir}…')
    model, tfidf, char_tfidf, scaler, scam_idx, st_model, threshold = load_from_dir(args.models_dir)
    print(f'✅ Loaded (threshold={threshold:.2f})')

    # Predict
    print(f'\nPredicting {len(items)} messages…')
    preds, probs = [], []
    t0 = time.time()
    for i, it in enumerate(items):
        if i and i % 50 == 0:
            rate = i / (time.time()-t0); eta = (len(items)-i)/rate
            print(f'  {i}/{len(items)}  ({rate:.1f} msg/s, ETA {eta:.0f}s)')
        r = predict_message(it['raw_text'], model, tfidf, char_tfidf, scaler,
                            scam_idx, st_model,
                            threshold=threshold, vt_api_key=None, gsb_api_key=None)
        v = r['verdict']
        preds.append(1 if v in ('SCAM', 'SUSPICIOUS') else 0)
        probs.append(float(r.get('confidence', 0)) / 100.0)

    y_true = np.array([it['label'] for it in items])
    y_pred = np.array(preds)
    y_prob = np.array(probs)

    # Metrics
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0,1]).ravel()
    result = {
        'models_dir':      args.models_dir,
        'n':               int(len(items)),
        'threshold':       float(threshold),
        'accuracy':        round(float(accuracy_score(y_true, y_pred)), 4),
        'precision':       round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        'recall':          round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        'f1':              round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        'roc_auc':         round(float(roc_auc_score(y_true, y_prob)), 4) if len(set(y_true)) > 1 else None,
        'pr_auc':          round(float(average_precision_score(y_true, y_prob)), 4) if len(set(y_true)) > 1 else None,
        'confusion':       {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    }

    # Per-source
    per_source = {}
    for src in set(it['source'] for it in items):
        idxs = [i for i, it in enumerate(items) if it['source'] == src]
        if not idxs: continue
        ys = y_true[idxs]; ps = y_pred[idxs]
        tn2, fp2, fn2, tp2 = confusion_matrix(ys, ps, labels=[0,1]).ravel()
        per_source[src] = {
            'n': len(idxs),
            'accuracy':  round(float(accuracy_score(ys, ps)), 4),
            'precision': round(float(precision_score(ys, ps, zero_division=0)), 4),
            'recall':    round(float(recall_score(ys, ps, zero_division=0)), 4),
            'f1':        round(float(f1_score(ys, ps, zero_division=0)), 4),
            'confusion': {'tn': int(tn2), 'fp': int(fp2), 'fn': int(fn2), 'tp': int(tp2)},
        }
    result['per_source'] = per_source

    # Print + save
    print(f'\n' + '='*70)
    print(f'EXTERNAL EVALUATION — {name}')
    print('='*70)
    print(f'  n={result["n"]}  threshold={result["threshold"]:.2f}')
    print(f'  Accuracy   {result["accuracy"]:.4f}')
    print(f'  Precision  {result["precision"]:.4f}')
    print(f'  Recall     {result["recall"]:.4f}')
    print(f'  F1         {result["f1"]:.4f}')
    print(f'  ROC-AUC    {result["roc_auc"]}')
    print(f'  PR-AUC     {result["pr_auc"]}')
    print(f'  Confusion  TN={result["confusion"]["tn"]} FP={result["confusion"]["fp"]} '
          f'FN={result["confusion"]["fn"]} TP={result["confusion"]["tp"]}')
    print(f'\n  Per-source:')
    for src, m in per_source.items():
        print(f'    {src:<25} n={m["n"]:>4}  P={m["precision"]:.4f}  R={m["recall"]:.4f}  F1={m["f1"]:.4f}')

    with open(out_json, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'\n✅ Wrote {out_json}')


if __name__ == '__main__':
    main()
