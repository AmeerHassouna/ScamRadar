"""
Materialize the two ScamRadar+ relational databases from parquet inputs.

The two databases represent the two ends of the CRISP-DM data-preparation
iteration:

  1. INITIAL DB — data/initial_db/scamradar_initial_253264.db
     Built from the four canonical splits at data/canonical/{train,val,test,
     external_benchmark}.parquet. Represents the 253,264-row approved
     baseline BEFORE the E8 augmentation cycle. Contains 14 sources
     (13 real-world + `synthetic_v1` seed), including spamassassin_ham.

  2. FINAL DB — data/final_db/scamradar_e8p9.db
     Built from data/interim/e7_p1_features_e8p9.parquet joined against
     data/canonical/clean.parquet to recover source labels. Represents the
     283,501-row corpus AFTER the E8 cycle. Contains 17 sources: the 12
     real-world sources that survived the E8-P3 spamassassin_ham removal,
     a catch-all `e5_base_corpus` for the small residue of legacy rows whose
     source could not be resolved by the join, and 4 new synthetic sources
     produced by E8-P2 / E8-P6 / E8-P8.

Both databases use the schema at docs/database/schema.sql. Neither .db file
is committed to Git (each is ~200-250 MB); both are gitignored by the
blanket `data/*` rule.

Usage:

    python scripts/data_prep/build_databases.py initial   # builds initial only
    python scripts/data_prep/build_databases.py final     # builds final only
    python scripts/data_prep/build_databases.py both      # builds both
    python scripts/data_prep/build_databases.py verify    # row-count check

Inputs required:
    data/canonical/train.parquet
    data/canonical/val.parquet
    data/canonical/test.parquet
    data/canonical/external_benchmark.parquet
    data/canonical/clean.parquet
    data/interim/e7_p1_features_e8p9.parquet

Neither the classifier bundle nor any model artifact is touched.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent

SCHEMA_SQL = _ROOT / 'docs' / 'database' / 'schema.sql'

INITIAL_INPUTS = {
    'train':    _ROOT / 'data' / 'canonical' / 'train.parquet',
    'val':      _ROOT / 'data' / 'canonical' / 'val.parquet',
    'test':     _ROOT / 'data' / 'canonical' / 'test.parquet',
    'external': _ROOT / 'data' / 'canonical' / 'external_benchmark.parquet',
}
INITIAL_DB = _ROOT / 'data' / 'initial_db' / 'scamradar_initial_253264.db'
INITIAL_EXPECTED_ROWS = 253_264

FINAL_INTERIM = _ROOT / 'data' / 'interim' / 'e7_p1_features_e8p9.parquet'
FINAL_CLEAN   = _ROOT / 'data' / 'canonical' / 'clean.parquet'
FINAL_DB      = _ROOT / 'data' / 'final_db' / 'scamradar_e8p9.db'
FINAL_EXPECTED_ROWS = 283_501


# The 25 engineered numerical feature columns (order matches
# src/canonical.NUMERICAL_FEATURES + docs/database/schema.sql).
NUMERICAL_FEATURE_COLS = [
    'text_length', 'word_count', 'has_url', 'url_count', 'exclamation_count',
    'uppercase_ratio', 'digit_ratio', 'urgency_score',
    'tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat',
    'url_suspicious_tld', 'url_suspicious_keyword', 'url_has_ip',
    'scam_phrase_score', 'sender_impersonation_score', 'legit_phrase_score',
    'avg_word_length', 'capitalized_word_count', 'punctuation_density',
    'question_mark_count', 'currency_symbol_count',
    'readability_score', 'unique_word_ratio',
]

# Cluster-id conventions from the E8-P{2,6,8} merge scripts. Any row whose
# cluster_id sits inside one of these ranges is attributable to that
# synthetic batch by construction (see
# scripts/data_prep/merge_e8p2_into_training.py and siblings).
SYNTHETIC_CLUSTER_RULES = [
    # (source_name, min_cluster_id_inclusive, max_cluster_id_exclusive)
    ('synthetic_e8p2_legit', -8_002_000, -8_000_000),      # ~1,978 rows
    ('synthetic_e8p6_legit', -8_020_000, -8_002_000),      # ~15,521 rows
    ('synthetic_e8p8_scam',  -8_040_000, -8_020_000),      # ~14,669 rows
    ('synthetic_e8p8_pair',  -8_050_000, -8_040_000),      # ~1,109 rows
]


def _apply_schema(con: sqlite3.Connection) -> None:
    ddl = SCHEMA_SQL.read_text()
    con.executescript(ddl)


def _upsert_source(con: sqlite3.Connection, name: str, kind: str,
                   era: str | None = None, license_: str | None = None) -> int:
    cur = con.execute(
        'INSERT OR IGNORE INTO Source (source_name, source_type, era, license) '
        'VALUES (?, ?, ?, ?)',
        (name, kind, era, license_)
    )
    con.commit()
    (sid,) = con.execute(
        'SELECT source_id FROM Source WHERE source_name = ?', (name,)
    ).fetchone()
    return sid


# ---------------------------------------------------------------------------
# Initial DB — from the four canonical split parquets
# ---------------------------------------------------------------------------
def build_initial() -> None:
    for name, path in INITIAL_INPUTS.items():
        if not path.exists():
            print(f'  MISSING: {path} — cannot build initial DB', file=sys.stderr)
            sys.exit(2)

    INITIAL_DB.parent.mkdir(parents=True, exist_ok=True)
    if INITIAL_DB.exists():
        INITIAL_DB.unlink()

    con = sqlite3.connect(INITIAL_DB)
    _apply_schema(con)

    # Read + concatenate the four splits (each carries a `source` column).
    frames = []
    for split, path in INITIAL_INPUTS.items():
        df = pd.read_parquet(path, columns=['text', 'label', 'source',
                                             'cluster_id', 'is_synthetic',
                                             'era', 'license'])
        df['split'] = split
        frames.append(df)
    corpus = pd.concat(frames, ignore_index=True)
    assert len(corpus) == INITIAL_EXPECTED_ROWS, \
        f'expected {INITIAL_EXPECTED_ROWS}, got {len(corpus)}'

    # Register every distinct source, honouring `is_synthetic` from the
    # parquet metadata for the type column.
    source_id_of: dict[str, int] = {}
    for src, group in corpus.groupby('source'):
        is_syn = bool(group['is_synthetic'].iloc[0])
        era = group['era'].iloc[0] if pd.notna(group['era'].iloc[0]) else None
        lic = group['license'].iloc[0] if pd.notna(group['license'].iloc[0]) else None
        source_id_of[src] = _upsert_source(
            con, src, 'synthetic' if is_syn else 'real', era, lic
        )

    # Insert messages (no engineered features are available at this stage;
    # MessageFeatures is empty for the initial DB. Features were added at E7-P1).
    corpus['source_id'] = corpus['source'].map(source_id_of)
    corpus['label'] = corpus['label'].astype(int)
    corpus['cluster_id'] = corpus['cluster_id'].astype('Int64')

    rows = list(corpus[['text', 'label', 'split', 'cluster_id',
                        'source_id']].itertuples(index=False, name=None))
    con.executemany(
        'INSERT INTO Message (text, label, split, cluster_id, source_id) '
        'VALUES (?, ?, ?, ?, ?)',
        rows,
    )
    con.commit()

    (n_msg,)    = con.execute('SELECT COUNT(*) FROM Message').fetchone()
    (n_source,) = con.execute('SELECT COUNT(*) FROM Source').fetchone()
    (n_feat,)   = con.execute('SELECT COUNT(*) FROM MessageFeatures').fetchone()
    con.close()

    size_mb = INITIAL_DB.stat().st_size / 1024 / 1024
    print(f'INITIAL DB: {INITIAL_DB}')
    print(f'  size:        {size_mb:.1f} MB')
    print(f'  Message:     {n_msg:,}  (expected {INITIAL_EXPECTED_ROWS:,})')
    print(f'  Source:      {n_source}')
    print(f'  MessageFeatures: {n_feat}  (empty by design — features added at E7-P1)')


# ---------------------------------------------------------------------------
# Final DB — from the E8-P9 interim parquet + a lookup back to clean.parquet
# to recover source labels for the real rows.
# ---------------------------------------------------------------------------
def _resolve_source_for_final(row_text: str, cluster_id: int | float,
                               clean_map: dict[str, str]) -> str:
    # 1) Cluster-id conventions for the synthetic batches
    if pd.notna(cluster_id):
        cid = int(cluster_id)
        for name, lo, hi in SYNTHETIC_CLUSTER_RULES:
            if lo <= cid < hi:
                return name
    # 2) Text-hash lookup into the clean corpus
    src = clean_map.get(row_text)
    if src is not None:
        return src
    # 3) Catch-all for any legacy row whose source is not resolvable
    return 'e5_base_corpus'


def build_final() -> None:
    for p in (FINAL_INTERIM, FINAL_CLEAN):
        if not p.exists():
            print(f'  MISSING: {p} — cannot build final DB', file=sys.stderr)
            sys.exit(2)

    FINAL_DB.parent.mkdir(parents=True, exist_ok=True)
    if FINAL_DB.exists():
        FINAL_DB.unlink()

    print('  reading clean.parquet (source lookup)...')
    clean = pd.read_parquet(FINAL_CLEAN, columns=['text', 'source'])
    clean_map: dict[str, str] = dict(zip(clean['text'], clean['source']))
    del clean

    print('  reading e7_p1_features_e8p9.parquet...')
    cols = ['text', 'label', 'split', 'cluster_id'] + NUMERICAL_FEATURE_COLS
    df = pd.read_parquet(FINAL_INTERIM, columns=cols)
    assert len(df) == FINAL_EXPECTED_ROWS, \
        f'expected {FINAL_EXPECTED_ROWS}, got {len(df)}'

    print('  resolving source labels for every row...')
    df['source'] = [
        _resolve_source_for_final(t, c, clean_map)
        for t, c in zip(df['text'].values, df['cluster_id'].values)
    ]

    con = sqlite3.connect(FINAL_DB)
    _apply_schema(con)

    # Register sources
    source_id_of: dict[str, int] = {}
    for src in sorted(df['source'].unique()):
        is_syn = src.startswith('synthetic_') or src == 'synthetic_v1'
        source_id_of[src] = _upsert_source(
            con, src, 'synthetic' if is_syn else 'real'
        )

    df['source_id'] = df['source'].map(source_id_of)
    df['label']      = df['label'].astype(int)
    df['cluster_id'] = df['cluster_id'].astype('Int64')

    print(f'  inserting {len(df):,} Message rows...')
    message_rows = list(df[['text', 'label', 'split', 'cluster_id',
                            'source_id']].itertuples(index=False, name=None))
    con.executemany(
        'INSERT INTO Message (text, label, split, cluster_id, source_id) '
        'VALUES (?, ?, ?, ?, ?)',
        message_rows,
    )

    print(f'  inserting {len(df):,} MessageFeatures rows...')
    (last_id,) = con.execute('SELECT MAX(message_id) FROM Message').fetchone()
    first_id = last_id - len(df) + 1
    df['_message_id'] = range(first_id, last_id + 1)
    feat_cols = ['_message_id'] + NUMERICAL_FEATURE_COLS
    feat_rows = list(df[feat_cols].itertuples(index=False, name=None))
    placeholders = ','.join(['?'] * len(feat_cols))
    con.executemany(
        f'INSERT INTO MessageFeatures ({",".join(["message_id"] + NUMERICAL_FEATURE_COLS)}) '
        f'VALUES ({placeholders})',
        feat_rows,
    )
    con.commit()

    (n_msg,)    = con.execute('SELECT COUNT(*) FROM Message').fetchone()
    (n_feat,)   = con.execute('SELECT COUNT(*) FROM MessageFeatures').fetchone()
    (n_source,) = con.execute('SELECT COUNT(*) FROM Source').fetchone()
    con.close()

    size_mb = FINAL_DB.stat().st_size / 1024 / 1024
    print(f'FINAL DB: {FINAL_DB}')
    print(f'  size:        {size_mb:.1f} MB')
    print(f'  Message:     {n_msg:,}  (expected {FINAL_EXPECTED_ROWS:,})')
    print(f'  MessageFeatures: {n_feat:,}  (expected {FINAL_EXPECTED_ROWS:,})')
    print(f'  Source:      {n_source}')


# ---------------------------------------------------------------------------
def verify() -> int:
    exit_code = 0
    for path, expected in ((INITIAL_DB, INITIAL_EXPECTED_ROWS),
                            (FINAL_DB, FINAL_EXPECTED_ROWS)):
        if not path.exists():
            print(f'  MISSING: {path}')
            exit_code = 1
            continue
        con = sqlite3.connect(path)
        (n,) = con.execute('SELECT COUNT(*) FROM Message').fetchone()
        con.close()
        mark = 'OK' if n == expected else 'FAIL'
        print(f'  [{mark}] {path.name:<40}  Message={n:,}  (expected {expected:,})')
        if n != expected:
            exit_code = 1
    return exit_code


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=('initial', 'final', 'both', 'verify'))
    args = p.parse_args()

    if args.command == 'initial':
        build_initial()
    elif args.command == 'final':
        build_final()
    elif args.command == 'both':
        build_initial()
        print()
        build_final()
    elif args.command == 'verify':
        return verify()
    return 0


if __name__ == '__main__':
    sys.exit(main())
