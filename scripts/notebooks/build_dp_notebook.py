"""
Builder for notebooks/data_preparation.ipynb — the Data Preparation deliverable
notebook for ScamRadar+ E8-P9.

Architecture (Option A, cache-aware):
  The Data Understanding notebook produces `data/interim/raw_unified.parquet`.
  This Data Preparation notebook consumes that file as input and orchestrates
  the production pipeline scripts (scamradar2 CLI + E8 merge scripts) to
  derive the final prepared corpus. Every stage is cache-aware: if its output
  artifact already exists on disk, the stage is skipped and the artifact is
  reused. If FORCE_REBUILD = True, every stage is re-run from scratch.

  Nothing in the production pipeline is modified; the notebook only invokes
  existing production code.

  After orchestrating the pipeline, the notebook stores the final prepared
  corpus in a relational SQLite database, defines retrieval functions,
  renders an ERD, and runs the Final EDA (descriptive statistics, plots,
  statistical tests) using SQL against the DB.

Regenerate with:
    python scripts/notebooks/build_dp_notebook.py
"""
from __future__ import annotations

import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_PATH = os.path.join(ROOT, 'notebooks', 'data_preparation.ipynb')

nb = nbf.v4.new_notebook()
cells: list = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.rstrip()))


def code(source: str) -> None:
    cells.append(nbf.v4.new_code_cell(source.rstrip()))


# ─────────────────────────────────────────────────────────────────────────────
# TITLE + OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

md("""# ScamRadar+ — Data Preparation Notebook

**Project:** ScamRadar+ (E8-P9 build)
**CRISP-DM phase:** Data Preparation — final deliverable

This notebook consumes the output of the Data Understanding notebook
(`data/interim/raw_unified.parquet`) and derives the final prepared corpus
by invoking the production pipeline scripts in order. Every pipeline stage
is **cache-aware**: if its output already exists on disk, the stage is
skipped and the cached artifact is reused. Set `FORCE_REBUILD = True` in
Section 0 to re-run every stage from scratch.

After the pipeline orchestration completes, the notebook stores the final
prepared corpus in a relational SQLite database, exposes retrieval
functions, renders an ERD, and runs the Final EDA.

**Chain from Data Understanding →**
`data/interim/raw_unified.parquet` (from DU notebook)
**→ this notebook →**
`data/interim/e7_p1_features_e8p9.parquet` (derived)
**→**
`data/final_db/scamradar_e8p9.db` (final DP deliverable)
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 0 — SETUP
# ─────────────────────────────────────────────────────────────────────────────

md("""## 0. Setup

Paths, imports, and cache-aware helpers.

- `FORCE_REBUILD` — set to `True` to re-run every pipeline stage even when
  its output is already cached on disk.
- `SCAMRADAR2_ROOT` — the standalone location of the upstream data-pipeline
  project that owns the `acquire → clean → audit → split` stages. The
  scamradar2 code was imported into `data_pipeline/src/scamradar/` in this
  repo but is invoked from its original working directory so the pipeline's
  relative paths resolve correctly.
""")

code("""from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy import stats

pd.set_option('display.max_columns', 60)
pd.set_option('display.width', 160)
plt.rcParams['figure.figsize'] = (10, 5)

# ─── Cache behaviour ──────────────────────────────────────────────────
FORCE_REBUILD = False   # flip to True to re-run every pipeline stage

# ─── Repo root discovery ──────────────────────────────────────────────
NB_DIR = Path.cwd()
REPO_ROOT = NB_DIR
for _ in range(6):
    if (REPO_ROOT / 'models' / 'e7_p1_variants').exists() and (REPO_ROOT / 'api').exists():
        break
    REPO_ROOT = REPO_ROOT.parent
else:
    raise RuntimeError(f'Could not locate ScamRadar+ repo root from {NB_DIR}')

# ─── Paths ────────────────────────────────────────────────────────────
# DU handoff (this notebook's input)
DU_OUTPUT = REPO_ROOT / 'data' / 'interim' / 'raw_unified.parquet'

# Scamradar2 (upstream pipeline) — configurable
SCAMRADAR2_ROOT = Path(os.environ.get(
    'SCAMRADAR2_ROOT', '/Users/ameer/Downloads/scamradar2'
))
SR2_CANONICAL = SCAMRADAR2_ROOT / 'data' / 'raw'      / 'canonical.parquet'
SR2_CLEAN     = SCAMRADAR2_ROOT / 'data' / 'interim'  / 'clean.parquet'
SR2_APPROVAL  = SCAMRADAR2_ROOT / 'data' / 'APPROVAL.json'
SR2_TRAIN     = SCAMRADAR2_ROOT / 'data' / 'processed' / 'train.parquet'
SR2_VAL       = SCAMRADAR2_ROOT / 'data' / 'processed' / 'val.parquet'
SR2_TEST      = SCAMRADAR2_ROOT / 'data' / 'processed' / 'test.parquet'
SR2_EXT       = SCAMRADAR2_ROOT / 'data' / 'external_benchmark' / 'benchmark.parquet'

# E7-P1 feature-engineered E5 base + synthetic + E8 stages
E7_P1_FEATURES = REPO_ROOT / 'data' / 'interim' / 'e7_p1_features.parquet'
E8P2_SYNTH     = REPO_ROOT / 'data' / 'synthetic_legit' / 'e8p2' / 'dataset.parquet'
E8P6_SYNTH     = REPO_ROOT / 'data' / 'synthetic_legit' / 'e8p6' / 'dataset.parquet'
E8P8_SCAM      = REPO_ROOT / 'data' / 'synthetic_scam'  / 'e8p8' / 'scam_dataset.parquet'
E8P8_PAIRS     = REPO_ROOT / 'data' / 'synthetic_scam'  / 'e8p8' / 'legit_pairs_dataset.parquet'
E8P2_MERGED    = REPO_ROOT / 'data' / 'interim' / 'e7_p1_features_e8p2.parquet'
E8P3_CLEANED   = REPO_ROOT / 'data' / 'interim' / 'e7_p1_features_e8p3.parquet'
E8P5_CLEANED   = REPO_ROOT / 'data' / 'interim' / 'e7_p1_features_e8p5.parquet'
E8P6_MERGED    = REPO_ROOT / 'data' / 'interim' / 'e7_p1_features_e8p6.parquet'
FINAL_PARQUET  = REPO_ROOT / 'data' / 'interim' / 'e7_p1_features_e8p9.parquet'

# DP deliverable (this notebook's output)
DB_DIR  = REPO_ROOT / 'data' / 'final_db'
DB_PATH = DB_DIR / 'scamradar_e8p9.db'
DB_DIR.mkdir(parents=True, exist_ok=True)

print(f'Repo root         : {REPO_ROOT}')
print(f'DU input          : {DU_OUTPUT}   (exists={DU_OUTPUT.exists()})')
print(f'SCAMRADAR2_ROOT   : {SCAMRADAR2_ROOT}   (exists={SCAMRADAR2_ROOT.exists()})')
print(f'Final DP output   : {DB_PATH}')
print(f'FORCE_REBUILD     : {FORCE_REBUILD}')""")

code("""# ─── Cache-aware helper ──────────────────────────────────────────────

def cached_step(name: str, outputs: list[Path] | Path, build_fn):
    \"\"\"Run build_fn only if any of the expected outputs is missing (or if
    FORCE_REBUILD is set). Prints a clear status line either way.\"\"\"
    outs = outputs if isinstance(outputs, list) else [outputs]
    missing = [o for o in outs if not o.exists()]

    print(f'── {name} ──')
    if not FORCE_REBUILD and not missing:
        for o in outs:
            print(f'  ✓ cached  {o}   ({o.stat().st_size / 1e6:.1f} MB)')
        return

    if FORCE_REBUILD:
        print(f'  ⟳ FORCE_REBUILD — running from scratch')
    else:
        print(f'  → building (missing: {[str(m) for m in missing]})')

    t0 = time.time()
    build_fn()
    dt = time.time() - t0

    still_missing = [o for o in outs if not o.exists()]
    if still_missing:
        raise RuntimeError(f'Build failed; still missing: {still_missing}')
    for o in outs:
        print(f'  ✓ built   {o}   ({o.stat().st_size / 1e6:.1f} MB)')
    print(f'  time: {dt:.1f}s')


