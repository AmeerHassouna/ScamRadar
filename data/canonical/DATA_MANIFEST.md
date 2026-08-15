# Canonical Data Manifest

Every file in this directory is part of the deployed E8-P9 lineage. All files are read-only from the codebase's perspective — none of the production code writes here.

Provenance: these files were originally produced by the project's upstream data-preparation workspace between Jul 31 and Aug 1 2026 and were subsequently incorporated into this repository under `data/canonical/`. The original acquisition / cleaning implementation is not shipped with the current repository, so the raw → clean transformation cannot be re-run from a clean clone; the identity + integrity of the raw snapshot and every downstream artifact is verifiable via the SHA-256 hashes recorded here and in `reports/raw_provenance.json`.

## Files

| File | Rows | Cols | Purpose | Provenance |
|---|---:|---:|---|---|
| `canonical_raw.parquet` | 280,730 | 10 | Union of all 14 documented sources. **See caveat below.** | Later re-acquisition (not the original raw snapshot). The **original raw snapshot** used to produce `clean.parquet` is preserved externally as defense/provenance material — 280,728 rows, SHA-256 `f0bef1515f7b02801c56cf3f215f25324c402666f727b6c7169ec1bdf90f9afd`, per-source counts matching `reports/acquisition_manifest.json` exactly across all 14 sources. The **in-repo** file (this row, 280,730) differs from that original by 2 rows in `sms_spam_collection` and is missing 546 of the 253,264 `clean.parquet` sample_ids, so it is **not** a valid preimage of `clean.parquet` — kept only for source-list traceability. Full verification metadata in `reports/raw_provenance.json`. |
| `clean.parquet` | **253,264** | 12 | Cleaned corpus post-dedup. **This is the frozen approved dataset.** | `scamradar clean` output; hash-locked in `APPROVAL.json`. |
| `train.parquet` | **159,571** | 12 | Training partition | `scamradar split` (cluster-aware stratified). |
| `val.parquet` | **34,193** | 12 | Validation partition (used for threshold selection at E5) | Same as above. |
| `test.parquet` | **34,194** | 12 | Held-out test partition | Same as above. |
| `external_benchmark.parquet` | **25,306** | 12 | Frozen external benchmark. This is what the deployed model's headline metrics are computed against. | Same as above; write-once via `external_benchmark_LOCK.json`. |
| `APPROVAL.json` | — | — | Signed approval gate for `clean.parquet` | Written by `scamradar approve-dataset`. Contains dataset_hash, audit_totals, class balance, accepted red flags. |
| `external_benchmark_LOCK.json` | — | — | Write-once seal for the external benchmark | `{"frozen": true, "rows": 25306, "evaluated": true, ...}` — matches the actual benchmark row count (25,306) and every deployed metric. |
| `reports/` | — | — | E-series stage reports from the upstream data-preparation workspace + this repository's raw-provenance record | `acquisition_manifest.json`, `dataset_audit.{json,md}`, `data_quality.json`, `e4_best.json`, `e4_e5_report.md`, `e5_final.json`, `e5_calibration.json`, `benchmark_plan.md`, `raw_provenance.json` (verifiable link from the original raw snapshot to `clean.parquet`). |

## Row count guarantees

`src/data.py` enforces these counts at load time (`_assert_rows`). If any of these files is mutated, load will raise `RuntimeError`. Re-verify against `APPROVAL.json::audit_totals` if that happens.

| Loader | Guaranteed row count |
|---|---:|
| `load_clean_corpus()` | 253,264 |
| `load_train()` | 159,571 |
| `load_val()` | 34,193 |
| `load_test()` | 34,194 |
| `load_external_benchmark()` | 25,306 |

## Class balance (from APPROVAL.json)

- Scam: 41,905 rows (16.55%)
- Legit: 211,359 rows (83.45%)

## Accepted red flags (documented in APPROVAL.json)

Three scam categories are synthetic-only (no real-world rows collected at time of approval):

- `bec_ceo_fraud`: 500 rows (all synthetic)
- `marketplace_delivery_scam`: 498 rows (all synthetic)
- `romance_scam`: 500 rows (all synthetic)

Two source distribution flags:

