# ScamRadar+ Data Pipeline — Technical Design Document

Status: **v2.0** (hardened data-first framework)
Author: ScamRadar+ project
Scope: Offline data-collection + audit + split pipeline. Produces the training splits consumed by `scripts/training/` in the parent repo.

Change summary vs. v1.0:
- Reframed the entire pipeline as **data-first**: no model training may begin until the
  dataset audit is explicitly approved.
- Formalised the **mandatory dataset audit** and its required metrics.
- Tightened the **synthetic data cap** from 40% → 25% (per-class default), with an
  evidence-based escape hatch.
- Replaced the single external benchmark with **multiple independent external
  benchmarks**, each frozen and each scored once.
- Added an explicit **promotion policy**: no baseline is replaced on a single-benchmark
  win.
- Added the **automatic error-analysis report** contract.
- Elevated **scientific integrity** to a first-class section with prohibited practices.
- Added the **"Before Training" approval package** the human must sign off on.

---

## 0. Guiding Principle

> **Scientific integrity outranks headline metrics.**
> Data quality outranks model complexity.
> Real data outranks synthetic data.
> Multi-benchmark consistency outranks single-benchmark wins.

Any conflict between these principles and a shiny result is resolved in favour of the
principle. Negative results are recorded and kept.

---

## 1. Data-First Workflow (mandatory ordering)

The project is data-driven, not model-driven. Stages execute strictly in this order.
Each arrow is a hard gate — the next stage refuses to run until the previous stage's
artifact and, where noted, human approval are present.

```
Dataset acquisition
        ↓
Dataset cleaning  (dedup, near-dedup, normalisation, provenance)
        ↓
Dataset audit  (automated report — see §5)
        ↓
Dataset approval  ← HUMAN GATE. Nothing downstream may run without it.
        ↓
Feature engineering
        ↓
Model experiments  (bake-off under identical folds/seeds)
        ↓
Hyperparameter optimisation
        ↓
Evaluation  (internal held-out + every external benchmark)
        ↓
Error analysis  (automatic, per experiment)
```

Enforcement: `data/APPROVAL.json` is written only by `python -m scamradar
approve-dataset` after a human confirms the audit. `ablate`, `bakeoff`, `tune`, `fit`,
and any evaluation command refuse to run without it, and re-check the audit's dataset
hash to make sure the data hasn't drifted since approval.

---

## 2. Overall Architecture

A fully reproducible, versioned, offline ML research pipeline. Each stage reads only
versioned artifacts from the previous stage and writes versioned artifacts plus a JSON
report. Nothing is ever overwritten (append-only experiment registry).

```
acquire → clean → audit → (APPROVAL) → split → features/train/tune → evaluate → error-analysis
(raw/)   (interim/)  (reports/)         (processed/ + external_benchmark/*)   (experiments/ + reports/)
```

Architectural invariants:

1. **Every external benchmark directory is write-once.** Each is carved out by *source*
   (not random rows), guarded by a lock file, and its evaluation CLI refuses to score
   it twice unless `--force-i-understand` is passed. Every access is logged.
2. **Cluster-aware splitting.** Near-duplicate clusters (MinHash/LSH over char 5-grams)
   are assigned atomically to exactly one split so no paraphrase leaks.
3. **Provenance on every row.** Every sample carries `source`, `license`, `category`,
   `platform`, `language`, `era`, `is_synthetic`, `acquired_at`, and a stable
   `sample_id` (SHA-1 of normalised text).
4. **Experiments are data.** Every run appends one JSON record (objective, hypothesis,
   dataset version/hash, config, metrics, per-benchmark results, conclusion) to
   `experiments/registry.jsonl`. Reproducing a run = re-executing with its recorded
   config and seed.

---

## 3. Dataset Acquisition Strategy

Kaggle is excluded entirely. Sources are declared in `src/scamradar/sources.py` as a
registry with URL, license, category mapping, platform, era, and parser.

