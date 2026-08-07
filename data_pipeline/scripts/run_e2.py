"""E2 — feature ablation with with-vs-without-synthetic (DESIGN §7 rule 6.f + §9).

10 model fits: {F1, F2, F3, F5, F6} × {with_synth, no_synth}
Each fit: LogReg + specified feature set, no calibration (calibration is E5's
concern; PR-AUC is calibration-invariant so feature comparison is unaffected).

For each fit we save:
  * bundle -> experiments/E2_<FS>_<cond>.joblib
  * eval_test  -> reports/eval_E2_<FS>_<cond>.json
  * eval_ext   -> reports/external_E2_<FS>_<cond>.json

At the end we render:
  * reports/e2_full_results.json     (raw)
  * reports/e2_comparison.md         (consolidated comparison table)
  * reports/e2_ranking.json          (ranked representations + winner)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.pipeline import Pipeline

from scamradar.features import build

FEATURE_SETS = ["F1", "F2", "F3", "F5", "F6"]
CONDITIONS = ["with_synth", "no_synth"]
EXP = Path("experiments")
REP = Path("reports")
PRECISION_FLOOR = 0.98


def load_split(name: str, exclude_synth: bool = False) -> pd.DataFrame:
    df = pd.read_parquet(f"data/processed/{name}.parquet").reset_index(drop=True)
    if exclude_synth:
        df = df[~df.is_synthetic].reset_index(drop=True)
    return df


def _metrics(df: pd.DataFrame, p: np.ndarray, t: float) -> dict:
    yhat = (p >= t).astype(int)
    y = df.label.values
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {
        "n": int(len(df)),
        "threshold": float(t),
        "accuracy": float((yhat == y).mean()),
        "precision": float(precision_score(y, yhat, zero_division=0)),
        "recall": float(recall_score(y, yhat, zero_division=0)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def _per_group(df: pd.DataFrame, p: np.ndarray, t: float, col: str) -> dict:
    out: dict = {}
    for g, gdf in df.groupby(col):
        idx = gdf.index
        yhat = (p[idx] >= t).astype(int)
        row: dict = {"n": int(len(gdf))}
        if gdf.label.nunique() == 1:
            key = "recall" if gdf.label.iloc[0] == 1 else "fp_rate"
            row[key] = float((yhat == gdf.label).mean() if key == "recall"
                             else (yhat != gdf.label).mean())
        else:
            row.update(
                precision=float(precision_score(gdf.label, yhat, zero_division=0)),
                recall=float(recall_score(gdf.label, yhat, zero_division=0)),
                f1=float(f1_score(gdf.label, yhat, zero_division=0)))
        out[str(g)] = row
    return out


def _fp_fn_dump(df: pd.DataFrame, p: np.ndarray, t: float,
                prefix: str, top_k: int = 50) -> None:
    """Top-N FP + FN by confidence, saved as CSV."""
    df2 = df.assign(p=p, pred=(p >= t).astype(int))
    fp = df2[(df2.pred == 1) & (df2.label == 0)].sort_values("p", ascending=False).head(top_k)
    fn = df2[(df2.pred == 0) & (df2.label == 1)].sort_values("p").head(top_k)
    fp.to_csv(REP / f"{prefix}_fp_top{top_k}.csv", index=False)
    fn.to_csv(REP / f"{prefix}_fn_top{top_k}.csv", index=False)


def fit_and_eval(feature_set: str, condition: str) -> dict:
    exclude = (condition == "no_synth")
    tag = f"{feature_set}_{condition}"
    print(f"\n===== E2 :: {tag} =====")
    t0 = time.time()
    train = load_split("train", exclude_synth=exclude)
    val = load_split("val", exclude_synth=exclude)
    test = load_split("test")                            # never filter
    external = pd.read_parquet(
        "data/external_benchmark/benchmark.parquet").reset_index(drop=True)

    print(f"  n_train={len(train):,} n_val={len(val):,} n_test={len(test):,} "
          f"n_external={len(external):,}")

    pipe = Pipeline([
        ("feats", build(feature_set)),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced",
                                   C=1.0, solver="liblinear")),
    ])
    print(f"  [fit] fitting pipeline...")
    fit_start = time.time()
    pipe.fit(train.text, train.label)
    fit_secs = time.time() - fit_start
    print(f"  [fit] done in {fit_secs:.1f}s")

    # Threshold selection on val
    p_val = pipe.predict_proba(val.text)[:, 1]
    val_pr_auc = float(average_precision_score(val.label, p_val))
    ths = np.linspace(0.01, 0.99, 197)
    f1s = np.array([f1_score(val.label, p_val >= t) for t in ths])
    t_f1 = float(ths[int(np.argmax(f1s))])
    ok = [t for t in ths
          if precision_score(val.label, p_val >= t, zero_division=0) >= PRECISION_FLOOR
          and (p_val >= t).sum() > 0]
    t_prec = float(min(ok)) if ok else t_f1

    # Test + external eval
    print(f"  [eval] predicting test + external...")
    p_test = pipe.predict_proba(test.text)[:, 1]
    p_ext = pipe.predict_proba(external.text)[:, 1]

    result = {
        "feature_set": feature_set,
        "condition": condition,
        "n_train": int(len(train)),
        "n_val": int(len(val)),
        "n_test": int(len(test)),
        "n_external": int(len(external)),
        "fit_seconds": round(fit_secs, 1),
        "val_pr_auc": val_pr_auc,
        "threshold_f1": t_f1,
        "threshold_precision_floor": t_prec,
        "test_internal": _metrics(test, p_test, t_f1),
        "test_at_precision_floor": _metrics(test, p_test, t_prec),
        "external": _metrics(external, p_ext, t_f1),
        "per_category_test": _per_group(test, p_test, t_f1, "category"),
        "per_source_test": _per_group(test, p_test, t_f1, "source"),
        "per_category_external": _per_group(external, p_ext, t_f1, "category"),
        "per_source_external": _per_group(external, p_ext, t_f1, "source"),
    }

    # Persist bundle + FP/FN dumps + individual JSONs
    EXP.mkdir(exist_ok=True)
    REP.mkdir(exist_ok=True)
    joblib.dump({
        "model": pipe, "feature_set": feature_set, "model_name": "logreg",
        "condition": condition, "threshold_f1": t_f1,
        "threshold_precision_floor": t_prec, "val_pr_auc": val_pr_auc,
    }, EXP / f"E2_{tag}.joblib")
    (REP / f"eval_E2_{tag}_test.json").write_text(
        json.dumps({"at_f1_threshold": result["test_internal"],
                    "at_precision_floor_threshold": result["test_at_precision_floor"],
                    "per_category": result["per_category_test"],
                    "per_source": result["per_source_test"]}, indent=2))
    (REP / f"eval_E2_{tag}_external.json").write_text(
        json.dumps({"at_f1_threshold": result["external"],
                    "per_category": result["per_category_external"],
                    "per_source": result["per_source_external"]}, indent=2))
    _fp_fn_dump(test, p_test, t_f1, f"E2_{tag}_test")
    _fp_fn_dump(external, p_ext, t_f1, f"E2_{tag}_external")

    m = result["test_internal"]
    mx = result["external"]
    print(f"  [eval] test:     PR-AUC {m['pr_auc']:.4f}  ROC-AUC {m['roc_auc']:.4f}  F1 {m['f1']:.4f}  P {m['precision']:.4f}  R {m['recall']:.4f}")
    print(f"  [eval] external: PR-AUC {mx['pr_auc']:.4f}  ROC-AUC {mx['roc_auc']:.4f}  F1 {mx['f1']:.4f}  P {mx['precision']:.4f}  R {mx['recall']:.4f}")
    print(f"  [eval] total wallclock {time.time() - t0:.1f}s")
    return result


# ---------------------------------------------------------------------------
# Comparison + ranking
# ---------------------------------------------------------------------------

E1_REFERENCE = {
    "internal_pr_auc": 0.9276,
    "internal_roc_auc": 0.9845,
    "internal_f1": 0.8574,
    "external_pr_auc": 0.9365,
    "external_roc_auc": 0.9831,
    "external_f1": 0.8644,
}


def rank(all_results: dict) -> dict:
    """Rank feature sets by external PR-AUC (with-synth condition), tiebreak
    by internal PR-AUC. Return primary winner + top-3."""
    per_fs = {}
    for fs in FEATURE_SETS:
        w = all_results[f"{fs}_with_synth"]
        n = all_results[f"{fs}_no_synth"]
        per_fs[fs] = {
            "ext_pr_auc_ws": w["external"]["pr_auc"],
            "ext_pr_auc_ns": n["external"]["pr_auc"],
            "int_pr_auc_ws": w["test_internal"]["pr_auc"],
            "int_pr_auc_ns": n["test_internal"]["pr_auc"],
            "ext_f1_ws": w["external"]["f1"],
            "ext_f1_ns": n["external"]["f1"],
            "synth_delta_ext_pr_auc": w["external"]["pr_auc"] - n["external"]["pr_auc"],
        }
    ordered = sorted(per_fs.items(),
                     key=lambda kv: (-kv[1]["ext_pr_auc_ws"], -kv[1]["int_pr_auc_ws"]))
    winner = ordered[0][0]
    return {
        "primary_metric": "external PR-AUC (with-synth condition)",
        "tiebreak": "internal test PR-AUC",
        "ranked": [{"feature_set": fs, **stats} for fs, stats in ordered],
        "winner": winner,
        "runner_up": ordered[1][0] if len(ordered) > 1 else None,
    }


def render_summary(all_results: dict, ranking: dict) -> None:
    L: list[str] = []
    p = L.append
    p("# E2 — Feature-Set Ablation with-vs-without Synthetic\n")
    p("Configuration: LogRegression + specified feature set, no calibration, "
      "class_weight=balanced, C=1.0, liblinear solver. Threshold optimised on val.")
    p("")
    p(f"E1 reference (from `reports/eval_test.json`): "
      f"test PR-AUC={E1_REFERENCE['internal_pr_auc']:.4f}, "
      f"external PR-AUC={E1_REFERENCE['external_pr_auc']:.4f}.")
    p("")

    p("## Absolute metrics")
    p("| feature_set | condition | val PR-AUC | test PR-AUC | test ROC-AUC | test F1 | test P | test R | ext PR-AUC | ext ROC-AUC | ext F1 | ext P | ext R |")
    p("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for fs in FEATURE_SETS:
        for cond in CONDITIONS:
            r = all_results[f"{fs}_{cond}"]
            m = r["test_internal"]; mx = r["external"]
            p(f"| {fs} | {cond} | {r['val_pr_auc']:.4f} | "
              f"{m['pr_auc']:.4f} | {m['roc_auc']:.4f} | {m['f1']:.4f} | "
              f"{m['precision']:.4f} | {m['recall']:.4f} | "
              f"{mx['pr_auc']:.4f} | {mx['roc_auc']:.4f} | {mx['f1']:.4f} | "
              f"{mx['precision']:.4f} | {mx['recall']:.4f} |")
    p("")

    p("## Delta vs E1 baseline (word TF-IDF + LogReg, calibrated)")
    p("| feature_set | condition | Δ test PR-AUC | Δ test F1 | Δ ext PR-AUC | Δ ext F1 |")
    p("|---|---|---:|---:|---:|---:|")
    for fs in FEATURE_SETS:
        for cond in CONDITIONS:
            r = all_results[f"{fs}_{cond}"]
            m = r["test_internal"]; mx = r["external"]
            d_int = m["pr_auc"] - E1_REFERENCE["internal_pr_auc"]
            d_intf = m["f1"] - E1_REFERENCE["internal_f1"]
            d_ext = mx["pr_auc"] - E1_REFERENCE["external_pr_auc"]
            d_extf = mx["f1"] - E1_REFERENCE["external_f1"]
            p(f"| {fs} | {cond} | {d_int:+.4f} | {d_intf:+.4f} | "
              f"{d_ext:+.4f} | {d_extf:+.4f} |")
    p("")

    p("## Δ from adding synthetic data (with_synth vs no_synth, per feature set)")
    p("| feature_set | Δ val PR-AUC | Δ test PR-AUC | Δ test F1 | **Δ ext PR-AUC** | Δ ext F1 |")
    p("|---|---:|---:|---:|---:|---:|")
    for fs in FEATURE_SETS:
        w = all_results[f"{fs}_with_synth"]; n = all_results[f"{fs}_no_synth"]
        p(f"| {fs} | "
          f"{w['val_pr_auc']-n['val_pr_auc']:+.4f} | "
          f"{w['test_internal']['pr_auc']-n['test_internal']['pr_auc']:+.4f} | "
          f"{w['test_internal']['f1']-n['test_internal']['f1']:+.4f} | "
          f"**{w['external']['pr_auc']-n['external']['pr_auc']:+.4f}** | "
          f"{w['external']['f1']-n['external']['f1']:+.4f} |")
    p("")

    p("## Per-category recall (external) — with_synth condition")
    cats_all: set = set()
    for fs in FEATURE_SETS:
        cats_all.update(all_results[f"{fs}_with_synth"]["per_category_external"].keys())
    scam_cats = sorted([c for c in cats_all if not c.startswith("ham_") and c != "email_spam" or c == "email_spam"])
    ham_cats = sorted([c for c in cats_all if c.startswith("ham_")])
    p("### Scam-category recall (higher is better)")
    p("| category | " + " | ".join(FEATURE_SETS) + " |")
    p("|---|" + "|".join("---:" for _ in FEATURE_SETS) + "|")
    for c in scam_cats:
        row = [f"| {c}"]
        for fs in FEATURE_SETS:
            r = all_results[f"{fs}_with_synth"]["per_category_external"].get(c, {})
            row.append(f"{r.get('recall', float('nan')):.3f}" if "recall" in r else "-")
        p(" | ".join(row) + " |")
    p("")
    p("### Ham-category FP rate (lower is better)")
    p("| category | " + " | ".join(FEATURE_SETS) + " |")
    p("|---|" + "|".join("---:" for _ in FEATURE_SETS) + "|")
    for c in ham_cats:
        row = [f"| {c}"]
        for fs in FEATURE_SETS:
            r = all_results[f"{fs}_with_synth"]["per_category_external"].get(c, {})
            row.append(f"{r.get('fp_rate', float('nan')):.3f}" if "fp_rate" in r else "-")
        p(" | ".join(row) + " |")
    p("")

    p("## Ranking")
    p(f"- Primary metric: **{ranking['primary_metric']}**")
    p(f"- Tiebreak: {ranking['tiebreak']}")
    p(f"- **Winner: {ranking['winner']}**  (runner-up: {ranking['runner_up']})")
    p("")
    p("| rank | feature_set | ext PR-AUC (ws) | int PR-AUC (ws) | ext F1 (ws) | Δ synth ext PR-AUC |")
    p("|---:|---|---:|---:|---:|---:|")
    for i, r in enumerate(ranking["ranked"], 1):
        p(f"| {i} | {r['feature_set']} | {r['ext_pr_auc_ws']:.4f} | "
          f"{r['int_pr_auc_ws']:.4f} | {r['ext_f1_ws']:.4f} | "
          f"{r['synth_delta_ext_pr_auc']:+.4f} |")
    p("")

    p("## Strengths / weaknesses (from per-category tables)")
    p("Automatic summary — for detail see reports/eval_E2_*_external.json.")
    p("")
    for fs in FEATURE_SETS:
        ext = all_results[f"{fs}_with_synth"]["per_category_external"]
        scam_rec = [(c, r["recall"]) for c, r in ext.items() if "recall" in r]
        ham_fpr = [(c, r["fp_rate"]) for c, r in ext.items() if "fp_rate" in r]
        weak_scam = sorted(scam_rec, key=lambda kv: kv[1])[:2]
        strong_scam = sorted(scam_rec, key=lambda kv: -kv[1])[:2]
        high_fp = sorted(ham_fpr, key=lambda kv: -kv[1])[:2]
        p(f"- **{fs}**: strong on `{', '.join(c for c, _ in strong_scam)}`; "
          f"weak on `{', '.join(f'{c} ({r:.2f})' for c, r in weak_scam)}`; "
          f"highest ham FPR: `{', '.join(f'{c} ({r:.3f})' for c, r in high_fp)}`.")
    p("")
    (REP / "e2_comparison.md").write_text("\n".join(L) + "\n")


def main() -> None:
    from scamradar.approval import require_dataset_approval
    require_dataset_approval()

    all_results: dict = {}
    for fs in FEATURE_SETS:
        for cond in CONDITIONS:
            key = f"{fs}_{cond}"
            all_results[key] = fit_and_eval(fs, cond)

    ranking = rank(all_results)
    (REP / "e2_full_results.json").write_text(
        json.dumps(all_results, indent=2, default=str))
    (REP / "e2_ranking.json").write_text(json.dumps(ranking, indent=2))
    render_summary(all_results, ranking)
    print(f"\n[E2] ranking: {[r['feature_set'] for r in ranking['ranked']]}")
    print(f"[E2] WINNER: {ranking['winner']}  (bundle: experiments/E2_{ranking['winner']}_with_synth.joblib)")
    print(f"[E2] reports/e2_comparison.md + reports/e2_ranking.json written")


if __name__ == "__main__":
    main()
