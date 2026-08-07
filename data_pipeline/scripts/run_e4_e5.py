"""E4 (HPO) + E5 (calibration + threshold study) on the frozen winner:
LogReg + F3.

E4 protocol:
  * Optuna TPE, up to 20 trials, early-stop after 8 no-improvement trials.
  * Objective: validation PR-AUC (single fit on train, eval on val — matches
    the "existing train/validation methodology" the user specified).
  * Search space: 8 impactful params (see SEARCH SPACE in objective()).
  * Per-trial record: params, val metrics, fit time, model size, ECE.

E5 protocol:
  * Take E4 winner, compare {no calibration, Platt sigmoid cv=3, isotonic
    cv=3} on val (ECE + Brier score). Pick by lowest ECE.
  * Threshold optimisation on val (F1-max).
  * One-shot external evaluation.
  * Final report answers the 4 questions.

Writes:
  * reports/e4_trials.json (per-trial log)
  * reports/e4_best.json (best trial + comparison to E3 baseline)
  * reports/e5_calibration.json (three calibrations compared)
  * reports/e5_final.json (final model + external eval)
  * reports/e4_e5_report.md (final human-readable report)
  * experiments/E5_final_logreg_F3.joblib (production candidate bundle)
"""
from __future__ import annotations

import json
import os
import time
import tracemalloc
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.pipeline import FeatureUnion, Pipeline

SEED = 42
EXP = Path("experiments")
REP = Path("reports")

