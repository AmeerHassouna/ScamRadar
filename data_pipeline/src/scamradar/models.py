"""Stages 4–6 — model bake-off, HPO (Optuna), calibration, threshold tuning (spec §5–§6).

All model selection happens on cluster-grouped CV over TRAIN + the VAL split.
The external benchmark is never imported here — by design there is no code path to it.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score
from sklearn.model_selection import StratifiedGroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .features import build

SEED = 42


def model_zoo(seed=SEED) -> dict:
    zoo = {
        "logreg": LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0),
        "linear_svc_cal": CalibratedClassifierCV(
            LinearSVC(class_weight="balanced", C=0.5), method="sigmoid", cv=3),
        "random_forest": RandomForestClassifier(
            n_estimators=400, class_weight="balanced", n_jobs=-1, random_state=seed),
        "grad_boost": GradientBoostingClassifier(random_state=seed),
    }
    for name, cls, kw in [
        ("xgboost", "xgboost.XGBClassifier",
         dict(n_estimators=600, tree_method="hist", eval_metric="aucpr")),
        ("lightgbm", "lightgbm.LGBMClassifier",
         dict(n_estimators=600, class_weight="balanced", verbose=-1)),
        ("catboost", "catboost.CatBoostClassifier",
         dict(iterations=600, verbose=False)),
    ]:
        try:
            mod, attr = cls.rsplit(".", 1)
            zoo[name] = getattr(__import__(mod), attr)(random_state=seed, **kw)
        except ImportError:
            pass  # optional dep not installed — bake-off simply skips it
    return zoo


def _load(split):
    df = pd.read_parquet(f"data/processed/{split}.parquet")
    return df


def bakeoff(feature_set="F6", models=None, folds=5) -> dict:
    """Compare models under identical conditions: same features, same
    cluster-grouped stratified folds on train (spec §5)."""
    tr = _load("train")
    results = {}
    zoo = model_zoo()
    models = models or list(zoo)
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED)
    for name in models:
        pipe = Pipeline([("feats", build(feature_set)), ("clf", zoo[name])])
        try:
            scores = cross_val_score(pipe, tr.text, tr.label, scoring="average_precision",
                                     cv=cv, groups=tr.cluster_id, n_jobs=1)
            results[name] = {"pr_auc_cv_mean": float(scores.mean()),
                             "pr_auc_cv_std": float(scores.std())}
            print(f"[bakeoff] {feature_set} {name}: PR-AUC {scores.mean():.4f} ± {scores.std():.4f}")
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def tune(model_name="logreg", feature_set="F6", n_trials=40) -> dict:
    """Optuna TPE over model + vectorizer params; objective = grouped-CV PR-AUC on train."""
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    tr = _load("train")
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)

    def objective(trial):
        if model_name == "logreg":
            clf = LogisticRegression(max_iter=3000, class_weight="balanced",
                                     C=trial.suggest_float("C", 1e-3, 100, log=True))
        elif model_name == "lightgbm":
            import lightgbm as lgb
            clf = lgb.LGBMClassifier(
                random_state=SEED, class_weight="balanced", verbose=-1,
                n_estimators=trial.suggest_int("n_estimators", 200, 1200),
                learning_rate=trial.suggest_float("lr", 0.01, 0.3, log=True),
                num_leaves=trial.suggest_int("num_leaves", 15, 255),
                min_child_samples=trial.suggest_int("min_child", 5, 100))
        elif model_name == "xgboost":
            import xgboost as xgb
            clf = xgb.XGBClassifier(
                random_state=SEED, tree_method="hist", eval_metric="aucpr",
                n_estimators=trial.suggest_int("n_estimators", 200, 1200),
                learning_rate=trial.suggest_float("lr", 0.01, 0.3, log=True),
                max_depth=trial.suggest_int("max_depth", 3, 10),
                subsample=trial.suggest_float("subsample", 0.6, 1.0))
        else:
            raise ValueError(f"tuning not wired for {model_name}")
        pipe = Pipeline([("feats", build(feature_set)), ("clf", clf)])
        return cross_val_score(pipe, tr.text, tr.label, scoring="average_precision",
                               cv=cv, groups=tr.cluster_id, n_jobs=1).mean()

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    out = {"model": model_name, "feature_set": feature_set,
           "best_params": study.best_params, "cv_pr_auc": study.best_value}
    Path("experiments").mkdir(exist_ok=True)
    Path(f"experiments/hpo_{model_name}_{feature_set}.json").write_text(json.dumps(out, indent=2))
    print("[tune]", json.dumps(out))
    return out


def fit_final(model_name="logreg", feature_set="F6", params=None,
              calibration="sigmoid", precision_floor=0.98) -> Path:
    """Fit on train, calibrate, tune thresholds on VAL only (spec §6), save bundle."""
    tr, va = _load("train"), _load("val")
    zoo = model_zoo()
    clf = zoo[model_name]
    if params:
        clf.set_params(**params)
    base = Pipeline([("feats", build(feature_set)), ("clf", clf)])
    model = CalibratedClassifierCV(base, method=calibration, cv=3) \
        if calibration != "none" else base
    model.fit(tr.text, tr.label)

    p_val = model.predict_proba(va.text)[:, 1]
    ths = np.linspace(0.01, 0.99, 197)
    f1s = [f1_score(va.label, p_val >= t) for t in ths]
    t_f1 = float(ths[int(np.argmax(f1s))])
    ok = [t for t in ths if precision_score(va.label, p_val >= t, zero_division=0)
          >= precision_floor and (p_val >= t).sum() > 0]
    t_prec = float(min(ok)) if ok else t_f1

    bundle = {"model": model, "feature_set": feature_set, "model_name": model_name,
              "threshold_f1": t_f1, "threshold_precision_floor": t_prec,
              "precision_floor": precision_floor, "calibration": calibration,
              "val_pr_auc": float(average_precision_score(va.label, p_val))}
    Path("experiments").mkdir(exist_ok=True)
    out = Path(f"experiments/final_{model_name}_{feature_set}.joblib")
    joblib.dump(bundle, out)
    print(f"[fit_final] val PR-AUC {bundle['val_pr_auc']:.4f} | "
          f"t_f1={t_f1:.3f} t_prec={t_prec:.3f} -> {out}")
    return out
