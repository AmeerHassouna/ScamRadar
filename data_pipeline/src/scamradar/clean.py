"""Stage 1 — cleaning & quality (spec §2).

Exact dedup (normalized SHA-1), near-duplicate clustering (MinHash 128 perms over
char 5-gram shingles + LSH 32 bands x 4 rows, union-find), quality report.
Cluster IDs are attached to every row and later drive cluster-aware splitting.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
NUM_RE = re.compile(r"\d")
WS_RE = re.compile(r"\s+")

# LSH threshold ~ (1/bands)^(1/rows) = (1/16)^(1/8) ~= 0.71 Jaccard
N_PERM, N_BANDS, ROWS_PER_BAND = 128, 16, 8
_rng = np.random.RandomState(1337)
_A = _rng.randint(1, 2**31 - 1, N_PERM).astype(np.uint64)
_B = _rng.randint(0, 2**31 - 1, N_PERM).astype(np.uint64)
_P = np.uint64(2**31 - 1)


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text)).lower()
    t = URL_RE.sub(" <url> ", t)
    t = NUM_RE.sub("0", t)
    return WS_RE.sub(" ", t).strip()


def exact_hash(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8", "ignore")).hexdigest()


def _shingle_hashes(norm: str, k: int = 5) -> np.ndarray:
    if len(norm) < k:
        norm = norm + " " * (k - len(norm))
    hs = {hash(norm[i:i + k]) & 0x7FFFFFFF for i in range(len(norm) - k + 1)}
    return np.fromiter(hs, dtype=np.uint64, count=len(hs))


def minhash(norm: str) -> np.ndarray:
    sh = _shingle_hashes(norm)
    # (n_perm, n_shingles) permuted hashes -> min over shingles
    return ((np.outer(_A, sh) + _B[:, None]) % _P).min(axis=1)


class _UF:
    def __init__(self, n): self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def near_dup_clusters(norms: list[str]) -> np.ndarray:
    sigs = np.stack([minhash(n) for n in norms])
    uf = _UF(len(norms))
    for b in range(N_BANDS):
        band = sigs[:, b * ROWS_PER_BAND:(b + 1) * ROWS_PER_BAND]
        buckets = defaultdict(list)
        for i, row in enumerate(band):
            buckets[row.tobytes()].append(i)
        for members in buckets.values():
            for j in members[1:]:
                uf.union(members[0], j)
    return np.array([uf.find(i) for i in range(len(norms))])


def run(inp="data/raw/canonical.parquet", out="data/interim/clean.parquet") -> Path:
    df = pd.read_parquet(inp)
    n0 = len(df)
    df["text"] = df.text.astype(str)
    df = df[df.text.str.strip().str.len() >= 5].copy()
    df["norm"] = df.text.map(normalize)
    df["exact_hash"] = df.norm.map(
        lambda n: hashlib.sha1(n.encode("utf-8", "ignore")).hexdigest())

    # exact dedup (keep first occurrence; provenance of drops recorded)
    before = len(df)
    df = df.drop_duplicates("exact_hash", keep="first").reset_index(drop=True)
    exact_removed = before - len(df)

    # near-dup clustering (kept, but clustered — splitting will respect clusters)
    df["cluster_id"] = near_dup_clusters(df.norm.tolist())
    cluster_sizes = df.cluster_id.value_counts()
    near_dup_rows = int((cluster_sizes[cluster_sizes > 1]).sum())

    report = {
        "rows_in": n0, "rows_out": int(len(df)),
        "exact_duplicates_removed": int(exact_removed),
        "near_duplicate_clusters_gt1": int((cluster_sizes > 1).sum()),
        "rows_in_near_dup_clusters": near_dup_rows,
        "class_balance": df.label.value_counts(normalize=True).round(4).to_dict(),
        "per_category": df.groupby("category").size().sort_values(ascending=False).to_dict(),
        "per_source": df.groupby("source").size().to_dict(),
        "synthetic_share": float(df.is_synthetic.mean()),
        "era_share": df.era.value_counts(normalize=True).round(4).to_dict(),
        "length_chars": {k: float(v) for k, v in
                         df.text.str.len().describe()[["mean", "50%", "max"]].items()},
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/data_quality.json").write_text(json.dumps(report, indent=2, default=str))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.drop(columns=["norm"]).to_parquet(out, index=False)
    print(f"[clean] {n0} -> {len(df)} rows | exact dups removed: {exact_removed} | "
          f"near-dup clusters: {report['near_duplicate_clusters_gt1']}")
    return Path(out)