E3_BASELINE = {
    "model_bundle": "experiments/E2_F3_with_synth.joblib",
    "val_pr_auc": 0.9790,
    "test_pr_auc": 0.9789,
    "test_f1": 0.9303,
    "ext_pr_auc": 0.9791,
    "ext_f1": 0.9318,
    "ext_ece": 0.028,
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _ece(y, p, n_bins=10):
    edges = np.linspace(0, 1, n_bins + 1)
    e = 0.0
    for i in range(n_bins):
        mask = (p >= edges[i]) & (p < edges[i + 1] if i < n_bins - 1 else p <= edges[i + 1])
        if not mask.any():
            continue
        acc = (y[mask] == 1).mean()
        conf = p[mask].mean()
        e += (mask.sum() / len(p)) * abs(acc - conf)
    return float(e)


def _full_metrics(df, p, t):
    yhat = (p >= t).astype(int)
    y = df.label.values
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {
        "n": int(len(df)), "threshold": float(t),
        "accuracy": float((yhat == y).mean()),
        "precision": float(precision_score(y, yhat, zero_division=0)),
        "recall": float(recall_score(y, yhat, zero_division=0)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "ece": _ece(y, p), "brier": float(brier_score_loss(y, p)),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def _per_group(df, p, t, col):
    out = {}
    for g, gdf in df.groupby(col):
        i = gdf.index
        yhat = (p[i] >= t).astype(int)
        row = {"n": int(len(gdf))}
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


def _latency(pipe, sample, batch_size, n_batches=30):
    times = []
    for i in range(n_batches):
        batch = sample[i * batch_size : (i + 1) * batch_size]
        if not batch:
            batch = sample[:batch_size]
        t0 = time.perf_counter()
        _ = pipe.predict_proba(batch)
        times.append((time.perf_counter() - t0) * 1000.0)
    arr = np.asarray(times)
    return float(arr.mean()), float(np.percentile(arr, 95))


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _load(name):
    return pd.read_parquet(f"data/processed/{name}.parquet").reset_index(drop=True)


TRAIN = None
VAL = None
TEST = None
EXTERNAL = None


def load_splits():
    global TRAIN, VAL, TEST, EXTERNAL
    TRAIN = _load("train")
    VAL = _load("val")
    TEST = _load("test")
    EXTERNAL = pd.read_parquet(
        "data/external_benchmark/benchmark.parquet").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pipeline factory
# ---------------------------------------------------------------------------

def make_pipeline(params: dict) -> Pipeline:
    """Build a fresh LogReg+F3 pipeline from a parameter dict."""
    word = TfidfVectorizer(
        ngram_range=params["word_ngram_range"],
        min_df=params["word_min_df"],
        max_df=params["word_max_df"],
        max_features=params["word_max_features"],
        sublinear_tf=params["sublinear_tf"],
    )
    char = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=params["char_ngram_range"],
        min_df=params["char_min_df"],
        max_features=params["char_max_features"],
        sublinear_tf=params["sublinear_tf"],
    )
    feats = FeatureUnion([("w", word), ("c", char)])
    clf = LogisticRegression(
        C=params["C"], penalty=params["penalty"],
        class_weight=params["class_weight"],
        solver="liblinear", max_iter=3000, random_state=SEED,
    )
    return Pipeline([("feats", feats), ("clf", clf)])


# ---------------------------------------------------------------------------
# E4 — HPO
# ---------------------------------------------------------------------------

TRIAL_LOG: list[dict] = []


def objective(trial) -> float:
    params = {
        "C": trial.suggest_float("C", 0.05, 20.0, log=True),
        "penalty": trial.suggest_categorical("penalty", ["l1", "l2"]),
        "class_weight": trial.suggest_categorical("class_weight",
                                                  ["balanced", None]),
        "word_ngram_range": trial.suggest_categorical(
            "word_ngram_range", [(1, 1), (1, 2), (1, 3)]),
        "word_min_df": trial.suggest_int("word_min_df", 2, 5),
        "word_max_df": trial.suggest_float("word_max_df", 0.90, 1.0),
        "word_max_features": trial.suggest_categorical(
            "word_max_features", [100_000, 200_000, 400_000]),
        "char_ngram_range": trial.suggest_categorical(
            "char_ngram_range", [(3, 5), (2, 5), (3, 6)]),
        "char_min_df": trial.suggest_int("char_min_df", 2, 5),
        "char_max_features": trial.suggest_categorical(
            "char_max_features", [200_000, 300_000, 500_000]),
        "sublinear_tf": trial.suggest_categorical("sublinear_tf", [True, False]),
    }

    t0 = time.time()
    pipe = make_pipeline(params)
    pipe.fit(TRAIN.text, TRAIN.label)
    fit_secs = time.time() - t0

    p_val = pipe.predict_proba(VAL.text)[:, 1]
    val_pr_auc = float(average_precision_score(VAL.label, p_val))
    val_roc = float(roc_auc_score(VAL.label, p_val))
    val_ece = _ece(VAL.label.values, p_val)

    # Model size — persist to a temp path
    tmp = EXP / f"_hpo_trial_{trial.number}.joblib"
    EXP.mkdir(exist_ok=True)
    joblib.dump(pipe, tmp)
    size_bytes = int(os.path.getsize(tmp))
    tmp.unlink()

    row = {
        "trial": trial.number, "params": params, "fit_secs": round(fit_secs, 1),
        "val_pr_auc": val_pr_auc, "val_roc_auc": val_roc,
        "val_ece": val_ece, "model_size_bytes": size_bytes,
    }
    TRIAL_LOG.append(row)
    print(f"  trial {trial.number:2d}: val_PR_AUC={val_pr_auc:.4f} "
          f"ECE={val_ece:.3f} fit={fit_secs:.1f}s "
          f"C={params['C']:.3f} pen={params['penalty']} "
          f"cw={params['class_weight']} wng={params['word_ngram_range']} "
          f"wmf={params['word_max_features']} cng={params['char_ngram_range']}")
    return val_pr_auc


def run_e4(n_trials=20, patience=8):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    load_splits()
    print(f"\n===== E4 :: HPO on LogReg + F3 (up to {n_trials} trials, "
          f"early-stop after {patience} no-improvement) =====")
    print(f"  train={len(TRAIN):,} val={len(VAL):,} test={len(TEST):,}")

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=SEED))
    best_so_far = -1.0
    no_improve = 0
    for i in range(n_trials):
        study.optimize(objective, n_trials=1)
        if study.best_value > best_so_far + 1e-6:
            best_so_far = study.best_value
            no_improve = 0
        else:
            no_improve += 1
        if no_improve >= patience:
            print(f"[E4] early-stop: {patience} trials without improvement "
                  f"(best val_PR_AUC={best_so_far:.4f} at trial {study.best_trial.number})")
            break

    best = study.best_trial
    result = {
        "n_trials_run": len(TRIAL_LOG),
        "best_trial": best.number,
        "best_val_pr_auc": float(best.value),
        "best_params": {k: (list(v) if isinstance(v, tuple) else v)
                        for k, v in best.params.items()},
        "improvement_vs_e3_val": float(best.value) - E3_BASELINE["val_pr_auc"],
    }
    (REP / "e4_trials.json").write_text(
        json.dumps([{**r, "params": {k: (list(v) if isinstance(v, tuple) else v)
                                     for k, v in r["params"].items()}}
                    for r in TRIAL_LOG], indent=2))
    (REP / "e4_best.json").write_text(json.dumps(result, indent=2))
    print(f"\n[E4] {len(TRIAL_LOG)} trials completed. "
          f"Best: trial {best.number}, val_PR_AUC={best.value:.4f}")
    print(f"[E4] improvement vs E3 baseline (val PR-AUC {E3_BASELINE['val_pr_auc']:.4f}): "
          f"{result['improvement_vs_e3_val']:+.4f}")
    return best.params


