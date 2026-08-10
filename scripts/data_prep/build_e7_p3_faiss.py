"""
E7-P3 Phase 1 — Encode E5 corpus + build FAISS indices.

Reads E5's train/val/test/external parquets, encodes every row with
all-MiniLM-L6-v2, builds two FAISS L2 indices (scam-only + legit-only
from training rows), and saves:

  models/e7_p3_faiss/embeddings_all.npy       — (253k, 384) float32
  models/e7_p3_faiss/scam_index.faiss         — training-scam FAISS L2
  models/e7_p3_faiss/legit_index.faiss        — training-legit FAISS L2
  models/e7_p3_faiss/manifest.json            — metadata + shapes

Uses IndexFlatL2 (exact search — no approximation, deterministic). Total
memory footprint at inference time: MiniLM ~90MB + two FAISS indices
~250MB + numpy embeddings for scoring ~350MB.
"""
from __future__ import annotations

import os, sys, json, time, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BASE_A = _ROOT
BASE_B = '/Users/ameer/Downloads/scamradar2'
OUT_DIR = os.path.join(BASE_A, 'models', 'e7_p3_faiss')
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    print('=== E7-P3 Phase 1: encode + build FAISS ===', flush=True)

    # Load all splits with indices preserved so we can align to features later
    print('Loading E5 splits...', flush=True)
    train = pd.read_parquet(f'{BASE_B}/data/processed/train.parquet')[['text','label']]
    val   = pd.read_parquet(f'{BASE_B}/data/processed/val.parquet')[['text','label']]
    test  = pd.read_parquet(f'{BASE_B}/data/processed/test.parquet')[['text','label']]
    ext   = pd.read_parquet(f'{BASE_B}/data/external_benchmark/benchmark.parquet')[['text','label']]
    train['split']='train'; val['split']='val'; test['split']='test'; ext['split']='external'
    combined = pd.concat([train, val, test, ext], ignore_index=True)
    print(f'  total rows: {len(combined):,}  '
          f'(train={len(train):,} val={len(val):,} test={len(test):,} ext={len(ext):,})', flush=True)

    # Load MiniLM
    print('Loading all-MiniLM-L6-v2...', flush=True)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    dim = model.get_sentence_embedding_dimension()
    print(f'  embedding dim: {dim}', flush=True)

    # Encode in batches
    embed_path = os.path.join(OUT_DIR, 'embeddings_all.npy')
    if os.path.exists(embed_path):
        print(f'Loading cached embeddings from {embed_path}...', flush=True)
        embs = np.load(embed_path)
        assert len(embs) == len(combined), 'cached embeddings shape mismatch'
    else:
        print(f'Encoding {len(combined):,} texts (batch=64)...', flush=True)
        t0 = time.time()
        embs = model.encode(
            combined.text.tolist(),
            batch_size=64,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=False,
        ).astype(np.float32)
        print(f'  encoded in {time.time()-t0:.0f}s  shape={embs.shape}', flush=True)
        np.save(embed_path, embs)
        print(f'  saved {embed_path}', flush=True)

    # Build FAISS indices from TRAINING rows only (never leak val/test/external)
    print('Building FAISS indices (training rows only)...', flush=True)
    import faiss
    train_mask = (combined.split == 'train').values
    train_scam_mask  = train_mask & (combined.label.values == 1)
    train_legit_mask = train_mask & (combined.label.values == 0)

    scam_embs  = embs[train_scam_mask].copy()
    legit_embs = embs[train_legit_mask].copy()
    print(f'  scam training rows:  {len(scam_embs):,}', flush=True)
    print(f'  legit training rows: {len(legit_embs):,}', flush=True)

    scam_idx = faiss.IndexFlatL2(dim)
    scam_idx.add(scam_embs)
    faiss.write_index(scam_idx, os.path.join(OUT_DIR, 'scam_index.faiss'))
    print(f'  wrote scam_index.faiss (ntotal={scam_idx.ntotal})', flush=True)

    legit_idx = faiss.IndexFlatL2(dim)
    legit_idx.add(legit_embs)
    faiss.write_index(legit_idx, os.path.join(OUT_DIR, 'legit_index.faiss'))
    print(f'  wrote legit_index.faiss (ntotal={legit_idx.ntotal})', flush=True)

    # Manifest
    manifest = {
        'model': 'all-MiniLM-L6-v2',
        'embedding_dim': dim,
        'total_encoded_rows': int(len(combined)),
        'scam_index_size': int(scam_idx.ntotal),
        'legit_index_size': int(legit_idx.ntotal),
        'index_type': 'IndexFlatL2 (exact search)',
        'source_splits': {'train': int(len(train)), 'val': int(len(val)),
                          'test': int(len(test)), 'external': int(len(ext))},
        'built_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f'  wrote manifest.json')

    # Also save the split arrays so downstream can reproduce ordering
    np.save(os.path.join(OUT_DIR, 'splits.npy'), combined.split.values)
    np.save(os.path.join(OUT_DIR, 'labels.npy'), combined.label.values)

    print('\nDone.', flush=True)


if __name__ == '__main__':
    main()
