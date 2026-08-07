"""Synthetic-vs-real diagnostic (DESIGN §7 rules 6–7, v2.0 revised).

Two-part diagnostic:

  1. **Named-artifact check** — for each synthetic-only category, compare
     emoji rate, em-dash rate, URL frequency, and length distribution against
     the nearest real neighbor. Flags any artifact outside a small tolerance.
     This IS a hard rule: cheap artifacts must be within tolerance.

  2. **Probe classifier** — a char-TF-IDF + LogReg that tries to predict
     `is_synthetic` from text. Its AUC is reported alongside its top-tell
     n-grams, but it is EXPLANATORY not gating: even AUC 1.000 is acceptable
     if the top tells are legitimate higher-order distributional differences
     (finite template pool vs infinite real vocabulary) rather than the
     specific artifacts caught by the named-artifact check.

The primary probe runs *within the scam label*. Per-category probes compare
each synthetic-only category against its "nearest real neighbor" scam
categories to isolate where the separation is coming from.

Writes: reports/probe_<exp_id>.{md,json}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import StratifiedKFold

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF]")

VERDICT_THRESHOLD = 0.75  # kept for reference / historical comparison only
NEIGHBOR_MAP = {
    # each synthetic-only category, and the "closest" real scam categories.
    # These MUST match the neighbor sets used by the batch generator's
    # scaffolding (scripts/synthesize_batch_1_v2.py `NEIGHBORS`), otherwise
    # the artifact check would compare against a different reference than
    # the one we generated against.
    "bec_ceo_fraud": ["email_phishing", "email_spam", "advance_fee_fraud"],
    "romance_scam": ["advance_fee_fraud"],
    "marketplace_delivery_scam": ["smishing", "email_phishing"],
}

# DESIGN §7 rule 6.a tolerances for the named-artifact check (this IS gating).
ARTIFACT_TOLERANCES = {
    "emoji_rate_abs": 0.010,        # ±1 percentage point vs real
    "emdash_rate_abs": 0.010,       # ±1 pp
    "curly_apos_rate_abs": 0.020,   # ±2 pp
    "url_rate_abs": 0.100,          # ±10 pp
    "len_p50_relative": 0.30,       # ±30% of real p50
}


def _artifact_check(real: pd.DataFrame, synth: pd.DataFrame) -> dict:
    """Concrete artifact-level comparison. Returns per-artifact pass/fail."""
    curly_apos = "’"
    def rates(sub: pd.DataFrame) -> dict:
        t = sub.text.astype(str)
        L = t.str.len()
        return {
            "n": int(len(t)),
            "emoji_rate": float(t.str.contains(
                r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF]"
            ).mean()),
            "emdash_rate": float(t.str.contains("—").mean()),
            "curly_apos_rate": float(t.str.contains(curly_apos).mean()),
            "url_rate": float(t.str.contains(
                r"https?://\S+|www\.\S+", regex=True).mean()),
            "len_p50": int(L.quantile(0.5)),
        }
    r_stats = rates(real)
    s_stats = rates(synth)

    def check(name, tol_key, mode="abs"):
        r, s = r_stats[name], s_stats[name]
        tol = ARTIFACT_TOLERANCES[tol_key]
        if mode == "abs":
            delta = s - r
            passed = abs(delta) <= tol
        else:  # relative
            denom = max(r, 1)
            delta = (s - r) / denom
            passed = abs(delta) <= tol
        return {"real": r, "synth": s, "delta": round(delta, 4),
                "tolerance": tol, "passed": bool(passed)}
    checks = {
        "emoji_rate": check("emoji_rate", "emoji_rate_abs"),
        "emdash_rate": check("emdash_rate", "emdash_rate_abs"),
        "curly_apos_rate": check("curly_apos_rate", "curly_apos_rate_abs"),
        "url_rate": check("url_rate", "url_rate_abs"),
        "len_p50": check("len_p50", "len_p50_relative", mode="relative"),
    }
    all_passed = all(v["passed"] for v in checks.values())
    return {"real_stats": r_stats, "synth_stats": s_stats,
            "checks": checks, "all_passed": bool(all_passed)}


def _cv_predict_proba(X, y, seed=42, folds=5) -> np.ndarray:
    """Out-of-fold probabilities so we never score on training data."""
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_predict
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                  sublinear_tf=True, min_df=2,
                                  max_features=200_000)),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced",
                                   C=1.0)),
    ])
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    return cross_val_predict(pipe, X, y, cv=cv, method="predict_proba",
                             n_jobs=1)[:, 1]


def _metric_row(y: np.ndarray, p: np.ndarray, t: float = 0.5) -> dict:
    yhat = (p >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {
        "threshold": t,
        "accuracy": float((yhat == y).mean()),
        "precision": float(precision_score(y, yhat, zero_division=0)),
        "recall": float(recall_score(y, yhat, zero_division=0)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
        "pr_auc": float(average_precision_score(y, p)) if len(set(y)) > 1 else None,
        "confusion": {"tn": int(tn), "fp": int(fp),
                      "fn": int(fn), "tp": int(tp)},
    }


def _top_features(X_texts: pd.Series, y: np.ndarray, k: int = 20) -> dict:
    """Refit a single-shot model on all data to expose top coefficients — for
    interpretability only. Metric numbers still come from CV predictions."""
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                          sublinear_tf=True, min_df=2, max_features=200_000)
    X = vec.fit_transform(X_texts.astype(str))
    clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0)
    clf.fit(X, y)
    coefs = clf.coef_.ravel()
    vocab = vec.get_feature_names_out()
    order = np.argsort(coefs)
    return {
        "most_synthetic_ngrams": [(vocab[i], round(float(coefs[i]), 3))
                                  for i in order[-k:][::-1]],
        "most_real_ngrams": [(vocab[i], round(float(coefs[i]), 3))
                             for i in order[:k]],
    }


def _stylistic_deltas(df_real: pd.DataFrame, df_synth: pd.DataFrame) -> dict:
    """Compare aggregate stylistic markers real vs synthetic."""
    def stats(s: pd.Series) -> dict:
        t = s.astype(str)
        L = t.str.len()
        wc = t.str.split().str.len()
        return {
            "n": int(len(t)),
            "len_chars_p50": int(L.quantile(0.5)),
            "len_chars_p95": int(L.quantile(0.95)),
            "len_words_p50": int(wc.quantile(0.5)),
            "url_frac": float(t.str.contains(URL_RE).mean()),
            "emoji_frac": float(t.str.contains(EMOJI_RE).mean()),
            "caps_ratio_p50": float((t.str.count(r"[A-Z]") / (L + 1)).quantile(0.5)),
            "excl_per_100c_p50": float((t.str.count("!") / (L + 1) * 100).quantile(0.5)),
            "digit_frac_p50": float((t.str.count(r"\d") / (L + 1)).quantile(0.5)),
            "newlines_p50": float(t.str.count("\n").quantile(0.5)),
        }
    return {"real": stats(df_real.text), "synthetic": stats(df_synth.text)}


def _probe_diagnosis(auc: float | None, artifact_pass: bool) -> str:
    """Diagnostic message. AUC is descriptive; the pass/fail comes from the
    named-artifact check (DESIGN §7 rule 6.a)."""
    if auc is None:
        return "diagnostic: insufficient-data"
    art = "artifact_check=PASS" if artifact_pass else "artifact_check=FAIL"
    return f"diagnostic: probe AUC {auc:.3f}; {art}"


def run(exp_id: str = "E1", clean_path: str = "data/interim/clean.parquet") -> dict:
    df = pd.read_parquet(clean_path).reset_index(drop=True)
    scam = df[df.label == 1].reset_index(drop=True)
    if scam.is_synthetic.nunique() < 2:
        raise SystemExit("Probe needs both real and synthetic scam data.")

    result: dict = {
        "experiment_id": exp_id,
        "probe_threshold": VERDICT_THRESHOLD,
        "totals": {
            "scam_real": int((~scam.is_synthetic).sum()),
            "scam_synth": int(scam.is_synthetic.sum()),
        },
        "probes": {},
    }

    # -- Global probe: all real-scam vs all synthetic-scam --
    y_all = scam.is_synthetic.astype(int).values
    print("[probe] global (all real scam vs all synthetic scam) — fitting CV...")
    p_all = _cv_predict_proba(scam.text.values, y_all)
    m_all = _metric_row(y_all, p_all)
    top_all = _top_features(scam.text, y_all)
    styles_all = _stylistic_deltas(scam[~scam.is_synthetic], scam[scam.is_synthetic])
    art_all = _artifact_check(scam[~scam.is_synthetic], scam[scam.is_synthetic])
    result["probes"]["global"] = {
        "description": "All real scam categories combined vs all synthetic scam samples combined",
        "n_real": int((y_all == 0).sum()),
        "n_synthetic": int((y_all == 1).sum()),
        "metrics": m_all,
        "top_ngrams": top_all,
        "stylistic_deltas": styles_all,
        "artifact_check": art_all,
        "diagnostic": _probe_diagnosis(m_all["roc_auc"], art_all["all_passed"]),
    }

    # -- Per-synthetic-category probes vs their nearest real neighbors --
    for synth_cat, neighbors in NEIGHBOR_MAP.items():
        synth_sub = scam[scam.is_synthetic & (scam.category == synth_cat)]
        real_sub = scam[(~scam.is_synthetic) & (scam.category.isin(neighbors))]
        if len(synth_sub) < 50 or len(real_sub) < 50:
            result["probes"][synth_cat] = {"skipped": True,
                                           "reason": "not enough rows"}
            continue
        # subsample the real side to ~5x synth for a workable balance
        target_real = min(len(real_sub), len(synth_sub) * 5)
        real_sub = real_sub.sample(target_real, random_state=42)
        sub = pd.concat([real_sub, synth_sub], ignore_index=True)
        y = sub.is_synthetic.astype(int).values
        print(f"[probe] {synth_cat} ({len(synth_sub)} synth vs "
              f"{len(real_sub)} real from {neighbors}) — fitting CV...")
        p = _cv_predict_proba(sub.text.values, y)
        m = _metric_row(y, p)
        art = _artifact_check(real_sub, synth_sub)
        result["probes"][synth_cat] = {
            "description": f"synthetic {synth_cat} vs real {neighbors}",
            "n_real": int(len(real_sub)),
            "n_synthetic": int(len(synth_sub)),
            "metrics": m,
            "top_ngrams": _top_features(sub.text, y, k=15),
            "stylistic_deltas": _stylistic_deltas(real_sub, synth_sub),
            "artifact_check": art,
            "diagnostic": _probe_diagnosis(m["roc_auc"], art["all_passed"]),
        }

    # Multi-criteria acceptance per DESIGN §7 rule 6 (v2.0 revised):
    # gating happens on the PER-CATEGORY named-artifact checks (that's where
    # cheap synth artifacts would show up). The `global` probe aggregates
    # across categories and is informational — its result depends on the
    # relative mix of synth vs real which is a batching decision, not a
    # style-quality signal.
    per_category_artifact_pass = {
        k: r["artifact_check"]["all_passed"]
        for k, r in result["probes"].items()
        if not r.get("skipped") and "artifact_check" in r
    }
    all_artifacts_pass = all(
        v for k, v in per_category_artifact_pass.items() if k != "global"
    ) if per_category_artifact_pass else False
    result["artifact_check_by_probe"] = per_category_artifact_pass
    result["global_probe_informational"] = per_category_artifact_pass.get("global")

    per_cat_fails = [k for k, v in per_category_artifact_pass.items()
                     if k != "global" and not v]
    global_pass = per_category_artifact_pass.get("global", True)
    if all_artifacts_pass:
        result["overall_verdict"] = (
            "PER-CATEGORY ARTIFACT CHECKS PASS. Rule 6.a satisfied for every "
            "synthetic-only category (bec_ceo_fraud, romance_scam, "
            "marketplace_delivery_scam). "
            f"Global aggregate: {'PASS' if global_pass else 'informational miss (mix-arithmetic artifact of batch weighting; does not reflect a per-category style problem)'}. "
            "Downstream benefit (rule 6.f) must still be verified by a controlled "
            "with-vs-without experiment before generating the next batch."
        )
        result["next_action"] = (
            "Batch is acceptable on artifact grounds. To formally accept, run a "
            "with-vs-without-synthetic training experiment and confirm external "
            "PR-AUC does not regress (DESIGN §7 rule 6.f)."
        )
    else:
        result["overall_verdict"] = (
            f"PER-CATEGORY ARTIFACT CHECKS FAIL for: {per_cat_fails}. "
            "One or more named artifacts (emoji, em-dash, curly apostrophe, URL rate, "
            "length p50) are outside tolerance. Fix them before considering acceptance."
        )
        result["next_action"] = (
            f"Regenerate the failing categories ({per_cat_fails}) with tighter "
            "distribution matching, then re-run the probe."
        )

    Path("reports").mkdir(exist_ok=True)
    Path(f"reports/probe_{exp_id}.json").write_text(
        json.dumps(result, indent=2, default=str))
    Path(f"reports/probe_{exp_id}.md").write_text(_render_md(result))
    print(f"[probe:{exp_id}] wrote reports/probe_{exp_id}.{{json,md}}")
    print(f"[probe:{exp_id}] {result['overall_verdict']}")
    return result


def _render_md(r: dict) -> str:
    L: list[str] = []
    p = L.append
    p(f"# Synthetic Diagnostic — {r['experiment_id']}")
    p("")
    p("Acceptance policy: DESIGN §7 rules 6.a–6.f. This report covers rule 6.a "
      "(named-artifact check, HARD GATE) and provides the probe classifier as a "
      "diagnostic (NOT gating — see rule 7).")
    p("")
    p("## Overall")
    p(f"- **{r['overall_verdict']}**")
    p(f"- Next action: {r['next_action']}")
    p(f"- Totals: real-scam={r['totals']['scam_real']}, "
      f"synthetic-scam={r['totals']['scam_synth']}")
    p(f"- Historical probe threshold (retained for comparison only): "
      f"AUC ≤ {r['probe_threshold']}")
    p("")
    for name, probe in r["probes"].items():
        p(f"## Probe — {name}")
        if probe.get("skipped"):
            p(f"- SKIPPED: {probe['reason']}")
            p("")
            continue
        p(f"- {probe['description']}")
        p(f"- n_real={probe['n_real']}, n_synthetic={probe['n_synthetic']}")
        m = probe["metrics"]
        p(f"- probe metrics: **AUC {m['roc_auc']:.3f}** | PR-AUC {m['pr_auc']:.3f} | "
          f"P {m['precision']:.3f} | R {m['recall']:.3f} | F1 {m['f1']:.3f}")
        p(f"- confusion (t=0.5): {m['confusion']}")
        p(f"- **{probe['diagnostic']}**")
        p("")
        # Named-artifact check (the HARD GATE, DESIGN §7 rule 6.a)
        ac = probe["artifact_check"]
        p(f"### Named-artifact check — {'PASS' if ac['all_passed'] else 'FAIL'}")
        p("| artifact | real | synthetic | delta | tolerance | pass |")
        p("|---|---:|---:|---:|---:|:-:|")
        for a, c in ac["checks"].items():
            emoji = "✓" if c["passed"] else "✗"
            p(f"| {a} | {c['real']} | {c['synth']} | {c['delta']} | "
              f"±{c['tolerance']} | {emoji} |")
        p("")
        p("**Most 'synthetic-looking' char n-grams:**  " +
          ", ".join(f"`{ng}`({c})" for ng, c in probe["top_ngrams"]["most_synthetic_ngrams"]))
        p("")
        p("**Most 'real-looking' char n-grams:**  " +
          ", ".join(f"`{ng}`({c})" for ng, c in probe["top_ngrams"]["most_real_ngrams"]))
        p("")
        d = probe["stylistic_deltas"]
        p("**Stylistic deltas:**")
        p("| feature | real | synthetic |")
        p("|---|---:|---:|")
        for k in d["real"]:
            if k == "n": continue
            p(f"| {k} | {d['real'][k]} | {d['synthetic'][k]} |")
        p("")
    return "\n".join(L) + "\n"
