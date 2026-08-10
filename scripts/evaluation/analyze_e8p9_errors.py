"""
E8-P9 external benchmark error analysis.

Re-scores the 25,306-item external benchmark capturing per-item detail
(confidence, ml_prob, final_prob, triggered_rules, has_url), then
groups FPs and FNs by category / confidence / rule involvement and
prints representative samples.

Purpose: understand WHY the 237 FPs and 346 FNs happen — is the model
mis-classifying whole categories, blowing calls at borderline
confidence, or getting individual items wrong for identifiable reasons.

Output: outputs/eval/e8p9_error_analysis.txt (full report)
        outputs/eval/e8p9_per_item.parquet    (raw per-item predictions)
"""
import json
import os
import sys
import time
import warnings
from collections import Counter

# Route inference to E8-P9 + rule engine active (same config as main eval)
os.environ['SCAMRADAR_LOCAL_MODEL']    = 'e7_p1_full_e8p9'
os.environ['SCAMRADAR_RULE_ENGINE_ON'] = 'true'
os.environ['SCAMRADAR_OTP_RULE_ON']    = 'false'
os.environ['SCAMRADAR_SAFETY_NET_ON']  = 'false'
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
from src._09_prediction_pipeline import load_pipeline, predict_message

BASE = '/Users/ameer/Downloads/scamradar2'
OUT_DIR = os.path.join(_ROOT, 'outputs', 'eval')
os.makedirs(OUT_DIR, exist_ok=True)
PER_ITEM_PARQUET = os.path.join(OUT_DIR, 'e8p9_per_item.parquet')
REPORT_PATH      = os.path.join(OUT_DIR, 'e8p9_error_analysis.txt')


def sec(title: str) -> str:
    bar = '═' * 80
    return f'\n{bar}\n  {title}\n{bar}\n'


def score_all():
    print('Loading pipeline...')
    t0 = time.time()
    model, tfidf, char_tfidf, scaler, scam_index, st_model = load_pipeline()
    print(f'  loaded in {time.time()-t0:.1f}s')

    df = pd.read_parquet(f'{BASE}/data/external_benchmark/benchmark.parquet')
    print(f'  benchmark: n={len(df):,}')

    rows: list = []
    t0 = time.time()
    for i, r in enumerate(df.itertuples(index=False), 1):
        text = r.text
        try:
            res = predict_message(text, model, tfidf, char_tfidf, scaler,
                                    scam_index, st_model,
                                    vt_api_key=None, gsb_api_key=None)
        except Exception as e:
            res = {'verdict': 'LEGIT', 'confidence': 0.0,
                   'ml_probability': 0.0, 'final_probability': 0.0,
                   'urls_found': [], 'rule_engine': None}
        v      = res.get('verdict', 'LEGIT')
        pred   = 1 if v in ('SCAM', 'SUSPICIOUS') else 0
        conf   = float(res.get('confidence', 0))
        mlp    = float(res.get('ml_probability') or 0)
        fp     = float(res.get('final_probability') or (conf/100.0))
        re_out = res.get('rule_engine') or {}
        triggered = [t['rule_id'] for t in (re_out.get('triggered_rules') or [])]
        forced = bool(re_out.get('forced_scam'))
        rows.append({
            'text':      text,
            'category':  r.category,
            'label':     int(r.label),
            'pred':      pred,
            'confidence': conf,
            'ml_prob':   mlp,
            'final_prob': fp,
            'triggered': ','.join(triggered),
            'n_rules':   len(triggered),
            'forced_scam': forced,
            'has_url':   1 if (res.get('urls_found') or []) else 0,
            'char_len':  len(text or ''),
        })
        if i % 2000 == 0:
            print(f'    {i:>6}/{len(df)}  ({i/(time.time()-t0):.0f} msg/s)')
    print(f'  scored in {time.time()-t0:.0f}s')

    per_df = pd.DataFrame(rows)
    per_df.to_parquet(PER_ITEM_PARQUET, index=False)
    print(f'\nSaved per-item results: {PER_ITEM_PARQUET}')
    return per_df


def bucket_conf(c: float) -> str:
    if c < 60:  return '<60 (borderline)'
    if c < 70:  return '60-70'
    if c < 80:  return '70-80'
    if c < 90:  return '80-90'
    return '90-100 (confident)'


