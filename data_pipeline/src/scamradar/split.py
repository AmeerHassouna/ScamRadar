"""Stage 2 — cluster-aware stratified split + write-once external benchmark (spec §2).

Whole near-duplicate clusters are assigned to exactly one of
{train, val, test, external}. The external benchmark:
  * real data only (is_synthetic == False) from benchmark-eligible sources,
  * carved out FIRST, then never read again until eval --external,
  * protected by data/external_benchmark/LOCK.json.
Leakage assertions run at the end and fail hard on any violation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .sources import get as get_source

FRACS = {"external": 0.10, "test": 0.15, "val": 0.15}  # remainder -> train
SEED = 42


def _greedy_assign(clusters: pd.DataFrame, targets: dict[str, float], seed: int) -> dict:
    """Assign clusters to splits, balancing per-split scam share toward global share.
    clusters: index=cluster_id, cols n (size), n_scam."""
    rng = np.random.RandomState(seed)
    order = clusters.sample(frac=1.0, random_state=rng).sort_values("n", ascending=False)
    total = clusters.n.sum()
    goal = {s: f * total for s, f in targets.items()}
    got = {s: 0.0 for s in targets}
    got_scam = {s: 0.0 for s in targets}
    global_scam = clusters.n_scam.sum() / max(total, 1)
    assign = {}
    for cid, row in order.iterrows():
        # candidates still under quota (or least-full as fallback)
        cands = [s for s in targets if got[s] < goal[s]] or list(targets)
        # pick the candidate whose scam-ratio deviates most in the direction this cluster fixes
        def score(s):
            cur = got_scam[s] / got[s] if got[s] else global_scam
            new = (got_scam[s] + row.n_scam) / (got[s] + row.n)
            delta = abs(new - global_scam) - abs(cur - global_scam)
            return (round(delta, 6), got[s] - goal[s])  # tie-break: most room left
        best = min(cands, key=score)
        assign[cid] = best
        got[best] += row.n
        got_scam[best] += row.n_scam
    return assign


def run(inp="data/interim/clean.parquet") -> None:
    df = pd.read_parquet(inp)
    df["benchmark_eligible"] = df.source.map(lambda s: get_source(s).benchmark_eligible) \
                               & ~df.is_synthetic

    cstats = df.groupby("cluster_id").agg(
        n=("sample_id", "size"), n_scam=("label", "sum"),
        eligible=("benchmark_eligible", "all"))

    # 1) external benchmark from eligible clusters only
    elig = cstats[cstats.eligible]
    f_ext = min(FRACS["external"] * len(df) / max(elig.n.sum(), 1), 0.9)
    ext_assign = _greedy_assign(elig, {"external": f_ext, "rest": 1.0 - f_ext}, SEED)
    ext_ids = {c for c, s in ext_assign.items() if s == "external"}

    # 2) remaining clusters -> train/val/test
    rest = cstats[~cstats.index.isin(ext_ids)]
    denom = rest.n.sum()
    f_test = FRACS["test"] * len(df) / denom
    f_val = FRACS["val"] * len(df) / denom
    tv = _greedy_assign(rest, {"test": f_test, "val": f_val,
                               "train": max(1.0 - f_test - f_val, 0.05)}, SEED + 1)

    df["split"] = df.cluster_id.map(lambda c: "external" if c in ext_ids else tv[c])

    # leakage assertions (spec §2/§12)
    for a in ["train", "val", "test", "external"]:
        for b in ["train", "val", "test", "external"]:
            if a >= b:
                continue
            ca = set(df.loc[df.split == a, "cluster_id"])
            cb = set(df.loc[df.split == b, "cluster_id"])
            ha = set(df.loc[df.split == a, "exact_hash"])
            hb = set(df.loc[df.split == b, "exact_hash"])
            assert not (ca & cb), f"CLUSTER LEAK between {a}/{b}"
            assert not (ha & hb), f"EXACT-HASH LEAK between {a}/{b}"

    Path("data/processed").mkdir(parents=True, exist_ok=True)
    for s in ["train", "val", "test"]:
        df[df.split == s].drop(columns="split").to_parquet(
            f"data/processed/{s}.parquet", index=False)

    ext_dir = Path("data/external_benchmark")
    ext_dir.mkdir(parents=True, exist_ok=True)
    lock = ext_dir / "LOCK.json"
    ext = df[df.split == "external"].drop(columns="split")
    if lock.exists() and json.loads(lock.read_text()).get("frozen"):
        print("[split] external benchmark already frozen — NOT overwriting it.")
    else:
        ext.to_parquet(ext_dir / "benchmark.parquet", index=False)
        lock.write_text(json.dumps({"frozen": True, "rows": int(len(ext)),
                                    "evaluated": False, "access_log": []}, indent=2))

    summary = {s: {"rows": int((df.split == s).sum()),
                   "scam_share": round(float(df.loc[df.split == s, "label"].mean()), 4)}
               for s in ["train", "val", "test", "external"]}
    Path("reports/split_summary.json").write_text(json.dumps(summary, indent=2))
    print("[split]", json.dumps(summary))
