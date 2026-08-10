# ScamRadar+ — Thesis Defense Navigation Guide

One-page cheat-sheet mapping likely examiner questions to the file that answers them.
Keep this open on a second monitor during the defense.

---

## The three CRISP-DM notebooks (evidence layer)

| Phase | Notebook | What it demonstrates |
|---|---|---|
| Data Understanding | `notebooks/data_understanding.ipynb` | Every source acquired, per-source stats, corpus-level EDA, initial ERD |
| Data Preparation | `notebooks/data_preparation.ipynb` | Cleaning, audit + approval, cluster-aware split, 25-feature engineering, E8 synthetic chain, relational DB build, final ERD, SQL-driven EDA + statistical tests |
| Modeling | `notebooks/modeling.ipynb` | E5 → E7 → E8-P9 iteration history, feature-group ablation, E8-P9 confusion matrix / ROC / PR, error analysis, coefficient evolution across the E8 chain |

**Golden rule:** the notebook is the *presentation layer*. It orchestrates the production code and shows evidence. Every heavy step lives in a production script and is invoked via `cached_step` or `run_repo_script`.

---

## "How is X implemented?" → open this file

### Data Understanding

| Question | File |
|---|---|
| Which sources are used? | `data_pipeline/src/scamradar/sources.py` (`SOURCES` list) |
| How is a specific source parsed? | `data_pipeline/src/scamradar/acquire.py` (`PARSERS` dict) |
| What is the canonical schema? | `data_pipeline/src/scamradar/acquire.py::CANON_COLS` |
| How is `sample_id` computed? | `acquire.py::_sid` (SHA-1 of lowercased text) |

### Data Preparation

| Question | File |
|---|---|
| How is text cleaned + deduplicated? | `data_pipeline/src/scamradar/clean.py` (Unicode normalisation + exact-hash + MinHash+LSH) |
| What does the audit check? | `data_pipeline/src/scamradar/audit.py` |
| How is the approval gate enforced? | `data_pipeline/src/scamradar/approval.py::require_dataset_approval` |
| How is the split done (cluster-aware)? | `data_pipeline/src/scamradar/split.py` |
| How are the 25 features engineered? | `scripts/training/train_e7_p1.py::compute_all_numerical` + `src/_02_feature_engineering.py` |
| How is synthetic data generated (E8-P2 legit)? | `scripts/data_prep/gen_e8p2_synthetic_legit.py` |
| How is synthetic data generated (E8-P6 legit)? | `scripts/data_prep/gen_e8p6_synthetic_legit.py` |
| How is synthetic data generated (E8-P8 scam + pairs)? | `scripts/data_prep/gen_e8p8_synthetic_scam.py` |
| How is the final DB built? | Section 10-11 of the DP notebook (three-table schema, executemany inserts) |

### Modeling

| Question | File |
|---|---|
| What is E5? | The recipe frozen inside `scripts/training/train_e7_p1.py` (`E5_LR_PARAMS`, `E5_WORD_PARAMS`, `E5_CHAR_PARAMS`) — inherited from the scamradar2 project |
| How is a variant trained? | `scripts/training/train_e7_p1.py::train_variant` (lines 193-243) |
| How is the E8-P9 model trained? | `scripts/training/train_e8p9.py` (delegates to `train_variant`) |
| What is the feature ablation? | `scripts/training/train_e7_p1.py::VARIANTS` + `scripts/evaluation/eval_e7_p1.py::role_classification` |
| What is the E7-P3 proximity feature? | `scripts/training/train_e7_p3.py` + `scripts/data_prep/build_e7_p3_faiss.py` |
| How is a model evaluated (ablation + 3 benchmarks)? | `scripts/evaluation/eval_e7_p1.py` |
| How is E8-P9 error-analysed? | `scripts/evaluation/analyze_e8p9_errors.py` |
| What metrics are computed? | `eval_e7_p1.py::score` — accuracy, precision, recall, F1, ROC-AUC, PR-AUC, ECE, Brier, confusion matrix |

### Deployment / Inference

| Question | File |
|---|---|
| How does the API load the model? | `api/main.py` → `src/_09_prediction_pipeline.py::load_pipeline` |
| How is a single message predicted? | `src/_09_prediction_pipeline.py::predict_message` |
| Which model file does production load? | `models/e7_p1_variants/e7_p1_full_e8p9.joblib` (via `src/e5_inference.py`) |
| How is the rule engine wired in? | `src/rule_engine/` (imported by `_09_prediction_pipeline.py`) |
| Where is the English-only policy enforced? | `api/main.py` (langdetect check + 400 on non-English) |
| What are the deployment configs? | `Dockerfile`, `Procfile`, `railway.toml`, `requirements.txt`, `runtime.txt`, `config.py` |

---

## Key artifacts to point at

| Artifact | Path |
|---|---|
| DU output = DP input | `data_pipeline/data/raw/canonical.parquet` |
| DP output = Modeling input | `data/interim/e7_p1_features_e8p9.parquet` |
| Final relational DB | `data/final_db/scamradar_e8p9.db` |
| Final ERD image | `notebooks/erd.png` |
| Production model | `models/e7_p1_variants/e7_p1_full_e8p9.joblib` |
| E8-P9 per-item predictions on external | `outputs/eval/e8p9_per_item.parquet` (25,306 rows) |
| E8-P9 error analysis | `outputs/eval/e8p9_error_analysis.txt` |
| E7-P1 ablation research report | `outputs/e7_p1_report.md` |
| E8-chain coefficient snapshots | `outputs/coefs/e7_p1_full_{before_e8p2,after_e8p2..e8p9}.json` |

---

## Boundaries — what to say clearly

- **The old v1.x pipeline was discarded.** The current model was built from scratch in a separate `scamradar2` project, imported here as `data_pipeline/`, then iterated on through E7 (research) and E8 (production hardening).
- **The notebook is not the implementation.** Every heavy step (acquisition, cleaning, splitting, feature engineering, training, evaluation) is executed by production scripts. The notebook orchestrates them and displays evidence.
- **English-only input policy.** The API returns 400 on non-English input by explicit design; auto-translation was rejected by the professor. See `api/main.py`.

---

## Common examiner questions I have a direct answer for

| Question | Direct answer |
|---|---|
| "Why 25 features?" | E7-P1 ablation showed the "full" set beats every subset. Evidence: `outputs/e7_p1_report.md`, DP notebook §6 |
| "Why did you drop spamassassin_ham?" | E8-P3 iteration removed it after E8-P2 error analysis flagged it as a noise source. See `outputs/eval/e8p3_error_analysis.txt` |
| "Why isn't recall higher?" | 25,306-item external benchmark F1=0.9131. FP=410 (dominated by ham_email; 8.3% of that category). FN=381 (recruitment_scam at 51.85% miss rate is the weakest category). See `outputs/eval/e8p9_error_analysis.txt` |
| "How do I know there's no train/test leakage?" | Cluster-aware split (MinHash+LSH) keeps near-duplicate rows in the same partition. Implementation: `data_pipeline/src/scamradar/split.py` |
| "How do I know the synthetic data isn't a shortcut?" | E7-P3 proximity probe measures how close synthetic rows sit to real ones in the training corpus. See `scripts/training/train_e7_p3.py` |
| "Is the model production-deployed?" | Yes — served by `api/main.py` on Render/Vercel; browser extension at `extension/`; web front at `web/`. Deployment configs at repo root (`Dockerfile`, `Procfile`, `railway.toml`) |
