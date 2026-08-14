"""
=============================================================================
ScamRadar+ | Canonical E8-P9 Pipeline
=============================================================================

This module is the single source of truth for the deployed ScamRadar+
system. Reading it top-to-bottom shows the complete flow — data,
preprocessing, features, model, rule engine, inference, evaluation — as
a linear narrative that references (and can execute) every step of the
real pipeline.

Nothing here reimplements logic. Every stage delegates to the same
production module the FastAPI layer uses:

  Stage                       | Implementation
  --------------------------- | ---------------------------------------------
  1. Canonical constants      | src/canonical.py
  2. Data loading             | src/data.py
  3. Text preprocessing       | src/features.py::preprocess_text
  4. Feature engineering      | src/features.py + src/rule_engine/numerical_features.py
  5. Model configuration      | src/model.py
  6. Model training           | src/model.py::train_e8p9_model
  7. Rule engine              | src/rule_engine/
  8. Single-message inference | src/inference.py (deployed by api/main.py)
  9. Evaluation               | src/evaluation.py
  10. Historical experiments  | experiments/  (not required by this module)

If you want to defend "the final implementation is a self-contained
codebase," open this file — it is the map. If you want to defend a
number, follow its link from `src/canonical.HEADLINE_METRICS` to the
generating code path.

=============================================================================
"""
from __future__ import annotations

import os
import sys

# ─── Section 1 — canonical constants (all values that identify E8-P9) ──
from src.canonical import (
    CANONICAL_DATA_DIR,
    DEPLOYED_MODEL_PATH, DEPLOYED_MODEL_NAME,
    LR_HYPERPARAMS, TFIDF_WORD_PARAMS, TFIDF_CHAR_PARAMS,
    NUMERICAL_FEATURES, FEATURE_MATRIX_WIDTH,
    CALIBRATION, OPERATING_THRESHOLD,
    RULE_ENGINE_CRITICAL_COUNT, RULE_ENGINE_STRONG_COUNT,
    RULE_ENGINE_LEGIT_COUNT, RULE_ENGINE_TOTAL,
    EXTERNAL_BENCHMARK_ROWS, HEADLINE_METRICS,
    TRAINING_CORPUS_E8P9_ROWS,
)

# ─── Section 2 — data loaders (canonical, in-repo, no external deps) ───
from src.data import (
    load_clean_corpus,           # 253,264 rows, approved (APPROVAL.json)
    load_train,                  # 159,571 rows
    load_val,                    # 34,193 rows
    load_test,                   # 34,194 rows
    load_external_benchmark,     # 25,306 rows, LOCKed (write-once)
    load_training_corpus_e8p9,   # 283,501 rows (base + synthetic - filtered)
    load_synthetic_e8p2_legit,   # 1,978 rows
    load_synthetic_e8p6_legit,   # 15,572 rows
    load_synthetic_e8p8_scam,    # 14,669 rows
    load_synthetic_e8p8_legit_pairs,  # 1,109 rows
    load_approval_manifest,      # dataset_hash + audit red flags
    load_external_lock,          # frozen: true
)

# ─── Section 3 — text preprocessing (adversarial-aware normalisation) ──
from src.features import preprocess_text
# preprocess_text applies: NFKC Unicode norm, char-spacing collapse
# ("Y o u r" → "Your"), emoji → text mapping, HTML strip, URL-shortener
# marking, whitespace collapse.