**Scam / phishing (real, documented licenses):**
- *Phishing Email Curated Datasets* (Champa, Rabbi & Zibran 2024, Zenodo, CC BY 4.0)
- *Nazario phishing corpus* (research use)
- *SMS Spam Collection* (Almeida & Gómez Hidalgo, CC BY 4.0) — **capped, `era=legacy`**
- *Mendeley "SMS Phishing Dataset"* (Mishra & Soni 2022, CC BY 4.0) — modern smishing
- *EMSCAD — Employment Scam Aegean Dataset* — recruitment scams
- *CLAIR fraud email collection* — advance-fee / romance-adjacent
- Curated Zenodo/Figshare crypto & investment scam sets (permissive licenses only)

**Legitimate (real):**
- *Enron email corpus* — workplace email, `era=legacy`
- *SpamAssassin easy/hard ham* (Apache 2.0)
- EMSCAD legitimate job postings
- Public customer-support corpora (permissive licenses only)

**Coverage gaps → synthetic** (see §7). Every acquired row is tagged with `source`,
`license`, `category`, `platform`, `language`, `era`, `is_synthetic`.

Rationale: modern coverage comes from 2020s sources + controlled synthesis; legacy
corpora are retained only for volume/regularisation with capped weight.

---

## 4. Dataset Cleaning

Deterministic, versioned, all thresholds in `configs/config.yaml`:

1. Unicode NFKC normalisation, whitespace collapse, boilerplate header stripping.
2. **Exact dedup**: SHA-1 over aggressively normalised text (case-folded, digits→0,
   URLs→token). Duplicate count reported.
3. **Near-dup clustering**: MinHash (128 perms) over char 5-gram shingles + LSH banding
   (32×4), union-find → cluster IDs; Jaccard ≥ 0.7 ⇒ same cluster. Near-dup count and
   cluster count reported.
4. Language ID (fastText/lid) recorded per row.
5. Output: `data/interim/clean.parquet` + `reports/clean_stats.json`.

Cleaning never *drops* data silently — every removal is counted and shown in the audit.

---

## 5. Mandatory Dataset Audit (approval gate)

Trigger: `python -m scamradar audit` runs automatically after cleaning and writes
`reports/dataset_audit.json` + a human-readable `reports/dataset_audit.md`. The audit
**must** report:

- Total dataset size
- Number of scam samples
- Number of legitimate samples
- Class balance (scam share, per-source share)
- Number of exact duplicates removed
- Number of near duplicates removed
- Number of clusters (total, singleton, largest cluster size, top-10 clusters)
- Samples per category (fraud sub-category taxonomy)
- Samples per source
- Samples per year (where the source records year)
- Samples per platform (SMS, Email, Discord, Reddit, WhatsApp, Marketplace, …)
- **Real vs synthetic ratio** — overall AND per-category
- Language distribution
- Average message length (+ p5/p50/p95)
- URL frequency (% messages containing ≥ 1 URL)
- Attachment frequency (where available)
- **Missing categories** — any expected category with < N samples (default N=200)
  is flagged as a red block in the summary

The audit also produces:
- `dataset_hash`: SHA-256 of the sorted `sample_id` list. Approval is bound to this
  hash.
- `red_flags[]`: any of {class balance outside \[0.15, 0.85\], synthetic share > 25%
  in any category unless justified, single source > 40% of a class, missing category,
  cluster > 5% of dataset, non-English share unexpected}.

**Gate**: training commands (`ablate`, `bakeoff`, `tune`, `fit`, `eval`, `external`)
call `require_dataset_approval()`, which:
1. Refuses to run if `data/APPROVAL.json` is missing.
2. Refuses to run if the approval's `dataset_hash` no longer matches the current
   dataset (i.e., the data changed after approval).
3. Refuses to run if `red_flags` is non-empty and the approval does not explicitly
   list the accepted red flags.

The command `python -m scamradar approve-dataset` writes `APPROVAL.json` after an
interactive confirmation showing the audit summary and any red flags. This is the
**only** way past the gate — there is no `--skip-approval` flag.

---

## 6. Dataset Quality Requirements

Quality outranks size. The audit + split pipeline enforces:

