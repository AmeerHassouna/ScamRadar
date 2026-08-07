"""Stage 3 — mandatory dataset audit (DESIGN §5).

Reads data/interim/clean.parquet, writes reports/dataset_audit.{json,md}, and
computes a stable `dataset_hash` that the approval gate binds to.

Nothing downstream (ablate/bakeoff/tune/fit/eval/external) may run until
`python -m scamradar approve-dataset` writes data/APPROVAL.json against the
hash produced here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .sources import get as get_source

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)

CATEGORY_FLOOR = 200                 # min samples per taxonomy category before "covered"
SYNTHETIC_CAP_PER_CATEGORY = 0.25    # DESIGN §7
SOURCE_DOMINANCE_CAP = 0.40          # DESIGN §6
CLASS_BALANCE_RANGE = (0.10, 0.90)   # scam-share must sit inside this
                                     # (loosened from 0.15 — real-world scam
                                     # prevalence is often < 15%; treating a
                                     # slightly-legit-heavy corpus as a red flag
                                     # was over-conservative)
CLUSTER_DOMINANCE_CAP = 0.05         # single cluster > 5% of dataset
MODERN_SCAM_SHARE_FLOOR = 0.30       # modern share within the scam class
MODERN_OVERALL_SHARE_FLOOR = 0.25    # modern share overall
UNKNOWN_ERA_SHARE_CAP = 0.10         # too many rows without era tag

# Target taxonomy (see reports/benchmark_plan.md). Any taxonomy category with
# 0 rows = missing; 0 < rows < CATEGORY_FLOOR = underrepresented.
TARGET_TAXONOMY: dict[str, list[str]] = {
    "scam": [
        "email_phishing",
        "smishing",
        "recruitment_scam",
        "advance_fee_fraud",
        "romance_scam",
        "bec_ceo_fraud",
        "marketplace_delivery_scam",
    ],
    "legit": [
        "ham_email",
        "ham_sms",
        "ham_chat",
    ],
}


def _dataset_hash(sample_ids: pd.Series) -> str:
    joined = "\n".join(sorted(str(s) for s in sample_ids.tolist()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _pct(x: float) -> float:
    return round(float(x), 4)


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


def _describe_length(s: pd.Series) -> dict:
    q = s.quantile([0.05, 0.5, 0.95])
    return {
        "mean": float(s.mean()),
        "p5": float(q.loc[0.05]),
        "p50": float(q.loc[0.5]),
        "p95": float(q.loc[0.95]),
        "max": int(s.max()),
    }


def _era_shares(df: pd.DataFrame) -> dict:
    """Legacy / modern / unknown shares, overall and within the scam class."""
    def _shares(sub: pd.DataFrame) -> dict:
        if not len(sub):
            return {"legacy": 0.0, "modern": 0.0, "unknown": 0.0}
        era = sub.get("era")
        if era is None:
            return {"legacy": 0.0, "modern": 0.0, "unknown": 1.0}
        e = era.fillna("unknown").astype(str)
        e = e.where(e.isin(["legacy", "modern"]), "unknown")
        vc = e.value_counts(normalize=True).to_dict()
        return {k: _pct(vc.get(k, 0.0)) for k in ("legacy", "modern", "unknown")}
    return {
        "overall": _shares(df),
        "scam": _shares(df[df.label == 1]),
        "legit": _shares(df[df.label == 0]),
    }


def _taxonomy_coverage(per_category: dict[str, int]) -> dict:
    """Bucket taxonomy categories into covered / underrepresented / missing.
    Also list `out_of_taxonomy` categories (in the data but not in the target)."""
    taxonomy_flat = {c for cats in TARGET_TAXONOMY.values() for c in cats}
    covered: dict[str, dict[str, int]] = {}
    underrep: dict[str, dict[str, int]] = {}
    missing: dict[str, list[str]] = {}
    for cls, cats in TARGET_TAXONOMY.items():
        for cat in cats:
            n = int(per_category.get(cat, 0))
            entry = {"class": cls, "n": n}
            if n == 0:
                missing.setdefault(cls, []).append(cat)
            elif n < CATEGORY_FLOOR:
                underrep[cat] = entry
            else:
                covered[cat] = entry
    out_of_taxonomy = {c: int(n) for c, n in per_category.items()
                       if c not in taxonomy_flat}
    return {
        "target_taxonomy": TARGET_TAXONOMY,
        "category_floor": CATEGORY_FLOOR,
        "covered": covered,
        "underrepresented": underrep,
        "missing": missing,
        "out_of_taxonomy": out_of_taxonomy,
    }


def _compute_red_flags(rep: dict) -> list[str]:
    flags: list[str] = []
    scam_share = rep["class_balance"]["scam_share"]
    if not (CLASS_BALANCE_RANGE[0] <= scam_share <= CLASS_BALANCE_RANGE[1]):
        flags.append(f"class_balance_out_of_range: scam_share={scam_share} "
                     f"outside {CLASS_BALANCE_RANGE}")

    # Target-taxonomy validation (Rule 2)
    tax = rep["taxonomy_coverage"]
    for cls, cats in tax["missing"].items():
        if cats:
            flags.append(f"taxonomy_missing[{cls}]: {sorted(cats)}")
    if tax["underrepresented"]:
        under = sorted(tax["underrepresented"].keys())
        flags.append(f"taxonomy_underrepresented(<{CATEGORY_FLOOR}): {under}")

    # Synthetic cap check — nuanced:
    #   * If a category has ANY real data, synthetic must stay under 25%.
    #   * If a category has ONLY synthetic (no real corpus yet found),
    #     that's a documented state, not a cap violation. Reported separately.
    for cat, comp in rep["category_composition"].items():
        real, synth, share = comp["real"], comp["synthetic"], comp["synthetic_share"]
        if real == 0 and synth > 0:
            flags.append(f"category_is_synthetic_only[{cat}]: {synth} rows, "
                         f"0 real. Requires written justification in "
                         f"docs/notes/ per DESIGN §7.")
        elif real > 0 and share > SYNTHETIC_CAP_PER_CATEGORY:
            flags.append(f"synthetic_over_cap[{cat}]: {share:.3f} "
                         f"> {SYNTHETIC_CAP_PER_CATEGORY} "
                         f"(real={real}, synthetic={synth})")

    for cls_name, srcs in rep["source_share_within_class"].items():
        top = max(srcs.items(), key=lambda kv: kv[1], default=(None, 0))
        if top[1] > SOURCE_DOMINANCE_CAP:
            flags.append(f"source_dominates_{cls_name}: {top[0]}={top[1]:.3f} "
                         f"> {SOURCE_DOMINANCE_CAP}")

    if rep["clusters"]["largest_cluster_share"] > CLUSTER_DOMINANCE_CAP:
        flags.append(f"cluster_dominance: largest cluster is "
                     f"{rep['clusters']['largest_cluster_share']:.3f} of the dataset "
                     f"> {CLUSTER_DOMINANCE_CAP}")

    # Modern-era coverage (Rule 1)
    era = rep["era_shares"]
    if era["scam"]["modern"] < MODERN_SCAM_SHARE_FLOOR:
        flags.append(f"modern_scam_share_below_floor: "
                     f"{era['scam']['modern']:.3f} < {MODERN_SCAM_SHARE_FLOOR}")
    if era["overall"]["modern"] < MODERN_OVERALL_SHARE_FLOOR:
        flags.append(f"modern_overall_share_below_floor: "
                     f"{era['overall']['modern']:.3f} < {MODERN_OVERALL_SHARE_FLOOR}")
    if era["overall"]["unknown"] > UNKNOWN_ERA_SHARE_CAP:
        flags.append(f"unknown_era_share_over_cap: "
                     f"{era['overall']['unknown']:.3f} > {UNKNOWN_ERA_SHARE_CAP}")
    return flags


def run(clean_path: str = "data/interim/clean.parquet",
        clean_stats_path: str = "reports/data_quality.json") -> dict:
    df = pd.read_parquet(clean_path)

    n = len(df)
    n_scam = int((df.label == 1).sum())
    n_legit = int((df.label == 0).sum())

    # per-source share within each class (for the source-dominance cap)
    per_source_within_class = {}
    for cls_name, cls_val in [("scam", 1), ("legit", 0)]:
        sub = df[df.label == cls_val]
        if len(sub):
            per_source_within_class[cls_name] = {
                str(k): _pct(v) for k, v in
                sub.source.value_counts(normalize=True).items()
            }
        else:
            per_source_within_class[cls_name] = {}

    # synthetic share overall and per category (with real/synth split so the
    # rule can distinguish "over-cap in mixed category" from "no real data yet")
    synth_overall = float(df.is_synthetic.mean())
    synth_per_cat = df.groupby("category").is_synthetic.mean().round(4).to_dict()
    cat_composition = {}
    for cat, sub in df.groupby("category"):
        r = int((~sub.is_synthetic).sum())
        s = int(sub.is_synthetic.sum())
        cat_composition[str(cat)] = {
            "real": r, "synthetic": s,
            "synthetic_share": _pct(s / max(r + s, 1)),
        }

    # clustering stats
    cluster_sizes = df.cluster_id.value_counts()
    largest_cluster = int(cluster_sizes.iloc[0]) if len(cluster_sizes) else 0
    clusters = {
        "n_clusters": int(cluster_sizes.size),
        "n_singleton_clusters": int((cluster_sizes == 1).sum()),
        "largest_cluster_size": largest_cluster,
        "largest_cluster_share": _pct(largest_cluster / max(n, 1)),
        "top10_cluster_sizes": [int(x) for x in cluster_sizes.head(10).tolist()],
    }

    # dedup counts come from the clean stage's report (source of truth)
    clean_stats = {}
    if Path(clean_stats_path).exists():
        clean_stats = json.loads(Path(clean_stats_path).read_text())

    # optional per-year / per-language / attachment — reported as "not_available"
    # if the ingestion didn't produce those columns yet
    per_year = (df.groupby("year").size().to_dict() if _has(df, "year")
                else "not_available")
    per_language = (df.language.value_counts(normalize=True).round(4).to_dict()
                    if _has(df, "language") else "not_available")
    attachment_freq = (float(df.has_attachment.mean())
                       if _has(df, "has_attachment") else "not_available")

    per_platform = df.groupby("platform").size().to_dict() if _has(df, "platform") else {}

    # augment platform from source registry when the row column is absent
    if not per_platform:
        per_platform = df.assign(
            platform=df.source.map(lambda s: get_source(s).platform)
        ).groupby("platform").size().to_dict()

    url_freq = float(df.text.astype(str).str.contains(URL_RE).mean())

    rep = {
        "dataset_hash": _dataset_hash(df.sample_id),
        "totals": {
            "n": int(n),
            "n_scam": n_scam,
            "n_legit": n_legit,
        },
        "class_balance": {
            "scam_share": _pct(n_scam / max(n, 1)),
            "legit_share": _pct(n_legit / max(n, 1)),
        },
        "dedup": {
            "exact_duplicates_removed": int(clean_stats.get("exact_duplicates_removed", 0)),
            "rows_in_near_dup_clusters": int(clean_stats.get("rows_in_near_dup_clusters", 0)),
        },
        "clusters": clusters,
        "per_category": {str(k): int(v) for k, v in
                         df.groupby("category").size().sort_values(ascending=False).items()},
        "per_source": {str(k): int(v) for k, v in df.groupby("source").size().items()},
        "per_year": per_year,
        "per_platform": {str(k): int(v) for k, v in per_platform.items()},
        "real_vs_synthetic": {
            "real": int((~df.is_synthetic).sum()),
            "synthetic": int(df.is_synthetic.sum()),
            "synthetic_share": _pct(synth_overall),
        },
        "synthetic_share_per_category": {str(k): _pct(v) for k, v in synth_per_cat.items()},
        "category_composition": cat_composition,
        "source_share_within_class": per_source_within_class,
        "language_distribution": per_language,
        "message_length_chars": _describe_length(df.text.astype(str).str.len()),
        "url_frequency": _pct(url_freq),
        "attachment_frequency": attachment_freq,
        "era_shares": _era_shares(df),
        "taxonomy_coverage": _taxonomy_coverage(
            {str(k): int(v) for k, v in df.groupby("category").size().items()}),
    }
    rep["red_flags"] = _compute_red_flags(rep)

    Path("reports").mkdir(exist_ok=True)
    Path("reports/dataset_audit.json").write_text(json.dumps(rep, indent=2, default=str))
    Path("reports/dataset_audit.md").write_text(_render_md(rep))

    era = rep["era_shares"]
    print(f"[audit] n={n} scam={n_scam} legit={n_legit} "
          f"scam_share={rep['class_balance']['scam_share']} "
          f"synthetic_share={rep['real_vs_synthetic']['synthetic_share']} "
          f"era(overall) legacy={era['overall']['legacy']} "
          f"modern={era['overall']['modern']} unknown={era['overall']['unknown']} "
          f"clusters={clusters['n_clusters']} "
          f"red_flags={len(rep['red_flags'])}")
    if rep["red_flags"]:
        for f in rep["red_flags"]:
            print(f"  RED FLAG: {f}")
    print(f"[audit] wrote reports/dataset_audit.json + .md  "
          f"(dataset_hash={rep['dataset_hash'][:12]}…)")
    return rep


def _render_md(rep: dict) -> str:
    lines: list[str] = []
    p = lines.append
    p("# Dataset Audit")
    p("")
    p(f"- **dataset_hash**: `{rep['dataset_hash']}`")
    p(f"- **total**: {rep['totals']['n']:,}  "
      f"(scam: {rep['totals']['n_scam']:,}, legit: {rep['totals']['n_legit']:,})")
    p(f"- **class balance**: scam={rep['class_balance']['scam_share']}, "
      f"legit={rep['class_balance']['legit_share']}")
    p(f"- **exact duplicates removed**: {rep['dedup']['exact_duplicates_removed']:,}")
    p(f"- **rows in near-dup clusters**: {rep['dedup']['rows_in_near_dup_clusters']:,}")
    p(f"- **clusters**: {rep['clusters']['n_clusters']:,} "
      f"(singletons: {rep['clusters']['n_singleton_clusters']:,}, "
      f"largest: {rep['clusters']['largest_cluster_size']:,} "
      f"= {rep['clusters']['largest_cluster_share']} of dataset)")
    p(f"- **synthetic share (overall)**: {rep['real_vs_synthetic']['synthetic_share']}  "
      f"(real: {rep['real_vs_synthetic']['real']:,}, "
      f"synthetic: {rep['real_vs_synthetic']['synthetic']:,})")
    p(f"- **URL frequency**: {rep['url_frequency']}")
    p(f"- **attachment frequency**: {rep['attachment_frequency']}")
    p("")
    p("## Message length (chars)")
    for k, v in rep["message_length_chars"].items():
        p(f"- {k}: {v}")
    p("")
    p("## Samples per category")
    for k, v in rep["per_category"].items():
        p(f"- {k}: {v:,}")
    p("")
    p("## Samples per source")
    for k, v in rep["per_source"].items():
        p(f"- {k}: {v:,}")
    p("")
    p("## Samples per platform")
    for k, v in rep["per_platform"].items():
        p(f"- {k}: {v:,}")
    p("")
    p("## Samples per year")
    p(f"{rep['per_year']}")
    p("")
    p("## Language distribution")
    p(f"{rep['language_distribution']}")
    p("")
    p("## Synthetic share per category")
    for k, v in rep["synthetic_share_per_category"].items():
        p(f"- {k}: {v}")
    p("")
    p("## Source share within class")
    for cls, srcs in rep["source_share_within_class"].items():
        p(f"### {cls}")
        for k, v in sorted(srcs.items(), key=lambda kv: -kv[1]):
            p(f"- {k}: {v}")
    p("")
    p("## Era shares")
    for scope in ("overall", "scam", "legit"):
        s = rep["era_shares"][scope]
        p(f"- **{scope}**: legacy={s['legacy']}, modern={s['modern']}, "
          f"unknown={s['unknown']}")
    p("")
    p("## Target-taxonomy coverage")
    tax = rep["taxonomy_coverage"]
    p(f"Floor: **{tax['category_floor']}** samples per category.")
    p("")
    p("### Covered (>= floor)")
    if tax["covered"]:
        for cat, e in sorted(tax["covered"].items(), key=lambda kv: -kv[1]["n"]):
            p(f"- `{cat}` ({e['class']}): {e['n']:,}")
    else:
        p("- (none)")
    p("")
    p("### Underrepresented (0 < n < floor)")
    if tax["underrepresented"]:
        for cat, e in sorted(tax["underrepresented"].items(), key=lambda kv: -kv[1]["n"]):
            p(f"- `{cat}` ({e['class']}): {e['n']:,}")
    else:
        p("- (none)")
    p("")
    p("### Missing (0 samples)")
    if any(tax["missing"].values()):
        for cls, cats in tax["missing"].items():
            for cat in sorted(cats):
                p(f"- `{cat}` ({cls})")
    else:
        p("- (none)")
    p("")
    p("### Out-of-taxonomy (present in data, not in target)")
    if tax["out_of_taxonomy"]:
        for cat, n in sorted(tax["out_of_taxonomy"].items(), key=lambda kv: -kv[1]):
            p(f"- `{cat}`: {n:,}")
    else:
        p("- (none)")
    p("")
    p("## Red flags")
    if rep["red_flags"]:
        for f in rep["red_flags"]:
            p(f"- **{f}**")
    else:
        p("- (none)")
    return "\n".join(lines) + "\n"
