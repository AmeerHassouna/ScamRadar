"""
E8-P2 merge step — backs up the training parquet, computes the 25 E7-P1
numerical features for each synthetic-legit row, and produces a merged
parquet WITHOUT overwriting the original.

Inputs
------
    data/interim/e7_p1_features.parquet          (253,264 rows, existing)
    data/synthetic_legit/e8p2/dataset.parquet    (1,978 rows, new)

Outputs
-------
    data/interim/e7_p1_features.parquet.pre_e8p2_backup   (safety copy)
    data/interim/e7_p1_features_e8p2.parquet              (merged, +1,978 legit train rows)
    data/synthetic_legit/e8p2/merge_report.json           (accounting)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import warnings

import pandas as pd
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

# Same feature-computation entrypoint used by the training script — this
# guarantees byte-for-byte identical feature values for the new rows.
from scripts.training.train_e7_p1 import compute_all_numerical

TRAIN_PATH  = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features.parquet')
BACKUP_PATH = TRAIN_PATH + '.pre_e8p2_backup'
MERGED_PATH = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p2.parquet')
SYNTH_PATH  = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p2', 'dataset.parquet')
REPORT_PATH = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p2', 'merge_report.json')


def main():
    print('=== E8-P2 merge into training corpus ===')

    # ── 1. Backup ─────────────────────────────────────────────────────────
    if not os.path.exists(BACKUP_PATH):
        print(f'Backing up {TRAIN_PATH}\n            → {BACKUP_PATH}')
        shutil.copy2(TRAIN_PATH, BACKUP_PATH)
    else:
        print(f'Backup already exists — leaving untouched: {BACKUP_PATH}')
    print(f'  original size: {os.path.getsize(BACKUP_PATH)/1e6:.1f} MB')

    # ── 2. Load original training features ────────────────────────────────
    print(f'\nLoading original training features...')
    orig = pd.read_parquet(TRAIN_PATH)
    print(f'  rows: {len(orig):,}')
    orig_split_label = orig.groupby(['split','label']).size().reset_index(name='n')
    print(orig_split_label.to_string(index=False))

    # ── 3. Load synthetic legit ───────────────────────────────────────────
    print(f'\nLoading synthetic legit dataset...')
    synth = pd.read_parquet(SYNTH_PATH)
    print(f'  rows: {len(synth):,}   all label=0? {(synth.label==0).all()}')

    # ── 4. Compute 25 numerical features for each synthetic row ──────────
    print(f'\nComputing 25 E7-P1 numerical features for synthetic rows...')
    feats: list = []
    for i, row in enumerate(synth.itertuples(index=False), 1):
        f = compute_all_numerical(row.text)
        feats.append(f)
        if i % 500 == 0:
            print(f'    {i:>5}/{len(synth)}')
    feats_df = pd.DataFrame(feats)
    print(f'  produced {len(feats_df):,} rows × {len(feats_df.columns)} feature columns')

    # ── 5. Assemble rows matching original schema ─────────────────────────
    # Required columns (from orig.columns): text, label, cluster_id, split, + 25 features
    # cluster_id: synthetic rows have no cluster; use a distinct negative-space
    # value (-8_000_000..-8_001_977) so cluster-based splitters can identify them.
    print(f'\nAssembling merged rows...')
    synth_out = feats_df.copy()
    synth_out['text']       = synth['text'].values
    synth_out['label']      = 0
    synth_out['split']      = 'train'
    synth_out['cluster_id'] = list(range(-8_000_000, -8_000_000 - len(synth), -1))
    # Reorder columns exactly like `orig` so pd.concat is clean
    missing_in_synth = [c for c in orig.columns if c not in synth_out.columns]
    extra_in_synth   = [c for c in synth_out.columns if c not in orig.columns]
    print(f'  missing (should be zero): {missing_in_synth}')
    print(f'  extra   (should be zero): {extra_in_synth}')
    synth_out = synth_out[list(orig.columns)]

    # ── 6. Concatenate + save ─────────────────────────────────────────────
    merged = pd.concat([orig, synth_out], axis=0, ignore_index=True)
    print(f'\nMerged rows: {len(merged):,}   (delta: +{len(merged)-len(orig)})')
    merged_split_label = merged.groupby(['split','label']).size().reset_index(name='n')
    print(merged_split_label.to_string(index=False))

    print(f'\nWriting merged parquet: {MERGED_PATH}')
    merged.to_parquet(MERGED_PATH, index=False)
    print(f'  size: {os.path.getsize(MERGED_PATH)/1e6:.1f} MB')

    # ── 7. Write accounting report ────────────────────────────────────────
    report = {
        'original_rows':        int(len(orig)),
        'synthetic_rows':       int(len(synth)),
        'merged_rows':          int(len(merged)),
        'delta':                int(len(merged) - len(orig)),
        'orig_train_label0':    int(((orig.split=='train') & (orig.label==0)).sum()),
        'merged_train_label0':  int(((merged.split=='train') & (merged.label==0)).sum()),
        'orig_train_label1':    int(((orig.split=='train') & (orig.label==1)).sum()),
        'merged_train_label1':  int(((merged.split=='train') & (merged.label==1)).sum()),
        'backup_path':          BACKUP_PATH,
        'merged_path':          MERGED_PATH,
        'note': ('Synthetic rows carry cluster_id in [-8_000_000, -8_000_000-N) '
                 'so downstream splitters can identify them. split="train", '
                 'label=0. Original parquet untouched; backup at '
                 f'{BACKUP_PATH}.'),
    }
    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\nWrote {REPORT_PATH}')


if __name__ == '__main__':
    main()
