"""Re-split train/val/test from the current clean.parquet WITHOUT touching
the frozen external benchmark.

Motivation: the batch1 v1 → v2b regeneration changed clean.parquet's contents.
The frozen external benchmark is real-only (per DESIGN §8) so its sample_ids
are all still present in the new clean.parquet — but train/val/test still
carry the stale v1 synthetic samples. This script re-runs the greedy
cluster-aware split on `clean − external_sample_ids` and rewrites the three
processed parquets. It never touches `data/external_benchmark/`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scamradar.split import _greedy_assign, FRACS, SEED


def main() -> None:
    df = pd.read_parquet("data/interim/clean.parquet")
    ext_df = pd.read_parquet(
        "data/external_benchmark/benchmark.parquet").reset_index(drop=True)
    ext_ids = set(ext_df.sample_id)

    before = len(df)
    df = df[~df.sample_id.isin(ext_ids)].reset_index(drop=True)
    print(f"[resplit] clean rows: {before:,} -> {len(df):,} after excluding "
          f"{len(ext_ids):,} external sample_ids")

    cstats = df.groupby("cluster_id").agg(
        n=("sample_id", "size"), n_scam=("label", "sum"))

    denom = cstats.n.sum()
    f_test = FRACS["test"] * len(df) / denom
    f_val = FRACS["val"] * len(df) / denom
    tv = _greedy_assign(cstats, {"test": f_test, "val": f_val,
                                 "train": max(1.0 - f_test - f_val, 0.05)},
                        SEED + 1)
    df["split"] = df.cluster_id.map(tv)

    # Leakage assertion within train/val/test
    for a in ["train", "val", "test"]:
        for b in ["train", "val", "test"]:
            if a >= b:
                continue
            ca = set(df.loc[df.split == a, "cluster_id"])
            cb = set(df.loc[df.split == b, "cluster_id"])
            ha = set(df.loc[df.split == a, "exact_hash"])
            hb = set(df.loc[df.split == b, "exact_hash"])
            assert not (ca & cb), f"CLUSTER LEAK {a}/{b}"
            assert not (ha & hb), f"EXACT-HASH LEAK {a}/{b}"

    # External leak check by sample_id
    for s in ["train", "val", "test"]:
        s_ids = set(df.loc[df.split == s, "sample_id"])
        assert not (s_ids & ext_ids), f"EXTERNAL sample_id LEAK into {s}"

    Path("data/processed").mkdir(parents=True, exist_ok=True)
    for s in ["train", "val", "test"]:
        sub = df[df.split == s].drop(columns="split")
        sub.to_parquet(f"data/processed/{s}.parquet", index=False)
        print(f"[resplit] {s}: {len(sub):,} rows "
              f"(scam_share={float(sub.label.mean()):.4f}, "
              f"synth={int(sub.is_synthetic.sum()):,})")

    print(f"[resplit] external unchanged: {len(ext_df):,} rows "
          f"(scam_share={float(ext_df.label.mean()):.4f})")


if __name__ == "__main__":
    main()
