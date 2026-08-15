"""
Canonical constants for the deployed ScamRadar+ E8-P9 pipeline.

This module is the single declarative source of truth for the values that
identify the final system: data paths, model paths, hyperparameters,
feature list, threshold, rule count, and headline metrics.

Anything else in the codebase that needs one of these values should import
it from here. If a value here disagrees with a value elsewhere, this
module wins.

Reading this module top-to-bottom answers:

  - What data was used?          → CANONICAL_DATA_*
  - What model is deployed?      → DEPLOYED_MODEL_PATH
  - Which hyperparameters?       → LR_HYPERPARAMS, TFIDF_WORD_PARAMS,
                                    TFIDF_CHAR_PARAMS
  - Which numerical features?    → NUMERICAL_FEATURES  (also in root config.py;
                                    re-exported here for locality)
  - Was calibration used?        → CALIBRATION
  - What is the threshold?       → OPERATING_THRESHOLD  (= config.E5_THRESHOLD)
  - How many rules?              → RULE_ENGINE_TOTAL  (9 + 7 + 3 = 19)
  - What are the final metrics?  → HEADLINE_METRICS
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import E5_THRESHOLD

# Note: `config.NUMERICAL_FEATURES` contains the same 25 features (order
# differs; that list preserves the historical training-time order used by
# scripts/training/train_e7_p1.py). This module holds the authoritative
# deployed order, verified against
# `models/e7_p1_variants/e7_p1_full_e8p9.joblib::feature_cols`. Do not
# import from config.NUMERICAL_FEATURES for inference; use this module.


# ─── Canonical data paths ────────────────────────────────────────────────
# All paths are absolute-from-repo-root so the code works from any cwd.

CANONICAL_DATA_DIR = os.path.join(_ROOT, 'data', 'canonical')
CANONICAL_CLEAN         = os.path.join(CANONICAL_DATA_DIR, 'clean.parquet')
CANONICAL_TRAIN         = os.path.join(CANONICAL_DATA_DIR, 'train.parquet')
CANONICAL_VAL           = os.path.join(CANONICAL_DATA_DIR, 'val.parquet')
CANONICAL_TEST          = os.path.join(CANONICAL_DATA_DIR, 'test.parquet')
CANONICAL_EXT_BENCHMARK = os.path.join(CANONICAL_DATA_DIR, 'external_benchmark.parquet')
CANONICAL_APPROVAL      = os.path.join(CANONICAL_DATA_DIR, 'APPROVAL.json')
CANONICAL_EXT_LOCK      = os.path.join(CANONICAL_DATA_DIR, 'external_benchmark_LOCK.json')

# Expected row counts (verified from the actual files, Aug 2026).
# A checksum-style guard — if any of these drift, the canonical data has
# been mutated and should be re-verified against APPROVAL.json.
CANONICAL_ROWS = {
    'clean':              253_264,
    'train':              159_571,
    'val':                 34_193,
    'test':                34_194,
    'external_benchmark':  25_306,
}

# Deployed E8-P9 training corpus (produced by the E8 build chain from the
# canonical splits above + synthetic augmentation batches).
TRAINING_CORPUS_E8P9 = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p9.parquet')
TRAINING_CORPUS_E8P9_ROWS = 283_501

SYNTHETIC_DIR = os.path.join(_ROOT, 'data')
SYNTHETIC_E8P2_LEGIT       = os.path.join(SYNTHETIC_DIR, 'synthetic_legit', 'e8p2', 'dataset.parquet')       # 1,978
SYNTHETIC_E8P6_LEGIT       = os.path.join(SYNTHETIC_DIR, 'synthetic_legit', 'e8p6', 'dataset.parquet')       # 15,572
SYNTHETIC_E8P8_SCAM        = os.path.join(SYNTHETIC_DIR, 'synthetic_scam',  'e8p8', 'scam_dataset.parquet')  # 14,669
SYNTHETIC_E8P8_LEGIT_PAIRS = os.path.join(SYNTHETIC_DIR, 'synthetic_scam',  'e8p8', 'legit_pairs_dataset.parquet')  # 1,109


# ─── Deployed model ──────────────────────────────────────────────────────

DEPLOYED_MODEL_PATH = os.path.join(_ROOT, 'models', 'e7_p1_variants',
                                    'e7_p1_full_e8p9.joblib')
DEPLOYED_MODEL_NAME = 'e7_p1_full_e8p9'
DEPLOYED_MODEL_SIZE_MB = 3.595
DEPLOYED_MODEL_LATENCY_MS_BATCH1 = 0.048


# ─── Classifier configuration (frozen at E4, retrained for E8-P9) ────────
#
# Selected via Optuna TPE hyperparameter optimization on the validation
# partition at the E4 stage of the modeling programme. Frozen thereafter;
# every E7 and E8 variant re-uses these exact settings — only the training
# data and feature block change.

LR_HYPERPARAMS = dict(
    C=5.968425624989058,
    penalty='l2',
    class_weight='balanced',
    solver='liblinear',
    max_iter=3000,
    tol=1e-4,
    fit_intercept=True,
    random_state=42,
)

TFIDF_WORD_PARAMS = dict(
    ngram_range=(1, 2),
    min_df=3,
    max_df=0.9462114758401128,
    max_features=200_000,
    sublinear_tf=True,
    lowercase=True,
)

TFIDF_CHAR_PARAMS = dict(
    analyzer='char_wb',
    ngram_range=(3, 6),
    min_df=4,
    max_df=1.0,
    max_features=300_000,
    sublinear_tf=True,
    lowercase=True,
)

# Concatenated matrix width: 200,000 word + 300,000 char + 25 numerical.
FEATURE_MATRIX_WIDTH = 200_000 + 300_000 + 25   # = 500_025


# ─── 25 engineered numerical features ────────────────────────────────────
#
# Order matters — this is the exact column order the deployed model's
# StandardScaler expects. Verified against
# `models/e7_p1_variants/e7_p1_full_e8p9.joblib::feature_cols`.

NUMERICAL_FEATURES: list[str] = [
    # Tone (4)
    'tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat',
    # URL structure (5)
    'has_url', 'url_count', 'url_suspicious_tld', 'url_suspicious_keyword', 'url_has_ip',
    # Phrase signals (3)
    'scam_phrase_score', 'sender_impersonation_score', 'legit_phrase_score',
    # Text base + structure (13)
    'text_length', 'word_count', 'exclamation_count', 'uppercase_ratio',
    'digit_ratio', 'urgency_score',
    'avg_word_length', 'capitalized_word_count', 'punctuation_density',
    'question_mark_count', 'currency_symbol_count', 'readability_score',
    'unique_word_ratio',
]
assert len(NUMERICAL_FEATURES) == 25, \
    f'NUMERICAL_FEATURES must be 25; found {len(NUMERICAL_FEATURES)}'


# ─── Calibration decision ────────────────────────────────────────────────
#
# Evaluated at E5 with candidates ['none', 'platt', 'isotonic']. Uncalibrated
# LR dominated on PR-AUC, ROC-AUC, ECE (0.0125), and Brier — the calibration
# was rejected. The deployed model outputs raw sigmoid probabilities.

CALIBRATION = 'none'
ECE_UNCALIBRATED = 0.0125


# ─── Operating threshold ─────────────────────────────────────────────────
#
# F1-max on the validation partition, chosen at E5, unchanged through
# E7 and E8. Same value in config.E5_THRESHOLD.

OPERATING_THRESHOLD = float(E5_THRESHOLD)   # 0.59


# ─── Rule engine ─────────────────────────────────────────────────────────
#
# Post-classification modular rule engine, active in production
# (SCAMRADAR_RULE_ENGINE_ON=true by default). Rules operate on the raw
# classifier probability and can FORCE_SCAM (Category A), INCREASE
# (Category B), or DECREASE (Category C) it. Implementation in
# src/rule_engine/.

RULE_ENGINE_CRITICAL_COUNT = 9   # Category A — FORCE_SCAM
RULE_ENGINE_STRONG_COUNT   = 7   # Category B — INCREASE
RULE_ENGINE_LEGIT_COUNT    = 3   # Category C — DECREASE
RULE_ENGINE_TOTAL          = RULE_ENGINE_CRITICAL_COUNT + RULE_ENGINE_STRONG_COUNT + RULE_ENGINE_LEGIT_COUNT   # 19


# ─── External evaluation ─────────────────────────────────────────────────

EXTERNAL_BENCHMARK_ROWS = 25_306
EXTERNAL_BENCHMARK_FROZEN = True   # LOCK.json in canonical dir


# ─── Headline metrics ────────────────────────────────────────────────────
#
# Computed against the canonical external benchmark (25,306 rows) with the
# deployed model + rule engine active. Reproducible from
# `python -m scripts.evaluation.analyze_e8p9_errors`.

HEADLINE_METRICS = {
    'raw_classifier': {
        'accuracy':  0.9698,
        'precision': 0.9149,
        'recall':    0.9171,
        'f1':        0.9160,
        'roc_auc':   0.9905,
        'pr_auc':    0.9692,
        'ece':       0.0125,
        'confusion': {'tn': 20_384, 'fp': 387, 'fn': 376, 'tp': 4_159},
        'n':         25_306,
    },
    'with_rule_engine': {
        'accuracy':  0.9687,
        'precision': 0.9102,
        'recall':    0.9160,
        'f1':        0.9131,
        'confusion': {'tn': 20_361, 'fp': 410, 'fn': 381, 'tp': 4_154},
        'n':         25_306,
    },
}


# ─── Historical / non-canonical values (documented so nobody confuses them) ───
#
# These are values that appeared in intermediate reports and are commonly
# misquoted as "the current result". They are HISTORICAL and must not be
# used as the current final result.

HISTORICAL_E8P1_WITH_RULES_F1 = 0.9368   # 13-rule engine, superseded by 19-rule
HISTORICAL_E8P1_WITH_RULES_ACC = 0.9776


__all__ = [
    'CANONICAL_DATA_DIR', 'CANONICAL_CLEAN', 'CANONICAL_TRAIN', 'CANONICAL_VAL',
    'CANONICAL_TEST', 'CANONICAL_EXT_BENCHMARK', 'CANONICAL_APPROVAL',
    'CANONICAL_EXT_LOCK', 'CANONICAL_ROWS',
    'TRAINING_CORPUS_E8P9', 'TRAINING_CORPUS_E8P9_ROWS',
    'SYNTHETIC_E8P2_LEGIT', 'SYNTHETIC_E8P6_LEGIT',
    'SYNTHETIC_E8P8_SCAM', 'SYNTHETIC_E8P8_LEGIT_PAIRS',
    'DEPLOYED_MODEL_PATH', 'DEPLOYED_MODEL_NAME',
    'DEPLOYED_MODEL_SIZE_MB', 'DEPLOYED_MODEL_LATENCY_MS_BATCH1',
    'LR_HYPERPARAMS', 'TFIDF_WORD_PARAMS', 'TFIDF_CHAR_PARAMS',
    'FEATURE_MATRIX_WIDTH', 'NUMERICAL_FEATURES',
    'CALIBRATION', 'ECE_UNCALIBRATED', 'OPERATING_THRESHOLD',
    'RULE_ENGINE_CRITICAL_COUNT', 'RULE_ENGINE_STRONG_COUNT',
    'RULE_ENGINE_LEGIT_COUNT', 'RULE_ENGINE_TOTAL',
    'EXTERNAL_BENCHMARK_ROWS', 'EXTERNAL_BENCHMARK_FROZEN',
    'HEADLINE_METRICS',
    'HISTORICAL_E8P1_WITH_RULES_F1', 'HISTORICAL_E8P1_WITH_RULES_ACC',
]
