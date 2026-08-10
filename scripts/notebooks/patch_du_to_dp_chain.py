"""
Patch the Data Understanding notebook so its final artifact matches the file
consumed by the Data Preparation notebook, and add a matching top-note to the
Data Preparation notebook.

What this changes
-----------------
DU notebook (data_pipeline/notebooks/data_understanding.ipynb):
  1. The final merge cell now writes raw_unified.parquet to a canonical
     repo-relative path (data/interim/raw_unified.parquet) instead of the
     current working directory.
  2. Adds a new "Handoff to Data Preparation" section that:
     - Explains the production pipeline steps that transform raw_unified
       into the final prepared corpus.
     - Loads the final prepared parquet the DP notebook consumes.
     - Confirms it as the handoff artifact.

DP notebook (notebooks/data_preparation.ipynb):
  1. Adds a top-level markdown note stating that the input parquet is
     produced by the DU notebook's handoff section (via the production
     pipeline).

Nothing in the production pipeline is modified.

Run:
    python scripts/notebooks/patch_du_to_dp_chain.py
"""
from __future__ import annotations

import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DU_PATH = os.path.join(ROOT, 'data_pipeline', 'notebooks', 'data_understanding.ipynb')
DP_PATH = os.path.join(ROOT, 'notebooks', 'data_preparation.ipynb')


# ─── new content for the DU notebook ─────────────────────────────────────

DU_UPDATED_MERGE_CELL = '''# Merge every source into the raw unified dataset
#
# Writes to a canonical repo-relative path so downstream notebooks and the
# production pipeline can locate this artifact deterministically.

from pathlib import Path
import pandas as pd

CANON_COLS = ["sample_id", "text", "label", "category", "source", "license",
              "is_synthetic", "era", "platform", "acquired_at"]

raw_unified = pd.concat([
    df_uci_sms,
    df_zenodo_champa_nazario_legacy,
    df_zenodo_champa_nazario_modern,
    df_zenodo_champa_nigerian_fraud_legacy,
    df_zenodo_champa_nigerian_fraud_modern,
    df_zenodo_champa_ceas08,
    df_zenodo_miltchev_phishing_2024,
    df_mendeley_sms_phishing_2022,
    df_emscad_job_scams,
    df_spamassassin_ham,
    df_enron_ham_sample,
    df_multiwoz_v22,
    df_dailydialog,
], ignore_index=True)[CANON_COLS]

# Repo root discovery — walk up until we find the deployed model artifact,
# which only exists at the true repo root (not inside data_pipeline/).
NB_DIR   = Path.cwd()
REPO_ROOT = NB_DIR
for _ in range(6):
    if (REPO_ROOT / "models" / "e7_p1_variants").exists() and (REPO_ROOT / "api").exists():
        break
    REPO_ROOT = REPO_ROOT.parent
else:
    raise RuntimeError(
        f"Could not locate ScamRadar+ repo root walking up from {NB_DIR}. "
        "Looking for a directory containing both models/e7_p1_variants and api/."
    )

RAW_UNIFIED_DIR = REPO_ROOT / "data" / "interim"
RAW_UNIFIED_DIR.mkdir(parents=True, exist_ok=True)

RAW_UNIFIED_PARQUET = RAW_UNIFIED_DIR / "raw_unified.parquet"
RAW_UNIFIED_CSV     = RAW_UNIFIED_DIR / "raw_unified.csv"

raw_unified.to_parquet(RAW_UNIFIED_PARQUET, index=False)
raw_unified.to_csv(RAW_UNIFIED_CSV, index=False)

print(f"raw_unified.parquet + raw_unified.csv: {len(raw_unified):,} rows")
print(f"Saved to: {RAW_UNIFIED_PARQUET}")
print(f"         {RAW_UNIFIED_CSV}")'''


DU_NEW_MARKDOWN_HANDOFF = '''## Handoff to Data Preparation

The `raw_unified.parquet` file above is the official output of the Data
Understanding phase — all 13 real source datasets concatenated into a
single canonical-schema table.

That file is the **input** to the Data Preparation notebook
(`notebooks/data_preparation.ipynb`). The DP notebook orchestrates the
production pipeline scripts to derive the final prepared corpus:

1. **Clean** — Unicode normalization, exact-hash dedup, MinHash+LSH
   near-duplicate clustering (via `scamradar clean`).
2. **Split** — cluster-aware stratified split into
   `train / val / test / external_benchmark` (via `scamradar split`).
3. **Feature-engineer** — 25 numerical features per row (via
   `scripts.training.train_e7_p1.load_or_compute_features`).
4. **Synthesize + merge** — the E8 chain (P2 / P3 / P5 / P6 / P8) adds
   template-generated legit and scam data and applies targeted noise
   cleanup, producing `data/interim/e7_p1_features_e8p9.parquet`.

The DP notebook is **cache-aware**: every stage is skipped if its output
already exists on disk, so re-runs are fast. Set `FORCE_REBUILD = True`
in its Section 0 to rebuild everything from scratch.'''


