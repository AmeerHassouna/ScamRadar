"""E3 — model bake-off on F3 (DESIGN §10).

Compares every classifier on the frozen F3 feature representation, the frozen
train/val/test/external splits, and the same seed. Measures:

  * Test + external metrics (accuracy, P, R, F1, ROC-AUC, PR-AUC)
  * Calibration quality (ECE, Brier score) — NOT calibrated in E3; measured
    natively so E5 can decide whether Platt/isotonic helps.
  * Inference latency (batch-1 and batch-32 mean + p95 over 500 samples)
  * Training time
  * Serialised model size (bytes)
  * Per-category + per-source (test AND external)
  * Top-N FP + FN CSV dumps
  * Delta vs the F3 + LogReg baseline reused from E2

Control: the strongest classifier is also fit on F6 to see whether a more
expressive model extracts signal from F5 that LogReg couldn't.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from scamradar.features import build

SEED = 42
EXP = Path("experiments")
REP = Path("reports")
PRECISION_FLOOR = 0.98
FEATURE_SET = "F3"


def load_split(name: str, exclude_synth: bool = False) -> pd.DataFrame:
    df = pd.read_parquet(f"data/processed/{name}.parquet").reset_index(drop=True)
    if exclude_synth:
        df = df[~df.is_synthetic].reset_index(drop=True)
    return df


def _ece(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (equal-width bins)."""
    edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (p >= edges[i]) & (p < edges[i + 1] if i < n_bins - 1 else p <= edges[i + 1])
        if not mask.any():
            continue
        acc = (y[mask] == 1).mean()
        conf = p[mask].mean()
        ece += (mask.sum() / len(p)) * abs(acc - conf)
    return float(ece)


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
        "ece": _ece(y, p),
        "brier": float(brier_score_loss(y, p)),
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
    df2 = df.assign(p=p, pred=(p >= t).astype(int))
    df2[(df2.pred == 1) & (df2.label == 0)].sort_values("p", ascending=False)\
        .head(top_k).to_csv(REP / f"{prefix}_fp_top{top_k}.csv", index=False)
    df2[(df2.pred == 0) & (df2.label == 1)].sort_values("p")\
        .head(top_k).to_csv(REP / f"{prefix}_fn_top{top_k}.csv", index=False)


def _latency(pipe, sample_texts: list[str], batch_size: int, n_batches: int = 30):
    """Return (mean_ms, p95_ms) per batch."""
    times: list[float] = []
    for i in range(n_batches):
        batch = sample_texts[i * batch_size : (i + 1) * batch_size]
        if not batch:
            batch = sample_texts[:batch_size]
        t0 = time.perf_counter()
        _ = pipe.predict_proba(batch)
        times.append((time.perf_counter() - t0) * 1000.0)
    arr = np.asarray(times)
    return float(arr.mean()), float(np.percentile(arr, 95))


# ---------------------------------------------------------------------------
# Model zoo — feature_set is baked in via a shared build()
# ---------------------------------------------------------------------------