- Remove exact duplicates (§4).
- Remove near duplicates (§4).
- Prevent data leakage — cluster-aware splits + post-split assertions (§2, §11).
- Cluster similar messages so paraphrases can never cross splits.
- **Category floor**: every category has ≥ N samples (default 200); shortfall = red flag.
- **Source-dominance cap**: no single source may exceed 40% of either the scam class
  or the legitimate class post-cleaning.
- **Era cap**: legacy (`era=legacy`) sources are down-weighted; a legacy source cannot
  exceed 30% of its category unless no modern equivalent exists (in which case a
  written note in `docs/notes/` records the exception).
- **Synthetic cap**: see §7.

None of these caps are enforced by silently discarding data — they raise red flags in
the audit, and the human decides how to fix them (add real data, cap sample weights,
etc.).

---

## 7. Synthetic Data Policy

Synthetic data exists **only to fill genuine coverage gaps** where no ethical public
corpus exists (e.g., current-phrasing marketplace/delivery smishing, romance long-cons,
Discord/gaming ham, BEC/CEO fraud, giveaway/refund scams).

Rules:

1. **Real first.** For any category with a viable real corpus, synthetic augmentation
   requires written justification in `docs/notes/`.
2. **Default cap: 25%** of the final training corpus, and 25% per category. A higher
   share is permitted only if a controlled experiment demonstrates that raising the
   cap improves performance on **independent external benchmarks** (not internal
   held-out). The experiment, the ratio tested, and the benchmark deltas are recorded
   in the experiment registry.
3. **Diversity**: synthetic generation must vary wording, grammar, writing style, tone,
   message length, scam strategy, geography, and platform. Prompts and personas live
   in `scripts/gen_synthetic_prompts.md`; generation happens in many small batches
   with different persona seeds.
4. **Provenance forever**: every row is labelled `is_synthetic ∈ {REAL, SYNTHETIC}`
   (stored as a boolean plus a human-readable string column). The `generation_run_id`
   is retained so any batch can be quarantined post-hoc.
5. **Never in external benchmarks.** All external benchmarks are real-only (§8).
6. **Synthetic acceptance policy (multi-criteria).** A synthetic batch is accepted
   when **all** of the following hold. The probe classifier is a **diagnostic
   tool**, not a hard pass/fail gate — see rule 7 below.

   a. **No obvious stylistic artifacts.** The named-artifact check (probe.py's
      `artifact_check`) reports per-category rates for emoji, em-dash, curly
      apostrophes, mismatched URL frequency vs the nearest real neighbor, and
      mismatched length distribution. Each artifact rate must be within a small
      tolerance of the nearest-neighbor real corpus (default: emoji within
      ±0.01, em-dash within ±0.01, URL rate within ±0.10, length p50 within
      ±30% of nearest-neighbor real).
   b. **Distributional agreement** with real corpus on measurable properties:
      length distribution, URL rate, emoji rate, punctuation profile,
      first-person density. These are reported by the batch manifest and
      compared to `data/interim/clean.parquet` real-scam statistics.
   c. **Complete provenance.** Every row carries `is_synthetic=True`,
      `batch_id`, `template_id`, `persona`, `geography`, `register`, and
      `platform`; the batch has a manifest JSON with generator config, seed,
      target/achieved statistics.
   d. **Excluded from every external benchmark.** Enforced at source level by
      `benchmark_eligible=False` in `sources.py` and asserted at split time.
   e. **Synthetic proportion within configured limits.** DESIGN §7 rule 2:
      25% per category if real data exists in that category; if the category
      is synthetic-only, requires a written note in `docs/notes/`.
   f. **Downstream benefit, not harm.** *Most importantly*, adding synthetic
      data must not reduce performance on independent external benchmarks
      compared to a baseline trained without it. This is measured empirically
      after each batch by re-running E1 (or the current baseline) with and
      without the batch and comparing external-benchmark PR-AUC / per-category
      recall. If the delta is negative and CI-significant on any benchmark,
      the batch is quarantined and regenerated.

