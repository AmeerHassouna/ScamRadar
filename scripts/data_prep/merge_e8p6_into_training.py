"""
E8-P6 merge — adds the 15,572-row E8-P6 synthetic legit corpus to
E8-P5's already-cleaned training parquet.

E8-P5 base already contains:
  - Original training data minus SA (spamassassin_ham)
  - E8-P2's 1,978 synthetic legit rows
  - Noise cleanup (mailing-list-mislabeled scam, spam-in-legit, very-short)

E8-P6 adds:
  - 15,572 additional synthetic legit rows across 21 categories, 65 brands

Output: data/interim/e7_p1_features_e8p6.parquet
E8-P5 parquet is NEVER overwritten — rollback stays trivial.
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import pandas as pd
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from scripts.training.train_e7_p1 import compute_all_numerical

E8P5_PATH   = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p5.parquet')
SYNTH_PATH  = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p6', 'dataset.parquet')
OUT_PATH    = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p6.parquet')
REPORT_PATH = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p6', 'merge_report.json')


def main():
    print('=== E8-P6 merge into training corpus ===')

    print(f'\nLoading E8-P5 base: {E8P5_PATH}')
    base = pd.read_parquet(E8P5_PATH)
    print(f'  rows: {len(base):,}')
    print(base.groupby(['split','label']).size().reset_index(name='n').to_string(index=False))

    print(f'\nLoading E8-P6 synthetic legit: {SYNTH_PATH}')
    synth = pd.read_parquet(SYNTH_PATH)
    print(f'  rows: {len(synth):,}   all label=0? {(synth.label==0).all()}')

    print(f'\nDeduping E8-P6 rows against E8-P5 by exact text match...')
    existing_texts = set(base.text)
    before = len(synth)
    synth = synth[~synth.text.isin(existing_texts)].reset_index(drop=True)
    print(f'  dropped {before - len(synth)} rows that already exist (mostly E8-P2 overlap)')
    print(f'  net new rows: {len(synth):,}')

    print(f'\nComputing 25 numerical features for {len(synth):,} new rows...')
    feats: list = []
    for i, row in enumerate(synth.itertuples(index=False), 1):
        feats.append(compute_all_numerical(row.text))
        if i % 2000 == 0:
            print(f'    {i:>6}/{len(synth)}')
    feats_df = pd.DataFrame(feats)
    print(f'  ✓ {len(feats_df):,} rows × {len(feats_df.columns)} feature columns')

    # Build rows matching base schema
    out = feats_df.copy()
    out['text']       = synth['text'].values
    out['label']      = 0
    out['split']      = 'train'
    # Distinct cluster_id space (deeper negative than E8-P2's -8_000_000)
    out['cluster_id'] = list(range(-9_000_000, -9_000_000 - len(synth), -1))
    missing = [c for c in base.columns if c not in out.columns]
    extra   = [c for c in out.columns if c not in base.columns]
    print(f'  missing (should be zero): {missing}')
    print(f'  extra   (should be zero): {extra}')
    out = out[list(base.columns)]

    merged = pd.concat([base, out], axis=0, ignore_index=True)
    print(f'\nMerged rows: {len(merged):,}   (delta: +{len(merged) - len(base)})')
    print(merged.groupby(['split','label']).size().reset_index(name='n').to_string(index=False))

    print(f'\nWriting {OUT_PATH}')
    merged.to_parquet(OUT_PATH, index=False)
    print(f'  size: {os.path.getsize(OUT_PATH)/1e6:.1f} MB')

    with open(REPORT_PATH, 'w') as f:
        json.dump({
            'e8p5_rows':         int(len(base)),
            'synth_input_rows':  int(before),
            'synth_added_rows':  int(len(synth)),
            'merged_rows':       int(len(merged)),
            'e8p5_train_label0': int(((base.split=='train')&(base.label==0)).sum()),
            'e8p6_train_label0': int(((merged.split=='train')&(merged.label==0)).sum()),
            'e8p5_train_label1': int(((base.split=='train')&(base.label==1)).sum()),
            'e8p6_train_label1': int(((merged.split=='train')&(merged.label==1)).sum()),
        }, f, indent=2)
    print(f'Wrote {REPORT_PATH}')


if __name__ == '__main__':
    main()
