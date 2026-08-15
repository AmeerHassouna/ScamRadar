# ScamRadar+ — Source of Truth

**One canonical answer per question.** If a value elsewhere in the repository contradicts a value here, this document wins.

Last verified: 2026-08-15 against the working tree.

> **What ships in this public repository:** production/inference source, deployment configs, the deployed model bundle (`models/e7_p1_variants/e7_p1_full_e8p9.joblib`), the E5 fallback bundle, E8-chain and E7-P1 training/evaluation scripts, and software documentation (`README.md`, `models/README.md`, `docs/USER_GUIDE.md`, this file). **What is intentionally external:** the raw / canonical / interim / synthetic parquet data, the frozen evaluation outputs, the four CRISP-DM notebooks, the thesis chapters, and the historical `experiments/` and `models/_archive/` trees. See "What is NOT in this public repository (and why)" below.
>
> **Data provenance.** The canonical corpus originated from an upstream data acquisition and preparation process; its frozen outputs were subsequently incorporated into the current ScamRadar+ project. The deployed pipeline does not require that upstream process at runtime.

---

## The one-table answer

| Question | Canonical answer | Evidence |
|---|---|---|
| What is the raw dataset? | A 14-source acquisition (13 real-world corpora + 1 in-house `synthetic_v1` seed) covering email / SMS / chat / job-posting, produced by the upstream data-preparation process and incorporated into `data/canonical/` | `data/canonical/reports/acquisition_manifest.json`, `data/canonical/reports/raw_provenance.json` |
| How many sources survive into the final E8-P9 corpus? | **12 real-world sources** (all 13 original real corpora except `spamassassin_ham`, which was dropped at E8-P3) + 4 new synthetic-source rows produced by E8-P2 / E8-P6 / E8-P8 + a `synthetic_v1` / `e5_base_corpus` legacy row. Documented in the `Source` table of the final database (17 rows total). | `docs/database/README.md`, `docs/database/schema.sql`, live final DB Source table |
| Where is the relational database? | **Two SQLite databases** representing the two ends of the data-preparation iteration. Neither `.db` file ships in Git (each is 200–250 MB); both are locally reproducible from `scripts/data_prep/build_databases.py`. See [`docs/database/README.md`](docs/database/README.md). | `data/initial_db/scamradar_initial_253264.db` (253,264 rows, 14 sources) and `data/final_db/scamradar_e8p9.db` (283,501 rows, 17 sources) |
| Where is the ERD? | [`docs/database/erd.svg`](docs/database/erd.svg) — same schema for both DBs. | `docs/database/erd.svg`, `docs/database/schema.sql` |
| What is the cleaned dataset? | **`data/canonical/clean.parquet`** — 253,264 rows | `data/canonical/APPROVAL.json` (dataset_hash: `f92fe4b7fb0b0080a1c04a959d236d15d297a75bafc1cee66477ac3aac322223`) |
| What are the modelling splits? | `data/canonical/{train,val,test}.parquet` — 159,571 / 34,193 / 34,194 | Produced by cluster-aware stratified split (`scamradar split`) |
| What is the external evaluation set? | **`data/canonical/external_benchmark.parquet`** — 25,306 rows | `data/canonical/external_benchmark_LOCK.json` (`frozen: true`, write-once) |
| What is the final training corpus? | **`data/interim/e7_p1_features_e8p9.parquet`** — 283,501 rows | Base splits + 4 synthetic batches − filter losses; see Data Lineage below |
| What is the text representation? | Word TF-IDF (1–2 grams, 200,000 max features) + character TF-IDF (3–6 char_wb grams, 300,000 max features) | `src/canonical.TFIDF_WORD_PARAMS` and `TFIDF_CHAR_PARAMS` |
| How many engineered numerical features? | **25** | `src/canonical.NUMERICAL_FEATURES` (verified against deployed bundle's `feature_cols`) |
| Total feature matrix width | **500,025** (200,000 + 300,000 + 25) | `src/canonical.FEATURE_MATRIX_WIDTH` |
| What is the final classifier? | **Logistic Regression** | `src/canonical.LR_HYPERPARAMS`; also confirmed in `outputs/eval/e8p9_bakeoff_results.json` (winner: LR) |
| Final hyperparameters | C=5.9684, penalty=l2, class_weight=balanced, solver=liblinear, max_iter=3000 | `src/canonical.LR_HYPERPARAMS`; frozen at E4 (Optuna TPE) |
| Calibration | **None** (rejected at E5) | `src/canonical.CALIBRATION`; uncalibrated LR dominated on PR-AUC, ROC-AUC, ECE (0.0125), Brier |
| Operating threshold | **0.59** (F1-max on validation) | `src/canonical.OPERATING_THRESHOLD` = `config.E5_THRESHOLD` |
| How many rules in the deployed Rule Engine? | **19** (9 Category-A critical + 7 Category-B strong + 3 Category-C legit) | `src/rule_engine/critical.py::CRITICAL_RULES`, `strong.py::STRONG_RULES`, `legit.py::LEGIT_RULES` |
| How are the three OTP mechanisms distinguished? | Two are inside the 19-rule engine and count toward the 19: **A3 `OtpTheftRule`** (Category-A, force-scam on OTP theft requests) at `src/rule_engine/critical.py::OtpTheftRule` and **C3 `OtpNotificationRule`** (Category-C, dampen on pure OTP notifications) at `src/rule_engine/legit.py::OtpNotificationRule`. A third mechanism, the legacy pre-rule-engine hardcoded detector **`_is_pure_otp`** in `src/e5_inference.py`, is **outside the 19-rule engine**, is env-gated by `SCAMRADAR_OTP_RULE_ON` (default OFF), and was explicitly disabled during the reported F1 = 0.9131 evaluation via `scripts/evaluation/analyze_e8p9_errors.py:26`. | `src/rule_engine/critical.py`, `src/rule_engine/legit.py`, `src/e5_inference.py` |
| What is the deployed model artifact? | **`models/e7_p1_variants/e7_p1_full_e8p9.joblib`** (3.6 MB) | `src/canonical.DEPLOYED_MODEL_PATH`; loaded by `api/main.py` via `src/inference.py` |
| Where is the canonical E8-P9 implementation? | **`src/`** — start with **`src/pipeline.py`** | Not a notebook. Every stage is a Python module. |
| Which iteration produced the deployed configuration? | **Final ScamRadar+ pipeline** (internal ID `E8-P9`) — retrained on the 283,501-row corpus + 19-rule engine | Full lineage in "Development journey — iterations of the same core pipeline" below |

---

## Final metrics (canonical)

Both computed against the 25,306-row frozen external benchmark. Reproducible via `python scripts/evaluation/analyze_e8p9_errors.py` (which now reads the in-repo canonical benchmark).

**Roles of the two headline metrics.** The classifier is trained/tuned/calibrated only on the training and validation partitions; the 25,306-row external benchmark is held out from **classifier training, hyperparameter optimization (E4), calibration (E5), and classifier threshold selection (E5)**. Therefore:

- **F1 = 0.9160 (raw classifier)** is the primary model evaluation — a held-out external evaluation of the classifier alone.
- **F1 = 0.9131 (classifier + 19-rule engine)** is the composite deployed metric. The Rule Engine layer was iteratively refined through error analysis: rules that mis-fired on the benchmark were removed or tightened (see the change-history comments in `src/rule_engine/critical.py`, `strong.py`, `legit.py`). This is a deliberate part of the deployment pipeline, not a fully independent blind evaluation of the rule layer itself.

Both numbers are legitimate — the first captures classifier generalisation; the second reflects the shipped composite that the user actually receives.

### Raw classifier (Logistic Regression, no rule engine), threshold = 0.59

**Model:** E8-P9 raw classifier — retrained on the *post-augmentation* **283,501-row** training corpus.

| Metric | Value |
|---|---:|
| Accuracy | **0.9698** (96.98%) |
| Precision | 0.9149 (91.49%) |
| Recall | 0.9171 (91.71%) |
| F1 | 0.9160 (91.60%) |
| ROC-AUC | 0.9905 |
| PR-AUC | 0.9692 |
| ECE (15-bin) | 0.0125 |
| Confusion (TN / FP / FN / TP) | 20,384 / 387 / 376 / 4,159 |
| n | 25,306 |

### Deployed pipeline (classifier + 19-rule engine), threshold = 0.59

**Model:** same E8-P9 classifier as above (trained on the 283,501-row corpus) + the 19-rule engine applied at inference.

| Metric | Value |
|---|---:|
| Accuracy | **0.9687** (96.87%) |
| Precision | 0.9102 (91.02%) |
| Recall | 0.9160 (91.60%) |
| F1 | **0.9131** (91.31%) |
| Confusion (TN / FP / FN / TP) | **20,361 / 410 / 381 / 4,154** |
| n | 25,306 |

### How the three headline F1 numbers relate

| F1 | Classifier trained on | Rule Engine? | Reads as |
|---:|---|---|---|
| **~0.941** (0.9414 / 0.9412) | **Pre-augmentation 253,264-row corpus** (E5 baseline / E7-P1-Full baseline) | No | Historical baseline — the pure classifier on the original approved corpus. |
| **0.9160** | **Post-augmentation 283,501-row corpus** (E8-P9 classifier) | No | The E8-P9 classifier alone, measured on the same 25,306-row benchmark. |
| **0.9131** | Same 283,501-row corpus | **Yes (19 rules)** | The full deployed pipeline. |

The ~0.941 → 0.9160 gap is **not** classifier degradation — it is the same architecture retrained on a deliberately expanded corpus that includes modern-scam categories the 2008-era external benchmark does not reward. See `README.md::Performance` for the explicit tradeoff explanation. The 0.9160 → 0.9131 gap is the small F1 cost of adding the 19-rule engine on top of the same classifier.

### Values that are NOT the current final result

| Value | Where it comes from | Status |
|---|---|---|
| F1 = 0.9368 | E8-P1 stage (13 legacy rules), `outputs/eval/e8p1_external.json` | **HISTORICAL** — must not be quoted as the current deployed result. It survives only as the E8-P1 stage entry in `outputs/eval/master_summary.json::stages[]`. The current-deployed headline in `external_headline_with_rule_engine` is F1 = 0.9131 (19-rule engine), computed directly from `outputs/eval/e8p9_per_item.parquet`. |
| Accuracy = 0.9776 with rules | Same E8-P1 block | HISTORICAL |
| Confusion TN=20545 / FP=226 / FN=340 / TP=4195 | Same E8-P1 block | HISTORICAL |
| 20 rules | Documentation stated 20; the actual runtime list is 19 (Rule A8 `BrandImpersonationWithActionRule` is defined as a class but not registered in any rule list) | Documentation drift; canonical count = 19 |

---

## Data lineage

```
upstream data acquisition (14 sources; email + SMS + chat + job postings)
      │
      │  acquire step  ── sample_id + exact_hash + cluster_id
      ▼
original raw snapshot (280,728 rows)
    Preserved externally as defense/provenance material.
    SHA-256: f0bef1515f7b02801c56cf3f215f25324c402666f727b6c7169ec1bdf90f9afd
    Verified as a valid preimage of clean.parquet (every one of the 253,264
    clean sample_ids is present in this snapshot; per-source counts match
    data/canonical/reports/acquisition_manifest.json exactly across all 14
    sources). See data/canonical/reports/raw_provenance.json.

    The in-repo data/canonical/canonical_raw.parquet (280,730 rows) is a
    later re-acquisition — differs from the original by 2 rows in the
    sms_spam_collection source; is missing 546 clean sample_ids — kept
    only for source-list traceability, not as a valid preimage of clean.
      │
      │  clean step  (SHA-1 exact dedup + MinHash-LSH near-dup)
      │  Original acquire/clean implementation is not shipped in this
      │  repository, so the raw → clean transformation cannot be re-run
      │  from a clean clone. What IS verifiable from this repository is
      │  the identity + provenance of the raw snapshot and the byte-level
      │  integrity of clean.parquet + all downstream artifacts.
      ▼
data/canonical/clean.parquet                                253,264
      │
      │  scamradar audit + approve-dataset
      │  (APPROVAL.json signed at 2026-08-01T00:04:40Z)
      ▼
      │  scamradar split  (cluster-aware stratified; external carved
      │                    FIRST, LOCKed write-once)
      ▼
data/canonical/train.parquet                                159,571
data/canonical/val.parquet                                   34,193
data/canonical/test.parquet                                  34,194
data/canonical/external_benchmark.parquet                    25,306   [LOCKED]
                                                       ───────────
                                                sum:       253,264
      │
      │  scripts/data_prep/build_databases.py initial
      ▼
data/initial_db/scamradar_initial_253264.db                  253,264   [INITIAL BASELINE DB]
    14 sources: 13 real-world corpora + `synthetic_v1` seed.
    Includes spamassassin_ham (2,238 rows). MessageFeatures empty at this
    stage — the 25 engineered numerical features arrived at E7-P1.
      │
      │  train_e7_p1.py (concatenate all 4 splits + compute 25 features)
      ▼
data/interim/e7_p1_features.parquet                         253,264
      │
      │  merge_e8p2_into_training.py  (+1,978 synthetic legit)
      ▼
data/interim/e7_p1_features_e8p2.parquet                    255,242
      │
      │  build_e8p3_training.py  (drop spamassassin_ham entirely: -2,238)
      ▼
data/interim/e7_p1_features_e8p3.parquet                    253,004
      │
      │  build_e8p5_training.py  (-802 mailing lists + spam-in-legit + short)
      ▼
data/interim/e7_p1_features_e8p5.parquet                    252,202
      │
      │  merge_e8p6_into_training.py  (+15,572 -51 dedup)
      ▼
data/interim/e7_p1_features_e8p6.parquet                    267,723
      │
      │  merge_e8p8_into_training.py  (+14,669 scam + 1,109 legit pairs)
      ▼
data/interim/e7_p1_features_e8p9.parquet                    283,501   [TRAINING CORPUS]
      │
      │  scripts/data_prep/build_databases.py final
      ▼
data/final_db/scamradar_e8p9.db                              283,501   [FINAL E8-P9 DB]
    17 sources: the 12 real-world sources that survived E8-P3 + a legacy
    `e5_base_corpus` catch-all row + 4 new synthetic sources produced by
    E8-P2 / E8-P6 / E8-P8. MessageFeatures fully populated (25 features
    per row).
      │
      │  train_e8p9.py  (fits word+char TF-IDF + StandardScaler + LR)
      ▼
models/e7_p1_variants/e7_p1_full_e8p9.joblib                          [DEPLOYED MODEL]
      │
      │  scripts/evaluation/analyze_e8p9_errors.py
      ▼
outputs/eval/e8p9_per_item.parquet                           25,306   [FINAL PER-ITEM PREDICTIONS]
outputs/eval/master_summary.json                                       [FINAL METRICS]
```

All row counts balance to the last row (per-batch evidence lives in the `merge_report.json` files under `data/synthetic_legit/e8p{2,6}/` and `data/synthetic_scam/e8p8/`, and in `data/interim/e8p5_cleanup_report.json`).

### Split composition at each stage

The cluster-aware split runs **once** on the 253,264-row clean corpus, producing the four standalone parquets above. The E8 iteration only writes into the training partition (synthetic rows are labelled `split='train'` by construction — see the merge scripts), but the E8-P3 and E8-P5 cleanup steps remove rows regardless of split (the target sources / patterns are cross-partition). This produces two distinct split views:

| View | Where | train | val | test | external | sum |
|---|---|---:|---:|---:|---:|---:|
| Initial baseline (frozen, evaluation source of truth) | `data/canonical/{train,val,test,external_benchmark}.parquet` | 159,571 | 34,193 | 34,194 | 25,306 | 253,264 |
| Inside the final E8-P9 training corpus | `data/interim/e7_p1_features_e8p9.parquet::split` | 191,140 | 33,790 | 33,730 | 24,841 | 283,501 |

The classifier fits only on `split=='train'` from the interim file (191,140 rows). **Final evaluation uses the untouched standalone `data/canonical/external_benchmark.parquet` (25,306 rows)**, not the 24,841-row external subset inside the interim file. The interim file's external subset is a byproduct of the cleanup filters and is not read by any evaluation script.

---

## Development journey — iterations of the same core pipeline

**Reading this section.** ScamRadar+ was developed as a single core modeling pipeline (word + character TF-IDF · 25 numerical features · StandardScaler · Logistic Regression · threshold 0.59) that was iteratively improved and retrained. Each row below is either (a) a foundational decision that fixed the core pipeline itself, (b) a targeted data-quality / feature / augmentation change followed by retraining, (c) a rejected iteration preserved for methodological honesty, or (d) a diagnostic pass that motivated the next iteration. The E-series identifiers are retained as internal repository references — filenames, parquet paths, and script names continue to use them — but the examiner-facing labels are the iteration titles in the first column.

| Development step | Internal ID | Question / change | Decision | Evidence |
|---|---|---|---|---|
| Baseline pipeline decision — text representation | E2 | Which text representation? | F3 = word + char TF-IDF | `data/canonical/reports/e2_ranking.json` (not in this repo — upstream artifact) |
| Baseline pipeline decision — classifier family | E3 | Which classifier on F3? | Logistic Regression | `data/canonical/reports/e3_ranking.json` (not in this repo — upstream artifact) |
| Baseline pipeline decision — hyperparameters | E4 | Hyperparameter optimisation on LR | C=5.9684, l2, balanced, sublinear_tf (frozen after E4; reused unchanged from here on) | `data/canonical/reports/e4_best.json`; `models/e5_metadata.json` |
| Baseline pipeline decision — calibration + threshold | E5 | Calibration + operating threshold | Calibration NONE; threshold 0.59 (F1-max on validation) | `data/canonical/reports/e5_final.json`; `models/e5_metadata.json` |
| Baseline pipeline decision — engineered features | E7-P1 | Which engineered numerical features? | All 25 (tone + URL + phrase + text-stats) | `outputs/eval/e7_p1_results.json` |
| *Rejected feature study* | E7-P3 | Proximity-to-scam feature (FAISS + MiniLM) | **REJECTED** — external PR-AUC +0.0011 but F1 −0.0114 with +166 FPs | not shipped (rejected direction) |
| **Iteration 0 — Rule Engine (initial 13 rules)** | E8-P1 | Add a decision-layer rule engine | 13-rule layer added; some brand rules overshoot on modern legit email (motivates later iterations) | `outputs/eval/e8p1_external.json` (F1 = 0.9368 with 13 rules — HISTORICAL intermediate, not the final deployed value) |
| **Iteration 1 — Targeted Legit Augmentation** | E8-P2 | Address false-positive pattern on modern-transactional legit | +1,978 synthetic legit rows adopted; retrained | `data/synthetic_legit/e8p2/` |
| **Iteration 2 — SpamAssassin Removal** | E8-P3 | Remove noise source hurting generalisation | −2,238 rows dropped (entire `spamassassin_ham` source); retrained | `data/interim/e7_p1_features_e8p3.parquet` |
| *Rejected iteration — rolled back* | E8-P4 | Attempted change on the E8-P3 corpus | **REJECTED / rolled back** — external F1 regressed 0.9173 → 0.8842 (precision 0.8503, recall 0.9208). Not adopted; no `e7_p1_features_e8p4.parquet` in the current chain. | `e8p4_per_item.parquet` no longer in current tree; numbers preserved in git history |
| **Iteration 3 — Data Quality Cleanup** | E8-P5 | Remove mailing-list mislabels + spam-in-legit + too-short | −802 rows: 397 mailing-list + 207 spam-in-legit + 198 too-short; retrained | `data/interim/e8p5_cleanup_report.json` |
| **Iteration 4 — Broad Legit Expansion** | E8-P6 | Broader modern-brand legit coverage | +15,521 net synthetic legit rows adopted; retrained | `data/synthetic_legit/e8p6/` |
| *Diagnostic analysis* | E8-P7 | Per-category recall analysis on the corpus so far | Identified weak modern-scam categories (investment/crypto, romance, emergency, refund, sextortion, threat/authority, gift-card CEO, modern phishing). Not a corpus-modifying step; motivated the next iteration. | Enumerated in `scripts/data_prep/gen_e8p8_synthetic_scam.py` docstring |
| **Iteration 5 — Contrastive Scam + Pair Augmentation** | E8-P8 | Target the weakness categories identified above | +14,669 modern synthetic scams + 1,109 legit-pair adversarial twins; retrained | `data/synthetic_scam/e8p8/` |
| **Final ScamRadar+ pipeline** | E8-P9 | Retrain on the 283,501-row corpus + refine the rule engine (13 → 19) | **DEPLOYED** — F1 = 0.916 classifier / 0.913 deployed composite on the 25,306-row external benchmark | `models/e7_p1_variants/e7_p1_full_e8p9.joblib` |

---

## What is NOT in this public repository (and why)

The following historical / rejected / defense-only material is intentionally excluded from the public repository. It is kept outside this repo as decision-journey evidence.

| Category | Excluded material | Reason |
|---|---|---|
| Rejected representation ablation | E7-P1 tone-only / url-only / phrase-only / textstats-only joblibs | All scored lower than `e7_p1_full` on external PR-AUC. |
| Rejected feature study | E7-P3 (FAISS + proximity-to-scam feature) code and artifacts | External PR-AUC dropped vs `e7_p1_full`. Not part of the deployed pipeline. |
| Superseded baseline | Pre-E8-P2 `e7_p1_full.joblib` (trained on 253,264 without synthetic augmentation) | Superseded by `e7_p1_full_e8p9.joblib`. |
| Earlier generation | Model artifacts from a prior architecture (before the E5 baseline was adopted) | Never loaded by the current code path. |
| Aug-10 data-prep regeneration | 279,230-row raw / 251,299 clean / 25,129 benchmark regeneration | Regenerated *after* E8-P9 was trained and evaluated. Never consumed by the deployed model. |
| E6 data-collection tiers | Reddit + web-page collectors, template collectors, tier-level dedup | Superseded by the canonical E5 corpus that seeds the 253,264 approved dataset. |
| Notebooks | Four CRISP-DM presentation notebooks | Presentation layer only; every heavy step is in `scripts/` and `src/`. Notebooks are maintained externally as defense material. |
| Thesis chapters | `docs/thesis_*.md` (data understanding / data preparation / modeling / evaluation) | Thesis narrative is maintained externally; the software repo carries `SOURCE_OF_TRUTH.md`, `data/canonical/DATA_MANIFEST.md`, and `models/README.md`. |
| Isolated experiment | v1.7 augmentation (840 synthetic + 325 real-world eval rows) | Never merged into E8-P9. |

---

## Genuinely UNRESOLVED items

None. The `external_headline_with_rule_engine` block of `outputs/eval/master_summary.json` is computed directly from `outputs/eval/e8p9_per_item.parquet` and matches the deployed 19-rule pipeline (F1 = 0.9131). The historical E8-P1 numbers remain only as the `stages[]::E8-P1` entry, correctly labeled as an intermediate stage.

The `e2_ranking.json` and `e3_ranking.json` artifacts were produced by the upstream data-preparation / modeling process and are not present in this repository; `build_evaluation_summary.py` emits stub records for those two stages. The E2 / E3 decisions are still reconstructible from `data/canonical/reports/e4_best.json::e3_baseline_reference`.

---

## How to reproduce the deployed metrics

```bash
# 1. Verify canonical data is intact
python -c "from src.data import load_all_splits, load_external_benchmark; print({k:len(v) for k,v in load_all_splits().items()}); print('external:', len(load_external_benchmark()))"
# Expected: {'train': 159571, 'val': 34193, 'test': 34194, 'external': 25306}; external: 25306

# 2. Print the canonical description
python -m src.pipeline

# 3. Re-run the deployed pipeline on the frozen benchmark
python scripts/evaluation/analyze_e8p9_errors.py
# Reads data/canonical/external_benchmark.parquet
# Writes outputs/eval/e8p9_per_item.parquet + outputs/eval/e8p9_error_analysis.txt
# Expected: 25,306 items scored, confusion TN=20361, FP=410, FN=381, TP=4154
```
