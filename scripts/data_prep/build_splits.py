"""
Build the deterministic dedup-cluster split used by v1.1_candidate onwards.

  python scripts/build_splits.py

Reads:  data/db 4.db
Writes: outputs/split_v1.json   { cluster_id: 'train' | 'test' }
        outputs/split_v1_summary.txt (human-readable)

Design:
  * Dedup on normalised text (src/_00_dedup.py)
  * 80/20 split at the CLUSTER level (never a row level)
  * Stratified by label — per-label random split, then merged
  * Seed=42 for reproducibility
  * Every future retrain reads this file so the split is stable
"""

import os, sys, json, sqlite3
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src._00_dedup import add_cluster_ids, dedup_by_cluster

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'db 4.db')
OUT_DIR  = os.path.join(BASE_DIR, 'outputs')
JSON_PATH = os.path.join(OUT_DIR, 'split_v1.json')
TXT_PATH  = os.path.join(OUT_DIR, 'split_v1_summary.txt')

SEED = 42
TEST_SIZE = 0.20

os.makedirs(OUT_DIR, exist_ok=True)

# ── Load ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT m.message_id, m.raw_text, m.label, ds.name AS source, c.type AS channel
    FROM Message m
    JOIN DataSource ds ON m.source_id = ds.source_id
    JOIN Channel    c  ON m.channel_id = c.channel_id
""", conn)
conn.close()
print(f"Loaded {len(df):,} rows")

# ── Dedup ───────────────────────────────────────────────────────────────────
df = add_cluster_ids(df)
deduped = dedup_by_cluster(df)
print(f"After dedup: {len(deduped):,} unique clusters")

# ── Stratified per-label random split at cluster level ─────────────────────
rng = np.random.RandomState(SEED)
assignments = {}

for label in [0, 1]:
    sub = deduped[deduped['label'] == label]
    clusters = sub['cluster_id'].to_numpy()
    n = len(clusters)
    n_test = int(round(n * TEST_SIZE))
    perm = rng.permutation(n)
    test_set = set(clusters[perm[:n_test]])
    for cid in clusters:
        assignments[cid] = 'test' if cid in test_set else 'train'

# Sanity: every cluster is assigned exactly once
assert len(assignments) == len(deduped)

# ── Write JSON ──────────────────────────────────────────────────────────────
with open(JSON_PATH, 'w') as f:
    json.dump(assignments, f)
print(f"\nWrote {len(assignments):,} cluster assignments → {JSON_PATH}")

# ── Human-readable summary ─────────────────────────────────────────────────
deduped['split'] = deduped['cluster_id'].map(assignments)

lines = [
    f"Split v1 — dedup-cluster-aware, label-stratified 80/20 (seed={SEED})",
    "=" * 66,
    f"Total rows (pre-dedup):    {len(df):>7,}",
    f"Unique clusters:           {len(deduped):>7,}",
    f"Split size (clusters):     train={sum(v=='train' for v in assignments.values()):>6,}  "
    f"test={sum(v=='test' for v in assignments.values()):>6,}",
    "",
    "Per-split label balance (clusters):",
]
for split in ['train', 'test']:
    sub = deduped[deduped['split'] == split]
    scam = (sub.label == 1).sum(); leg = (sub.label == 0).sum()
    lines.append(f"  {split:<6}  scam={scam:>5,}  legit={leg:>5,}  "
                 f"(scam frac = {scam/len(sub):.3f})")
lines += ["", "Per-source split (clusters):"]
for src, sub in deduped.groupby('source'):
    tr = (sub.split=='train').sum(); te = (sub.split=='test').sum()
    lines.append(f"  {src:<26}  train={tr:>5,}  test={te:>4,}")

summary = "\n".join(lines)
print("\n" + summary)
with open(TXT_PATH, 'w') as f:
    f.write(summary + "\n")
print(f"\nWrote human-readable summary → {TXT_PATH}")