def analyze(per_df: pd.DataFrame):
    out: list = []
    w = out.append

    # ── FP / FN slicing ──────────────────────────────────────────────────
    fps = per_df[(per_df.label == 0) & (per_df.pred == 1)].copy()
    fns = per_df[(per_df.label == 1) & (per_df.pred == 0)].copy()
    w(f'E8-P9 external benchmark error analysis')
    w(f'   total: {len(per_df):,}   FPs: {len(fps):,}   FNs: {len(fns):,}')

    # ══════════════════════════════════════════════════════════════════════
    # FPs
    # ══════════════════════════════════════════════════════════════════════
    w(sec(f'FP ANALYSIS  (n={len(fps)})  — legit items called SCAM'))

    w('  FPs per category:')
    for cat, n in fps.category.value_counts().items():
        total_cat = int((per_df.category == cat).sum())
        w(f'    {cat:26s}  {n:>4d}  / {total_cat:>5d}  ({100*n/total_cat:.2f}% of category)')

    w('\n  FP confidence distribution (how confident was the mis-call?):')
    fps['bucket'] = fps.confidence.apply(bucket_conf)
    order = ['<60 (borderline)', '60-70', '70-80', '80-90', '90-100 (confident)']
    for b in order:
        n = int((fps.bucket == b).sum())
        w(f'    {b:22s}  {n:>4d}  ({100*n/max(len(fps),1):.1f}%)')

    w('\n  Rule engine involvement in FPs:')
    n_rule_touched = int((fps.n_rules > 0).sum())
    n_forced       = int(fps.forced_scam.sum())
    w(f'    rule engine fired on:  {n_rule_touched:>4d}  ({100*n_rule_touched/max(len(fps),1):.1f}% of FPs)')
    w(f'    force-scam by A rule:  {n_forced:>4d}  ({100*n_forced/max(len(fps),1):.1f}% of FPs)')
    if n_rule_touched:
        rule_hits = Counter()
        for t in fps[fps.n_rules > 0].triggered:
            for r in t.split(','):
                if r: rule_hits[r] += 1
        w(f'    rules that fired on FPs (rule + count):')
        for r, n in rule_hits.most_common():
            w(f'      {r:40s} {n:>4d}')

    w('\n  URL presence in FPs:')
    with_url = int(fps.has_url.sum())
    w(f'    with URL:  {with_url:>4d}  ({100*with_url/max(len(fps),1):.1f}%)')
    w(f'    no URL:    {len(fps)-with_url:>4d}  ({100*(len(fps)-with_url)/max(len(fps),1):.1f}%)')

    w('\n  Text-length distribution of FPs:')
    for lo, hi, label in [(0,100,'<100'), (100,300,'100-300'),
                           (300,800,'300-800'), (800,2000,'800-2k'),
                           (2000,10**9,'>2k')]:
        n = int(((fps.char_len >= lo) & (fps.char_len < hi)).sum())
        w(f'    {label:>8s} chars:  {n:>4d}  ({100*n/max(len(fps),1):.1f}%)')

    # Sample FPs stratified across categories and confidence buckets
    w('\n  SAMPLE FPs — 3 highest-confidence + 3 borderline per top category:')
    top_cats = list(fps.category.value_counts().head(3).index)
    for cat in top_cats:
        sub = fps[fps.category == cat]
        w(f'\n  ── {cat} (n={len(sub)}) ──')
        for what, subset in [('HIGH confidence (90-100%)', sub.nlargest(3, 'confidence')),
                              ('BORDERLINE (<70%)', sub[sub.confidence < 70].nlargest(3, 'confidence'))]:
            w(f'    {what}:')
            for _, r in subset.iterrows():
                w(f'      conf={r.confidence:>5.1f}  ml_prob={r.ml_prob:.3f}  final={r.final_prob:.3f}  '
                  f'rules=[{r.triggered or "-"}]  url={"Y" if r.has_url else "N"}')
                preview = (r.text or '')[:260].replace('\n', ' ')
                w(f'         "{preview}"')

    # ══════════════════════════════════════════════════════════════════════
    # FNs
    # ══════════════════════════════════════════════════════════════════════
    w(sec(f'FN ANALYSIS  (n={len(fns)})  — scam items called LEGIT'))

    w('  FNs per category:')
    for cat, n in fns.category.value_counts().items():
        total_cat = int(((per_df.category == cat) & (per_df.label == 1)).sum())
        w(f'    {cat:26s}  {n:>4d}  / {total_cat:>5d}  ({100*n/max(total_cat,1):.2f}% of scam-in-category)')

    w('\n  FN confidence distribution (how confident was the mis-call?):')
    fns['bucket'] = fns.confidence.apply(bucket_conf)
    # For FNs confidence is <threshold — reverse-order buckets
    order_fn = ['<10 (very legit)', '10-30', '30-45', '45-55 (near-miss)']
    def bucket_fn(c: float) -> str:
        if c < 10:  return '<10 (very legit)'
        if c < 30:  return '10-30'
        if c < 45:  return '30-45'
        return '45-55 (near-miss)'
    fns['bucket'] = fns.confidence.apply(bucket_fn)
    for b in order_fn:
        n = int((fns.bucket == b).sum())
        w(f'    {b:22s}  {n:>4d}  ({100*n/max(len(fns),1):.1f}%)')

    w('\n  Rule engine involvement in FNs:')
    rule_touched_fn = int((fns.n_rules > 0).sum())
    w(f'    rule engine fired on:  {rule_touched_fn:>4d}  ({100*rule_touched_fn/max(len(fns),1):.1f}% of FNs)')
    # For FNs, C-rules (DECREASE) firing is BAD — the rule pushed a real scam
    # further away from SCAM verdict. Count how often that happened.
    c_rule_hits = 0
    if rule_touched_fn:
        rule_hits = Counter()
        for t in fns[fns.n_rules > 0].triggered:
            for r in t.split(','):
                if r:
                    rule_hits[r] += 1
                    if r.startswith('C'):
                        c_rule_hits += 1
        w(f'    C-rules (DECREASE) fired on FNs:  {c_rule_hits:>4d}  '
          f'(dropped scam prob below threshold)')
        w(f'    rules that fired on FNs (rule + count):')
        for r, n in rule_hits.most_common():
            w(f'      {r:40s} {n:>4d}')

    w('\n  URL presence in FNs:')
    with_url_fn = int(fns.has_url.sum())
    w(f'    with URL:  {with_url_fn:>4d}  ({100*with_url_fn/max(len(fns),1):.1f}%)')
    w(f'    no URL:    {len(fns)-with_url_fn:>4d}  ({100*(len(fns)-with_url_fn)/max(len(fns),1):.1f}%)')

    w('\n  Text-length distribution of FNs:')
    for lo, hi, label in [(0,100,'<100'), (100,300,'100-300'),
                           (300,800,'300-800'), (800,2000,'800-2k'),
                           (2000,10**9,'>2k')]:
        n = int(((fns.char_len >= lo) & (fns.char_len < hi)).sum())
        w(f'    {label:>8s} chars:  {n:>4d}  ({100*n/max(len(fns),1):.1f}%)')

    # Sample FNs — the scariest ones are (a) most confident LEGIT + (b) near-miss
    w('\n  SAMPLE FNs — 3 most-confident-LEGIT + 3 near-miss per top category:')
    top_cats = list(fns.category.value_counts().head(3).index)
    for cat in top_cats:
        sub = fns[fns.category == cat]
        w(f'\n  ── {cat} (n={len(sub)}) ──')
        for what, subset in [('MOST CONFIDENT LEGIT (conf near 0)', sub.nsmallest(3, 'confidence')),
                              ('NEAR-MISS (45-55%)', sub[(sub.confidence >= 45) & (sub.confidence < 55)].nlargest(3, 'confidence'))]:
            w(f'    {what}:')
            for _, r in subset.iterrows():
                w(f'      conf={r.confidence:>5.1f}  ml_prob={r.ml_prob:.3f}  final={r.final_prob:.3f}  '
                  f'rules=[{r.triggered or "-"}]  url={"Y" if r.has_url else "N"}')
                preview = (r.text or '')[:260].replace('\n', ' ')
                w(f'         "{preview}"')

    return '\n'.join(out)


def main():
    if os.path.exists(PER_ITEM_PARQUET):
        print(f'Loading cached per-item results from {PER_ITEM_PARQUET}')
        per_df = pd.read_parquet(PER_ITEM_PARQUET)
    else:
        per_df = score_all()
    report = analyze(per_df)
    with open(REPORT_PATH, 'w') as f:
        f.write(report)
    print(f'\nWrote {REPORT_PATH}  ({os.path.getsize(REPORT_PATH):,} bytes)')


if __name__ == '__main__':
    main()
