# Model Artifacts

The deployed ScamRadar+ model represents the final state of a single core modeling pipeline (word + character TF-IDF · 25 numerical features · StandardScaler · Logistic Regression · threshold 0.59) that was iteratively improved and retrained through successive data-quality, feature, augmentation, and decision-layer improvements. The internal `e7_p1_full_e8p9` identifier is the repository-level reference for the final iteration; see [`../SOURCE_OF_TRUTH.md::Development journey`](../SOURCE_OF_TRUTH.md) for the full sequence.

Not every file here is loaded in production. This README says which one is.

## Deployed

| Path | Role |
|---|---|
| **`e7_p1_variants/e7_p1_full_e8p9.joblib`** | **The deployed model.** Loaded by `api/main.py` via `src/inference.py` → `src/e5_inference.load_e5_pipeline()`. Trained on the 283,501-row E8-P9 corpus. Bundles the fitted word-TF-IDF + char-TF-IDF vectorizers, the `StandardScaler` for the 25 numerical features, the Logistic Regression head, and the operating threshold (0.59). Wrapped at inference time by the 19-rule engine in `src/rule_engine/`. |

## Fallback + calibration/threshold provenance

| Path | Role |
|---|---|
| `e5_bundle.joblib` | E5 text-only fallback bundle. Only loaded if `SCAMRADAR_LOCAL_MODEL` is explicitly set to a non-`e7_p1_*` value. Not the deployed model. |
| `e5_metadata.json` | Frozen E4 hyperparameters + E5 calibration report + operating threshold. Read by `scripts/evaluation/build_evaluation_summary.py`. |
| `e5_threshold_sweep.json` | Full precision / recall / F1 grid over thresholds used to select 0.59 at E5. |

## What is intentionally NOT in this repository

Earlier model variants and rejected E7-P1 ablations are intentionally not shipped — they are external evidence of the modeling decision journey. Only the artifacts listed above are needed to run the deployed pipeline.

## Where to look next

- Canonical constants (paths, hyperparameters, threshold, rule counts): [`../src/canonical.py`](../src/canonical.py).
- End-to-end pipeline description: [`../src/pipeline.py`](../src/pipeline.py) (or `python -m src.pipeline`).
- Deployment: [`../api/main.py`](../api/main.py) + [`../Dockerfile`](../Dockerfile).
- Full lineage: [`../SOURCE_OF_TRUTH.md`](../SOURCE_OF_TRUTH.md).