7. **Detectability probe as diagnostic.** A char-TFIDF + LogReg probe still
   runs after every batch and is written to `reports/probe_<exp_id>.md`. Its
   role is **explanatory**, not gating: it names which n-grams the model uses
   to separate real from synthetic, so we can decide whether the separation
   reflects (a) cheap artifacts (fix them and regenerate — this is what v1 →
   v2b did) or (b) legitimate higher-order distributional differences
   inherent to template-based generation (accepted as a known limitation).
   The probe's AUC is reported alongside its top-tell n-grams; a high AUC
   alone does not block acceptance if the rules 6.a–6.f are met.

---

## 8. Multiple Independent External Benchmarks

A single benchmark is one opinion. The system therefore maintains **several
independent, frozen, real-only** benchmarks covering different domains:

| ID | Domain | Notes |
|---|---|---|
| `B_phish_modern` | Modern phishing (2022+) | Champa/Rabbi/Zibran holdouts, real only |
| `B_bec` | Business email compromise / CEO fraud | curated modern BEC set |
| `B_sms` | SMS smishing | Mendeley SMS holdouts, real only |
| `B_recruit` | Recruitment scams vs real job ads | EMSCAD holdouts |
| `B_marketplace` | Marketplace / delivery scams | curated modern set |
| `B_banking` | Bank-impersonation phishing | curated modern set |
| `B_social_eng` | Social-engineering long-form | romance / advance-fee holdouts |
| `B_ham` | General legitimate conversations | SpamAssassin ham + customer-support holdouts |

Rules:

- Each benchmark is carved out **by source**, not by random rows.
- Each benchmark is written once to `data/external_benchmark/<ID>/` with a `LOCK.json`.
- **No tuning may touch any benchmark** — no threshold selection, no HPO, no early
  stopping. The evaluation CLI refuses a second scoring per benchmark per model
  (bypass requires `--force-i-understand`, and every access is logged).
- Benchmarks that don't yet have enough real data are marked `status: "pending"` and
  do not participate in promotion decisions until they reach their floor.

---

## 9. Feature Engineering Plan

Candidate representations (each an ablation vs. the E1 word-TF-IDF baseline):

- **F1** Word TF-IDF (1–2 grams, sublinear, min_df tuned)
- **F2** Char TF-IDF (3–5 grams) — robust to obfuscation ("fr3e g1ft")
- **F3** F1 ∪ F2
- **F4** Sentence embeddings (multilingual MiniLM / E5) — optional, if compute allows
- **F5** Handcrafted security features (~40 dims): URL count, shorteners, IP-literal
  URLs, punycode, TLD risk class, urgency lexicon hits, money/crypto symbols, phone
  patterns, caps ratio, digit ratio, exclamation density,
  "verify/suspend/account" lexicon, greeting anonymity, length stats
- **F6** Best text rep ∪ F5

A feature set is kept only if it beats the incumbent on validation PR-AUC with a
bootstrap 95% CI excluding zero improvement.

---

## 10. Model Comparison Strategy

Under identical folds, identical features, identical seeds: Logistic Regression,
LinearSVC (+calibration), Random Forest, Gradient Boosting, XGBoost, LightGBM, CatBoost;
transformer fine-tune (DistilRoBERTa / multilingual MiniLM) only if the classical
ceiling looks beatable and compute allows.

Selection metric: PR-AUC (primary), ROC-AUC + F1@tuned-threshold (secondary). Class
imbalance is handled by class weights, not by resampling the test data.

---

## 11. Hyperparameter Optimization & Splits

Optuna TPE, budgeted per model family. Objective = mean PR-AUC over 5-fold stratified
**cluster-grouped** CV on train only. Then:

1. **Probability calibration** (Platt vs isotonic; choice made on validation).
2. **Threshold optimisation** on validation only, reporting a max-F1 threshold *and* a
   precision-floor operating point.
3. **External benchmarks are never touched during tuning.**

Cluster-aware split assignments (see §2) are locked by a seed and recorded per
experiment; splits themselves are content-hashed.