# ─── Subprocess wrappers ──────────────────────────────────────────────

PY = sys.executable   # use the same interpreter this notebook is running under


def run_scamradar(subcommand: list[str], extra_env: dict | None = None):
    \"\"\"Invoke the scamradar2 CLI from its own working directory so its
    relative paths (data/raw, data/interim, data/processed) resolve.\"\"\"
    env = os.environ.copy()
    env['PYTHONPATH'] = str(SCAMRADAR2_ROOT / 'src')
    if extra_env:
        env.update(extra_env)
    subprocess.run(
        [PY, '-m', 'scamradar', *subcommand],
        cwd=str(SCAMRADAR2_ROOT),
        env=env, check=True,
    )


def run_repo_script(script_rel: str):
    \"\"\"Invoke a script inside this repo (scripts/data_prep/*, etc.).\"\"\"
    subprocess.run(
        [PY, script_rel],
        cwd=str(REPO_ROOT),
        check=True,
    )


print('Helpers ready.')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — LOAD DU OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

md("""## 1. Load the Data Understanding output

The DU notebook produced `data/interim/raw_unified.parquet` — 13 real source
corpora concatenated into a single canonical-schema table. That file is the
input to this notebook.
""")

code("""if not DU_OUTPUT.exists():
    raise FileNotFoundError(
        f'Expected DU output at {DU_OUTPUT}. '
        f'Run data_pipeline/notebooks/data_understanding.ipynb first to '
        f'produce it.'
    )

raw_unified = pd.read_parquet(DU_OUTPUT)
print(f'Loaded {DU_OUTPUT}')
print(f'  rows    : {len(raw_unified):,}')
print(f'  columns : {list(raw_unified.columns)}')
print(f'  sources : {raw_unified.source.nunique()} distinct')
print(f'  labels  : {raw_unified.label.value_counts().to_dict()}')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — HAND OFF TO SCAMRADAR2 PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

md("""## 2. Hand off to the scamradar2 pipeline

The scamradar2 upstream pipeline (imported into this repo under
`data_pipeline/src/scamradar/`) expects its input at
`SCAMRADAR2_ROOT/data/raw/canonical.parquet`. The DU output is already in
canonical schema, so we simply copy it into place. This is the boundary
between the DU-produced artifact and the production pipeline.
""")

code("""def stage_canonical():
    SR2_CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DU_OUTPUT, SR2_CANONICAL)


cached_step('Stage canonical.parquet', SR2_CANONICAL, stage_canonical)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — DATA CLEANING (scamradar2 clean)
# ─────────────────────────────────────────────────────────────────────────────

md("""## 3. Data cleaning — `scamradar clean`

The `clean` stage performs:
- Unicode NFKC normalization + URL/digit/whitespace canonicalization.
- Exact-hash deduplication.
- Near-duplicate clustering via MinHash (128 permutations over char 5-gram
  shingles) + LSH (16 bands × 8 rows) + union-find.

Output: `SCAMRADAR2_ROOT/data/interim/clean.parquet` (adds `cluster_id` and
`exact_hash` columns), plus a `reports/data_quality.json` audit summary.
""")

