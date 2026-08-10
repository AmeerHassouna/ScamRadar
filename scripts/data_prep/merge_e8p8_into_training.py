"""
E8-P8 merge — adds 14,669 synthetic-scam + 1,109 paired-legit rows to
the E8-P6 training parquet, producing the E8-P9 training corpus.

Base: data/interim/e7_p1_features_e8p6.parquet     (267,723 rows)
Add:  data/synthetic_scam/e8p8/scam_dataset.parquet (14,669 label=1)
      data/synthetic_scam/e8p8/legit_pairs_dataset.parquet (1,109 label=0)
Out:  data/interim/e7_p1_features_e8p9.parquet     (~283,501 rows)

E8-P6 parquet NEVER overwritten — rollback stays trivial.
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
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.training.train_e7_p1 import compute_all_numerical

E8P6_PATH  = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p6.parquet')
SCAM_PATH  = os.path.join(_ROOT, 'data', 'synthetic_scam', 'e8p8', 'scam_dataset.parquet')
PAIR_PATH  = os.path.join(_ROOT, 'data', 'synthetic_scam', 'e8p8', 'legit_pairs_dataset.parquet')
OUT_PATH   = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p9.parquet')
REPORT     = os.path.join(_ROOT, 'data', 'synthetic_scam', 'e8p8', 'merge_report.json')


def _compute_batch(df: pd.DataFrame, tag: str) -> pd.DataFrame:
    print(f'  computing 25 numerical features for {len(df):,} {tag} rows...')
    feats = []
    for i, row in enumerate(df.itertuples(index=False), 1):
        feats.append(compute_all_numerical(row.text))
        if i % 2500 == 0:
            print(f'    {i:>6}/{len(df)}')
    return pd.DataFrame(feats)


def main():
    print('=== E8-P8 merge into training corpus (produces E8-P9 base) ===')
    print(f'\nLoading E8-P6 base: {E8P6_PATH}')
    base = pd.read_parquet(E8P6_PATH)
    print(f'  rows: {len(base):,}')
    print(base.groupby(['split','label']).size().reset_index(name='n').to_string(index=False))

    scam = pd.read_parquet(SCAM_PATH)
    pair = pd.read_parquet(PAIR_PATH)
    print(f'\nLoading synthetic sources:')
    print(f'  scams:      {len(scam):,}  (all label=1)')
    print(f'  legit pairs: {len(pair):,}  (all label=0)')

    # Dedupe against existing base by text
    existing = set(base.text)
    before_scam, before_pair = len(scam), len(pair)
    scam = scam[~scam.text.isin(existing)].reset_index(drop=True)
    pair = pair[~pair.text.isin(existing)].reset_index(drop=True)
    print(f'  scam net new:  {len(scam):,}  (dropped {before_scam-len(scam)} dupes vs base)')
    print(f'  pair net new:  {len(pair):,}  (dropped {before_pair-len(pair)} dupes vs base)')

    # Compute numerical features
    scam_feats = _compute_batch(scam, 'scam')
    pair_feats = _compute_batch(pair, 'pair')

    # Build rows matching base schema
    def build(feats_df, text_df, label, cluster_start):
        out = feats_df.copy()
        out['text']       = text_df['text'].values
        out['label']      = label
        out['split']      = 'train'
        out['cluster_id'] = list(range(cluster_start, cluster_start - len(text_df), -1))
        return out[list(base.columns)]

    scam_rows = build(scam_feats, scam, 1, -9_500_000)
    pair_rows = build(pair_feats, pair, 0, -9_600_000)

    merged = pd.concat([base, scam_rows, pair_rows], axis=0, ignore_index=True)
    print(f'\nMerged rows: {len(merged):,}   (delta: +{len(merged)-len(base)})')
    print(merged.groupby(['split','label']).size().reset_index(name='n').to_string(index=False))

    print(f'\nWriting {OUT_PATH}')
    merged.to_parquet(OUT_PATH, index=False)
    print(f'  size: {os.path.getsize(OUT_PATH)/1e6:.1f} MB')

    with open(REPORT, 'w') as f:
        json.dump({
            'e8p6_rows':          int(len(base)),
            'scam_added':         int(len(scam)),
            'pair_added':         int(len(pair)),
            'merged_rows':        int(len(merged)),
            'e8p6_train_label0':  int(((base.split=='train')&(base.label==0)).sum()),
            'e8p6_train_label1':  int(((base.split=='train')&(base.label==1)).sum()),
            'e8p9_train_label0':  int(((merged.split=='train')&(merged.label==0)).sum()),
            'e8p9_train_label1':  int(((merged.split=='train')&(merged.label==1)).sum()),
        }, f, indent=2)
    print(f'Wrote {REPORT}')


if __name__ == '__main__':
    main()