def make_model(name: str, feature_set: str):
    fb = lambda: build(feature_set)
    if name == "logreg":
        return Pipeline([("feats", fb()),
                         ("clf", LogisticRegression(
                             max_iter=3000, class_weight="balanced",
                             C=1.0, solver="liblinear"))])
    if name == "linear_svc_cal":
        base = Pipeline([("feats", fb()),
                         ("clf", LinearSVC(class_weight="balanced", C=0.5,
                                           max_iter=3000))])
        return CalibratedClassifierCV(base, method="sigmoid", cv=3)
    if name == "random_forest":
        # Sparse F3 has ~500k features; keep n_estimators modest and rely on
        # sqrt max_features to bound per-split cost.
        return Pipeline([("feats", fb()),
                         ("clf", RandomForestClassifier(
                             n_estimators=100, class_weight="balanced",
                             max_features="sqrt", n_jobs=-1,
                             random_state=SEED))])
    if name == "gradient_boosting":
        # Sklearn GB doesn't accept class_weight and is single-threaded; kept
        # modest to fit in budget. Boosted-tree quality is expected to be
        # captured by xgboost / lightgbm / catboost anyway.
        return Pipeline([("feats", fb()),
                         ("clf", GradientBoostingClassifier(
                             n_estimators=100, max_depth=3, learning_rate=0.1,
                             random_state=SEED))])
    if name == "xgboost":
        import xgboost as xgb
        return Pipeline([("feats", fb()),
                         ("clf", xgb.XGBClassifier(
                             n_estimators=400, max_depth=6, learning_rate=0.1,
                             tree_method="hist", eval_metric="aucpr",
                             scale_pos_weight=5.0,  # ~scam:legit imbalance
                             random_state=SEED, n_jobs=-1, verbosity=0))])
    if name == "lightgbm":
        import lightgbm as lgb
        return Pipeline([("feats", fb()),
                         ("clf", lgb.LGBMClassifier(
                             n_estimators=400, num_leaves=63, learning_rate=0.1,
                             class_weight="balanced", random_state=SEED,
                             verbose=-1, n_jobs=-1))])
    if name == "catboost":
        import catboost as cat
        return Pipeline([("feats", fb()),
                         ("clf", cat.CatBoostClassifier(
                             iterations=400, depth=6, learning_rate=0.1,
                             auto_class_weights="Balanced",
                             random_seed=SEED, verbose=False))])
    raise ValueError(f"unknown model {name}")


MODELS = [
    "logreg",
    "linear_svc_cal",
    "random_forest",
    "gradient_boosting",
    "xgboost",
    "lightgbm",
    "catboost",
]


# ---------------------------------------------------------------------------
# Per-model runner
# ---------------------------------------------------------------------------

def _predict_proba(pipe, X):
    """Uniform predict_proba across sklearn Pipelines and CalibratedClassifierCV."""
    return pipe.predict_proba(X)[:, 1]


