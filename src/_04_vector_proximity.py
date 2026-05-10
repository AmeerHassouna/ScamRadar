"""
ScamRadar+ | Step 04: Vector Proximity  (v5)
Sentence Transformers + FAISS — dual index (scam + legit), k=10,
REBUILD_INDEX flag to skip re-encoding when embeddings already exist.
"""

import numpy as np
import faiss
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MODELS_PATH, FAISS_K_SCAM, FAISS_K_LEGIT, REBUILD_INDEX

os.makedirs(MODELS_PATH, exist_ok=True)

_EMBEDDINGS_PATH   = os.path.join(MODELS_PATH, 'embeddings.npy')
_SCAM_INDEX_PATH   = os.path.join(MODELS_PATH, 'scam_faiss.index')
_LEGIT_INDEX_PATH  = os.path.join(MODELS_PATH, 'legit_faiss.index')


def load_sentence_model():
    from sentence_transformers import SentenceTransformer
    print("Loading Sentence Transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"✅ Model loaded! Embedding dim: {model.get_embedding_dimension()}")
    return model


def encode_messages(model, texts, batch_size=128):
    """Encode texts — skips if embeddings.npy exists and REBUILD_INDEX=False."""
    if not REBUILD_INDEX and os.path.exists(_EMBEDDINGS_PATH):
        print(f"✅ Loading cached embeddings from {_EMBEDDINGS_PATH}")
        return np.load(_EMBEDDINGS_PATH)

    print(f"Encoding {len(texts)} messages (REBUILD_INDEX=True)...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    print(f"✅ Embeddings shape: {embeddings.shape}")
    return embeddings


def build_faiss_index(embeddings: np.ndarray, labels: np.ndarray):
    """Build scam FAISS index from embeddings where label==1."""
    scam_mask = labels == 1
    scam_emb  = embeddings[scam_mask].astype('float32')
    faiss.normalize_L2(scam_emb)

    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(scam_emb)
    print(f"✅ Scam FAISS index: {index.ntotal} vectors")
    return index


def build_legit_faiss_index(embeddings: np.ndarray, labels: np.ndarray):
    """Build legit FAISS index from embeddings where label==0."""
    legit_mask = labels == 0
    legit_emb  = embeddings[legit_mask].astype('float32')
    faiss.normalize_L2(legit_emb)

    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(legit_emb)
    print(f"✅ Legit FAISS index: {index.ntotal} vectors")
    return index


def compute_proximity_scores(embeddings: np.ndarray, scam_index,
                              legit_index=None,
                              k_scam: int = FAISS_K_SCAM,
                              k_legit: int = FAISS_K_LEGIT):
    """
    Returns (scam_scores, legit_scores, delta_scores).
    legit_scores / delta_scores are None if legit_index is None.
    """
    print("Computing proximity scores...")
    norm = embeddings.astype('float32').copy()
    faiss.normalize_L2(norm)

    D_scam, _ = scam_index.search(norm, k=k_scam)
    scam_scores = D_scam.mean(axis=1)

    if legit_index is not None:
        D_legit, _  = legit_index.search(norm, k=k_legit)
        legit_scores = D_legit.mean(axis=1)
        delta_scores = scam_scores - legit_scores
    else:
        legit_scores = None
        delta_scores = None

    print("✅ Proximity scores computed!")
    return scam_scores, legit_scores, delta_scores


def save_faiss_index(scam_index, embeddings, legit_index=None):
    faiss.write_index(scam_index, _SCAM_INDEX_PATH)
    np.save(_EMBEDDINGS_PATH, embeddings)
    if legit_index is not None:
        faiss.write_index(legit_index, _LEGIT_INDEX_PATH)
        print("✅ Scam + legit FAISS indices and embeddings saved!")
    else:
        print("✅ Scam FAISS index and embeddings saved!")


def load_faiss_index():
    index = faiss.read_index(_SCAM_INDEX_PATH)
    print(f"✅ Scam FAISS index loaded: {index.ntotal} vectors")
    return index


def load_legit_faiss_index():
    if not os.path.exists(_LEGIT_INDEX_PATH):
        return None
    index = faiss.read_index(_LEGIT_INDEX_PATH)
    print(f"✅ Legit FAISS index loaded: {index.ntotal} vectors")
    return index


def get_similar_scams(text: str, model, scam_index, scam_texts, k: int = 3):
    """Return top-k most similar known scam messages."""
    emb = model.encode([text], convert_to_numpy=True).astype('float32')
    faiss.normalize_L2(emb)
    D, I = scam_index.search(emb, k=k)
    return [
        {'similarity': round(float(d), 4), 'message': scam_texts[i][:150]}
        for d, i in zip(D[0], I[0])
    ]
