"""
Canonical data loaders for the ScamRadar+ E8-P9 pipeline.

All data used by the deployed model comes from `data/canonical/` (imported
from the upstream data-preparation workspace where the E5 baseline was
originally built).
This module exposes a small, typed API over those files so downstream code
never needs to remember the exact filenames.

Everything here is READ-ONLY. Any code that wants to *build* new data
should live in `scripts/data_prep/` or `scripts/training/` and archive
its output under `data/`.
"""
from __future__ import annotations

import json
import os
import pandas as pd

from src.canonical import (
    CANONICAL_APPROVAL, CANONICAL_CLEAN, CANONICAL_EXT_BENCHMARK,
    CANONICAL_EXT_LOCK, CANONICAL_ROWS, CANONICAL_TEST, CANONICAL_TRAIN,
    CANONICAL_VAL, TRAINING_CORPUS_E8P9, TRAINING_CORPUS_E8P9_ROWS,
    SYNTHETIC_E8P2_LEGIT, SYNTHETIC_E8P6_LEGIT,
    SYNTHETIC_E8P8_SCAM, SYNTHETIC_E8P8_LEGIT_PAIRS,
)


# ─── Canonical corpus loaders ────────────────────────────────────────────

def load_clean_corpus() -> pd.DataFrame:
    """The 253,264-row approved cleaned corpus.

    This is the file `APPROVAL.json` was signed against. All train/val/test/
    external partitions derive from it via `scamradar split` (cluster-aware
    stratified split). See `data/canonical/reports/` for the audit.
    """
    df = pd.read_parquet(CANONICAL_CLEAN)
    _assert_rows(df, 'clean', CANONICAL_ROWS['clean'])
    return df


def load_train() -> pd.DataFrame:
    df = pd.read_parquet(CANONICAL_TRAIN)
    _assert_rows(df, 'train', CANONICAL_ROWS['train'])
    return df


def load_val() -> pd.DataFrame:
    df = pd.read_parquet(CANONICAL_VAL)
    _assert_rows(df, 'val', CANONICAL_ROWS['val'])
    return df


def load_test() -> pd.DataFrame:
    df = pd.read_parquet(CANONICAL_TEST)
    _assert_rows(df, 'test', CANONICAL_ROWS['test'])
    return df


def load_external_benchmark() -> pd.DataFrame:
    """The 25,306-row frozen external benchmark.

    This is the ONLY set the final E8-P9 metrics are computed against.
    LOCK.json flags it as `frozen: true` — do not rewrite this file.
    """
    df = pd.read_parquet(CANONICAL_EXT_BENCHMARK)
    _assert_rows(df, 'external_benchmark', CANONICAL_ROWS['external_benchmark'])
    return df


def load_all_splits() -> dict[str, pd.DataFrame]:
    """train / val / test / external as a dict."""
    return {
        'train':    load_train(),
        'val':      load_val(),
        'test':     load_test(),
        'external': load_external_benchmark(),
    }


# ─── Training corpus (E5 splits + synthetic augmentation) ────────────────

def load_training_corpus_e8p9() -> pd.DataFrame:
    """The 283,501-row final E8-P9 training corpus.

    Produced by the E8 build chain:
        e7_p1_features       (253,264, all 4 canonical splits + 25 features)
        + E8-P2 synthetic     (+1,978 legit)
        - E8-P3 SA filter     (-1,095 spamassassin_ham + -1,143 other)
        - E8-P5 cleanup       (-802 mailing lists + spam-in-legit + short)
        + E8-P6 synthetic     (+15,572 legit, -51 dedup)
        + E8-P8 synthetic     (+14,669 scam + 1,109 legit pairs)
        = e7_p1_features_e8p9 (283,501)

    Rebuilding is a one-shot: run `scripts/data_prep/*` merge scripts in
    order (see the script docstrings for the exact chain).
    """
    df = pd.read_parquet(TRAINING_CORPUS_E8P9)
    _assert_rows(df, 'training_corpus_e8p9', TRAINING_CORPUS_E8P9_ROWS)
    return df


# ─── Synthetic sources (individual, per-batch) ───────────────────────────

def load_synthetic_e8p2_legit() -> pd.DataFrame:
    return pd.read_parquet(SYNTHETIC_E8P2_LEGIT)

def load_synthetic_e8p6_legit() -> pd.DataFrame:
    return pd.read_parquet(SYNTHETIC_E8P6_LEGIT)

def load_synthetic_e8p8_scam() -> pd.DataFrame:
    return pd.read_parquet(SYNTHETIC_E8P8_SCAM)

def load_synthetic_e8p8_legit_pairs() -> pd.DataFrame:
    return pd.read_parquet(SYNTHETIC_E8P8_LEGIT_PAIRS)


# ─── Approval + lock manifest ────────────────────────────────────────────

def load_approval_manifest() -> dict:
    """The signed approval gate that authorised the training data.

    Contains the dataset_hash, class balance, audit totals, and any
    accepted red flags. Written by `scamradar approve-dataset` after
    human review of `scamradar audit`.
    """
    with open(CANONICAL_APPROVAL) as f:
        return json.load(f)


def load_external_lock() -> dict:
    """LOCK.json for the external benchmark — a write-once seal."""
    with open(CANONICAL_EXT_LOCK) as f:
        return json.load(f)


# ─── Guards ──────────────────────────────────────────────────────────────

def _assert_rows(df: pd.DataFrame, name: str, expected: int) -> None:
    """Fail fast if a canonical file has been mutated."""
    if len(df) != expected:
        raise RuntimeError(
            f'Canonical data drift detected: {name} has {len(df):,} rows, '
            f'expected {expected:,}. Verify data/canonical/ against '
            f'data/canonical/APPROVAL.json.'
        )


__all__ = [
    'load_clean_corpus', 'load_train', 'load_val', 'load_test',
    'load_external_benchmark', 'load_all_splits',
    'load_training_corpus_e8p9',
    'load_synthetic_e8p2_legit', 'load_synthetic_e8p6_legit',
    'load_synthetic_e8p8_scam', 'load_synthetic_e8p8_legit_pairs',
    'load_approval_manifest', 'load_external_lock',
]
