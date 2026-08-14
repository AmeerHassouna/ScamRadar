"""
E8-P3 training corpus — starts from E8-P2's merged parquet (255,242 rows)
and removes every row whose source is `spamassassin_ham`.

We recover the source mapping by joining on text hash against the
original E5-source parquets (train/val/test/external_benchmark), which
carry the `source` column that the feature parquet dropped.

Output: data/interim/e7_p1_features_e8p3.parquet
"""
from __future__ import annotations

import os
import sys
import hashlib
import warnings

import pandas as pd
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

MERGED_IN  = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p2.parquet')
MERGED_OUT = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p3.parquet')

E5 = os.path.join(_ROOT, 'data', 'canonical')


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8', 'ignore')).hexdigest()


def main():
    print('=== E8-P3 training corpus: drop spamassassin_ham + retain E8-P2 synthetic ===')

    print(f'\nLoading E8-P2 merged parquet: {MERGED_IN}')
    df = pd.read_parquet(MERGED_IN)
    print(f'  rows: {len(df):,}')

    # ── Build set of SA-source text hashes ────────────────────────────────
    print('\nCollecting spamassassin_ham text hashes from source parquets...')
    sa_hashes: set = set()
    for name, path in [
        ('train',  f'{E5}/train.parquet'),
        ('val',    f'{E5}/val.parquet'),
        ('test',   f'{E5}/test.parquet'),
        ('ext',    f'{E5}/external_benchmark.parquet'),
    ]:
        s = pd.read_parquet(path, columns=['text', 'source'])
        s_sa = s[s.source == 'spamassassin_ham']
        for t in s_sa.text:
            sa_hashes.add(_hash(t))
        print(f'  {name:6s}: {len(s_sa):>5} SA rows')
    print(f'  total unique SA text hashes: {len(sa_hashes):,}')

    # ── Filter ────────────────────────────────────────────────────────────
    print('\nHashing merged texts...')
    df['_h'] = df.text.map(_hash)
    before = len(df)
    df = df[~df._h.isin(sa_hashes)].drop(columns=['_h']).reset_index(drop=True)
    after = len(df)
    dropped = before - after
    print(f'  dropped: {dropped:,}   remaining: {after:,}')
    print(f'\nPer-split-label breakdown:')
    print(df.groupby(['split','label']).size().reset_index(name='n').to_string(index=False))

    print(f'\nWriting {MERGED_OUT}')
    df.to_parquet(MERGED_OUT, index=False)
    print(f'  size: {os.path.getsize(MERGED_OUT)/1e6:.1f} MB')


if __name__ == '__main__':
    main()