---

## 12. Evaluation & Promotion Criteria

A candidate model is **never** promoted because it wins on a single benchmark.
Promotion requires a **broad, consistent, and honestly-reported** win.

For every candidate, `eval` records:

- Internal held-out set metrics (Accuracy, P, R, F1, ROC-AUC, PR-AUC, bootstrap CIs)
- Per-category metrics
- Per-source metrics
- Per-platform metrics
- Calibration quality (reliability curve + expected calibration error)
- False-positive rate at operating threshold
- False-negative rate at operating threshold
- Threshold sensitivity sweep
- Inference latency (ms/sample, batch-size-1 and batch-32)
- Peak memory usage during inference
- Serialised model size on disk

Then it scores **every ready external benchmark** exactly once and aggregates.

**Promotion policy (`experiments/promotion.py`):** a new model replaces the current
baseline only if all of the following hold:

1. It improves the **primary** metric (mean external PR-AUC across ready benchmarks)
   by more than the bootstrap noise floor.
2. It does not regress on any single external benchmark by more than a small tolerance
   (default: PR-AUC drop > 0.01 with 95% CI excluding zero blocks promotion).
3. It does not regress on any category by more than the tolerance.
4. Its calibration ECE is not worse by more than 0.02.
5. Its latency and memory are within the deployment envelope (configurable).

If a candidate improves one benchmark but regresses elsewhere, the failing benchmarks
and categories are named in `reports/promotion_decision.json` and the baseline stays.
Promotion overrides require a written justification stored alongside the decision.

---

## 13. Automatic Error Analysis

Every experiment automatically writes `reports/error_analysis_<exp_id>.md` +
`.json` containing:

- All false positives (text, source, category, platform, probability, top contributing
  features via linear weights / SHAP)
- All false negatives (same fields)
- Confidence-score distributions (per class, per category)
- Category breakdown of FP/FN
- Source breakdown of FP/FN
- Common failure patterns (top n-grams / URL patterns overrepresented in errors)
- **Largest regressions vs previous best** (per category, per source, per benchmark)
- **Largest improvements vs previous best**
- **Recommendation section** — always exactly one of:
  - *collect additional data* (which category/source, evidence: shortage + high FN rate)
  - *improve feature engineering* (which patterns errors share, evidence: n-gram lift)
  - *change model architecture* (evidence: capacity / non-linearity signal)
  - *probability calibration* (evidence: reliability diagram deviation)
  - *threshold optimisation* (evidence: PR curve shape near operating point)

Every recommendation cites the specific evidence used. Recommendations that repeat
across three experiments become "hard tickets" in the registry.

---

## 14. Experiment Registry

`experiments/registry.jsonl` is **append-only**. Every experiment records:

- `experiment_id`, `timestamp_utc`, `git_or_content_hash`
- `objective`, `hypothesis`
- `dataset_version`, `dataset_hash` (must match the approved audit)
- `preprocessing_version`
- `feature_set` (F1/…/F6, params)
- `model`, `hyperparameters`
- `calibration_method`, `thresholds` (F1, precision-floor)
- Internal evaluation metrics
- **Per-benchmark results** (one entry per external benchmark that was ready)
- Per-category and per-source metrics
- Latency / memory / model-size
- Conclusion (`kept`, `discarded`, `superseded_by`)
- Path to `error_analysis_<exp_id>.md`

Nothing is overwritten. Every run is reproducible from its record + seed.

---

## 15. Scientific Integrity

Scientific integrity has higher priority than achieving larger numbers.

**Prohibited (blocked mechanically where possible, reviewed manually otherwise):**

- Data leakage across splits (asserted at split time — hard failure).
- Duplicate contamination (asserted at split time — hard failure).
- Benchmark contamination — no benchmark row may share a cluster with any training row
  (asserted).
- Threshold tuning on external benchmarks — the evaluation code path for external
  benchmarks does not accept a `threshold` argument; it always uses the frozen
  bundle's thresholds.