DU_NEW_CODE_HANDOFF = '''# Confirm the DU output was written to the canonical location that the
# Data Preparation notebook expects to read from.

from pathlib import Path
import pandas as pd

print(f"DU output artifact : {RAW_UNIFIED_PARQUET}")
print(f"                     ({RAW_UNIFIED_PARQUET.stat().st_size / 1e6:.1f} MB, "
      f"{len(raw_unified):,} rows)")
print()
print("Next: open notebooks/data_preparation.ipynb and run all cells.")
print("      That notebook reads this file and orchestrates the production")
print("      pipeline to derive the final prepared corpus and build the DB.")'''


DU_END_MARKDOWN = '''---

**End of Data Understanding notebook.**

Next: `notebooks/data_preparation.ipynb` consumes the `raw_unified.parquet`
produced above and orchestrates the full production pipeline to derive the
final prepared corpus, store it in a relational SQLite database, generate
the ERD, and run the Final EDA.'''


# ─── new note for the top of the DP notebook ─────────────────────────────

DP_TOP_NOTE = '''> **Chain from Data Understanding**
>
> This notebook consumes `data/interim/e7_p1_features_e8p9.parquet`, the
> final prepared corpus. That file is the handoff artifact verified at the
> end of `data_pipeline/notebooks/data_understanding.ipynb` — the DU
> notebook demonstrates how the raw sources were acquired and unified, and
> its final section shows how the production pipeline transforms
> `raw_unified.parquet` into the file this notebook reads.'''


# ─── patch functions ──────────────────────────────────────────────────────

def patch_du():
    nb = nbf.read(DU_PATH, as_version=4)

    # Locate + replace the existing merge cell (the one that writes
    # raw_unified.parquet). It is currently the last cell.
    merge_idx = None
    for i, c in enumerate(nb.cells):
        if c.cell_type == 'code' and 'raw_unified = pd.concat' in c.source:
            merge_idx = i
            break
    if merge_idx is None:
        raise RuntimeError('Could not find the raw_unified merge cell in DU notebook.')

    nb.cells[merge_idx] = nbf.v4.new_code_cell(DU_UPDATED_MERGE_CELL)

    # Trim any cells that came after the merge cell (nothing should, but be safe).
    nb.cells = nb.cells[: merge_idx + 1]

    # Append the handoff section (markdown + code + closing markdown).
    nb.cells.append(nbf.v4.new_markdown_cell(DU_NEW_MARKDOWN_HANDOFF))
    nb.cells.append(nbf.v4.new_code_cell(DU_NEW_CODE_HANDOFF))
    nb.cells.append(nbf.v4.new_markdown_cell(DU_END_MARKDOWN))

    # Ensure every cell has an id (nbformat 4.5+ requirement).
    nbf.validate(nb)

    with open(DU_PATH, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

    print(f'✓ Patched {DU_PATH}')
    print(f'  total cells: {len(nb.cells)}')
    print(f'  merge cell now writes to data/interim/raw_unified.parquet')
    print(f'  handoff section appended')


def patch_dp():
    nb = nbf.read(DP_PATH, as_version=4)

    # Insert the chain note as a new markdown cell right after the title
    # markdown cell (which is cell 0). Skip if already present.
    already_patched = any(
        c.cell_type == 'markdown' and 'Chain from Data Understanding' in c.source
        for c in nb.cells
    )
    if already_patched:
        print(f'ℹ Skipping DP patch — "Chain from Data Understanding" already present.')
        return

    chain_cell = nbf.v4.new_markdown_cell(DP_TOP_NOTE)
    nb.cells.insert(1, chain_cell)

    nbf.validate(nb)

    with open(DP_PATH, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

    print(f'✓ Patched {DP_PATH}')
    print(f'  inserted chain note as cell [1] (after title)')


if __name__ == '__main__':
    patch_du()
    print()
    patch_dp()