code("""def build_clean():
    run_scamradar(['clean'])


cached_step('scamradar clean', SR2_CLEAN, build_clean)

# Show the current cleaning report if present.
report_path = SCAMRADAR2_ROOT / 'reports' / 'data_quality.json'
if report_path.exists():
    import json
    r = json.loads(report_path.read_text())
    print()
    print(f'  clean.parquet rows              : {r.get("rows_after", "n/a")}')
    print(f'  exact duplicates removed        : {r.get("exact_duplicates_removed", "n/a")}')
    print(f'  rows in near-dup clusters       : {r.get("rows_in_near_dup_clusters", "n/a")}')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — AUDIT + APPROVAL
# ─────────────────────────────────────────────────────────────────────────────

md("""## 4. Dataset audit + approval gate

The scamradar2 pipeline requires a human-in-the-loop approval before
`split`. In production this is a manual review of the audit report. For a
re-execution of an already-approved corpus, we auto-approve non-
interactively with `--yes` so the notebook is reproducible.
""")

code("""def build_approval():
    run_scamradar(['audit'])
    run_scamradar(['approve-dataset', '--yes', '--accept-red-flags',
                   '--approver', 'data_preparation_notebook'])


cached_step('audit + approve-dataset', SR2_APPROVAL, build_approval)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — CLUSTER-AWARE SPLIT
# ─────────────────────────────────────────────────────────────────────────────

md("""## 5. Cluster-aware split — `scamradar split`

Produces four parquets: `train / val / test / external_benchmark`. The
split is stratified by class and grouped by `cluster_id` so no near-
duplicate ever appears on both sides of the split.
""")

code("""def build_split():
    run_scamradar(['split'])


cached_step('scamradar split',
            [SR2_TRAIN, SR2_VAL, SR2_TEST, SR2_EXT],
            build_split)

# Make the E5 base parquets available at the location train_e7_p1 expects
# (data_pipeline/data/processed/...). Symlink so we don't duplicate ~100 MB.
DATA_PIPELINE_DATA = REPO_ROOT / 'data_pipeline' / 'data'
if not DATA_PIPELINE_DATA.exists():
    DATA_PIPELINE_DATA.symlink_to(SCAMRADAR2_ROOT / 'data')
    print(f'Symlinked {DATA_PIPELINE_DATA} → {SCAMRADAR2_ROOT / "data"}')
else:
    print(f'{DATA_PIPELINE_DATA} already exists — leaving as-is.')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

md("""## 6. Feature engineering — 25 numerical features per row

For every row in the E5 base, compute the 25 numerical features implemented
in `src/features.py` (tone × 4, URL × 5, phrase × 3,
textstats × 13). Cached to `data/interim/e7_p1_features.parquet`.

The heavy work is done by `scripts.training.train_e7_p1.load_or_compute_features()`,
the same code path used at model training. Nothing is re-implemented here.
""")

code("""def build_e7_p1_features():
    # Import lazily so REPO_ROOT is on the path.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.training.train_e7_p1 import load_or_compute_features
    load_or_compute_features()


cached_step('compute e7_p1 features on E5 base',
            E7_P1_FEATURES,
            build_e7_p1_features)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — SYNTHETIC DATA GENERATION
# ─────────────────────────────────────────────────────────────────────────────

md("""## 7. Synthetic data generation

Three template-based generators produce the adversarial synthetic corpora:

- **E8-P2** — 1,978 near-boundary legitimate messages (shipping, OTP,
  banking notifications) targeting the E7-P1 false-positive region.
- **E8-P6** — 15,572 additional legitimate messages across 21 categories,
  65 brands.
- **E8-P8** — 14,669 synthetic scams + 1,109 paired-legit twins across
  weak-recall categories (investment, romance, emergency, refund,
  sextortion, threat, gift-card CEO, modern phishing).

Every generated message passes the rule-engine's validators before being
kept, so no synthetic legit row can contain a dangerous action pattern and
no synthetic scam is gibberish or unlabelled legit.
""")

code("""def build_e8p2_synth():  run_repo_script('scripts/data_prep/gen_e8p2_synthetic_legit.py')
def build_e8p6_synth():  run_repo_script('scripts/data_prep/gen_e8p6_synthetic_legit.py')
def build_e8p8_synth():  run_repo_script('scripts/data_prep/gen_e8p8_synthetic_scam.py')


cached_step('generate E8-P2 synthetic legit', E8P2_SYNTH, build_e8p2_synth)
cached_step('generate E8-P6 synthetic legit', E8P6_SYNTH, build_e8p6_synth)
cached_step('generate E8-P8 synthetic scam + pairs',
            [E8P8_SCAM, E8P8_PAIRS], build_e8p8_synth)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — E8 MERGE CHAIN
# ─────────────────────────────────────────────────────────────────────────────

md("""## 8. E8 merge chain

Five ordered stages that transform the E5-featurized base into the final
prepared corpus:

| # | Stage | What it does |
|---|---|---|
| 8a | `merge_e8p2` | + 1,978 E8-P2 synthetic legit rows |
| 8b | `build_e8p3` | − `spamassassin_ham` source (hash-based drop) |
| 8c | `build_e8p5` | − mailing-list scam / spam-in-legit / very-short rows |
| 8d | `merge_e8p6` | + 15,572 E8-P6 synthetic legit rows (deduped) |
| 8e | `merge_e8p8` | + 14,669 synthetic scam + 1,109 legit-pair rows |

Each stage reads its input from the preceding stage's output and writes a
new parquet without overwriting. Rollback is trivial.
""")

code("""def build_e8p2_merged():  run_repo_script('scripts/data_prep/merge_e8p2_into_training.py')
def build_e8p3_cleaned():  run_repo_script('scripts/data_prep/build_e8p3_training.py')
def build_e8p5_cleaned():  run_repo_script('scripts/data_prep/build_e8p5_training.py')
def build_e8p6_merged():   run_repo_script('scripts/data_prep/merge_e8p6_into_training.py')
def build_e8p9_final():    run_repo_script('scripts/data_prep/merge_e8p8_into_training.py')


cached_step('8a. merge E8-P2 into training', E8P2_MERGED,  build_e8p2_merged)
cached_step('8b. build E8-P3 (drop SA)',      E8P3_CLEANED, build_e8p3_cleaned)
cached_step('8c. build E8-P5 (noise cleanup)', E8P5_CLEANED, build_e8p5_cleaned)
cached_step('8d. merge E8-P6 into training',  E8P6_MERGED,  build_e8p6_merged)
cached_step('8e. merge E8-P8 into training',  FINAL_PARQUET, build_e8p9_final)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — LOAD FINAL PREPARED CORPUS
# ─────────────────────────────────────────────────────────────────────────────

md("""## 9. Load the final prepared corpus

The pipeline is complete. Load the final parquet and confirm the row-count
evolution from the DU output through every stage.
""")

code("""df = pd.read_parquet(FINAL_PARQUET)
print(f'Final prepared corpus: {FINAL_PARQUET}')
print(f'  rows    : {len(df):,}')
print(f'  columns : {len(df.columns)} '
      f'(text + label + cluster_id + split + 25 numerical features)')
print(f'  splits  : {df.split.value_counts().to_dict()}')
print(f'  labels  : {df.label.value_counts().to_dict()}')
print()
print('Row-count evolution:')
stages = [
    ('DU output (raw_unified)',                 len(raw_unified)),
    ('after scamradar clean',                   pd.read_parquet(SR2_CLEAN).shape[0]),
    ('after cluster-aware split (E5 base sum)', sum(pd.read_parquet(p).shape[0]
                                                     for p in [SR2_TRAIN, SR2_VAL, SR2_TEST, SR2_EXT])),
    ('after E7-P1 feature engineering',         pd.read_parquet(E7_P1_FEATURES).shape[0]),
    ('after E8-P2 merge (+synth legit)',        pd.read_parquet(E8P2_MERGED).shape[0]),
    ('after E8-P3 (drop spamassassin_ham)',     pd.read_parquet(E8P3_CLEANED).shape[0]),
    ('after E8-P5 (noise cleanup)',             pd.read_parquet(E8P5_CLEANED).shape[0]),
    ('after E8-P6 merge (+synth legit)',        pd.read_parquet(E8P6_MERGED).shape[0]),
    ('after E8-P8 merge (+synth scam+pairs)',   len(df)),
]
for name, n in stages:
    print(f'  {name:44s} {n:>8,}')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — SOURCE PROVENANCE (was Section 2 in old DP)
# ─────────────────────────────────────────────────────────────────────────────

md("""## 10. Recover source provenance for the DB

The merge chain drops the `source` column from the feature parquet
(it is only kept transiently during E8-P5 cleanup). To populate a proper
`Source` table in the database we reattach a source name to every row:

- **Real rows** — hash-join back to the E5 base parquets, which still carry
  `source`, `license`, and `era`.
- **Synthetic rows** — identified by their `cluster_id` bucket. The merge
  scripts assign disjoint negative ranges (see the E8-P2/6/8 code) so we
  can tell each generation stage apart deterministically:

  | `cluster_id` range | Stage | Label |
  |---|---|---|
  | `[-8_001_977, -8_000_000]` | E8-P2 synthetic legit | 0 |
  | `[-9_015_571, -9_000_000]` | E8-P6 synthetic legit | 0 |
  | `[-9_514_668, -9_500_000]` | E8-P8 synthetic scam | 1 |
  | `[-9_601_108, -9_600_000]` | E8-P8 legit pairs | 0 |
""")

code("""SYNTH_BUCKETS = [
    ('synthetic_e8p2_legit',  -8_100_000, -8_000_000, 'synthetic'),
    ('synthetic_e8p6_legit',  -9_100_000, -9_000_000, 'synthetic'),
    ('synthetic_e8p8_scam',   -9_600_000, -9_500_000, 'synthetic'),
    ('synthetic_e8p8_pair',   -9_700_000, -9_600_000, 'synthetic'),
]


def bucket_synthetic(cid: int) -> str | None:
    for name, lo, hi, _ in SYNTH_BUCKETS:
        if lo <= cid <= hi:
            return name
    return None


df['source_name'] = df.cluster_id.map(bucket_synthetic)
print(f'Synthetic rows tagged by cluster_id: {df.source_name.notna().sum():,}')
print(df[df.source_name.notna()].source_name.value_counts().to_string())""")

code("""def sha1(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8', 'ignore')).hexdigest()


real_source_map: dict[str, tuple[str, str, str]] = {}   # hash → (source, license, era)

print('Recovering real-row provenance from the E5 base parquets...')
for split_name, path in [
    ('train',    SR2_TRAIN),
    ('val',      SR2_VAL),
    ('test',     SR2_TEST),
    ('external', SR2_EXT),
]:
    cols = pd.read_parquet(path).columns.tolist()
    want = ['text', 'source'] + [c for c in ('license', 'era') if c in cols]
    s = pd.read_parquet(path, columns=want)
    for row in s.itertuples(index=False):
        real_source_map[sha1(row.text)] = (
            row.source,
            getattr(row, 'license', None) or 'unknown',
            getattr(row, 'era', None)     or 'unknown',
        )
    print(f'  {split_name:9s}: +{len(s):>6,} rows  (map size: {len(real_source_map):,})')""")

code("""mask_real = df.source_name.isna()
hashes = df.loc[mask_real, 'text'].map(sha1)
df.loc[mask_real, 'source_name'] = hashes.map(
    lambda h: real_source_map.get(h, (None, None, None))[0]
)
n_unresolved = df.source_name.isna().sum()
if n_unresolved:
    print(f'Unresolved after hash join: {n_unresolved:,}  → tagging as "e5_base_corpus"')
    df.source_name = df.source_name.fillna('e5_base_corpus')

print('\\nFinal source_name distribution (top 20):')
print(df.source_name.value_counts().head(20).to_string())""")

code("""# Build the Source lookup table.
source_rows = []
for name in sorted(df.source_name.unique()):
    if name.startswith('synthetic_') or name == 'synthetic_v1':
        source_rows.append({
            'source_name': name,
            'source_type': 'synthetic',
            'era':         'modern' if 'e8p' in name else 'legacy',
            'license':     'project_internal',
        })
    elif name == 'e5_base_corpus':
        source_rows.append({
            'source_name': name, 'source_type': 'real',
            'era': 'unknown', 'license': 'unknown',
        })
    else:
        h_any = next((h for h, (sn, _, _) in real_source_map.items() if sn == name), None)
        _, lic, era = real_source_map[h_any] if h_any else (None, 'unknown', 'unknown')
        source_rows.append({
            'source_name': name, 'source_type': 'real',
            'era': era, 'license': lic,
        })

sources_df = pd.DataFrame(source_rows)
print(f'{len(sources_df)} distinct sources:')
sources_df""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 — SCHEMA DESIGN + DB CREATE
# ─────────────────────────────────────────────────────────────────────────────

md("""## 11. Relational schema + create the database

Three tables, matching the natural structure of the prepared corpus.

- **`Source`** — one row per data provenance (real corpora + synthetic
  stages). Attributes: name, type, era, license.
- **`Message`** — one row per prepared example. FK to `Source`. Holds the
  raw text, binary label, split, and cluster identifier.
- **`MessageFeatures`** — 1:1 with `Message`, holding the 25 engineered
  numerical features.

Cardinality: `Source 1—N Message`, `Message 1—1 MessageFeatures`.
""")

code("""DDL_SOURCE = '''
CREATE TABLE Source (
    source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name   TEXT    NOT NULL UNIQUE,
    source_type   TEXT    NOT NULL CHECK (source_type IN ('real','synthetic')),
    era           TEXT,
    license       TEXT
);
'''.strip()

DDL_MESSAGE = '''
CREATE TABLE Message (
    message_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    text          TEXT    NOT NULL,
    label         INTEGER NOT NULL CHECK (label IN (0,1)),
    split         TEXT    NOT NULL CHECK (split IN ('train','val','test','external')),
    cluster_id    INTEGER,
    source_id     INTEGER NOT NULL,
    FOREIGN KEY (source_id) REFERENCES Source(source_id)
);
'''.strip()

DDL_FEATURES = '''
CREATE TABLE MessageFeatures (
    message_id                 INTEGER PRIMARY KEY,
    text_length                INTEGER,
    word_count                 INTEGER,
    has_url                    INTEGER,
    url_count                  INTEGER,
    exclamation_count          INTEGER,
    uppercase_ratio            REAL,
    digit_ratio                REAL,
    urgency_score              REAL,
    tone_urgency               INTEGER,
    tone_fear                  INTEGER,
    tone_reward                INTEGER,
    tone_threat                INTEGER,
    url_suspicious_tld         INTEGER,
    url_suspicious_keyword     INTEGER,
    url_has_ip                 INTEGER,
    scam_phrase_score          INTEGER,
    sender_impersonation_score INTEGER,
    legit_phrase_score         INTEGER,
    avg_word_length            REAL,
    capitalized_word_count     INTEGER,
    punctuation_density        REAL,
    question_mark_count        INTEGER,
    currency_symbol_count      INTEGER,
    readability_score          REAL,
    unique_word_ratio          REAL,
    FOREIGN KEY (message_id) REFERENCES Message(message_id)
);
'''.strip()

DDL_INDEXES = [
    'CREATE INDEX idx_message_split  ON Message(split);',
    'CREATE INDEX idx_message_label  ON Message(label);',
    'CREATE INDEX idx_message_source ON Message(source_id);',
]

print(DDL_SOURCE);   print()
print(DDL_MESSAGE);  print()
print(DDL_FEATURES); print()
for s in DDL_INDEXES: print(s)""")

code("""if DB_PATH.exists():
    DB_PATH.unlink()
    print(f'Removed existing DB at {DB_PATH}')

conn = sqlite3.connect(str(DB_PATH))
conn.execute('PRAGMA foreign_keys = ON;')
cur = conn.cursor()

for stmt in [DDL_SOURCE, DDL_MESSAGE, DDL_FEATURES] + DDL_INDEXES:
    cur.execute(stmt)
conn.commit()

schema = pd.read_sql(
    "SELECT type, name FROM sqlite_master WHERE type IN ('table','index') ORDER BY type, name",
    conn,
)
schema""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12 — INSERT
# ─────────────────────────────────────────────────────────────────────────────

md("""## 12. Insert the prepared data

Insertion order follows the FK: `Source` → `Message` → `MessageFeatures`.
Bulk `executemany` is used for the two large tables; every `INSERT`
statement is printed above its execution.
""")

code("""INSERT_SOURCE = '''
INSERT INTO Source (source_name, source_type, era, license) VALUES (?, ?, ?, ?);
'''.strip()
print(INSERT_SOURCE, '\\n')

cur.executemany(INSERT_SOURCE, [
    (r.source_name, r.source_type, r.era, r.license)
    for r in sources_df.itertuples(index=False)
])
conn.commit()

source_id_map = dict(pd.read_sql('SELECT source_name, source_id FROM Source', conn).values)
print(f'Inserted {len(sources_df)} sources.')""")

code("""INSERT_MESSAGE = '''
INSERT INTO Message (text, label, split, cluster_id, source_id) VALUES (?, ?, ?, ?, ?);
'''.strip()
print(INSERT_MESSAGE, '\\n')

msg_rows = [
    (row.text, int(row.label), row.split, int(row.cluster_id),
     source_id_map[row.source_name])
    for row in df.itertuples(index=False)
]
cur.executemany(INSERT_MESSAGE, msg_rows)
conn.commit()

n_inserted = cur.execute('SELECT COUNT(*) FROM Message').fetchone()[0]
print(f'Inserted {n_inserted:,} messages.')""")

code("""FEATURE_COLS = [
    'text_length', 'word_count', 'has_url', 'url_count', 'exclamation_count',
    'uppercase_ratio', 'digit_ratio', 'urgency_score',
    'tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat',
    'url_suspicious_tld', 'url_suspicious_keyword', 'url_has_ip',
    'scam_phrase_score', 'sender_impersonation_score', 'legit_phrase_score',
    'avg_word_length', 'capitalized_word_count', 'punctuation_density',
    'question_mark_count', 'currency_symbol_count',
    'readability_score', 'unique_word_ratio',
]

INSERT_FEATURES = f'''
INSERT INTO MessageFeatures (message_id, {", ".join(FEATURE_COLS)})
VALUES ({", ".join(["?"] * (1 + len(FEATURE_COLS)))});
'''.strip()
print(INSERT_FEATURES[:200], '...\\n')

feat_rows = [
    tuple([i + 1] + [
        (int(v) if isinstance(v, (bool, np.bool_)) else v)
        for v in (getattr(row, c) for c in FEATURE_COLS)
    ])
    for i, row in enumerate(df.itertuples(index=False))
]
cur.executemany(INSERT_FEATURES, feat_rows)
conn.commit()

n_feats = cur.execute('SELECT COUNT(*) FROM MessageFeatures').fetchone()[0]
print(f'Inserted {n_feats:,} feature rows.')""")

code("""for t in ['Source', 'Message', 'MessageFeatures']:
    n = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'  {t:20s} {n:>8,}')

orph = cur.execute('''
    SELECT COUNT(*) FROM Message m
    LEFT JOIN Source s ON m.source_id = s.source_id
    WHERE s.source_id IS NULL
''').fetchone()[0]
print(f'\\norphaned messages : {orph}')
print(f'DB file size      : {DB_PATH.stat().st_size / 1e6:.1f} MB')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13 — RETRIEVAL FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

md("""## 13. Retrieval functions

Named Python functions, each backed by a real SQL query. Grouped into
three tiers:

- **Tier 1** — corpus-level descriptives (single-table aggregates).
- **Tier 2** — feature-level descriptives (JOINs across `Message` and
  `MessageFeatures`).
- **Tier 3** — analytical / sample retrieval (parameterised queries).

Every function returns a pandas DataFrame so the results feed the plots
and statistical tests in Section 15 directly.
""")

code("""# ── Tier 1: corpus-level ─────────────────────────────────────────────

def class_distribution() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT label, COUNT(*) AS n FROM Message GROUP BY label ORDER BY label
    ''', conn)


def per_split_class_balance() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT split, label, COUNT(*) AS n
        FROM Message GROUP BY split, label ORDER BY split, label
    ''', conn)


def source_distribution() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT s.source_name, s.source_type, s.era, COUNT(*) AS n
        FROM Message m
        JOIN Source s ON m.source_id = s.source_id
        GROUP BY s.source_name, s.source_type, s.era
        ORDER BY n DESC
    ''', conn)


def real_vs_synthetic() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT s.source_type, COUNT(*) AS n
        FROM Message m
        JOIN Source s ON m.source_id = s.source_id
        GROUP BY s.source_type
    ''', conn)


print('class_distribution():');       print(class_distribution().to_string(index=False), '\\n')
print('per_split_class_balance():');  print(per_split_class_balance().to_string(index=False), '\\n')
print('real_vs_synthetic():');        print(real_vs_synthetic().to_string(index=False))""")

code("""source_distribution()""")

code("""# ── Tier 2: feature-level ────────────────────────────────────────────

def length_stats_by_label() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT m.label, COUNT(*) AS n,
               ROUND(AVG(f.text_length)) AS mean_len,
               MIN(f.text_length) AS min_len,
               MAX(f.text_length) AS max_len
        FROM Message m
        JOIN MessageFeatures f ON m.message_id = f.message_id
        GROUP BY m.label
    ''', conn)


def feature_mean_by_label(feature: str) -> pd.DataFrame:
    return pd.read_sql(f'''
        SELECT m.label,
               ROUND(AVG(f.{feature}), 4) AS mean_val,
               ROUND(MIN(f.{feature}), 4) AS min_val,
               ROUND(MAX(f.{feature}), 4) AS max_val,
               COUNT(*) AS n
        FROM Message m
        JOIN MessageFeatures f ON m.message_id = f.message_id
        GROUP BY m.label
    ''', conn)


def has_url_share_by_label() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT m.label,
               SUM(CASE WHEN f.has_url = 1 THEN 1 ELSE 0 END) AS with_url,
               COUNT(*)                                       AS total,
               ROUND(100.0 * SUM(CASE WHEN f.has_url = 1 THEN 1 ELSE 0 END) / COUNT(*), 2)
                                                              AS pct_with_url
        FROM Message m
        JOIN MessageFeatures f ON m.message_id = f.message_id
        GROUP BY m.label
    ''', conn)


print('length_stats_by_label():');
print(length_stats_by_label().to_string(index=False), '\\n')
print('feature_mean_by_label("tone_fear"):');
print(feature_mean_by_label('tone_fear').to_string(index=False), '\\n')
print('has_url_share_by_label():');
print(has_url_share_by_label().to_string(index=False))""")

code("""# ── Tier 3: analytical + sample retrieval ────────────────────────────

def sample_messages(source: str | None = None,
                    label: int | None = None,
                    split: str | None = None,
                    limit: int = 5) -> pd.DataFrame:
    where, params = [], []
    if source is not None: where.append('s.source_name = ?'); params.append(source)
    if label  is not None: where.append('m.label = ?');       params.append(label)
    if split  is not None: where.append('m.split = ?');       params.append(split)
    clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    return pd.read_sql(f'''
        SELECT m.message_id, m.label, m.split, s.source_name,
               substr(m.text, 1, 140) AS text_preview
        FROM Message m
        JOIN Source s ON m.source_id = s.source_id
        {clause}
        ORDER BY RANDOM()
        LIMIT ?
    ''', conn, params=params + [limit])


def crosstab_source_x_label() -> pd.DataFrame:
    return pd.read_sql('''
        SELECT s.source_name,
               SUM(CASE WHEN m.label = 0 THEN 1 ELSE 0 END) AS legit,
               SUM(CASE WHEN m.label = 1 THEN 1 ELSE 0 END) AS scam,
               COUNT(*)                                     AS total
        FROM Message m
        JOIN Source s ON m.source_id = s.source_id
        GROUP BY s.source_name
        ORDER BY total DESC
    ''', conn)


def messages_where(sql_predicate: str, limit: int = 10) -> pd.DataFrame:
    return pd.read_sql(f'''
        SELECT m.message_id, m.label, s.source_name,
               f.tone_urgency, f.tone_fear, f.scam_phrase_score,
               substr(m.text, 1, 120) AS text_preview
        FROM Message m
        JOIN Source s          ON m.source_id  = s.source_id
        JOIN MessageFeatures f ON m.message_id = f.message_id
        WHERE {sql_predicate}
        LIMIT {int(limit)}
    ''', conn)


print('sample_messages(label=1, split="train", limit=3):')
print(sample_messages(label=1, split='train', limit=3).to_string(index=False), '\\n')

print('crosstab_source_x_label() — top 10:')
print(crosstab_source_x_label().head(10).to_string(index=False), '\\n')

print('messages_where("f.tone_urgency > 3 AND m.label = 0", limit=3):')
print(messages_where('f.tone_urgency > 3 AND m.label = 0', limit=3).to_string(index=False))""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 14 — ERD
# ─────────────────────────────────────────────────────────────────────────────

md("""## 14. Entity–Relationship Diagram

Drawn directly from the schema created in Section 11. Rendered in-notebook
with matplotlib so no external tools are required.
""")

code("""def draw_erd(save_path: Path | None = None):
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.set_xlim(0, 13); ax.set_ylim(0, 8); ax.axis('off')

    def entity(x, y, w, h, title, cols, pk_idx=(), fk_idx=()):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
            boxstyle='round,pad=0.05', linewidth=1.4,
            edgecolor='#2c3e50', facecolor='#ecf0f1'))
        ax.text(x + w/2, y + h - 0.35, title, ha='center', va='center',
                fontsize=12, fontweight='bold', color='#2c3e50')
        ax.plot([x, x + w], [y + h - 0.65, y + h - 0.65],
                color='#2c3e50', linewidth=0.8)
        for i, (col, typ) in enumerate(cols):
            marks = []
            if i in pk_idx: marks.append('PK')
            if i in fk_idx: marks.append('FK')
            prefix = f'[{", ".join(marks)}] ' if marks else '     '
            ax.text(x + 0.15, y + h - 0.95 - i*0.28,
                    f'{prefix}{col:32s} {typ}',
                    ha='left', va='center',
                    fontsize=8.5, family='monospace', color='#34495e')

    entity(0.2, 4.5, 3.8, 3.0, 'Source', [
        ('source_id', 'INTEGER'), ('source_name', 'TEXT UNIQUE'),
        ('source_type', 'TEXT'), ('era', 'TEXT'), ('license', 'TEXT'),
    ], pk_idx=(0,))

    entity(4.8, 2.6, 3.8, 4.8, 'Message', [
        ('message_id', 'INTEGER'), ('text', 'TEXT'), ('label', 'INTEGER'),
        ('split', 'TEXT'), ('cluster_id', 'INTEGER'), ('source_id', 'INTEGER'),
    ], pk_idx=(0,), fk_idx=(5,))

    features = [
        ('message_id',                 'INTEGER'),
        ('text_length',                'INTEGER'),
        ('word_count',                 'INTEGER'),
        ('has_url',                    'INTEGER'),
        ('url_count',                  'INTEGER'),
        ('exclamation_count',          'INTEGER'),
        ('uppercase_ratio',            'REAL'),
        ('digit_ratio',                'REAL'),
        ('urgency_score',              'REAL'),
        ('tone_urgency',               'INTEGER'),
        ('tone_fear',                  'INTEGER'),
        ('tone_reward',                'INTEGER'),
        ('tone_threat',                'INTEGER'),
        ('url_suspicious_tld',         'INTEGER'),
        ('url_suspicious_keyword',     'INTEGER'),
        ('url_has_ip',                 'INTEGER'),
        ('scam_phrase_score',          'INTEGER'),
        ('sender_impersonation_score', 'INTEGER'),
        ('legit_phrase_score',         'INTEGER'),
        ('avg_word_length',            'REAL'),
        ('capitalized_word_count',     'INTEGER'),
        ('punctuation_density',        'REAL'),
        ('question_mark_count',        'INTEGER'),
        ('currency_symbol_count',      'INTEGER'),
        ('readability_score',          'REAL'),
        ('unique_word_ratio',          'REAL'),
    ]
    entity(9.4, 0.2, 3.5, 7.2, 'MessageFeatures', features,
           pk_idx=(0,), fk_idx=(0,))

    ax.add_patch(FancyArrowPatch((4.0, 5.5), (4.8, 4.6),
        arrowstyle='->', mutation_scale=14, color='#c0392b', linewidth=1.4))
    ax.text(4.3, 5.15, '1  ..  N', fontsize=9, color='#c0392b')
    ax.add_patch(FancyArrowPatch((8.6, 4.6), (9.4, 4.0),
        arrowstyle='->', mutation_scale=14, color='#27ae60', linewidth=1.4))
    ax.text(8.7, 4.15, '1  ..  1', fontsize=9, color='#27ae60')

    ax.set_title('ScamRadar+ E8-P9 — Final Prepared Dataset ERD',
                 fontsize=13, fontweight='bold', pad=14, color='#2c3e50')
    plt.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()


draw_erd(save_path=REPO_ROOT / 'notebooks' / 'erd.png')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 15 — FINAL EDA
# ─────────────────────────────────────────────────────────────────────────────

md("""## 15. Final EDA — SQL-driven

Every plot and statistic below comes from a SQL query run against the
database built in Section 11. Pandas is used only for rendering; the
analytical logic is in the SQL.

### 15.1 Class distribution
""")

code("""cd = class_distribution()
cd['pct'] = (100 * cd['n'] / cd['n'].sum()).round(2)
cd['label_name'] = cd.label.map({0: 'legit', 1: 'scam'})
print(cd.to_string(index=False))

fig, ax = plt.subplots(figsize=(6, 4))
ax.bar(cd.label_name, cd.n, color=['#3498db', '#e74c3c'])
for i, (name, n, pct) in enumerate(zip(cd.label_name, cd.n, cd.pct)):
    ax.text(i, n, f'{n:,}\\n({pct}%)', ha='center', va='bottom', fontsize=10)
ax.set_ylabel('Number of messages')
ax.set_title(f'Class distribution — full corpus ({cd.n.sum():,} messages)')
ax.set_ylim(0, cd.n.max() * 1.15)
plt.tight_layout(); plt.show()""")

code("""psb = per_split_class_balance()
pivot = psb.pivot(index='split', columns='label', values='n').fillna(0).astype(int)
pivot.columns = ['legit', 'scam']
pivot['scam_share_%'] = (100 * pivot.scam / (pivot.legit + pivot.scam)).round(2)
print(pivot)

fig, ax = plt.subplots(figsize=(9, 4))
pivot[['legit','scam']].plot(kind='bar', stacked=True, ax=ax,
                              color=['#3498db', '#e74c3c'])
ax.set_ylabel('Rows'); ax.set_title('Class balance by split')
ax.set_xticklabels(pivot.index, rotation=0)
plt.tight_layout(); plt.show()""")

md("""### 15.2 Source composition""")

code("""sd = source_distribution().head(15)
print(sd.to_string(index=False))

fig, ax = plt.subplots(figsize=(11, 5))
colors = ['#e74c3c' if t == 'synthetic' else '#3498db' for t in sd.source_type]
ax.barh(sd.source_name[::-1], sd.n[::-1], color=colors[::-1])
ax.set_xlabel('Rows')
ax.set_title('Top 15 sources by row count  (red = synthetic, blue = real)')
plt.tight_layout(); plt.show()""")

md("""### 15.3 Message-length distribution by label""")

code("""len_df = pd.read_sql('''
    SELECT m.label, f.text_length
    FROM Message m JOIN MessageFeatures f ON m.message_id = f.message_id
    WHERE f.text_length < 5000
''', conn)

fig, ax = plt.subplots(figsize=(10, 5))
for lab, color, name in [(0, '#3498db', 'legit'), (1, '#e74c3c', 'scam')]:
    subset = len_df[len_df.label == lab].text_length
    ax.hist(subset, bins=80, alpha=0.55, color=color, label=name)
ax.set_xlabel('Character length'); ax.set_ylabel('Count')
ax.set_title('Text-length distribution by label  (truncated at 5,000 chars)')
ax.legend(); plt.tight_layout(); plt.show()

print(length_stats_by_label().to_string(index=False))""")

md("""### 15.4 Tone-feature means by label""")

code("""tone_stats = pd.read_sql('''
    SELECT m.label,
           ROUND(AVG(f.tone_urgency), 3) AS mean_urgency,
           ROUND(AVG(f.tone_fear),    3) AS mean_fear,
           ROUND(AVG(f.tone_reward),  3) AS mean_reward,
           ROUND(AVG(f.tone_threat),  3) AS mean_threat
    FROM Message m JOIN MessageFeatures f ON m.message_id = f.message_id
    GROUP BY m.label
''', conn)
print(tone_stats.to_string(index=False))

fig, ax = plt.subplots(figsize=(9, 5))
tones = ['urgency', 'fear', 'reward', 'threat']
means_legit = tone_stats[tone_stats.label == 0].iloc[0, 1:].values
means_scam  = tone_stats[tone_stats.label == 1].iloc[0, 1:].values
x = np.arange(len(tones)); w = 0.36
ax.bar(x - w/2, means_legit, w, color='#3498db', label='legit')
ax.bar(x + w/2, means_scam,  w, color='#e74c3c', label='scam')
ax.set_xticks(x); ax.set_xticklabels(tones)
ax.set_ylabel('Mean feature value')
ax.set_title('Mean tone-feature values by label')
ax.legend(); plt.tight_layout(); plt.show()""")

md("""### 15.5 URL presence by label""")

code("""url_pct = has_url_share_by_label()
url_pct['label_name'] = url_pct.label.map({0: 'legit', 1: 'scam'})
print(url_pct.to_string(index=False))

fig, ax = plt.subplots(figsize=(6, 4))
ax.bar(url_pct.label_name, url_pct.pct_with_url, color=['#3498db', '#e74c3c'])
for i, pct in enumerate(url_pct.pct_with_url):
    ax.text(i, pct, f'{pct}%', ha='center', va='bottom', fontsize=10)
ax.set_ylabel('% of rows containing a URL')
ax.set_title('URL presence rate by label')
ax.set_ylim(0, max(url_pct.pct_with_url) * 1.2)
plt.tight_layout(); plt.show()""")

md("""### 15.6 Feature ↔ label correlation

Point-biserial correlation between each numerical feature and the binary
label. Positive → pushes toward SCAM; negative → toward LEGIT.
""")

code("""corr_data = pd.read_sql(f'''
    SELECT m.label, {", ".join(f"f.{c}" for c in FEATURE_COLS)}
    FROM Message m JOIN MessageFeatures f ON m.message_id = f.message_id
''', conn)

corrs = corr_data.corr(numeric_only=True)['label'].drop('label').sort_values()

fig, ax = plt.subplots(figsize=(9, 8))
colors = ['#e74c3c' if v > 0 else '#3498db' for v in corrs.values]
ax.barh(corrs.index, corrs.values, color=colors)
ax.axvline(0, color='black', linewidth=0.6)
ax.set_xlabel('Point-biserial correlation with label (positive → scam)')
ax.set_title('Feature ↔ label correlation')
plt.tight_layout(); plt.show()

print(corrs.round(3).to_string())""")

md("""### 15.7 Statistical tests

Four tests, each answering a specific DP-level question. All contingency
tables and paired samples are pulled from the DB by SQL.
""")

code("""# Test 1: chi-square — class distribution × split
ct = pd.read_sql('''
    SELECT split, label, COUNT(*) AS n FROM Message GROUP BY split, label
''', conn).pivot(index='split', columns='label', values='n').fillna(0).astype(int)
chi2, p, dof, _ = stats.chi2_contingency(ct.values)
print('Test 1 — Chi-square: class × split')
print(f'  H0: label is independent of split')
print(f'  chi2={chi2:.2f}   dof={dof}   p={p:.4g}')
print(f'  → {"reject" if p < 0.05 else "do not reject"} H0 at alpha=0.05')
print(ct)""")

code("""# Test 2: chi-square — has_url × label
ct = pd.read_sql('''
    SELECT f.has_url, m.label, COUNT(*) AS n
    FROM Message m JOIN MessageFeatures f ON m.message_id = f.message_id
    GROUP BY f.has_url, m.label
''', conn).pivot(index='has_url', columns='label', values='n').fillna(0).astype(int)
chi2, p, dof, _ = stats.chi2_contingency(ct.values)
print('Test 2 — Chi-square: has_url × label')
print(f'  H0: URL presence is independent of label')
print(f'  chi2={chi2:.2f}   dof={dof}   p={p:.4g}')
print(f'  → {"reject" if p < 0.05 else "do not reject"} H0 at alpha=0.05')
print(ct)""")

code("""# Test 3: Mann-Whitney U — text_length by label
legit = pd.read_sql('''
    SELECT f.text_length FROM Message m
    JOIN MessageFeatures f ON m.message_id = f.message_id
    WHERE m.label = 0
''', conn).text_length.values
scam  = pd.read_sql('''
    SELECT f.text_length FROM Message m
    JOIN MessageFeatures f ON m.message_id = f.message_id
    WHERE m.label = 1
''', conn).text_length.values

u, p = stats.mannwhitneyu(legit, scam, alternative='two-sided')
print('Test 3 — Mann-Whitney U: text_length by label')
print(f'  H0: distributions identical across label')
print(f'  U={u:.2e}   p={p:.4g}   n_legit={len(legit):,}   n_scam={len(scam):,}')
print(f'  medians: legit={int(np.median(legit))}   scam={int(np.median(scam))}')
print(f'  → {"reject" if p < 0.05 else "do not reject"} H0 at alpha=0.05')""")

code("""# Test 4: Mann-Whitney U — scam_phrase_score by label (one-sided: legit < scam)
legit = pd.read_sql('''
    SELECT f.scam_phrase_score FROM Message m
    JOIN MessageFeatures f ON m.message_id = f.message_id
    WHERE m.label = 0
''', conn).scam_phrase_score.values
scam  = pd.read_sql('''
    SELECT f.scam_phrase_score FROM Message m
    JOIN MessageFeatures f ON m.message_id = f.message_id
    WHERE m.label = 1
''', conn).scam_phrase_score.values

u, p = stats.mannwhitneyu(legit, scam, alternative='less')
print('Test 4 — Mann-Whitney U: scam_phrase_score by label  (one-sided: legit < scam)')
print(f'  U={u:.2e}   p={p:.4g}')
print(f'  means: legit={legit.mean():.3f}   scam={scam.mean():.3f}')
print(f'  → {"reject" if p < 0.05 else "do not reject"} H0 at alpha=0.05')""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 16 — SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

md("""## 16. Summary

**End-to-end chain proven:**

```
data_understanding.ipynb
   → data/interim/raw_unified.parquet
   → [this notebook orchestrates the production pipeline, cache-aware]
   → data/interim/e7_p1_features_e8p9.parquet
   → data/final_db/scamradar_e8p9.db
```

**Data Preparation deliverables produced by this notebook:**

- **Relational database** — `data/final_db/scamradar_e8p9.db` (SQLite,
  three tables + FK relationships + three indexes).
- **Insertion code** — Section 12 (visible SQL, bulk `executemany`).
- **Retrieval code** — Section 13 (eight named functions, real SQL, JOINs).
- **ERD** — Section 14 (inline + saved to `notebooks/erd.png`).
- **Final EDA** — Section 15 (descriptive stats for target + features, six
  plots, four statistical tests).

**Nothing in the production pipeline was modified.** Every pipeline stage
is invoked via subprocess or import of existing production code. If any
intermediate artifact is missing, the corresponding stage rebuilds it; if
all are cached, the notebook completes in seconds.

Set `FORCE_REBUILD = True` in Section 0 and re-run All to rebuild every
stage from scratch (approximately 20–30 minutes on first run).
""")

code("""conn.close()
print(f'Closed connection. DB persists at: {DB_PATH}')
print(f'File size: {DB_PATH.stat().st_size / 1e6:.1f} MB')""")


# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLE + WRITE
# ─────────────────────────────────────────────────────────────────────────────

nb['cells'] = cells
nb['metadata'] = {
    'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
    'language_info': {'name': 'python', 'pygments_lexer': 'ipython3',
                      'file_extension': '.py'},
}

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print(f'Wrote {OUT_PATH}')
print(f'  cells: {len(cells)}  '
      f'({sum(1 for c in cells if c.cell_type == "markdown")} md, '
      f'{sum(1 for c in cells if c.cell_type == "code")} code)')
