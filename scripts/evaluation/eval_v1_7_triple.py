"""
Triple evaluation — v1.7_local_experiment vs 11866bb vs v1.3.

Scores three models on four datasets:
  A. ab_180_corpus         (tests/comparison_corpus.json)
  B. external_400          (data/external_evaluation/external_eval.csv)
  C. enron_hard_legit      (data/v1.7_augmentation/real_world/enron_hard_legit.jsonl)
  D. spamassassin_hard_legit (data/v1.7_augmentation/real_world/spamassassin_hard_legit.jsonl)

Efficiency:
  * v1.7 and 11866bb: loaded in-process (via predict_message).
  * v1.3: REUSES existing per-item predictions from:
      - tests/comparison_results.json      (has v1.3 predictions for ab_180)
      - outputs/eval/deployed_v1.3_smoke_400.json (has v1.3 predictions for external_400)
    Deployed API is only called for enron / spamassassin slices (325 × 3.2s ≈ 17 min).

Output: outputs/eval/v1.7_triple_comparison.json
"""
import os
import sys
import json
import csv
import time
import pickle
import ssl
import urllib.request
import urllib.error
from collections import defaultdict

import numpy as np
import certifi
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, average_precision_score,
                             confusion_matrix)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DEFAULT_THRESHOLD

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

DEPLOYED_URL = 'https://scamradar-api-l2vv.onrender.com/predict'
DEPLOYED_SLEEP_S = 3.2


# ─── model loading ────────────────────────────────────────────────────────────
def load_local(model_dir):
    import faiss
    from sentence_transformers import SentenceTransformer
    payload = pickle.load(open(f'{model_dir}/scamradar_model.pkl', 'rb'))
    return {
        'model':     payload['model'],
        'threshold': float(payload.get('threshold', DEFAULT_THRESHOLD)),
        'tfidf':     pickle.load(open(f'{model_dir}/tfidf_vectorizer.pkl', 'rb')),
        'char':      pickle.load(open(f'{model_dir}/char_vectorizer.pkl', 'rb')),
        'scaler':    pickle.load(open(f'{model_dir}/scaler.pkl', 'rb')),
        'scam_idx':  faiss.read_index(f'{model_dir}/scam_faiss.index'),
        'st':        SentenceTransformer('all-MiniLM-L6-v2'),
    }


def predict_local_batch(items, bundle):
    from src._09_prediction_pipeline import predict_message
    preds, probs = [], []
    for it in items:
        try:
            r = predict_message(it['text'], bundle['model'], bundle['tfidf'],
                                bundle['char'], bundle['scaler'],
                                bundle['scam_idx'], bundle['st'],
                                threshold=bundle['threshold'],
                                vt_api_key=None, gsb_api_key=None)
            v = r.get('verdict')
            preds.append(1 if v in ('SCAM', 'SUSPICIOUS') else 0)
            probs.append(float(r.get('confidence', 0)) / 100.0)
        except Exception:
            preds.append(None); probs.append(0.0)
    return preds, probs


def call_deployed(text, retries=6):
    body = json.dumps({'text': text}).encode('utf-8')
    req = urllib.request.Request(DEPLOYED_URL, data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90, context=SSL_CTX) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                v = data.get('verdict')
                return {'ok': True,
                        'pred': 1 if v in ('SCAM', 'SUSPICIOUS') else 0,
                        'conf': float(data.get('confidence', 0)) / 100.0}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                ra = e.headers.get('Retry-After')
                time.sleep(float(ra) if ra else 4.0); continue
            return {'ok': False, 'error': str(e)}
        except Exception:
            if attempt < retries - 1:
                time.sleep(2.0); continue
            return {'ok': False, 'error': 'timeout'}


