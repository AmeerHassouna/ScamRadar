# ScamRadar+ 2.0 — Research Pipeline

State-of-the-art, scientifically defensible scam-message detection.
**No Kaggle anywhere.** Every source has a documented URL + license (`src/scamradar/sources.py`).

Read `docs/DESIGN.md` first — it is the full technical design document (v2.0, data-first
framework with a mandatory dataset-audit approval gate before any training).

## Setup in VS Code

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Select `.venv` as the Python interpreter (Ctrl/Cmd+Shift+P → "Python: Select Interpreter").

## 1) Sanity check (60 seconds, toy data)

```bash
python -m scamradar smoke
rm -rf data experiments reports/*.json reports/figures   # clean up toy artifacts
```

## 2) Real run — data-first, gated

The workflow is strict: **no model training runs until the dataset audit is approved.**

```bash
# a) DATA — acquire + clean
python -m scamradar acquire       # download / ingest all real sources; drop manual sources into data/raw/
python -m scamradar clean         # exact + near-dup dedup, clustering, provenance

# b) AUDIT — produces reports/dataset_audit.{json,md}
python -m scamradar audit

# c) APPROVAL GATE — human review + explicit approval
#    Prints the audit summary + red flags and asks for confirmation.
#    Writes data/APPROVAL.json (binds the current dataset_hash).
python -m scamradar approve-dataset

# d) SPLIT — cluster-aware; freezes each external benchmark write-once
python -m scamradar split

# e) EXPERIMENTS  (all refuse to run without APPROVAL.json)
python -m scamradar ablate                              # E2: feature sets F1..F6
python -m scamradar bakeoff --features F6               # E3: all installed model families
python -m scamradar tune --model lightgbm --trials 60   # E4: Optuna HPO (cluster-grouped CV)
python -m scamradar fit  --model lightgbm --features F6 \
       --params-json experiments/hpo_lightgbm_F6.json   # calibrate + thresholds (val only)

# f) INTERNAL EVAL — full metric suite + auto error-analysis report
python -m scamradar eval --bundle experiments/final_lightgbm_F6.joblib --split test

# g) EXTERNAL BENCHMARKS — one-shot per benchmark. Each locks itself.
#    Runs every "ready" benchmark and writes reports/promotion_decision.json.
python -m scamradar external --bundle experiments/final_lightgbm_F6.joblib
```

## Where things land

| Path | Contents |
|---|---|
| `data/raw/` | canonical dataset + downloaded/manual sources |
| `data/interim/clean.parquet` | deduped, clustered, provenance-tagged |
| `data/APPROVAL.json` | signed approval (binds `dataset_hash`) — created by `approve-dataset` |
| `data/processed/` | train/val/test parquet (cluster-aware, leak-checked) |
| `data/external_benchmark/<ID>/` | frozen one-shot benchmarks + `LOCK.json` access log (one per benchmark, see DESIGN §8) |
| `reports/dataset_audit.{json,md}` | mandatory audit report (DESIGN §5) |
| `reports/benchmark_plan.md` | which benchmarks exist and their status |
| `reports/model_comparison_plan.md` | model bake-off matrix |
| `reports/feature_engineering_plan.md` | feature-set definitions and ablation order |
| `reports/experiment_roadmap.md` | ordered roadmap with go/no-go criteria |
| `reports/eval_*.json` + `reports/error_analysis_<exp_id>.md` | per-experiment eval + auto error analysis |
| `reports/promotion_decision.json` | whether a candidate replaces the current baseline |
| `experiments/registry.jsonl` | append-only experiment history |

## Integrity guarantees (enforced by code, not discipline)

- **No training without approval.** `ablate`/`bakeoff`/`tune`/`fit`/`eval`/`external` refuse to run
  unless `data/APPROVAL.json` exists and its `dataset_hash` still matches the current dataset.
- **Cluster-aware splits.** Exact + near-duplicate leakage between splits ⇒ hard assertion failure.
- **Real-only external benchmarks.** Synthetic samples are code-barred from every benchmark.
- **Per-benchmark write-once locks.** Each external benchmark refuses a second scoring per model.
- **No threshold arg on external eval.** External evaluation always uses the bundle's frozen thresholds.
- **Multi-benchmark promotion policy.** A new baseline requires broad, non-regressive improvement (DESIGN §12).
- **Append-only registry.** Every experiment record carries dataset content hashes + seed ⇒ reproducible.
- **Provenance forever.** Every row is `REAL` or `SYNTHETIC` with source, license, era, platform, language.
