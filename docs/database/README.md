# ScamRadar+ Relational Database

The project uses a small three-table relational schema (SQLite) to
persist the corpus that feeds the ML pipeline. There are **two databases**
representing the two ends of the iterative development of the same
core ScamRadar+ modeling pipeline:

| # | Database | Path | Rows | Role |
|---|---|---|---:|---|
| 1 | **Initial baseline** | `data/initial_db/scamradar_initial_253264.db` | **253,264** | The approved clean corpus after cleaning and splitting. Represents the state used for the initial modeling round of the ScamRadar+ pipeline. Contains 14 sources (13 real-world + the `synthetic_v1` seed), including `spamassassin_ham`. `MessageFeatures` is empty at this stage — the 25 engineered numerical features were introduced later as part of the iterative development. |
| 2 | **Final ScamRadar+ pipeline** (internal ID `E8-P9`) | `data/final_db/scamradar_e8p9.db` | **283,501** | The corpus that the deployed final ScamRadar+ classifier was trained on. Contains 17 sources: the 12 real-world sources that remained after the SpamAssassin removal iteration, a catch-all `e5_base_corpus` for legacy rows without a specific source label, and 4 new synthetic sources produced by the augmentation iterations. `MessageFeatures` is fully populated (283,501 rows, 25 numerical features per row). |

Both databases share the same schema — see [`schema.sql`](schema.sql) —
and the ERD is in [`erd.svg`](erd.svg).

## Why two databases?

The two-database story reflects the iterative-development narrative
recorded in `SOURCE_OF_TRUTH.md::Development journey`. The same core
ScamRadar+ modeling pipeline was iteratively improved and retrained
as new data, preprocessing, features, and decision-layer improvements
were introduced:

```
Initial 253,264-row approved clean corpus
      ↓
(materialized into the initial baseline database)
      ↓
Initial ScamRadar+ pipeline round + error analysis
      ↓
Iterative data / feature / preprocessing improvements
      ↓
Retraining after each meaningful update
      ↓
Further iterative improvements
      ↓
Final 283,501-row corpus
      ↓
(materialized into the final ScamRadar+ database)
```

Keeping both artifacts makes the "before/after" of the iterative-development
process inspectable side-by-side. Neither database is a different model
architecture — both are snapshots of the same schema populated at different
stages of the ScamRadar+ pipeline's iterative development.

## Why aren't the `.db` files committed?

Each SQLite database is around 200–250 MB, larger than GitHub's 100 MB
per-file limit for regular git objects. Both files are gitignored by the
blanket `data/*` rule. What **is** committed:

- [`schema.sql`](schema.sql) — the shared CREATE TABLE / CREATE INDEX definitions
- [`erd.svg`](erd.svg) — the entity-relationship diagram
- [`../../scripts/data_prep/build_databases.py`](../../scripts/data_prep/build_databases.py) — the build script that materialises either or both databases from the parquet inputs
- This README

## Rebuilding either database

The build script requires the canonical parquet inputs (`data/canonical/*.parquet`
and `data/interim/e7_p1_features_e8p9.parquet`). Those files are also
gitignored — they are preserved externally as defense/provenance material
alongside the parquets themselves. Given the parquets, both databases
rebuild deterministically:

```bash
# From the repository root
python scripts/data_prep/build_databases.py both     # builds initial + final
python scripts/data_prep/build_databases.py initial  # builds initial only
python scripts/data_prep/build_databases.py final    # builds final only
python scripts/data_prep/build_databases.py verify   # row-count assertion
```

Expected verification output:

```
[OK] scamradar_initial_253264.db          Message=253,264  (expected 253,264)
[OK] scamradar_e8p9.db                    Message=283,501  (expected 283,501)
```

The build script does not touch the model, the classifier bundle, or any
evaluation artifact.

## Table reference

### `Source`

Catalog of every acquisition source. Each `Message` row references
exactly one `Source` via `source_id`.

- `source_type IN ('real', 'synthetic')` distinguishes real-world
  corpora from the synthetic augmentations.
- `era` is `'legacy'` (typically pre-2010 corpora), `'modern'`
  (post-2015), or `'unknown'`.
- `license` records the redistributable-under license quoted from each
  upstream source.

### `Message`

One row per message in the corpus. `label ∈ {0, 1}` (0 = legit, 1 = scam).
`split ∈ {train, val, test, external}` follows the cluster-aware split
performed on the initial 253,264 corpus; the E8 iteration only adds
synthetic rows to `train`, but the cleanup removals (E8-P3, E8-P5) touch
all four splits. `cluster_id` is preserved from the cluster-aware split
step so that near-duplicate reasoning stays possible after ingestion.

Indexes: `idx_message_label`, `idx_message_source`, `idx_message_split`.

### `MessageFeatures`

One row per message, keyed by `message_id`. Contains the 25 engineered
numerical features produced by `src/rule_engine/numerical_features.py`
(4 tone + 5 URL + 3 phrase + 13 text-statistics).

In the initial DB this table is empty — the 25 features had not yet
been designed at that point in the project (they arrived at E7-P1).
In the final DB it is fully populated (283,501 rows).