def eval_deployed_batch(items, tag=''):
    preds, probs = [], []
    for i, it in enumerate(items, 1):
        r = call_deployed(it['text'])
        if r.get('ok'):
            preds.append(r['pred']); probs.append(r['conf'])
        else:
            preds.append(None); probs.append(0.0)
        if i % 25 == 0:
            print(f'    deployed {tag} {i}/{len(items)}', flush=True)
        time.sleep(DEPLOYED_SLEEP_S)
    return preds, probs


# ─── metrics ──────────────────────────────────────────────────────────────────
def score(y, preds, probs):
    valid_mask = np.array([p is not None for p in preds])
    y = np.asarray(y)[valid_mask]
    p = np.asarray([x for x in preds if x is not None]).astype(int)
    pr = np.asarray(probs)[valid_mask]
    if not len(y):
        return {'n': 0, 'error': 'no valid preds'}
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    m = {
        'n':         int(len(y)),
        'accuracy':  round(float(accuracy_score(y, p)), 4),
        'precision': round(float(precision_score(y, p, zero_division=0)), 4),
        'recall':    round(float(recall_score(y, p, zero_division=0)), 4),
        'f1':        round(float(f1_score(y, p, zero_division=0)), 4),
        'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    }
    if len(set(y)) > 1:
        m['roc_auc'] = round(float(roc_auc_score(y, pr)), 4)
        m['pr_auc']  = round(float(average_precision_score(y, pr)), 4)
    return m


# ─── dataset loaders ──────────────────────────────────────────────────────────
def load_ab():
    d = json.load(open(f'{BASE}/tests/comparison_corpus.json'))
    return [{'text': m['text'], 'label': 1 if m['ground_truth'] == 'SCAM' else 0,
             'category': m['category']} for m in d['messages']]


def load_external():
    items = []
    with open(f'{BASE}/data/external_evaluation/external_eval.csv') as f:
        for r in csv.DictReader(f):
            items.append({'text': r['raw_text'], 'label': int(r['label']),
                          'category': r.get('source', 'external')})
    return items


def load_jsonl(path):
    items = []
    with open(path) as f:
        for line in f:
            if not line.strip(): continue
            r = json.loads(line)
            items.append({'text': r['text'], 'label': int(r['label']),
                          'category': r.get('category', 'held_out')})
    return items


# ─── reuse existing v1.3 predictions where possible ──────────────────────────
def load_v13_predictions_ab(items):
    """Read tests/comparison_results.json — has v1.3 predictions for ab_180."""
    d = json.load(open(f'{BASE}/tests/comparison_results.json'))
    by_text = {r['text']: r['deployed'] for r in d['results']}
    preds, probs = [], []
    for it in items:
        b = by_text.get(it['text'], {})
        if not b.get('ok'):
            preds.append(None); probs.append(0.0); continue
        v = b.get('verdict')
        preds.append(1 if v in ('SCAM', 'SUSPICIOUS') else 0)
        probs.append(float(b.get('confidence', 0)) / 100.0)
    return preds, probs


def load_v13_predictions_external(items):
    """Read outputs/eval/deployed_v1.3_smoke_400.json — has items_full[]."""
    d = json.load(open(f'{BASE}/outputs/eval/deployed_v1.3_smoke_400.json'))
    # Match by idx (order matches the CSV row order)
    by_idx = {it['idx']: it for it in d.get('items_full', [])}
    preds, probs = [], []
    for i, it in enumerate(items):
        b = by_idx.get(i)
        if b is None:
            preds.append(None); probs.append(0.0); continue
        preds.append(int(b['pred']))
        probs.append(float(b['conf']) / 100.0)
    return preds, probs


# ─── main ────────────────────────────────────────────────────────────────────
def main():
    print('Loading v1.7 model...', flush=True)
    v17 = load_local(f'{BASE}/models/v1.7_local_experiment')
    print(f'  v1.7 threshold: {v17["threshold"]:.3f}')

    print('Loading 11866bb model (from backup)...', flush=True)
    orig = load_local(f'{BASE}/models/backups/pre_v1.7_experiment')
    print(f'  11866bb threshold: {orig["threshold"]:.3f}')

    ab   = load_ab()
    ext  = load_external()
    enron = load_jsonl(f'{BASE}/data/v1.7_augmentation/real_world/enron_hard_legit.jsonl')
    sa    = load_jsonl(f'{BASE}/data/v1.7_augmentation/real_world/spamassassin_hard_legit.jsonl')
    print(f'  ab: {len(ab)}, external: {len(ext)}, enron: {len(enron)}, spamassassin: {len(sa)}')

    per_model = {'v1.7': {}, '11866bb': {}, 'v1.3_deployed': {}}
    raw_preds = {'v1.7': {}, '11866bb': {}, 'v1.3_deployed': {}}

    for ds_name, items in [('ab_180_corpus', ab), ('external_400', ext),
                            ('enron_hard_legit', enron), ('spamassassin_hard_legit', sa)]:
        print(f'\n=== {ds_name} (n={len(items)}) ===', flush=True)
        y = [it['label'] for it in items]

        print(f'  v1.7 in-process...', flush=True)
        p17, pr17 = predict_local_batch(items, v17)
        per_model['v1.7'][ds_name] = score(y, p17, pr17)
        raw_preds['v1.7'][ds_name] = {'preds': p17, 'probs': pr17}

        print(f'  11866bb in-process...', flush=True)
        po, pro = predict_local_batch(items, orig)
        per_model['11866bb'][ds_name] = score(y, po, pro)
        raw_preds['11866bb'][ds_name] = {'preds': po, 'probs': pro}

        # v1.3 — reuse existing preds where available
        if ds_name == 'ab_180_corpus':
            print(f'  v1.3 (reused from tests/comparison_results.json)...', flush=True)
            pd_, prd = load_v13_predictions_ab(items)
        elif ds_name == 'external_400':
            print(f'  v1.3 (reused from outputs/eval/deployed_v1.3_smoke_400.json)...', flush=True)
            pd_, prd = load_v13_predictions_external(items)
        else:
            print(f'  v1.3 deployed — fresh calls (~{len(items)*DEPLOYED_SLEEP_S:.0f}s)...', flush=True)
            pd_, prd = eval_deployed_batch(items, tag=ds_name)
        per_model['v1.3_deployed'][ds_name] = score(y, pd_, prd)
        raw_preds['v1.3_deployed'][ds_name] = {'preds': pd_, 'probs': prd}

        # print quick summary
        for m in ('v1.7', '11866bb', 'v1.3_deployed'):
            s = per_model[m][ds_name]
            print(f'    {m:15s} acc={s.get("accuracy",0):.3f} prec={s.get("precision",0):.3f} '
                  f'recall={s.get("recall",0):.3f} f1={s.get("f1",0):.3f}', flush=True)

    # Per-category on ab_180
    print(f'\n=== Per-category (ab_180_corpus) ===', flush=True)
    cat_map = defaultdict(list)
    for i, it in enumerate(ab):
        cat_map[it['category']].append(i)
    per_cat = {}
    for m in per_model:
        rp = raw_preds[m]['ab_180_corpus']
        per_cat[m] = {}
        for cat, idxs in cat_map.items():
            y_c = [ab[i]['label'] for i in idxs]
            p_c = [rp['preds'][i] for i in idxs]
            pr_c = [rp['probs'][i] for i in idxs]
            per_cat[m][cat] = score(y_c, p_c, pr_c)

    output = {
        'v1.7_threshold':    v17['threshold'],
        '11866bb_threshold': orig['threshold'],
        'per_model_per_dataset': per_model,
        'per_category_ab_180':  per_cat,
        'v1.3_notes':           ('ab_180 & external_400 predictions reused from existing evaluation '
                                 'files; hard-legit slices fresh-called (deployed API @ 3.2s each).'),
    }
    out_path = f'{BASE}/outputs/eval/v1.7_triple_comparison.json'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f'\nWrote {out_path}')


if __name__ == '__main__':
    main()