def fit_and_eval(name: str, feature_set: str = FEATURE_SET) -> dict:
    tag = f"{name}_{feature_set}"
    print(f"\n===== E3 :: {tag} =====")
    t0 = time.time()
    train = load_split("train")
    val = load_split("val")
    test = load_split("test")
    external = pd.read_parquet(
        "data/external_benchmark/benchmark.parquet").reset_index(drop=True)
    print(f"  n_train={len(train):,} n_val={len(val):,} n_test={len(test):,} "
          f"n_ext={len(external):,}")

    pipe = make_model(name, feature_set)
    fit_t0 = time.time()
    pipe.fit(train.text, train.label)
    fit_secs = time.time() - fit_t0
    print(f"  [fit] done in {fit_secs:.1f}s")

    # Predict on val for threshold selection
    p_val = _predict_proba(pipe, val.text)
    val_pr_auc = float(average_precision_score(val.label, p_val))
    ths = np.linspace(0.01, 0.99, 197)
    f1s = np.array([f1_score(val.label, p_val >= t) for t in ths])
    t_f1 = float(ths[int(np.argmax(f1s))])
    ok = [t for t in ths
          if precision_score(val.label, p_val >= t, zero_division=0) >= PRECISION_FLOOR
          and (p_val >= t).sum() > 0]
    t_prec = float(min(ok)) if ok else t_f1

    # Test + external
    p_test = _predict_proba(pipe, test.text)
    p_ext = _predict_proba(pipe, external.text)

    # Latency: 30 batches of 1, 30 batches of 32, over a shuffled test sample
    latency_sample = test.text.sample(n=min(len(test), 500),
                                      random_state=SEED).tolist()
    lat1_mean, lat1_p95 = _latency(pipe, latency_sample, batch_size=1)
    lat32_mean, lat32_p95 = _latency(pipe, latency_sample, batch_size=32)

    # Save bundle + measure size
    EXP.mkdir(exist_ok=True)
    REP.mkdir(exist_ok=True)
    bundle_path = EXP / f"E3_{tag}.joblib"
    joblib.dump({
        "model": pipe, "feature_set": feature_set, "model_name": name,
        "threshold_f1": t_f1, "threshold_precision_floor": t_prec,
        "val_pr_auc": val_pr_auc,
    }, bundle_path)
    model_size_bytes = int(os.path.getsize(bundle_path))

    result = {
        "model": name,
        "feature_set": feature_set,
        "fit_seconds": round(fit_secs, 1),
        "model_size_bytes": model_size_bytes,
        "latency_ms": {
            "batch_1_mean": round(lat1_mean, 3),
            "batch_1_p95": round(lat1_p95, 3),
            "batch_32_mean": round(lat32_mean, 3),
            "batch_32_p95": round(lat32_p95, 3),
        },
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

    (REP / f"eval_E3_{tag}_test.json").write_text(
        json.dumps({"at_f1_threshold": result["test_internal"],
                    "at_precision_floor_threshold": result["test_at_precision_floor"],
                    "per_category": result["per_category_test"],
                    "per_source": result["per_source_test"]}, indent=2))
    (REP / f"eval_E3_{tag}_external.json").write_text(
        json.dumps({"at_f1_threshold": result["external"],
                    "per_category": result["per_category_external"],
                    "per_source": result["per_source_external"]}, indent=2))
    _fp_fn_dump(test, p_test, t_f1, f"E3_{tag}_test")
    _fp_fn_dump(external, p_ext, t_f1, f"E3_{tag}_external")

    m = result["test_internal"]; mx = result["external"]
    print(f"  [eval] test:  PR-AUC {m['pr_auc']:.4f}  ROC-AUC {m['roc_auc']:.4f}  "
          f"F1 {m['f1']:.4f}  ECE {m['ece']:.4f}")
    print(f"  [eval] ext:   PR-AUC {mx['pr_auc']:.4f}  ROC-AUC {mx['roc_auc']:.4f}  "
          f"F1 {mx['f1']:.4f}  ECE {mx['ece']:.4f}")
    print(f"  [meta] fit={fit_secs:.1f}s  size={model_size_bytes/1e6:.1f}MB  "
          f"lat b1={lat1_mean:.2f}ms  b32={lat32_mean:.2f}ms")
    print(f"  [eval] total wallclock {time.time() - t0:.1f}s")
    return result


# ---------------------------------------------------------------------------
# Ranking + comparison
# ---------------------------------------------------------------------------

BASELINE_KEY = "logreg_F3"


def rank(all_results: dict) -> dict:
    """Rank by external PR-AUC first; tiebreak by test PR-AUC then ECE (low)."""
    rows = []
    for k, r in all_results.items():
        rows.append({
            "key": k,
            "model": r["model"],
            "feature_set": r["feature_set"],
            "ext_pr_auc": r["external"]["pr_auc"],
            "int_pr_auc": r["test_internal"]["pr_auc"],
            "ext_f1": r["external"]["f1"],
            "ext_ece": r["external"]["ece"],
            "fit_seconds": r["fit_seconds"],
            "model_size_mb": r["model_size_bytes"] / 1e6,
            "lat_b1_ms": r["latency_ms"]["batch_1_mean"],
        })
    ranked = sorted(rows, key=lambda r: (-r["ext_pr_auc"], -r["int_pr_auc"], r["ext_ece"]))
    return {
        "primary_metric": "external PR-AUC (higher)",
        "tiebreak": "internal test PR-AUC, then ECE (lower)",
        "ranked": ranked,
        "winner_key": ranked[0]["key"],
    }


def render_summary(all_results: dict, ranking: dict) -> None:
    L: list[str] = []
    p = L.append
    p("# E3 — Model Bake-off on F3 (word TF-IDF ∪ char TF-IDF)")
    p("")
    p("Held constant across all fits: F3 features, cluster-aware train/val/test/"
      "external splits, seed=42, threshold selected by max-F1 on val, precision-"
      "floor at 0.98. No calibration wrapper except for LinearSVC (which lacks "
      "native predict_proba). Calibration quality is *measured* (ECE, Brier); "
      "fitting calibration is E5's concern.")
    p("")

    p(f"Baseline for delta: **F3 + LogReg** (key `{BASELINE_KEY}`).")
    p("")

    baseline = all_results.get(BASELINE_KEY)

    p("## Absolute metrics — internal test")
    p("| model | fit s | size MB | lat b1 ms | lat b32 ms | val PR-AUC | test PR-AUC | test ROC-AUC | test F1 | test P | test R | test ECE | test Brier |")
    p("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in ranking["ranked"]:
        rr = all_results[r["key"]]
        m = rr["test_internal"]
        fs = f"{rr['fit_seconds']:.1f}" if rr['fit_seconds'] is not None else "reused"
        p(f"| {r['key']} | {fs} | {rr['model_size_bytes']/1e6:.1f} | "
          f"{rr['latency_ms']['batch_1_mean']} | {rr['latency_ms']['batch_32_mean']} | "
          f"{rr['val_pr_auc']:.4f} | "
          f"{m['pr_auc']:.4f} | {m['roc_auc']:.4f} | {m['f1']:.4f} | "
          f"{m['precision']:.4f} | {m['recall']:.4f} | {m['ece']:.4f} | {m['brier']:.4f} |")
    p("")

    p("## Absolute metrics — external benchmark")
    p("| model | ext PR-AUC | ext ROC-AUC | ext F1 | ext P | ext R | ext ECE | ext Brier |")
    p("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in ranking["ranked"]:
        m = all_results[r["key"]]["external"]
        p(f"| {r['key']} | {m['pr_auc']:.4f} | {m['roc_auc']:.4f} | {m['f1']:.4f} | "
          f"{m['precision']:.4f} | {m['recall']:.4f} | {m['ece']:.4f} | {m['brier']:.4f} |")
    p("")

    if baseline:
        p("## Delta vs F3 + LogReg baseline")
        b_i = baseline["test_internal"]
        b_e = baseline["external"]
        p("| model | Δ test PR-AUC | Δ test F1 | Δ test ECE | Δ ext PR-AUC | Δ ext F1 | Δ ext ECE |")
        p("|---|---:|---:|---:|---:|---:|---:|")
        for r in ranking["ranked"]:
            if r["key"] == BASELINE_KEY:
                continue
            rr = all_results[r["key"]]
            m = rr["test_internal"]; mx = rr["external"]
            p(f"| {r['key']} | {m['pr_auc']-b_i['pr_auc']:+.4f} | "
              f"{m['f1']-b_i['f1']:+.4f} | {m['ece']-b_i['ece']:+.4f} | "
              f"{mx['pr_auc']-b_e['pr_auc']:+.4f} | {mx['f1']-b_e['f1']:+.4f} | "
              f"{mx['ece']-b_e['ece']:+.4f} |")
        p("")

    p("## Per-category recall (external benchmark)")
    cats: set = set()
    for r in all_results.values():
        cats.update(r["per_category_external"].keys())
    scam_cats = sorted([c for c in cats if not c.startswith("ham_")])
    ham_cats = sorted([c for c in cats if c.startswith("ham_")])
    p("### Scam-category recall (↑ better)")
    header = "| category |" + "|".join(f" `{r['key']}`" for r in ranking["ranked"]) + " |"
    p(header)
    p("|---" + "|---:" * len(ranking["ranked"]) + "|")
    for c in scam_cats:
        row = [f"| {c}"]
        for r in ranking["ranked"]:
            v = all_results[r["key"]]["per_category_external"].get(c, {})
            row.append(f"{v.get('recall', float('nan')):.3f}" if "recall" in v else "-")
        p(" | ".join(row) + " |")
    p("")
    p("### Ham-category FP rate (↓ better)")
    p(header)
    p("|---" + "|---:" * len(ranking["ranked"]) + "|")
    for c in ham_cats:
        row = [f"| {c}"]
        for r in ranking["ranked"]:
            v = all_results[r["key"]]["per_category_external"].get(c, {})
            row.append(f"{v.get('fp_rate', float('nan')):.3f}" if "fp_rate" in v else "-")
        p(" | ".join(row) + " |")
    p("")

    p("## Ranking (primary: external PR-AUC, tiebreak: internal PR-AUC then ECE)")
    p("| rank | key | ext PR-AUC | int PR-AUC | ext F1 | ext ECE | fit s | size MB | lat b1 ms |")
    p("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for i, r in enumerate(ranking["ranked"], 1):
        fs = f"{r['fit_seconds']:.1f}" if r['fit_seconds'] is not None else "reused"
        p(f"| {i} | {r['key']} | {r['ext_pr_auc']:.4f} | {r['int_pr_auc']:.4f} | "
          f"{r['ext_f1']:.4f} | {r['ext_ece']:.4f} | {fs} | "
          f"{r['model_size_mb']:.1f} | {r['lat_b1_ms']} |")
    p("")

    (REP / "e3_comparison.md").write_text("\n".join(L) + "\n")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    from scamradar.approval import require_dataset_approval
    require_dataset_approval()

    all_results: dict = {}
    # 1. Reuse E2 F3 + LogReg as baseline (same split, same features, same seed)
    #    — measure the missing metrics (ECE, Brier, latency, size).
    print("\n===== E3 :: logreg_F3 (baseline, reused from E2 fit) =====")
    b_path = Path("experiments/E2_F3_with_synth.joblib")
    if not b_path.exists():
        raise SystemExit("Missing experiments/E2_F3_with_synth.joblib. Run E2 first.")
    b = joblib.load(b_path)
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
    size = int(os.path.getsize(b_path))
    r0 = {
        "model": "logreg", "feature_set": "F3",
        "fit_seconds": None,       # already fit in E2
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
    _fp_fn_dump(test, p_test, t_f1, "E3_logreg_F3_test")
    _fp_fn_dump(external, p_ext, t_f1, "E3_logreg_F3_external")
    all_results["logreg_F3"] = r0
    m = r0["test_internal"]; mx = r0["external"]
    print(f"  [reused] test PR-AUC {m['pr_auc']:.4f} F1 {m['f1']:.4f}  "
          f"ext PR-AUC {mx['pr_auc']:.4f} F1 {mx['f1']:.4f}  "
          f"ECE test {m['ece']:.4f} ext {mx['ece']:.4f}  "
          f"size {size/1e6:.1f}MB  lat b1 {l1m:.2f}ms")

    # 2. Fit the remaining models on F3
    for name in MODELS:
        if name == "logreg":
            continue
        key = f"{name}_F3"
        try:
            all_results[key] = fit_and_eval(name, "F3")
        except Exception as e:
            print(f"[E3:{key}] FAILED: {type(e).__name__}: {e}")
            all_results[key] = {"error": f"{type(e).__name__}: {e}"}

    # 3. Provisional ranking (F3-only)
    valid = {k: r for k, r in all_results.items() if "error" not in r}
    ranking = rank(valid)
    print(f"\n[E3 F3-only] provisional winner: {ranking['winner_key']}")

    # 4. Control: run the winner on F6 too
    winner_model = valid[ranking["winner_key"]]["model"]
    print(f"\n===== E3 :: {winner_model}_F6 (control on richer feature set) =====")
    control_key = f"{winner_model}_F6"
    try:
        all_results[control_key] = fit_and_eval(winner_model, "F6")
    except Exception as e:
        print(f"[E3:{control_key}] FAILED: {type(e).__name__}: {e}")
        all_results[control_key] = {"error": f"{type(e).__name__}: {e}"}

    # 5. Final ranking + render
    valid = {k: r for k, r in all_results.items() if "error" not in r}
    ranking = rank(valid)
    (REP / "e3_full_results.json").write_text(
        json.dumps(all_results, indent=2, default=str))
    (REP / "e3_ranking.json").write_text(json.dumps(ranking, indent=2))
    render_summary(valid, ranking)
    print(f"\n[E3] final ranking: {[r['key'] for r in ranking['ranked'][:5]]}")
    print(f"[E3] WINNER: {ranking['winner_key']}  "
          f"(bundle: experiments/E3_{ranking['winner_key']}.joblib)")
    print(f"[E3] reports/e3_comparison.md + reports/e3_ranking.json written")


if __name__ == "__main__":
    main()