# ---------------------------------------------------------------------------
# E5 — Calibration + threshold study + final external eval
# ---------------------------------------------------------------------------

def run_e5(best_params: dict):
    print(f"\n===== E5 :: Calibration + threshold + final external eval =====")
    # Refit best pipeline on train
    print("  refitting best HPO pipeline on train...")
    t0 = time.time()
    pipe = make_pipeline(best_params)
    pipe.fit(TRAIN.text, TRAIN.label)
    fit_secs = time.time() - t0
    print(f"  refit done in {fit_secs:.1f}s")

    # Compare calibrations on val
    print("  comparing calibrations on val...")
    variants = {}
    # 1) no calibration — use pipe directly
    p_val_none = pipe.predict_proba(VAL.text)[:, 1]
    variants["none"] = {"pipe": pipe, "p_val": p_val_none}
    # 2) Platt (sigmoid) cv=3
    print("    fitting Platt (cv=3)...")
    platt = CalibratedClassifierCV(pipe, method="sigmoid", cv=3)
    platt.fit(TRAIN.text, TRAIN.label)
    p_val_platt = platt.predict_proba(VAL.text)[:, 1]
    variants["platt"] = {"pipe": platt, "p_val": p_val_platt}
    # 3) Isotonic cv=3
    print("    fitting isotonic (cv=3)...")
    iso = CalibratedClassifierCV(pipe, method="isotonic", cv=3)
    iso.fit(TRAIN.text, TRAIN.label)
    p_val_iso = iso.predict_proba(VAL.text)[:, 1]
    variants["isotonic"] = {"pipe": iso, "p_val": p_val_iso}

    # Score each on val
    cal_report = {}
    for name, v in variants.items():
        p = v["p_val"]
        y = VAL.label.values
        cal_report[name] = {
            "val_pr_auc": float(average_precision_score(y, p)),
            "val_roc_auc": float(roc_auc_score(y, p)),
            "val_ece": _ece(y, p),
            "val_brier": float(brier_score_loss(y, p)),
        }
        print(f"    {name:9s}: PR-AUC={cal_report[name]['val_pr_auc']:.4f} "
              f"ECE={cal_report[name]['val_ece']:.4f} "
              f"Brier={cal_report[name]['val_brier']:.4f}")

    # Pick winner by lowest ECE
    cal_winner = min(cal_report, key=lambda n: cal_report[n]["val_ece"])
    print(f"  calibration winner (lowest ECE): {cal_winner}")

    winning_pipe = variants[cal_winner]["pipe"]
    p_val = variants[cal_winner]["p_val"]

    # Threshold optimisation on val (F1-max)
    ths = np.linspace(0.01, 0.99, 197)
    f1s = np.array([f1_score(VAL.label, p_val >= t) for t in ths])
    t_f1 = float(ths[int(np.argmax(f1s))])
    ok = [t for t in ths
          if precision_score(VAL.label, p_val >= t, zero_division=0) >= 0.98
          and (p_val >= t).sum() > 0]
    t_prec = float(min(ok)) if ok else t_f1
    print(f"  optimal thresholds on val: F1-max={t_f1:.3f}, "
          f"precision-floor(0.98)={t_prec:.3f}")

    # Test + external eval
    print("  scoring test + external...")
    p_test = winning_pipe.predict_proba(TEST.text)[:, 1]
    p_ext = winning_pipe.predict_proba(EXTERNAL.text)[:, 1]
    test_metrics = _full_metrics(TEST, p_test, t_f1)
    ext_metrics = _full_metrics(EXTERNAL, p_ext, t_f1)
    per_cat_test = _per_group(TEST, p_test, t_f1, "category")
    per_src_test = _per_group(TEST, p_test, t_f1, "source")
    per_cat_ext = _per_group(EXTERNAL, p_ext, t_f1, "category")
    per_src_ext = _per_group(EXTERNAL, p_ext, t_f1, "source")

    # Save final bundle
    bundle_path = EXP / "E5_final_logreg_F3.joblib"
    joblib.dump({
        "model": winning_pipe, "feature_set": "F3", "model_name": "logreg",
        "hpo_params": best_params, "calibration": cal_winner,
        "threshold_f1": t_f1, "threshold_precision_floor": t_prec,
    }, bundle_path)
    size_bytes = int(os.path.getsize(bundle_path))

    # Latency
    lat_sample = TEST.text.sample(n=min(len(TEST), 500),
                                  random_state=SEED).tolist()
    l1m, l1p = _latency(winning_pipe, lat_sample, 1)
    l32m, l32p = _latency(winning_pipe, lat_sample, 32)

    # Memory during inference
    proc = psutil.Process()
    mem_before = proc.memory_info().rss
    tracemalloc.start()
    _ = winning_pipe.predict_proba(lat_sample[:100])
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    mem_after = proc.memory_info().rss
    mem_report = {
        "process_rss_before_bytes": int(mem_before),
        "process_rss_after_bytes": int(mem_after),
        "tracemalloc_peak_bytes_during_predict_100": int(peak),
    }

    final = {
        "e4_best_params": best_params,
        "e5_calibration_winner": cal_winner,
        "e5_calibration_report": cal_report,
        "e5_thresholds": {"F1_max": t_f1, "precision_floor_0.98": t_prec},
        "test_internal": test_metrics,
        "external": ext_metrics,
        "per_category_test": per_cat_test,
        "per_source_test": per_src_test,
        "per_category_external": per_cat_ext,
        "per_source_external": per_src_ext,
        "model_size_bytes": size_bytes,
        "latency_ms": {"batch_1_mean": round(l1m, 3), "batch_1_p95": round(l1p, 3),
                       "batch_32_mean": round(l32m, 3), "batch_32_p95": round(l32p, 3)},
        "memory": mem_report,
        "e3_baseline_reference": E3_BASELINE,
    }
    (REP / "e5_calibration.json").write_text(json.dumps(cal_report, indent=2))
    (REP / "e5_final.json").write_text(json.dumps(final, indent=2, default=str))
    print(f"\n[E5] final bundle: {bundle_path}")
    print(f"[E5] test:  PR-AUC {test_metrics['pr_auc']:.4f}  F1 {test_metrics['f1']:.4f}  "
          f"ECE {test_metrics['ece']:.4f}")
    print(f"[E5] ext:   PR-AUC {ext_metrics['pr_auc']:.4f}  F1 {ext_metrics['f1']:.4f}  "
          f"ECE {ext_metrics['ece']:.4f}")
    return final


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------

