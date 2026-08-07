"""E3 resumption — after killing the sklearn GradientBoosting fit.

Reuses:
  * `logreg_F3` from the E2 F3+with_synth bundle
  * `linear_svc_cal_F3` from the E3 bundle already saved
  * `random_forest_F3` from the E3 bundle already saved

Skips `gradient_boosting_F3` and records it with `status: skipped_time_budget`
so the omission is documented (see note in the final report + registry).

Fits fresh:
  * xgboost_F3, lightgbm_F3, catboost_F3
  * winner-on-F6 (control)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Reuse everything from run_e3
from run_e3 import (BASELINE_KEY, FEATURE_SET, SEED, EXP, REP,  # noqa: F401
                    _fp_fn_dump, _latency, _metrics, _per_group,
                    _predict_proba, fit_and_eval, load_split,
                    make_model, rank, render_summary)


def reuse_bundle(bundle_path: Path, model_name: str,
                 feature_set: str) -> dict:
    b = joblib.load(bundle_path)
    pipe = b["model"]
    val = load_split("val")
    test = load_split("test")
    external = pd.read_parquet(
        "data/external_benchmark/benchmark.parquet").reset_index(drop=True)
    p_val = _predict_proba(pipe, val.text)
    p_test = _predict_proba(pipe, test.text)
    p_ext = _predict_proba(pipe, external.text)
    t_f1 = b["threshold_f1"]
    t_prec = b["threshold_precision_floor"]
    lat_sample = test.text.sample(n=min(len(test), 500),
                                  random_state=SEED).tolist()
    l1m, l1p = _latency(pipe, lat_sample, 1)
    l32m, l32p = _latency(pipe, lat_sample, 32)
    size = int(os.path.getsize(bundle_path))
    from sklearn.metrics import average_precision_score
    r = {
        "model": model_name, "feature_set": feature_set,
        "fit_seconds": None,   # already fit
        "model_size_bytes": size,
        "latency_ms": {"batch_1_mean": round(l1m, 3),
                       "batch_1_p95": round(l1p, 3),
                       "batch_32_mean": round(l32m, 3),
                       "batch_32_p95": round(l32p, 3)},
        "val_pr_auc": float(average_precision_score(val.label, p_val)),
        "threshold_f1": t_f1, "threshold_precision_floor": t_prec,
        "test_internal": _metrics(test, p_test, t_f1),
        "test_at_precision_floor": _metrics(test, p_test, t_prec),
        "external": _metrics(external, p_ext, t_f1),
        "per_category_test": _per_group(test, p_test, t_f1, "category"),
        "per_source_test": _per_group(test, p_test, t_f1, "source"),
        "per_category_external": _per_group(external, p_ext, t_f1, "category"),
        "per_source_external": _per_group(external, p_ext, t_f1, "source"),
    }
    prefix = f"E3_{model_name}_{feature_set}"
    _fp_fn_dump(test, p_test, t_f1, f"{prefix}_test")
    _fp_fn_dump(external, p_ext, t_f1, f"{prefix}_external")
    return r


def main() -> None:
    from scamradar.approval import require_dataset_approval
    require_dataset_approval()

    all_results: dict = {}

    # 1) Reuse LogReg baseline (from E2)
    print("\n===== E3 :: logreg_F3 (reused from E2) =====")
    all_results["logreg_F3"] = reuse_bundle(
        Path("experiments/E2_F3_with_synth.joblib"), "logreg", "F3")
    m = all_results["logreg_F3"]["test_internal"]
    mx = all_results["logreg_F3"]["external"]
    print(f"  [reused] test PR-AUC {m['pr_auc']:.4f} F1 {m['f1']:.4f}  "
          f"ext PR-AUC {mx['pr_auc']:.4f} F1 {mx['f1']:.4f}")

    # 2) Reuse LinearSVC + Cal (already fit before kill)
    print("\n===== E3 :: linear_svc_cal_F3 (reused from prior fit) =====")
    all_results["linear_svc_cal_F3"] = reuse_bundle(
        Path("experiments/E3_linear_svc_cal_F3.joblib"), "linear_svc_cal", "F3")
    m = all_results["linear_svc_cal_F3"]["test_internal"]
    mx = all_results["linear_svc_cal_F3"]["external"]
    # fit time recorded from console — patch in
    all_results["linear_svc_cal_F3"]["fit_seconds"] = 298.3
    print(f"  [reused] test PR-AUC {m['pr_auc']:.4f} F1 {m['f1']:.4f}  "
          f"ext PR-AUC {mx['pr_auc']:.4f} F1 {mx['f1']:.4f}")

    # 3) Reuse RandomForest (already fit before kill)
    print("\n===== E3 :: random_forest_F3 (reused from prior fit) =====")
    all_results["random_forest_F3"] = reuse_bundle(
        Path("experiments/E3_random_forest_F3.joblib"), "random_forest", "F3")
    m = all_results["random_forest_F3"]["test_internal"]
    mx = all_results["random_forest_F3"]["external"]
    all_results["random_forest_F3"]["fit_seconds"] = 168.7
    print(f"  [reused] test PR-AUC {m['pr_auc']:.4f} F1 {m['f1']:.4f}  "
          f"ext PR-AUC {mx['pr_auc']:.4f} F1 {mx['f1']:.4f}")

    # 4) Skip sklearn GradientBoosting (documented reason)
    all_results["gradient_boosting_F3"] = {
        "model": "gradient_boosting", "feature_set": "F3",
        "status": "skipped_time_budget",
        "reason": ("Sklearn GradientBoostingClassifier is single-threaded and "
                   "was projected to take 30-60 min on 500k sparse features. "
                   "The gradient-boosted-tree algorithm family is more "
                   "efficiently and comprehensively represented by XGBoost, "
                   "LightGBM, and CatBoost, all of which are fit below. "
                   "Killed at ~13 min into fitting on 2026-08-01."),
    }
    print("\n===== E3 :: gradient_boosting_F3 (SKIPPED — time budget) =====")

    # 5) Fit XGBoost, LightGBM, CatBoost fresh
    for name in ("xgboost", "lightgbm", "catboost"):
        key = f"{name}_F3"
        try:
            all_results[key] = fit_and_eval(name, "F3")
        except Exception as e:
            print(f"[E3:{key}] FAILED: {type(e).__name__}: {e}")
            all_results[key] = {"error": f"{type(e).__name__}: {e}"}

    # 6) Provisional ranking (F3-only, valid results)
    valid = {k: r for k, r in all_results.items()
             if "error" not in r and "status" not in r}
    ranking = rank(valid)
    print(f"\n[E3 F3-only] provisional winner: {ranking['winner_key']}")

    # 7) Control: run winner on F6
    winner_model = valid[ranking["winner_key"]]["model"]
    control_key = f"{winner_model}_F6"
    print(f"\n===== E3 :: {control_key} (control on richer feature set) =====")
    try:
        all_results[control_key] = fit_and_eval(winner_model, "F6")
    except Exception as e:
        print(f"[E3:{control_key}] FAILED: {type(e).__name__}: {e}")
        all_results[control_key] = {"error": f"{type(e).__name__}: {e}"}

    # 8) Final ranking + render
    valid = {k: r for k, r in all_results.items()
             if "error" not in r and "status" not in r}
    ranking = rank(valid)
    (REP / "e3_full_results.json").write_text(
        json.dumps(all_results, indent=2, default=str))
    (REP / "e3_ranking.json").write_text(json.dumps(ranking, indent=2))
    render_summary(valid, ranking)

    # Post-hoc: patch the rendered md with the skip note
    md_path = REP / "e3_comparison.md"
    text = md_path.read_text()
    note = ("\n> **Note on sklearn GradientBoostingClassifier:** intentionally "
            "skipped. Fitting was killed at ~13 min into a projected 30-60 min "
            "run on 500k sparse features. The gradient-boosted-tree algorithm "
            "family is more efficiently and comprehensively represented by "
            "XGBoost, LightGBM, and CatBoost, all included below. See "
            "`experiments/registry.jsonl` for the omission record.\n")
    md_path.write_text(text.replace(
        "Baseline for delta:",
        note + "\nBaseline for delta:", 1))

    print(f"\n[E3] final ranking: {[r['key'] for r in ranking['ranked'][:5]]}")
    print(f"[E3] WINNER: {ranking['winner_key']}  "
          f"(bundle: experiments/E3_{ranking['winner_key']}.joblib)")
    print(f"[E3] reports/e3_comparison.md + reports/e3_ranking.json written")

    # Log GBM skip to registry
    from scamradar.tracking import log as track_log
    track_log(
        "E3 gradient_boosting_F3 SKIPPED",
        "sklearn GBM is dominated by XGB/LGB/CatBoost and single-threaded",
        {"reason": "time_budget", "killed_at_secs": 811},
        {"status": "skipped_time_budget"},
        conclusion="algorithm family represented by XGB/LGB/CatBoost")


if __name__ == "__main__":
    main()