# ─── Section 4 — feature engineering (word TF-IDF + char TF-IDF + 25 num) ─
from src.model import (
    build_word_vectorizer,       # TfidfVectorizer(**TFIDF_WORD_PARAMS)
    build_char_vectorizer,       # TfidfVectorizer(**TFIDF_CHAR_PARAMS)
    compute_numerical_features,  # dict[str, float]  (25 keys)
    numerical_features_matrix,   # scaled matrix + fitted StandardScaler
)
from src.features import (
    compute_tone_features,       # urgency, fear, reward, threat  (4)
    compute_url_features,        # susp_tld, susp_kw, has_ip      (3)
    compute_new_features,        # 10 more (avg_word_len, ...)
    classify_scam_type,          # 14-category rule-based classifier
    extract_urls,                # regex URL extractor
)
# The exact 25 features (declared in src/canonical.NUMERICAL_FEATURES):
#
#   Text base (4):    text_length, word_count, has_url, url_count
#   Text structure (4): exclamation_count, uppercase_ratio, digit_ratio,
#                       urgency_score
#   Tone (4):         tone_urgency, tone_fear, tone_reward, tone_threat
#   URL structure (3): url_suspicious_tld, url_suspicious_keyword,
#                     url_has_ip
#   Phrase signals (3): scam_phrase_score, sender_impersonation_score,
#                     legit_phrase_score
#   Text statistics (7): avg_word_length, capitalized_word_count,
#                     punctuation_density, question_mark_count,
#                     currency_symbol_count, readability_score,
#                     unique_word_ratio
#
# All feature computations converge in
# src/rule_engine/numerical_features.py::compute_all_numerical — the
# single implementation used by BOTH training and inference (parity is
# guaranteed by construction).

# ─── Section 5 — final classifier (Logistic Regression, uncalibrated) ──
from src.model import (
    build_classifier,            # LogisticRegression(**LR_HYPERPARAMS)
    train_e8p9_model,            # end-to-end training from training corpus
    save_bundle, load_deployed_bundle,
)
# Calibration: NONE (rejected at E5 — uncalibrated dominated on PR-AUC,
# ROC-AUC, ECE, Brier). Operating threshold: 0.59 (F1-max on validation).
# ECE at 0.59: 0.0125.

# ─── Section 6 — 19-rule post-classification engine ────────────────────
from src.rule_engine import build_default_engine, build_context, DEFAULT_RULES
# 9 CRITICAL (A) rules — can FORCE_SCAM:
#   A1 MaliciousUrlRule, A2 CredentialRequestRule, A3 OtpTheftRule,
#   A4 GiftCardPaymentRule, A5 CryptoSeedPhraseRule, A6 RemoteAccessRule,
#   A9 InvestmentScamTypeFloorRule, A10 RomanceScamTypeFloorRule,
#   A11 ThreatScamTypeFloorRule.
# 7 STRONG (B) rules — can INCREASE:
#   B1 UrlShortenerActionRule, B2 HomoglyphDomainRule, B3 PunycodeDomainRule,
#   B4 QrPaymentLoginRule, B5 ThreatImmediatePaymentRule,
#   B6 ImpossibleBrandDomainRule, B7 HighRiskFinancialRule.
# 3 LEGIT (C) rules — can DECREASE:
#   C1 BrandOfficialDomainRule, C2 OfficialDomainConsistencyRule,
#   C3 OtpNotificationRule.
# Total = 19. NB: BrandImpersonationWithActionRule is a defined-but-
# unused class in critical.py (not registered in CRITICAL_RULES); it is
# not counted.

# ─── Section 7 — single-message inference (used by api/main.py) ────────
from src.inference import load_pipeline, predict_message
# Full request-time path:
#   text →  bundle.model.predict_proba([text])[:,1]  (raw ML prob)
#       →  ancillary analysis (scam_type, tone, urls, url reputation)
#       →  rule engine (if SCAMRADAR_RULE_ENGINE_ON=true, default)
#       →  verdict = 'SCAM' if prob >= 0.59 else 'LEGIT'
#       →  compose response dict (verdict, confidence, why_flagged,
#          triggered_rules, tone/url signals, URL reputation, etc.)

# ─── Section 8 — evaluation (canonical headline metrics reproduction) ──
from src.evaluation import (
    compute_metrics,
    evaluate_raw_classifier,
    evaluate_with_rule_engine,
    fp_fn_by_category,
    rule_engagement,
)


# =============================================================================
# HIGH-LEVEL ENTRY POINTS
# =============================================================================