- `multiwoz_v22` dominates legit (49.5% > 40% ceiling)
- Modern-era scam share is 12.4% (< 30% floor)

These flags were accepted at approval time on the condition of written justification. The deployed pipeline was later augmented with E8-P2/P6/P8 synthetic batches that partially compensated for the modern-scam gap.

## Relational databases (materialised from the parquets)

Two SQLite databases share the schema at [`../../docs/database/schema.sql`](../../docs/database/schema.sql) and the ERD at [`../../docs/database/erd.svg`](../../docs/database/erd.svg):

| # | Database | Rows | Purpose |
|---|---|---:|---|
| 1 | `data/initial_db/scamradar_initial_253264.db` | **253,264** | Initial baseline DB — the approved clean corpus BEFORE any E8 augmentation. 14 sources (13 real-world + `synthetic_v1` seed), including `spamassassin_ham`. Represents the state used for the initial modeling round. |
| 2 | `data/final_db/scamradar_e8p9.db` | **283,501** | Final E8-P9 DB — the corpus that the deployed classifier was trained on. 17 sources: the 12 real-world sources that survived the E8-P3 removal of `spamassassin_ham`, a catch-all `e5_base_corpus` for legacy rows, and 4 new synthetic sources from E8-P2 / E8-P6 / E8-P8. |

Neither `.db` file ships in Git (each is 200–250 MB). Both are locally reproducible via `python scripts/data_prep/build_databases.py both`. See [`docs/database/README.md`](../../docs/database/README.md) for the full description.

## Downstream: iterative data refinement and augmentation

The 283,501-row final training corpus at `data/interim/e7_p1_features_e8p9.parquet` is the accumulated result of iteratively refining and augmenting the approved 253,264-row baseline. The same core ScamRadar+ modeling pipeline (word + character TF-IDF · 25 numerical features · StandardScaler · Logistic Regression · threshold 0.59) was retrained after each iteration. Internal `E8-P*` identifiers are the repository-level references for the individual iterations; the primary interpretation is the iteration name.

```
train + val + test + external_benchmark              253,264   [initial baseline DB]
  ┈┈┈ 25 numerical features computed by train_e7_p1.py ┈┈┈
+ Iteration 1 — Targeted Legit Augmentation                     E8-P2
    +1,978 synthetic modern-transactional legit    →  255,242
- Iteration 2 — SpamAssassin Removal                            E8-P3
    -2,238 legacy noise source dropped entirely    →  253,004
                (Rejected iteration — rolled back; see          E8-P4)
- Iteration 3 — Data Quality Cleanup                            E8-P5
    -802 (397 mailing-list + 207 spam-in-legit + 198 short)
                                                    →  252,202
+ Iteration 4 — Broad Legit Expansion                           E8-P6
    +15,521 net synthetic modern-brand legit       →  267,723
                (Diagnostic analysis — per-category recall;     E8-P7)
+ Iteration 5 — Contrastive Scam + Pair Augmentation            E8-P8
    +14,669 modern synthetic scam                  →  282,392
    +1,109 legit-pair adversarial twins            →  283,501   [final E8-P9 DB]
```

**Split composition inside the E8-P9 corpus** (differs from the base splits because the E8-P3/P5 cleanup filters touched all four partitions cross-cluster):

- train: 191,140 (159,571 base + 33,277 synthetic − 1,708 cleaned)
- val: 33,790 (34,193 base − 403 cleaned)
- test: 33,730 (34,194 base − 464 cleaned)
- external: 24,841 (25,306 base − 465 cleaned)

The classifier fits on `split=='train'` from the interim file (191,140 rows). **Final evaluation uses the untouched standalone `data/canonical/external_benchmark.parquet` (25,306 rows)**, not the 24,841-row external subset inside the interim file.

## Files intentionally NOT in this directory

- The Aug 10 DP regeneration files (a parallel rebuild that happened *after* E8-P9 was already trained and evaluated). Archived at `data/_archive/aug10_regeneration/`.
- The v1.7_augmentation isolated experiment. Stays at `data/v1.7_augmentation/` for now; not required by E8-P9.
- The E8 synthetic source files. Stay at `data/synthetic_legit/e8p{2,6}/` and `data/synthetic_scam/e8p8/` alongside their generation stats + merge reports.
