"""Comprehensive error analysis per DESIGN §13.

Extends the basic FP/FN dumps produced by evaluate.py with:
  - confidence-score distributions (per class, per category)
  - common failure patterns (top word-lift n-grams in FP vs TP)
  - per-category / per-source contribution to overall error
  - a single evidence-backed recommendation for the next experiment

Writes: reports/error_analysis_<exp_id>.{md,json}
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer


REL_TOL = 1e-9


def _confidence_hist(p: np.ndarray, y: np.ndarray) -> dict:
    """Simple 10-bin histogram of predicted probabilities per class."""
    edges = np.linspace(0.0, 1.0, 11)
    hist_pos = np.histogram(p[y == 1], bins=edges)[0].tolist()
    hist_neg = np.histogram(p[y == 0], bins=edges)[0].tolist()
    return {
        "bin_edges": edges.round(3).tolist(),
        "scam_class_counts": hist_pos,
        "legit_class_counts": hist_neg,
        "scam_conf_mean": float(p[y == 1].mean()) if (y == 1).any() else None,
        "scam_conf_p5": float(np.percentile(p[y == 1], 5)) if (y == 1).any() else None,
        "scam_conf_p50": float(np.percentile(p[y == 1], 50)) if (y == 1).any() else None,
        "scam_conf_p95": float(np.percentile(p[y == 1], 95)) if (y == 1).any() else None,
    }


def _lift_ngrams(df_err: pd.DataFrame, df_ok: pd.DataFrame, top_k: int = 25,
                 ngram=(1, 2)) -> list[tuple[str, float, int, int]]:
    """Word 1-2 grams over-represented in the error set vs the correct set.
    Returns (ngram, lift, count_err, count_ok) rows sorted by lift."""
    if len(df_err) == 0 or len(df_ok) == 0:
        return []
    vec = CountVectorizer(lowercase=True, ngram_range=ngram, min_df=5,
                          max_features=20_000)
    corpus = pd.concat([df_err.text, df_ok.text], ignore_index=True)
    X = vec.fit_transform(corpus.astype(str))
    err_slice = X[:len(df_err)].sum(axis=0).A1
    ok_slice = X[len(df_err):].sum(axis=0).A1
    n_err, n_ok = err_slice.sum() + REL_TOL, ok_slice.sum() + REL_TOL
    freq_err = err_slice / n_err
    freq_ok = ok_slice / n_ok
    lift = freq_err / (freq_ok + 1e-6)
    idx = np.argsort(-lift)
    vocab = vec.get_feature_names_out()
    rows: list[tuple[str, float, int, int]] = []
    for i in idx:
        if err_slice[i] < 5:
            continue
        rows.append((vocab[i], round(float(lift[i]), 3),
                     int(err_slice[i]), int(ok_slice[i])))
        if len(rows) >= top_k:
            break
    return rows


def _length_stats(s: pd.Series) -> dict:
    if not len(s):
        return {}
    L = s.str.len()
    return {"n": int(len(s)), "p5": int(L.quantile(0.05)),
            "p50": int(L.quantile(0.5)),
            "p95": int(L.quantile(0.95))}


def _pick_recommendation(eval_test: dict, eval_ext: dict, fp_ngrams: list,
                         per_cat: dict, weak_cats: list) -> dict:
    """Choose the single most-supported next-experiment class."""
    reasons: list[str] = []

    # 1) If a scam category has < 60% recall and > 50 samples: collect more data.
    poor = [c for c, r in per_cat.items()
            if "recall" in r and r["recall"] < 0.60 and r["n"] > 50]
    if poor:
        reasons.append(f"category recall < 0.60 with n > 50 on: {poor}")

    # 2) If ham-source FPR > 10%: features / architecture (linear model
    #    can't discriminate stylistic ham lookalikes).
    high_fpr = []
    for src, r in eval_test.get("per_source", {}).items():
        if "fp_rate" in r and r["fp_rate"] > 0.10 and r["n"] > 200:
            high_fpr.append((src, r["fp_rate"]))
    if high_fpr:
        reasons.append(f"ham-source FPR > 10% on: {high_fpr}")

    # 3) If external PR-AUC > internal test PR-AUC: possible dataset skew,
    #    not a model problem.
    m_int = eval_test["at_f1_threshold"]["pr_auc"]
    m_ext = eval_ext["at_f1_threshold"]["pr_auc"]
    ext_gap = m_ext - m_int

    # Rank recommendations:
    # - If poor categories exist, "collect additional data" or "features" wins.
    #   Prefer "collect additional data" if the poor categories are ones we
    #   *know* are under-represented (from the audit).
    if weak_cats and set(weak_cats) & set(poor):
        return {
            "class": "collect_additional_data",
            "target": sorted(set(weak_cats) & set(poor)),
            "evidence": [
                f"categories under recall floor (0.60): {poor}",
                f"audit flags these as under-represented / synthetic-only: {weak_cats}",
                f"internal-test PR-AUC = {m_int:.4f}, external = {m_ext:.4f}",
            ],
            "expected_lift": "large (root cause is data volume)",
        }
    if high_fpr:
        return {
            "class": "improve_feature_engineering",
            "target": [s for s, _ in high_fpr],
            "evidence": [
                f"ham-source FPR exceeds 10% on {high_fpr}",
                f"top FP n-gram lifts include: {fp_ngrams[:8]}",
                "linear model + word TF-IDF has no non-linear or structural signal",
            ],
            "expected_lift": "moderate (F5 handcrafted + F6 hybrid should help)",
        }
    if abs(ext_gap) > 0.03:
        direction = "higher on external" if ext_gap > 0 else "lower on external"
        return {
            "class": "collect_additional_data",
            "target": ["improve external representativeness"],
            "evidence": [
                f"external PR-AUC is {ext_gap:+.4f} vs internal ({direction})",
                "suggests dataset skew, not model capacity",
            ],
            "expected_lift": "unclear — measure with per-source recall first",
        }
    return {
        "class": "improve_feature_engineering",
        "target": ["run E2 ablations (F1..F6)"],
        "evidence": [
            "no dominant weakness — proceed to next planned experiment",
            f"headline PR-AUC {m_int:.4f} on internal, {m_ext:.4f} on external",
        ],
        "expected_lift": "small (proceed by protocol)",
    }


def run(bundle_path: str, exp_id: str = "E1") -> dict:
    """Extended analysis over the test split + external benchmark.
    Assumes evaluate.run(...) and evaluate.run_external(...) have already fired
    and written eval_test.json + external_benchmark_FINAL.json."""
    b = joblib.load(bundle_path)
    test_df = pd.read_parquet("data/processed/test.parquet").reset_index(drop=True)
    ext_df = pd.read_parquet(
        "data/external_benchmark/benchmark.parquet").reset_index(drop=True)

    p_test = b["model"].predict_proba(test_df.text)[:, 1]
    p_ext = b["model"].predict_proba(ext_df.text)[:, 1]
    t = b["threshold_f1"]

    eval_test = json.loads(Path("reports/eval_test.json").read_text())
    eval_ext = json.loads(Path("reports/external_benchmark_FINAL.json").read_text())

    # Confidence distributions
    conf_test = _confidence_hist(p_test, test_df.label.values)
    conf_ext = _confidence_hist(p_ext, ext_df.label.values)

    # Confidence by category (test only — FP/FN dumps are already there)
    conf_by_cat: dict[str, dict] = {}
    for cat, sub in test_df.groupby("category"):
        i = sub.index.to_numpy()
        conf_by_cat[str(cat)] = _confidence_hist(p_test[i], sub.label.values)

    # Failure patterns: n-gram lift in FP vs TN (why does the model call this scam?)
    #                  and in FN vs TP (why does the model miss this scam?)
    df_test = test_df.assign(p=p_test, pred=(p_test >= t).astype(int))
    fp = df_test[(df_test.pred == 1) & (df_test.label == 0)]
    tn = df_test[(df_test.pred == 0) & (df_test.label == 0)]
    fn = df_test[(df_test.pred == 0) & (df_test.label == 1)]
    tp = df_test[(df_test.pred == 1) & (df_test.label == 1)]
    fp_ngrams = _lift_ngrams(fp, tn)
    fn_ngrams = _lift_ngrams(fn, tp)

    # Length distributions on errors
    length_stats = {
        "fp": _length_stats(fp.text),
        "fn": _length_stats(fn.text),
        "tp": _length_stats(tp.text),
        "tn_sample": _length_stats(tn.text.sample(min(len(tn), 5000), random_state=1)),
    }

    # Per-category / per-source contribution to error count
    fp_by_source = fp.source.value_counts().to_dict()
    fn_by_category = fn.category.value_counts().to_dict()
    fn_by_source = fn.source.value_counts().to_dict()

    # Confidence for the synthetic samples specifically (probe-adjacent check)
    synth_mask = test_df.is_synthetic.values
    synth_conf: dict | None = None
    if synth_mask.any():
        synth_conf = {
            "n": int(synth_mask.sum()),
            "scam_class_pr": float(p_test[synth_mask & (test_df.label.values == 1)].mean()
                                   if ((synth_mask) & (test_df.label.values == 1)).any() else float("nan")),
            "note": "synthetic samples in test set — mean predicted prob for label=1",
        }

    # Recommendation
    weak_from_audit = ["recruitment_scam", "advance_fee_fraud",
                       "smishing"]  # under 1500 rows each
    rec = _pick_recommendation(eval_test, eval_ext, fp_ngrams,
                               eval_test["per_category"], weak_from_audit)

    report = {
        "experiment_id": exp_id,
        "bundle": str(bundle_path),
        "headline": {
            "internal_test": eval_test["at_f1_threshold"],
            "external_benchmark": eval_ext["at_f1_threshold"],
            "precision_floor_internal": eval_test["at_precision_floor_threshold"],
        },
        "confidence_distribution": {
            "internal_test": conf_test,
            "external_benchmark": conf_ext,
            "by_category_test": conf_by_cat,
            "synthetic_only": synth_conf,
        },
        "failure_patterns": {
            "top_fp_ngram_lifts": fp_ngrams,
            "top_fn_ngram_lifts": fn_ngrams,
        },
        "error_length_stats": length_stats,
        "fp_by_source": {str(k): int(v) for k, v in fp_by_source.items()},
        "fn_by_category": {str(k): int(v) for k, v in fn_by_category.items()},
        "fn_by_source": {str(k): int(v) for k, v in fn_by_source.items()},
        "per_category_internal": eval_test["per_category"],
        "per_source_internal": eval_test["per_source"],
        "per_category_external": eval_ext["per_category"],
        "per_source_external": eval_ext["per_source"],
        "recommendation": rec,
        "notes": [
            "Only one external benchmark is currently carved (design §8 calls "
            "for 8 independent panels); per-source and per-category breakdowns "
            "on that one benchmark are used as a proxy until the multi-benchmark "
            "structure is wired.",
            "Bootstrap CIs are on the eval_*.json headline metrics.",
        ],
    }

    Path("reports").mkdir(exist_ok=True)
    Path(f"reports/error_analysis_{exp_id}.json").write_text(
        json.dumps(report, indent=2, default=str))
    Path(f"reports/error_analysis_{exp_id}.md").write_text(_render_md(report))
    print(f"[error-analysis:{exp_id}] wrote reports/error_analysis_{exp_id}.{{json,md}}")
    print(f"[error-analysis:{exp_id}] recommendation: {rec['class']} -> {rec['target']}")
    return report


def _render_md(rep: dict) -> str:
    L: list[str] = []
    p = L.append
    p(f"# Error Analysis — {rep['experiment_id']}")
    p("")
    p(f"Bundle: `{rep['bundle']}`")
    p("")
    p("## Headline")
    for scope, m in rep["headline"].items():
        p(f"### {scope}")
        keys = ("pr_auc", "roc_auc", "f1", "precision", "recall", "threshold")
        vals = {k: m.get(k) for k in keys if k in m}
        p("| " + " | ".join(vals.keys()) + " |")
        p("| " + " | ".join("---" for _ in vals) + " |")
        p("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                            for v in vals.values()) + " |")
        cm = m.get("confusion_matrix", {})
        if cm:
            p("")
            p(f"confusion (t={m.get('threshold','?'):.3f}): "
              f"TP={cm.get('tp')} FN={cm.get('fn')} "
              f"FP={cm.get('fp')} TN={cm.get('tn')}")
        p("")
    p("## Recommendation")
    rec = rep["recommendation"]
    p(f"- **Class**: `{rec['class']}`")
    p(f"- **Target**: `{rec['target']}`")
    p(f"- **Expected lift**: {rec['expected_lift']}")
    p("- **Evidence**:")
    for e in rec["evidence"]:
        p(f"  - {e}")
    p("")
    p("## Per-category (internal test)")
    p("| category | n | recall / fpr | precision | f1 |")
    p("|---|---:|---:|---:|---:|")
    for cat, r in sorted(rep["per_category_internal"].items()):
        rec_key = "recall" if "recall" in r else "fp_rate"
        val = f"{r.get(rec_key,0):.3f} ({rec_key})"
        p(f"| {cat} | {r.get('n')} | {val} | "
          f"{r.get('precision','')} | {r.get('f1','')} |")
    p("")
    p("## Per-source (internal test)")
    p("| source | n | recall / fpr | precision | f1 |")
    p("|---|---:|---:|---:|---:|")
    for src, r in sorted(rep["per_source_internal"].items()):
        rec_key = "recall" if "recall" in r else "fp_rate"
        val = f"{r.get(rec_key,0):.3f} ({rec_key})"
        p(f"| {src} | {r.get('n')} | {val} | "
          f"{r.get('precision','')} | {r.get('f1','')} |")
    p("")
    p("## Per-category (external benchmark)")
    p("| category | n | recall / fpr | precision | f1 |")
    p("|---|---:|---:|---:|---:|")
    for cat, r in sorted(rep["per_category_external"].items()):
        rec_key = "recall" if "recall" in r else "fp_rate"
        val = f"{r.get(rec_key,0):.3f} ({rec_key})"
        p(f"| {cat} | {r.get('n')} | {val} | "
          f"{r.get('precision','')} | {r.get('f1','')} |")
    p("")
    p("## Per-source (external benchmark)")
    p("| source | n | recall / fpr | precision | f1 |")
    p("|---|---:|---:|---:|---:|")
    for src, r in sorted(rep["per_source_external"].items()):
        rec_key = "recall" if "recall" in r else "fp_rate"
        val = f"{r.get(rec_key,0):.3f} ({rec_key})"
        p(f"| {src} | {r.get('n')} | {val} | "
          f"{r.get('precision','')} | {r.get('f1','')} |")
    p("")
    p("## Confidence distributions (internal test)")
    ct = rep["confidence_distribution"]["internal_test"]
    p(f"- scam mean/p5/p50/p95: "
      f"{ct['scam_conf_mean']:.3f} / {ct['scam_conf_p5']:.3f} / "
      f"{ct['scam_conf_p50']:.3f} / {ct['scam_conf_p95']:.3f}")
    p(f"- scam bin counts: {ct['scam_class_counts']}")
    p(f"- legit bin counts: {ct['legit_class_counts']}")
    if rep["confidence_distribution"].get("synthetic_only"):
        s = rep["confidence_distribution"]["synthetic_only"]
        p(f"- synthetic-only (n={s['n']}) mean scam-prob: {s['scam_class_pr']:.3f}")
    p("")
    p("## Top false-positive n-gram lifts (why the model over-fires)")
    p("| n-gram | lift | count in FP | count in TN |")
    p("|---|---:|---:|---:|")
    for ng, lift, ne, no in rep["failure_patterns"]["top_fp_ngram_lifts"]:
        p(f"| `{ng}` | {lift} | {ne} | {no} |")
    p("")
    p("## Top false-negative n-gram lifts (what the model misses)")
    p("| n-gram | lift | count in FN | count in TP |")
    p("|---|---:|---:|---:|")
    for ng, lift, ne, no in rep["failure_patterns"]["top_fn_ngram_lifts"]:
        p(f"| `{ng}` | {lift} | {ne} | {no} |")
    p("")
    p("## Error length distribution")
    for name, ls in rep["error_length_stats"].items():
        p(f"- {name}: {ls}")
    p("")
    p("## Concentration of errors")
    p(f"- FP by source (top 10): "
      f"{dict(sorted(rep['fp_by_source'].items(), key=lambda kv: -kv[1])[:10])}")
    p(f"- FN by category (top 10): "
      f"{dict(sorted(rep['fn_by_category'].items(), key=lambda kv: -kv[1])[:10])}")
    p(f"- FN by source (top 10): "
      f"{dict(sorted(rep['fn_by_source'].items(), key=lambda kv: -kv[1])[:10])}")
    p("")
    p("## Notes")
    for n in rep["notes"]:
        p(f"- {n}")
    return "\n".join(L) + "\n"