def describe() -> str:
    """One-page description of the deployed system.

    Useful in a defence: `python -c "from src.pipeline import describe;
    print(describe())"` prints the whole story.
    """
    return f"""
ScamRadar+ deployed E8-P9 pipeline
==================================

DATA (canonical, in-repo at data/canonical/):
  clean.parquet             253,264 rows  (approved via APPROVAL.json)
  train.parquet             159,571
  val.parquet                34,193
  test.parquet               34,194
  external_benchmark.parquet 25,306  (frozen, write-once)

TRAINING CORPUS (data/interim/e7_p1_features_e8p9.parquet):
  Base:  253,264  (all four canonical splits, concatenated + 25 features)
  +E8-P2 synthetic legit:      +1,978
  -E8-P3 SA + other filter:    -2,238
  -E8-P5 cleanup:                -802
  +E8-P6 synthetic legit:     +15,572   (-51 dedup)
  +E8-P8 synthetic scam:      +14,669
  +E8-P8 legit pairs:          +1,109
  = final:                    {TRAINING_CORPUS_E8P9_ROWS:,}

CLASSIFIER: Logistic Regression (uncalibrated)
  C={LR_HYPERPARAMS['C']:.4f}, penalty={LR_HYPERPARAMS['penalty']}, class_weight={LR_HYPERPARAMS['class_weight']}
  solver={LR_HYPERPARAMS['solver']}, max_iter={LR_HYPERPARAMS['max_iter']}

TEXT REPRESENTATION:
  Word TF-IDF: ngrams={TFIDF_WORD_PARAMS['ngram_range']}, max_features={TFIDF_WORD_PARAMS['max_features']:,}
  Char TF-IDF: ngrams={TFIDF_CHAR_PARAMS['ngram_range']}, max_features={TFIDF_CHAR_PARAMS['max_features']:,}, analyzer=char_wb
  Numerical: {len(NUMERICAL_FEATURES)} engineered features (see src.canonical.NUMERICAL_FEATURES)
  Total feature width: {FEATURE_MATRIX_WIDTH:,}

CALIBRATION: {CALIBRATION}   (rejected at E5)
OPERATING THRESHOLD: {OPERATING_THRESHOLD}   (F1-max on validation)

RULE ENGINE: {RULE_ENGINE_TOTAL} rules
  Category A (critical, force_scam):  {RULE_ENGINE_CRITICAL_COUNT}
  Category B (strong, increase):      {RULE_ENGINE_STRONG_COUNT}
  Category C (legit, decrease):       {RULE_ENGINE_LEGIT_COUNT}

DEPLOYED ARTIFACT:
  {DEPLOYED_MODEL_PATH}

EXTERNAL EVALUATION: {EXTERNAL_BENCHMARK_ROWS:,} rows (LOCKed)
  Raw classifier: F1={HEADLINE_METRICS['raw_classifier']['f1']:.4f}, Acc={HEADLINE_METRICS['raw_classifier']['accuracy']:.4f}
  With rules:     F1={HEADLINE_METRICS['with_rule_engine']['f1']:.4f}, Acc={HEADLINE_METRICS['with_rule_engine']['accuracy']:.4f}
""".strip()


def reproduce_training() -> dict:
    """Retrain the deployed bundle from the canonical training corpus.

    Loads `data/interim/e7_p1_features_e8p9.parquet`, filters to the
    `train` split, and refits the whole word+char+25-features+LR
    pipeline. Returns the freshly-trained bundle dict.

    This is the reproducibility recipe: given only this repository, one
    function call rebuilds the deployed model. Runtime: ~1 hour on CPU.
    """
    corpus = load_training_corpus_e8p9()
    train_df = corpus[corpus['split'] == 'train'].copy()
    return train_e8p9_model(train_df)


def reproduce_metrics() -> dict:
    """Reproduce the canonical headline metrics on the frozen benchmark.

    Loads the currently-deployed bundle from disk, scores every item in
    the 25,306-row external benchmark, and returns the metric block. The
    returned dict should match `HEADLINE_METRICS['with_rule_engine']`
    up to float rounding.

    Runtime: ~10 min on CPU.
    """
    bundle = load_deployed_bundle()
    benchmark = load_external_benchmark()
    metrics, per_df = evaluate_with_rule_engine(bundle, benchmark)
    return metrics


if __name__ == '__main__':
    print(describe())