def render_report(best_params: dict, final: dict) -> None:
    L: list[str] = []
    p = L.append
    b = E3_BASELINE
    t = final["test_internal"]
    e = final["external"]
    p("# E4 (HPO) + E5 (Calibration + Threshold) — Final Report")
    p("")
    p("Frozen production candidate: **LogReg + F3** (word TF-IDF ∪ char TF-IDF).")
    p("")

    p("## E4 — Hyperparameter Optimisation")
    p(f"- Trials run: {len(TRIAL_LOG)} (early-stop patience 8, budget 20)")
    p(f"- Objective: validation PR-AUC (single train fit, val eval)")
    p(f"- Best trial val PR-AUC: **{max(r['val_pr_auc'] for r in TRIAL_LOG):.4f}**")
    p(f"- E3 baseline val PR-AUC: **{b['val_pr_auc']:.4f}**")
    diff_val = max(r['val_pr_auc'] for r in TRIAL_LOG) - b['val_pr_auc']
    p(f"- Δ val PR-AUC: **{diff_val:+.4f}**")
    p("")
    p("### Best parameters")
    p("| param | value |")
    p("|---|---|")
    for k, v in best_params.items():
        p(f"| `{k}` | `{v}` |")
    p("")

    p("## E5 — Calibration comparison (measured on val)")
    p("| method | val PR-AUC | val ROC-AUC | val ECE | val Brier |")
    p("|---|---:|---:|---:|---:|")
    for name, r in final["e5_calibration_report"].items():
        marker = " ← selected" if name == final["e5_calibration_winner"] else ""
        p(f"| {name}{marker} | {r['val_pr_auc']:.4f} | {r['val_roc_auc']:.4f} | "
          f"{r['val_ece']:.4f} | {r['val_brier']:.4f} |")
    p("")

    p("## E5 — Threshold selection (on val)")
    p(f"- F1-max threshold: **{final['e5_thresholds']['F1_max']:.3f}**")
    p(f"- Precision-floor(0.98) threshold: {final['e5_thresholds']['precision_floor_0.98']:.3f}")
    p("")

    p("## Final headline metrics")
    p("| split | accuracy | precision | recall | F1 | ROC-AUC | PR-AUC | ECE | Brier |")
    p("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, m in [("internal test", t), ("external benchmark", e)]:
        p(f"| {name} | {m['accuracy']:.4f} | {m['precision']:.4f} | {m['recall']:.4f} | "
          f"{m['f1']:.4f} | {m['roc_auc']:.4f} | {m['pr_auc']:.4f} | "
          f"{m['ece']:.4f} | {m['brier']:.4f} |")
    p("")
    p(f"- Confusion (test, t={t['threshold']:.3f}): {t['confusion']}")
    p(f"- Confusion (external, t={e['threshold']:.3f}): {e['confusion']}")
    p("")

    p("## Delta vs the E3 baseline (LogReg + F3, no HPO, no calibration)")
    p("| metric | E3 baseline | E4+E5 final | Δ |")
    p("|---|---:|---:|---:|")
    p(f"| test PR-AUC | {b['test_pr_auc']:.4f} | {t['pr_auc']:.4f} | {t['pr_auc']-b['test_pr_auc']:+.4f} |")
    p(f"| test F1 | {b['test_f1']:.4f} | {t['f1']:.4f} | {t['f1']-b['test_f1']:+.4f} |")
    p(f"| ext PR-AUC | {b['ext_pr_auc']:.4f} | {e['pr_auc']:.4f} | {e['pr_auc']-b['ext_pr_auc']:+.4f} |")
    p(f"| ext F1 | {b['ext_f1']:.4f} | {e['f1']:.4f} | {e['f1']-b['ext_f1']:+.4f} |")
    p(f"| ext ECE | {b['ext_ece']:.4f} | {e['ece']:.4f} | {e['ece']-b['ext_ece']:+.4f} |")
    p("")

    p("## Per-category recall (external, scam categories)")
    p("| category | n | recall |")
    p("|---|---:|---:|")
    for c, r in sorted(final["per_category_external"].items()):
        if "recall" in r:
            p(f"| {c} | {r['n']} | {r['recall']:.3f} |")
    p("")
    p("## Per-category FP rate (external, ham categories)")
    p("| category | n | fp_rate |")
    p("|---|---:|---:|")
    for c, r in sorted(final["per_category_external"].items()):
        if "fp_rate" in r:
            p(f"| {c} | {r['n']} | {r['fp_rate']:.4f} |")
    p("")

    p("## Per-source (external)")
    p("| source | n | metric |")
    p("|---|---:|---|")
    for s, r in sorted(final["per_source_external"].items()):
        if "recall" in r:
            m = f"P {r.get('precision','n/a'):.3f}  R {r['recall']:.3f}  F1 {r['f1']:.3f}" \
                if "precision" in r else f"recall {r['recall']:.3f}"
        else:
            m = f"fp_rate {r.get('fp_rate','n/a'):.4f}"
        p(f"| {s} | {r['n']} | {m} |")
    p("")

    p("## Operational metrics")
    p(f"- Model size: **{final['model_size_bytes']/1e6:.1f} MB**")
    p(f"- Prediction latency batch-1: mean **{final['latency_ms']['batch_1_mean']} ms**, "
      f"p95 {final['latency_ms']['batch_1_p95']} ms")
    p(f"- Prediction latency batch-32: mean {final['latency_ms']['batch_32_mean']} ms, "
      f"p95 {final['latency_ms']['batch_32_p95']} ms")
    p(f"- Peak allocation during predict_proba(100 samples): "
      f"**{final['memory']['tracemalloc_peak_bytes_during_predict_100']/1e6:.1f} MB**")
    p(f"- Process RSS before/after inference: "
      f"{final['memory']['process_rss_before_bytes']/1e6:.1f} MB → "
      f"{final['memory']['process_rss_after_bytes']/1e6:.1f} MB")
    p("")

    # -----------------------------------------------------------------------
    # The four questions
    # -----------------------------------------------------------------------
    hpo_lift_val = max(r['val_pr_auc'] for r in TRIAL_LOG) - b['val_pr_auc']
    hpo_lift_ext = e['pr_auc'] - b['ext_pr_auc']
    cal_none_ece = final["e5_calibration_report"]["none"]["val_ece"]
    cal_winner_ece = final["e5_calibration_report"][final["e5_calibration_winner"]]["val_ece"]
    ece_lift = cal_none_ece - cal_winner_ece
    ext_ece_lift = b["ext_ece"] - e["ece"]
    ext_f1_lift = e["f1"] - b["ext_f1"]

    p("## Answers to the four questions")
    p("")
    q1 = ("Yes" if hpo_lift_val >= 0.003 else
          "No, not meaningfully" if hpo_lift_val <= 0.001 else
          "Marginal")
    p(f"**1. Did hyperparameter optimisation produce a meaningful improvement?**  {q1}.")
    p(f"   Val PR-AUC change: {hpo_lift_val:+.4f}. External PR-AUC change: "
      f"{hpo_lift_ext:+.4f} (from {b['ext_pr_auc']:.4f} to {e['pr_auc']:.4f}). "
      f"The bootstrap 95% CI on this dataset's PR-AUC in E1 spanned roughly "
      f"±0.006, so shifts below ~0.003 are within noise. This result is "
      f"{'above' if hpo_lift_ext > 0.003 else 'within'} that noise floor.")
    p("")
    q2 = ("Yes" if ece_lift > 0.005 or ext_ece_lift > 0.005 else
          "No, ECE was already good" if final["e5_calibration_winner"] == "none" else
          "Marginal")
    p(f"**2. Did calibration improve probability quality?**  {q2}.")
    p(f"   ECE went from {cal_none_ece:.4f} (no calibration) to {cal_winner_ece:.4f} "
      f"(winner: {final['e5_calibration_winner']}) on val — a change of "
      f"{ece_lift:+.4f}. On external: baseline ECE {b['ext_ece']:.4f} → "
      f"final ECE {e['ece']:.4f} ({-ext_ece_lift:+.4f}). "
      f"LogReg outputs are near-linearly-calibrated sigmoid probabilities by "
      f"construction; large lifts from Platt/isotonic are rare on this model.")
    p("")
    q3 = ("Yes" if ext_f1_lift > 0.005 else
          "No, threshold was already near-optimal" if abs(ext_f1_lift) < 0.002 else
          "Marginal")
    p(f"**3. Did threshold optimisation improve external F1?**  {q3}.")
    p(f"   External F1 baseline {b['ext_f1']:.4f} → final {e['f1']:.4f} "
      f"({ext_f1_lift:+.4f}). E3 baseline's threshold was also selected on val, "
      f"so this measures HPO + calibration effects on the threshold curve.")
    p("")
    is_meaningful = (hpo_lift_ext > 0.003 or ext_f1_lift > 0.005 or
                     ext_ece_lift > 0.005)
    if is_meaningful:
        p(f"**4. Is the tuned model now the recommended final production model?**  Yes.")
        p(f"   The E4+E5 pipeline produced material improvement on at least one of "
          f"{{external PR-AUC, external F1, external ECE}}. The tuned bundle "
          f"`experiments/E5_final_logreg_F3.joblib` replaces the E3 baseline "
          f"as the production candidate.")
    else:
        p(f"**4. Is the tuned model now the recommended final production model?**  No.")
        p(f"   None of {{external PR-AUC, external F1, external ECE}} improved by a "
          f"practically meaningful margin (thresholds: PR-AUC > 0.003, F1 > 0.005, "
          f"ECE > 0.005). The original F3 + LogReg configuration "
          f"(`experiments/E2_F3_with_synth.joblib`) remains the recommended "
          f"final model. HPO/calibration/threshold gains on this feature+model "
          f"combination are within statistical noise; further compute is better "
          f"spent on data or feature work than on retuning a model that is already "
          f"near its ceiling for this configuration.")
    p("")

    (REP / "e4_e5_report.md").write_text("\n".join(L) + "\n")
    print(f"\n[E4+E5] wrote reports/e4_e5_report.md")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main():
    from scamradar.approval import require_dataset_approval
    require_dataset_approval()
    best_params = run_e4(n_trials=20, patience=8)
    # Ensure ngram tuples (Optuna serialises tuples as-is but be safe)
    best_params = {k: (tuple(v) if isinstance(v, list) else v)
                   for k, v in best_params.items()}
    final = run_e5(best_params)
    render_report(best_params, final)

    from scamradar.tracking import log as track_log
    track_log(
        "E4 HPO + E5 calibration study",
        "Focused HPO on frozen LogReg+F3; three calibrations compared; final external eval",
        {"n_trials": len(TRIAL_LOG), "best_params": {
            k: (list(v) if isinstance(v, tuple) else v)
            for k, v in best_params.items()}},
        {"ext_pr_auc": final["external"]["pr_auc"],
         "ext_f1": final["external"]["f1"],
         "ext_ece": final["external"]["ece"],
         "calibration_winner": final["e5_calibration_winner"],
         "threshold_f1_max": final["e5_thresholds"]["F1_max"]},
        conclusion="see reports/e4_e5_report.md for the 4-question answer.")


if __name__ == "__main__":
    main()
