"""
E7-P3 Phase 2 — Compute proximity features for every training row.

Uses the FAISS indices built by build_e7_p3_faiss.py. For each row:
  proximity_scam_score  = 1 - (mean L2 distance to top-K nearest scam neighbours) / sqrt(dim)
  proximity_legit_score = 1 - (mean L2 distance to top-K nearest legit neighbours) / sqrt(dim)
  proximity_delta       = proximity_scam_score - proximity_legit_score

Writes the extended features parquet:
  data/interim/e7_p3_features.parquet  =  e7_p1_features.parquet + 3 new columns.

K=10 matches v1.x's FAISS_K_SCAM/FAISS_K_LEGIT.
"""
from __future__ import annotations

import os, sys, time, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BASE_A = _ROOT
FAISS_DIR = os.path.join(BASE_A, 'models', 'e7_p3_faiss')
FEAT_IN   = os.path.join(BASE_A, 'data', 'interim', 'e7_p1_features.parquet')
FEAT_OUT  = os.path.join(BASE_A, 'data', 'interim', 'e7_p3_features.parquet')

K = 10   # match v1.x FAISS_K_SCAM / FAISS_K_LEGIT


def main():
    import faiss

    print('=== E7-P3 Phase 2: compute proximity features ===', flush=True)

    print(f'Loading embeddings + FAISS indices from {FAISS_DIR}...', flush=True)
    embs = np.load(f'{FAISS_DIR}/embeddings_all.npy')
    splits = np.load(f'{FAISS_DIR}/splits.npy', allow_pickle=True)
    scam_idx = faiss.read_index(f'{FAISS_DIR}/scam_index.faiss')
    legit_idx = faiss.read_index(f'{FAISS_DIR}/legit_index.faiss')
    dim = embs.shape[1]
    print(f'  embeddings: {embs.shape}   splits: {splits.shape}   '
          f'scam_idx.ntotal={scam_idx.ntotal}   legit_idx.ntotal={legit_idx.ntotal}', flush=True)

    # L2 normalisation constant — bounds distances to a comparable scale
    norm_factor = float(np.sqrt(dim))

    print(f'Computing top-{K} nearest-neighbour distances for {len(embs):,} rows...', flush=True)
    t0 = time.time()
    # scam_dists shape: (n, K)
    scam_dists, _ = scam_idx.search(embs, K)
    legit_dists, _ = legit_idx.search(embs, K)
    print(f'  FAISS search done in {time.time()-t0:.0f}s', flush=True)

    # Convert to similarity: 1 - mean_L2 / sqrt(dim)
    # Higher = more similar to that class
    scam_sim  = 1.0 - (scam_dists.mean(axis=1)  / norm_factor)
    legit_sim = 1.0 - (legit_dists.mean(axis=1) / norm_factor)
    delta = scam_sim - legit_sim

    print('Loading E7-P1 features parquet to extend...', flush=True)
    feats = pd.read_parquet(FEAT_IN)
    assert len(feats) == len(embs), f'row count mismatch: {len(feats)} vs {len(embs)}'
    # Sanity check split alignment
    assert (feats.split.values == splits).all(), 'split alignment mismatch'

    feats['proximity_scam_score']  = scam_sim.astype(np.float32)
    feats['proximity_legit_score'] = legit_sim.astype(np.float32)
    feats['proximity_delta']       = delta.astype(np.float32)

    print(f'Summary stats:', flush=True)
    for col in ['proximity_scam_score', 'proximity_legit_score', 'proximity_delta']:
        v = feats[col]
        print(f'  {col:24s} min={v.min():.4f}  max={v.max():.4f}  '
              f'mean={v.mean():.4f}  std={v.std():.4f}', flush=True)

    # Sanity: on train, scam rows should have higher proximity_scam than legit rows
    tr = feats[feats.split=='train']
    print(f'\nSeparation check (train):', flush=True)
    for label in [0, 1]:
        rows = tr[tr.label == label]
        print(f'  label={label}  scam_sim={rows.proximity_scam_score.mean():.4f}  '
              f'legit_sim={rows.proximity_legit_score.mean():.4f}  '
              f'delta={rows.proximity_delta.mean():.4f}', flush=True)

    feats.to_parquet(FEAT_OUT, index=False)
    print(f'\nWrote {FEAT_OUT}  ({len(feats):,} rows)', flush=True)


if __name__ == '__main__':
    main()