- Manually inspecting external-benchmark errors before promotion — external error
  dumps are gated behind `--after-promotion` and access is logged.
- Silent data changes after approval — dataset-hash check rejects the run.

Negative results are recorded honestly. A discarded experiment stays in the registry
with `conclusion: "discarded"` and a reason. Experiments that seemed to work but were
later invalidated get a `superseded_by` pointer, never a deletion.

---

## 16. Before Training — Approval Package

Before training the first model, the human is presented with — and must approve — five
artifacts:

1. **`reports/dataset_audit.md`** — the complete dataset audit (§5).
2. **`reports/benchmark_plan.md`** — the proposed benchmark structure (§8): which
   benchmarks exist, which are `ready` vs `pending`, source-carveout definitions,
   size targets.
3. **`reports/model_comparison_plan.md`** — the model bake-off matrix (§10): model
   families, feature sets, CV protocol, seeds, budget.
4. **`reports/feature_engineering_plan.md`** — feature-set definitions and ablation
   order (§9).
5. **`reports/experiment_roadmap.md`** — the ordered experiment roadmap (§17) with
   go/no-go criteria at each step.

`approve-dataset` prints a checklist confirming all five artifacts exist and shows
their content hashes; approval commits those hashes so any post-approval edit
invalidates the gate and requires re-approval.

---

## 17. Experiment Roadmap

- **E0** acquire → clean → audit → **APPROVAL** (§16 package)
- **E1** baseline: word TF-IDF + LogisticRegression (honest yardstick)
- **E2.x** feature ablations (F1–F6)
- **E3.x** model bake-off on winning features
- **E4** HPO on top-2 models
- **E5** calibration + threshold study
- **E6** error-analysis-driven data/feature fixes (iterate until Δ < CI noise)
- **E7** freeze → one-shot **per-benchmark** external evaluations → promotion decision
  → final report

Stopping rule: iterate E6 until two consecutive iterations improve validation PR-AUC
by less than the bootstrap noise floor, and the promotion policy (§12) does not admit
a new baseline.

---

## 18. Deployment Roadmap (deferred)

Only after E7 and a passing promotion decision: export calibrated sklearn/ONNX
artifact + feature pipeline, FastAPI wrapper, drift monitoring plan. Not designed
further here on purpose.

---

## 19. Risks & Expected Challenges

| Risk | Mitigation |
|---|---|
| Public "modern scam" text is scarce | controlled synthesis with provenance + 25% cap; real-only benchmarks |
| Legacy corpora inflate metrics | `era` tags, per-era weights, per-source evaluation exposes it |
| Cross-source near-duplicates (mirrored corpora) | cross-source MinHash dedup before splitting |
| Synthetic style being trivially learnable | REAL-vs-SYNTHETIC probe per category; regenerate if AUC > 0.75 |
| Benchmark contamination temptation | write-once locks + logged access + no threshold argument on external eval path |
| Overfitting to one platform (email) | platform tags + per-platform recall reporting + separate SMS/BEC benchmarks |
| Single-benchmark cherry-picking | promotion policy requires broad, non-regressive wins |
| Data silently changing after approval | dataset-hash bound to approval; mismatch blocks training |

---

## 20. Decision Justifications (summary)

- *Data-first, gated by human approval*: mechanical prevention beats disciplined
  restraint; the gate makes "start training" a deliberate act.
- *PR-AUC primary*: scams are the minority class in reality; ROC-AUC alone flatters.
- *Cluster-aware splits*: the single biggest source of inflated published
  spam-detection numbers is paraphrase leakage; this kills it mechanically.
- *Multiple frozen benchmarks*: any single benchmark can be gamed or drift; a panel is
  much harder to Goodhart.
- *Promotion by consistency, not headline*: prevents accidental regressions in the
  categories users actually care about.
- *Classical-first, transformer-if-justified*: keeps the honest baseline cheap to
  reproduce.
- *25% synthetic cap*: real data has priority; escape hatch requires evidence on
  independent benchmarks, not internal metrics.
- *Append-only registry*: every claim must be reproducible from a record and a seed.
