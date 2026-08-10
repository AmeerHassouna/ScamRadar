"""
E8-P9 retrain — identical E7-P1-full recipe. Two differences from E8-P2:

  1. A8 rule removed from the rule engine (does NOT affect training).
  2. spamassassin_ham source removed from training corpus.

Output: models/e7_p1_variants/e7_p1_full_e8p9.joblib
"""
from __future__ import annotations

import os
import sys
import warnings

warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from scripts.training import train_e7_p1 as t
import pandas as pd

MERGED_PARQUET = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p9.parquet')
OUT_DIR        = t.OUT_DIR


def main():
    print(f'=== E8-P9 retrain (SA removed, A8 deleted) ===')
    print(f'  Input:  {MERGED_PARQUET}')
    print(f'  Output: {OUT_DIR}/e7_p1_full_e8p9.joblib')

    combined = pd.read_parquet(MERGED_PARQUET)
    tr = combined[combined.split == 'train']
    print(f'  train:  {len(tr):,}  '
          f'(scam={int((tr.label==1).sum()):,}  '
          f'legit={int((tr.label==0).sum()):,})')

    feature_cols = t.VARIANTS['e7_p1_full']
    bundle = t.train_variant('e7_p1_full_e8p9', feature_cols, combined, OUT_DIR)

    out = os.path.join(OUT_DIR, 'e7_p1_full_e8p9.joblib')
    print(f'\n✓ E8-P9 bundle saved: {out}')
    print(f'  Size: {os.path.getsize(out)/1e6:.1f} MB')


if __name__ == '__main__':
    main()
