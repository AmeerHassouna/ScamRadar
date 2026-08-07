"""Append-only experiment registry (spec §9–§10). Never overwrites; every record
carries dataset content hashes so any run is reproducible from its record."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REG = Path("experiments/registry.jsonl")


def _file_hash(p: str) -> str | None:
    f = Path(p)
    return hashlib.sha1(f.read_bytes()).hexdigest()[:12] if f.exists() else None


def log(objective: str, hypothesis: str, config: dict, metrics: dict,
        conclusion: str = "") -> dict:
    rec = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "at": datetime.now(timezone.utc).isoformat(),
        "objective": objective,
        "hypothesis": hypothesis,
        "config": config,
        "dataset_versions": {s: _file_hash(f"data/processed/{s}.parquet")
                             for s in ("train", "val", "test")},
        "external_benchmark_version": _file_hash("data/external_benchmark/benchmark.parquet"),
        "metrics": metrics,
        "conclusion": conclusion,
    }
    REG.parent.mkdir(exist_ok=True)
    with REG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
