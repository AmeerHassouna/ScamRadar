"""Stage 7 — rigorous evaluation (spec §7) + write-once external benchmark (spec §12)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (accuracy_score, average_precision_score,
                             confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score, roc_curve)

LOCK = Path("data/external_benchmark/LOCK.json")


def _bootstrap_ci(y, p, metric, n=1000, seed=42):
    rng = np.random.RandomState(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n):
        i = rng.randint(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            continue
        vals.append(metric(y[i], p[i]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def _full_metrics(y, p, threshold):
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y, yhat)),
        "precision": float(precision_score(y, yhat, zero_division=0)),
        "recall": float(recall_score(y, yhat, zero_division=0)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc_ci95": _bootstrap_ci(y, p, roc_auc_score),
        "pr_auc_ci95": _bootstrap_ci(y, p, average_precision_score),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def _curves(y, p, outdir: Path, tag: str):
    outdir.mkdir(parents=True, exist_ok=True)
    fpr, tpr, _ = roc_curve(y, p)
    pr, rc, _ = precision_recall_curve(y, p)
    frac_pos, mean_pred = calibration_curve(y, p, n_bins=10)
    ths = np.linspace(0.05, 0.95, 19)
    for name, plot in {
        "roc": lambda ax: (ax.plot(fpr, tpr), ax.plot([0, 1], [0, 1], "--"),
                           ax.set(xlabel="FPR", ylabel="TPR", title=f"ROC — {tag}")),
        "pr": lambda ax: (ax.plot(rc, pr),
                          ax.set(xlabel="Recall", ylabel="Precision", title=f"PR — {tag}")),
        "calibration": lambda ax: (ax.plot(mean_pred, frac_pos, "o-"),
                                   ax.plot([0, 1], [0, 1], "--"),
                                   ax.set(xlabel="Predicted p", ylabel="Observed freq",
                                          title=f"Calibration — {tag}")),
        "threshold_sensitivity": lambda ax: (
            ax.plot(ths, [f1_score(y, p >= t) for t in ths], label="F1"),
            ax.plot(ths, [precision_score(y, p >= t, zero_division=0) for t in ths], label="P"),
            ax.plot(ths, [recall_score(y, p >= t) for t in ths], label="R"),
            ax.legend(), ax.set(xlabel="threshold", title=f"Threshold sweep — {tag}")),
    }.items():
        fig, ax = plt.subplots(figsize=(5, 4))
        plot(ax)
        fig.tight_layout()
        fig.savefig(outdir / f"{name}_{tag}.png", dpi=150)
        plt.close(fig)


def _per_group(df, p, threshold, col):
    out = {}
    for g, gdf in df.groupby(col):
        i = gdf.index
        yhat = (p[i] >= threshold).astype(int)
        row = {"n": int(len(gdf))}
        if gdf.label.nunique() == 1:  # single-class group: only rates make sense
            key = "recall" if gdf.label.iloc[0] == 1 else "fp_rate"
            row[key] = float((yhat == gdf.label).mean() if key == "recall"
                             else (yhat != gdf.label).mean())
        else:
            row.update(precision=float(precision_score(gdf.label, yhat, zero_division=0)),
                       recall=float(recall_score(gdf.label, yhat, zero_division=0)),
                       f1=float(f1_score(gdf.label, yhat, zero_division=0)))
        out[str(g)] = row
    return out


def run(bundle_path: str, split="test") -> dict:
    b = joblib.load(bundle_path)
    df = pd.read_parquet(f"data/processed/{split}.parquet").reset_index(drop=True)
    p = b["model"].predict_proba(df.text)[:, 1]
    t = b["threshold_f1"]
    rep = {"bundle": str(bundle_path), "split": split,
           "at_f1_threshold": _full_metrics(df.label, p, t),
           "at_precision_floor_threshold": _full_metrics(df.label, p,
                                                         b["threshold_precision_floor"]),
           "per_category": _per_group(df, p, t, "category"),
           "per_source": _per_group(df, p, t, "source")}
    outdir = Path("reports")
    _curves(df.label.values, p, outdir / "figures", split)
    (outdir / f"eval_{split}.json").write_text(json.dumps(rep, indent=2))
    # error dump for spec §8
    df2 = df.assign(p=p, pred=(p >= t).astype(int))
    df2[(df2.pred == 1) & (df2.label == 0)].to_csv(outdir / f"false_positives_{split}.csv", index=False)
    df2[(df2.pred == 0) & (df2.label == 1)].to_csv(outdir / f"false_negatives_{split}.csv", index=False)
    print(f"[eval:{split}] PR-AUC {rep['at_f1_threshold']['pr_auc']:.4f} "
          f"ROC-AUC {rep['at_f1_threshold']['roc_auc']:.4f} "
          f"F1 {rep['at_f1_threshold']['f1']:.4f}")
    return rep


def run_external(bundle_path: str, force=False) -> dict:
    """One-shot benchmark. Refuses a second evaluation unless forced; logs access."""
    state = json.loads(LOCK.read_text())
    if state.get("evaluated") and not force:
        raise SystemExit(
            "External benchmark was already evaluated once. Re-evaluation would "
            "invalidate scientific claims (spec §2/§12). Use --force-i-understand "
            "only for a genuinely frozen, different model — access will be logged.")
    df = pd.read_parquet("data/external_benchmark/benchmark.parquet").reset_index(drop=True)
    b = joblib.load(bundle_path)
    p = b["model"].predict_proba(df.text)[:, 1]
    t = b["threshold_f1"]
    rep = {"bundle": str(bundle_path),
           "evaluated_at": datetime.now(timezone.utc).isoformat(),
           "at_f1_threshold": _full_metrics(df.label, p, t),
           "per_category": _per_group(df, p, t, "category"),
           "per_source": _per_group(df, p, t, "source")}
    Path("reports/external_benchmark_FINAL.json").write_text(json.dumps(rep, indent=2))
    _curves(df.label.values, p, Path("reports/figures"), "external")
    state["evaluated"] = True
    state.setdefault("access_log", []).append(
        {"at": rep["evaluated_at"], "bundle": str(bundle_path), "forced": force})
    LOCK.write_text(json.dumps(state, indent=2))
    print(f"[eval:EXTERNAL] PR-AUC {rep['at_f1_threshold']['pr_auc']:.4f} — benchmark now locked.")
    return rep
