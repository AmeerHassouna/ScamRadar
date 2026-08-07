"""Dataset-approval gate (DESIGN §5, §16).

`require_dataset_approval()` is called at the top of every training / evaluation
command. It refuses to run unless:
  1. data/APPROVAL.json exists,
  2. its `dataset_hash` still matches the current dataset (recomputed live),
  3. its `accepted_red_flags` covers every red flag currently in the audit.

`approve_dataset()` prints the audit summary + red flags, asks the human to
confirm, and writes APPROVAL.json. This is the ONLY way past the gate — there is
no --skip-approval flag.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_PATH = Path("data/APPROVAL.json")
AUDIT_PATH = Path("reports/dataset_audit.json")
CLEAN_PATH = "data/interim/clean.parquet"


def _load_audit() -> dict:
    if not AUDIT_PATH.exists():
        raise SystemExit(
            "Missing reports/dataset_audit.json. Run:  python -m scamradar audit")
    return json.loads(AUDIT_PATH.read_text())


def _current_dataset_hash() -> str:
    # Recompute from the current clean.parquet so post-approval edits are caught.
    from . import audit as _audit
    import pandas as pd
    df = pd.read_parquet(CLEAN_PATH)
    return _audit._dataset_hash(df.sample_id)


def require_dataset_approval() -> dict:
    if not APPROVAL_PATH.exists():
        raise SystemExit(
            "REFUSED: no dataset approval on file (data/APPROVAL.json).\n"
            "Run:  python -m scamradar audit  &&  python -m scamradar approve-dataset\n"
            "See docs/DESIGN.md §1, §5, §16.")
    approval = json.loads(APPROVAL_PATH.read_text())

    live_hash = _current_dataset_hash()
    if approval.get("dataset_hash") != live_hash:
        raise SystemExit(
            "REFUSED: dataset changed since approval.\n"
            f"  approved hash: {approval.get('dataset_hash','?')[:12]}…\n"
            f"  current  hash: {live_hash[:12]}…\n"
            "Re-run:  python -m scamradar audit  &&  python -m scamradar approve-dataset")

    audit = _load_audit()
    current_flags = set(audit.get("red_flags", []))
    accepted = set(approval.get("accepted_red_flags", []))
    unaccepted = current_flags - accepted
    if unaccepted:
        raise SystemExit(
            "REFUSED: the current audit has red flags not accepted by the approval:\n  - "
            + "\n  - ".join(sorted(unaccepted))
            + "\nRe-run:  python -m scamradar approve-dataset")
    return approval


def _print_audit_summary(audit: dict) -> None:
    print("=" * 72)
    print("DATASET AUDIT — please review before approving")
    print("=" * 72)
    print(f"dataset_hash    : {audit['dataset_hash']}")
    print(f"total rows      : {audit['totals']['n']:,}")
    print(f"  scam          : {audit['totals']['n_scam']:,}")
    print(f"  legit         : {audit['totals']['n_legit']:,}")
    print(f"scam share      : {audit['class_balance']['scam_share']}")
    print(f"synthetic share : {audit['real_vs_synthetic']['synthetic_share']}")
    print(f"clusters        : {audit['clusters']['n_clusters']:,} "
          f"(largest = {audit['clusters']['largest_cluster_share']} of dataset)")
    print(f"exact dups removed         : {audit['dedup']['exact_duplicates_removed']:,}")
    print(f"rows in near-dup clusters  : {audit['dedup']['rows_in_near_dup_clusters']:,}")
    tc = audit.get("taxonomy_coverage", {})
    print(f"taxonomy covered           : "
          f"{sorted(tc.get('covered', {}).keys())}")
    print(f"taxonomy underrepresented  : "
          f"{sorted(tc.get('underrepresented', {}).keys())}")
    print(f"taxonomy missing           : {tc.get('missing', {})}")
    print("-" * 72)
    print(f"RED FLAGS ({len(audit['red_flags'])}):")
    if audit["red_flags"]:
        for f in audit["red_flags"]:
            print(f"  - {f}")
    else:
        print("  (none)")
    print("=" * 72)
    print("Full audit: reports/dataset_audit.md")
    print()


def approve_dataset(assume_yes: bool = False,
                    accept_red_flags: bool = False,
                    approver: str | None = None) -> dict:
    audit = _load_audit()
    _print_audit_summary(audit)

    red_flags = list(audit.get("red_flags", []))
    if red_flags and not accept_red_flags:
        print("This audit has red flags. To approve anyway, re-run with "
              "--accept-red-flags (and be prepared to justify it in the registry).")
        raise SystemExit(2)

    if not assume_yes:
        try:
            resp = input("Type 'I APPROVE' to sign off on this dataset: ").strip()
        except EOFError:
            resp = ""
        if resp != "I APPROVE":
            raise SystemExit("Approval aborted.")

    approver = approver or os.environ.get("USER") or "unknown"
    payload = {
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approver": approver,
        "dataset_hash": audit["dataset_hash"],
        "audit_totals": audit["totals"],
        "audit_class_balance": audit["class_balance"],
        "accepted_red_flags": red_flags,
    }
    APPROVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVAL_PATH.write_text(json.dumps(payload, indent=2))
    print(f"[approve-dataset] wrote {APPROVAL_PATH} "
          f"(hash={audit['dataset_hash'][:12]}…, approver={approver})")
    return payload
