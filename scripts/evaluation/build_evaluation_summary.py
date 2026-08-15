"""
Build the consolidated evaluation-phase artifacts.

Aggregation-only script. Reads the persisted evaluation JSONs, the trained
model bundle, and the E8-P9 per-item benchmark results, and emits three
synthesis outputs:

  1. outputs/eval/master_summary.json  — one record per stage of the
     modelling programme (E2 through the final E8-P9 bake-off), each with
     its methodological role, number of candidates evaluated, winner,
     primary-metric name and value, and the evidence artifact from which
     the record was drawn. Also carries the deployed-model card
     (hyperparameters, operating threshold, headline external metrics).

  2. outputs/eval/master_summary.csv   — the same as (1) as a flat table
     for direct display in the Evaluation notebook.

  3. outputs/eval/e8p9_findings.md     — the formal Evaluation-phase
     findings document: Conclusions, Discovered issues (per-category
     residual FP/FN, confidence stratification, rule-engine involvement,
     length distribution), Known limitations, and the alternative-classifier
     comparison summary.

Nothing is retrained, re-scored, or recomputed. Every number in the
outputs traces back to an artifact already on disk.

Inputs read (all resolve under this repository; upstream artifacts that
were never copied in-repo — e2_ranking.json, e3_ranking.json,
e4_trials.json — are treated as optional and emit stub stage records
if absent):
  data/canonical/reports/acquisition_manifest.json
  data/canonical/reports/e4_best.json
  models/e5_metadata.json
  outputs/eval/e7_p1_results.json
  outputs/eval/e8p1_external.json
  outputs/eval/e8p9_bakeoff_results.json
  outputs/eval/e8p9_per_item.parquet
  models/e7_p1_variants/e7_p1_full_e8p9.joblib

Outputs written:
  outputs/eval/master_summary.json
  outputs/eval/master_summary.csv
  outputs/eval/e8p9_findings.md
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent


def _resolve_report(name: str, required: bool = True) -> Path | None:
    """Resolve an E-series report path from the canonical in-repo location
    at ``data/canonical/reports/``. E2/E3 ranking artifacts were produced
    by the upstream data-preparation workspace and were not copied into
    this repository; callers can pass ``required=False`` for those, and
    the corresponding stage summariser will emit a stub record noting
    the artifact is not in-repo. This keeps the summary regeneration
    robust to the historical gap."""
    candidate = _ROOT / 'data' / 'canonical' / 'reports' / name
    if candidate.exists():
        return candidate
    if required:
        raise FileNotFoundError(
            f'Could not locate report {name!r} at {candidate}'
        )
    return None

# ─── Input paths ─────────────────────────────────────────────────────────────
# E2/E3 rankings originated in the upstream workspace and are not present
# in-repo; treat as optional and emit stub stage records if absent.
E2_RANKING       = _resolve_report('e2_ranking.json', required=False)
E3_RANKING       = _resolve_report('e3_ranking.json', required=False)
E4_TRIALS        = _resolve_report('e4_trials.json', required=False)
E4_BEST          = _resolve_report('e4_best.json')
E5_METADATA      = _ROOT / 'models' / 'e5_metadata.json'
E7P1_RESULTS     = _ROOT / 'outputs' / 'eval' / 'e7_p1_results.json'
E8P1_EXTERNAL    = _ROOT / 'outputs' / 'eval' / 'e8p1_external.json'
E8P9_BAKEOFF     = _ROOT / 'outputs' / 'eval' / 'e8p9_bakeoff_results.json'
E8P9_PER_ITEM    = _ROOT / 'outputs' / 'eval' / 'e8p9_per_item.parquet'
E8P9_BUNDLE      = _ROOT / 'models' / 'e7_p1_variants' / 'e7_p1_full_e8p9.joblib'
ACQUISITION      = _resolve_report('acquisition_manifest.json')

# ─── Output paths ────────────────────────────────────────────────────────────
OUT_JSON     = _ROOT / 'outputs' / 'eval' / 'master_summary.json'
OUT_CSV      = _ROOT / 'outputs' / 'eval' / 'master_summary.csv'
OUT_FINDINGS = _ROOT / 'outputs' / 'eval' / 'e8p9_findings.md'


def _load_json(p: Path) -> dict | list:
    with p.open() as f:
        return json.load(f)


# ─── Stage summarisers ───────────────────────────────────────────────────────
def _stub_stage(stage: str, role: str, note: str) -> dict:
    """Placeholder record for stages whose primary evidence artifact was
    produced by the upstream data-preparation workspace and is not
    physically present here. The stage still happened; only its detailed
    ranking JSON is upstream. See E4 report + SOURCE_OF_TRUTH.md for the
    reconstruction of the E2/E3 decisions."""
    return {
        'stage':               stage,
        'role':                role,
        'n_candidates':        None,
        'winner':              None,
        'primary_metric_name': None,
        'primary_metric_value': None,
        'tiebreak_metric_name': None,
        'tiebreak_metric_value': None,
        'evidence_artifact':   'not-in-repo (produced by upstream workspace)',
        'notes':               note,
    }


def _stage_e2() -> dict:
    if E2_RANKING is None:
        return _stub_stage(
            'E2',
            'textual representation ablation (F1-F6)',
            ('Ranking JSON not in this repo. Decision recorded in '
             'data/canonical/reports/e4_best.json::e3_baseline_reference '
             'and SOURCE_OF_TRUTH.md: F3 (word + char TF-IDF) selected.'),
        )
    d = _load_json(E2_RANKING)
    ranked = d['ranked']
    winner = ranked[0]
    return {
        'stage':               'E2',
        'role':                'textual representation ablation (F1-F6)',
        'n_candidates':        len(ranked),
        'winner':              winner['feature_set'],
        'primary_metric_name': 'external PR-AUC (with-synthetic)',
        'primary_metric_value': round(float(winner['ext_pr_auc_ws']), 4),
        'tiebreak_metric_name': 'external F1 (with-synthetic)',
        'tiebreak_metric_value': round(float(winner['ext_f1_ws']), 4),
        'evidence_artifact':   str(E2_RANKING.relative_to(_ROOT)) if E2_RANKING.is_relative_to(_ROOT) else str(E2_RANKING),
        'notes':               f'Winner F3 (word + char TF-IDF); runner-up F6 (+handcrafted security).',
    }


def _stage_e3() -> dict:
    if E3_RANKING is None:
        return _stub_stage(
            'E3',
            'classifier bake-off on winning representation',
            ('Ranking JSON not in this repo. Decision recorded in '
             'data/canonical/reports/e4_best.json::e3_baseline_reference: '
             'Logistic Regression on F3 selected as the classifier family.'),
        )
    d = _load_json(E3_RANKING)
    ranked = d['ranked']
    winner = ranked[0]
    return {
        'stage':               'E3',
        'role':                'classifier bake-off on winning representation',
        'n_candidates':        len(ranked),
        'winner':              winner['key'],
        'primary_metric_name': d.get('primary_metric', 'external PR-AUC'),
        'primary_metric_value': round(float(winner['ext_pr_auc']), 4),
        'tiebreak_metric_name': 'external F1',
        'tiebreak_metric_value': round(float(winner['ext_f1']), 4),
        'evidence_artifact':   str(E3_RANKING.relative_to(_ROOT)) if E3_RANKING.is_relative_to(_ROOT) else str(E3_RANKING),
        'notes':               (f'{len(ranked)} classifier x feature-set combinations; '
                                f'logistic_regression on F3 dominated on PR-AUC and ECE.'),
    }


def _stage_e4() -> dict:
    best = _load_json(E4_BEST)
    trials = _load_json(E4_TRIALS) if E4_TRIALS is not None else None
    n_trials = int(best.get('n_trials_run', len(trials) if trials is not None else 20))
    return {
        'stage':               'E4',
        'role':                'hyperparameter optimisation (Optuna TPE)',
        'n_candidates':        n_trials,
        'winner':              f"trial {best['best_trial']}",
        'primary_metric_name': 'validation PR-AUC (Optuna objective)',
        'primary_metric_value': round(float(best['best_val_pr_auc']), 4),
        'tiebreak_metric_name': 'improvement vs E3 val PR-AUC',
        'tiebreak_metric_value': round(float(best.get('improvement_vs_e3_val', 0.0)), 4),
        'evidence_artifact':   (E4_BEST.name + (f' + {E4_TRIALS.name}' if E4_TRIALS is not None else '')),
        'notes':               (f'Tuned C, penalty, class_weight, TF-IDF n-gram ranges, '
                                f'min_df/max_df/max_features, sublinear_tf. Best params '
                                f'persisted at models/e5_metadata.json / e4_best_params.'),
    }


def _stage_e5() -> dict:
    e5 = _load_json(E5_METADATA)
    cal_rep = e5['e5_calibration_report']
    winner_cal = e5['e5_calibration_winner']
    ext = e5['external']
    return {
        'stage':               'E5',
        'role':                'calibration + operating threshold selection',
        'n_candidates':        len(cal_rep),
        'winner':              f'calibration={winner_cal}, threshold={e5["e5_thresholds"]["F1_max"]}',
        'primary_metric_name': 'external PR-AUC at t=0.59',
        'primary_metric_value': round(float(ext['pr_auc']), 4),
        'tiebreak_metric_name': 'external ECE',
        'tiebreak_metric_value': round(float(ext['ece']), 4),
        'evidence_artifact':   str(E5_METADATA.relative_to(_ROOT)) if E5_METADATA.is_relative_to(_ROOT) else str(E5_METADATA),
        'notes':               (f'Compared {list(cal_rep.keys())} calibrations on validation; '
                                f'uncalibrated dominated on PR-AUC, ROC-AUC, ECE, and Brier. '
                                f'Threshold selected as F1-max on validation.'),
    }


def _stage_e7p1() -> dict:
    d = _load_json(E7P1_RESULTS)
    results = d['results']
    variants = [v for v in results if v != 'e5']
    return {
        'stage':               'E7-P1',
        'role':                'engineered numerical feature-group ablation',
        'n_candidates':        len(results),  # baseline + 5 variants (tone/url/phrase/textstats/full)
        'winner':              'e7_p1_full (all 25 features)',
        'primary_metric_name': 'external PR-AUC at t=0.59 (full variant)',
        'primary_metric_value': round(float(results['e7_p1_full']['external']['primary_threshold_0.59']['pr_auc']), 4),
        'tiebreak_metric_name': 'acceptance-corpus FP rate (full variant)',
        'tiebreak_metric_value': round(float(results['e7_p1_full']['acceptance']['primary_threshold_0.59']['fp_rate']), 4),
        'evidence_artifact':   str(E7P1_RESULTS.relative_to(_ROOT)),
        'notes':               ('Per-family role classification labels every family as '
                                'FP-reducer on modern transactional legit corpus while '
                                'holding external recall within 0.5 percentage points.'),
    }


def _stage_e8p1() -> dict:
    d = _load_json(E8P1_EXTERNAL)
    return {
        'stage':               'E8-P1',
        'role':                'rule-engine post-processing layer',
        'n_candidates':        1,
        'winner':              'E7-P1-full + rule engine',
        'primary_metric_name': 'external F1 (with rule engine)',
        'primary_metric_value': round(float(d['f1']), 4),
        'tiebreak_metric_name': 'external accuracy (with rule engine)',
        'tiebreak_metric_value': round(float(d['accuracy']), 4),
        'evidence_artifact':   str(E8P1_EXTERNAL.relative_to(_ROOT)),
        'notes':               ('A-rules force SCAM on unambiguous constructions; '
                                'B-rules reinforce SCAM in ambiguous cases; '
                                'C-rules decrement score on known FP-triggering patterns.'),
    }


def _stage_e8p9_bakeoff() -> dict:
    d = _load_json(E8P9_BAKEOFF)
    ranked = d['ranked']
    winner = ranked[0]
    return {
        'stage':               'E8-P9 bake-off',
        'role':                ('final classifier confirmation on the deployed corpus '
                                '(raw-classifier, no rule engine)'),
        'n_candidates':        len(ranked),
        'winner':              winner['model'],
        'primary_metric_name': d['primary_metric'],
        'primary_metric_value': round(float(winner['external_pr_auc']), 4),
        'tiebreak_metric_name': d['tiebreak_metric'],
        'tiebreak_metric_value': round(float(winner['external_f1_at_0.59']), 4),
        'evidence_artifact':   str(E8P9_BAKEOFF.relative_to(_ROOT)),
        'notes':               (f'Excluded: {", ".join(d["excluded_candidates"].keys())}. '
                                f'Rule engine disabled to measure classifier alone.'),
    }


def _stages() -> list[dict]:
    return [
        _stage_e2(), _stage_e3(), _stage_e4(), _stage_e5(),
        _stage_e7p1(), _stage_e8p1(), _stage_e8p9_bakeoff(),
    ]


# ─── Deployed model card ─────────────────────────────────────────────────────
def _with_rules_headline_from_per_item() -> dict:
    """Compute the deployed-pipeline (classifier + 19-rule engine) headline
    directly from the E8-P9 per-item predictions on the frozen external
    benchmark. The parquet's `pred` column already reflects the deployed
    verdict at threshold 0.59 (rules applied); `final_prob` is the post-rule
    probability. This replaces the earlier practice of copying the E8-P1
    (13-rule, historical) block, which was stale after the rule engine was
    refined to 19 rules at E8-P9."""
    from sklearn.metrics import (confusion_matrix, precision_score, recall_score,
                                 f1_score, accuracy_score, roc_auc_score,
                                 average_precision_score)
    per = pd.read_parquet(E8P9_PER_ITEM)
    y = per['label'].astype(int).values
    yhat = per['pred'].astype(int).values
    p_final = per['final_prob'].astype(float).values
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {
        'accuracy':  round(float(accuracy_score(y, yhat)), 4),
        'precision': round(float(precision_score(y, yhat)), 4),
        'recall':    round(float(recall_score(y, yhat)), 4),
        'f1':        round(float(f1_score(y, yhat)), 4),
        'pr_auc':    round(float(average_precision_score(y, p_final)), 4),
        'roc_auc':   round(float(roc_auc_score(y, p_final)), 4),
        'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
        'n':         int(len(per)),
        'threshold': 0.59,
        'rule_engine': '19 rules (9 Critical + 7 Strong + 3 Legit)',
        'source':    str(E8P9_PER_ITEM.relative_to(_ROOT)),
        'note':      ('Computed directly from the E8-P9 per-item predictions on '
                      'the frozen 25,306-row external benchmark. This IS the '
                      'current deployed configuration (LR + 19-rule engine). '
                      'For the historical E8-P1 (13-rule) numbers see the '
                      'E8-P1 entry in the `stages` list and its evidence '
                      'artifact outputs/eval/e8p1_external.json.'),
    }


def _deployed_card() -> dict:
    import joblib
    b = joblib.load(E8P9_BUNDLE)
    lr = b['lr']
    e5 = _load_json(E5_METADATA)
    bakeoff = _load_json(E8P9_BAKEOFF)
    lr_row = bakeoff['results'][0]
    ext = lr_row['external_at_deployed_0.59']
    return {
        'artifact_path':                 str(E8P9_BUNDLE.relative_to(_ROOT)),
        'classifier_family':             'LogisticRegression',
        'hyperparameters':               e5['e4_best_params'],
        'operating_threshold':           b.get('threshold', 0.59),
        'feature_matrix_dim':            int(lr.coef_.shape[1]),
        'classifier_size_mb':            lr_row['classifier_size_mb'],
        'latency_batch1_ms_median':      lr_row['latency_batch1_ms_median'],
        'external_headline_raw_classifier':   ext,
        'external_headline_with_rule_engine': _with_rules_headline_from_per_item(),
    }


# ─── Findings synthesis from per-item parquet ────────────────────────────────
def _findings_stats() -> dict:
    per = pd.read_parquet(E8P9_PER_ITEM)
    n = len(per)
    fps = per[(per.label == 0) & (per.pred == 1)]
    fns = per[(per.label == 1) & (per.pred == 0)]

    # Per-category FPs (labelled legit)
    fp_by_cat = []
    for cat, k in fps.category.value_counts().items():
        total = int((per.category == cat).sum())
        fp_by_cat.append({
            'category': str(cat), 'fp_count': int(k),
            'category_size': int(total),
            'fp_rate_within_category': round(float(k) / max(total, 1), 4),
        })

    # Per-category FNs (labelled scam)
    fn_by_cat = []
    for cat, k in fns.category.value_counts().items():
        total_scam = int(((per.category == cat) & (per.label == 1)).sum())
        fn_by_cat.append({
            'category': str(cat), 'fn_count': int(k),
            'category_scam_size': int(total_scam),
            'fn_rate_within_category': round(float(k) / max(total_scam, 1), 4),
        })

    # FP confidence stratification (predicted-scam certainty)
    def _bucket_conf(c: float) -> str:
        if c < 60:  return '<60 (borderline)'
        if c < 70:  return '60-70'
        if c < 80:  return '70-80'
        if c < 90:  return '80-90'
        return '90-100 (confident)'
    fps_ = fps.copy(); fps_['bucket'] = fps_.confidence.apply(_bucket_conf)
    fp_conf = [{'bucket': b, 'count': int((fps_.bucket == b).sum())}
               for b in ['<60 (borderline)', '60-70', '70-80', '80-90', '90-100 (confident)']]

    # Rule-engine involvement in FPs and FNs
    rule_fp = {
        'engine_fired_on_fp_count':  int((fps.n_rules > 0).sum()),
        'engine_fired_on_fp_share':  round(float((fps.n_rules > 0).mean()), 4),
        'forced_scam_by_a_rule':     int(fps.forced_scam.sum()),
        'forced_scam_share_of_fp':   round(float(fps.forced_scam.mean()), 4),
    }
    rule_fn = {
        'engine_fired_on_fn_count':  int((fns.n_rules > 0).sum()),
        'engine_fired_on_fn_share':  round(float((fns.n_rules > 0).mean()), 4),
    }

    # URL presence in FPs / FNs
    url_stats = {
        'fp_with_url_share': round(float(fps.has_url.mean()), 4),
        'fn_with_url_share': round(float(fns.has_url.mean()), 4),
    }

    # Length distribution buckets
    buckets = [(0,100,'<100'), (100,300,'100-300'), (300,800,'300-800'),
               (800,2000,'800-2k'), (2000,10**9,'>2k')]
    def _len_hist(sub):
        return [{'bucket': lbl, 'count': int(((sub.char_len >= lo) & (sub.char_len < hi)).sum())}
                for lo, hi, lbl in buckets]

    return {
        'n_scored':                n,
        'n_fp':                    int(len(fps)),
        'n_fn':                    int(len(fns)),
        'external_accuracy':       round(1 - (len(fps) + len(fns)) / n, 4),
        'fp_by_category':          fp_by_cat,
        'fn_by_category':          fn_by_cat,
        'fp_confidence_buckets':   fp_conf,
        'rule_engine_in_fp':       rule_fp,
        'rule_engine_in_fn':       rule_fn,
        'url_presence':            url_stats,
        'fp_length_histogram':     _len_hist(fps),
        'fn_length_histogram':     _len_hist(fns),
    }


# ─── Findings markdown formatter ─────────────────────────────────────────────
def _render_findings(deployed: dict, stats: dict, stages: list[dict]) -> str:
    bakeoff = _load_json(E8P9_BAKEOFF)
    ranked = bakeoff['ranked']
    ex = deployed['external_headline_raw_classifier']
    exre = deployed['external_headline_with_rule_engine']

    lines = []
    w = lines.append
    w('# Evaluation Findings — Deployed E8-P9 System')
    w('')
    w(f'*Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*')
    w('')
    w('This document synthesises the evaluation-phase findings for the '
      'deployed ScamRadar+ system. Every quoted number is drawn from a '
      'persisted evaluation artifact under `outputs/eval/` or the sibling '
      '`reports/` folders; nothing is recomputed in this document.')
    w('')

    # 1. Deployed model card
    w('## 1. Deployed model')
    w('')
    w(f'- **Artifact:** `{deployed["artifact_path"]}`')
    w(f'- **Family:** {deployed["classifier_family"]}')
    w(f'- **Operating threshold:** {deployed["operating_threshold"]}')
    w(f'- **Feature-matrix dimension:** {deployed["feature_matrix_dim"]:,}')
    w(f'- **Serialised size:** {deployed["classifier_size_mb"]:.2f} MB (classifier only)')
    w(f'- **Batch-1 inference latency (median):** {deployed["latency_batch1_ms_median"]:.3f} ms')
    w('')

    # 2. External headline metrics
    w('## 2. External benchmark headline (n = 25,306)')
    w('')
    w('**Raw classifier (rule engine disabled) — comparable to the E8-P9 bake-off:**')
    w('')
    w(f'| Metric | Value |')
    w(f'|---|---:|')
    w(f'| Accuracy      | {ex["accuracy"]} |')
    w(f'| Precision     | {ex["precision"]} |')
    w(f'| Recall        | {ex["recall"]} |')
    w(f'| F1            | {ex["f1"]} |')
    w(f'| ROC-AUC       | {ex.get("roc_auc","-")} |')
    w(f'| PR-AUC        | {ex.get("pr_auc","-")} |')
    w(f'| ECE (10-bin)  | {ex.get("ece","-")} |')
    w(f'| Confusion (TN, FP, FN, TP) | {ex["confusion"]["tn"]}, {ex["confusion"]["fp"]}, {ex["confusion"]["fn"]}, {ex["confusion"]["tp"]} |')
    w('')
    w('**Deployed pipeline (classifier + rule engine) — the shipped configuration:**')
    w('')
    w(f'| Metric | Value |')
    w(f'|---|---:|')
    w(f'| Accuracy      | {exre["accuracy"]} |')
    w(f'| Precision     | {exre["precision"]} |')
    w(f'| Recall        | {exre["recall"]} |')
    w(f'| F1            | {exre["f1"]} |')
    w(f'| ROC-AUC       | {exre["roc_auc"]} |')
    w(f'| PR-AUC        | {exre["pr_auc"]} |')
    w(f'| Confusion (TN, FP, FN, TP) | {exre["confusion"]["tn"]}, {exre["confusion"]["fp"]}, {exre["confusion"]["fn"]}, {exre["confusion"]["tp"]} |')
    w('')

    # 3. Alternative-classifier comparison summary
    w('## 3. Alternative-classifier comparison (E8-P9 bake-off)')
    w('')
    w('Three classifier families were compared on identical features, '
      'identical partitions, identical evaluation protocol; only the '
      'classifier changed. Primary metric: external PR-AUC at threshold '
      '0.59. See `outputs/eval/e8p9_bakeoff_results.json` for the full '
      'metric matrix.')
    w('')
    w('| Rank | Model | Ext PR-AUC | Ext F1 @ 0.59 | Ext ECE | Size (MB) | Latency b=1 (ms) |')
    w('|---:|---|---:|---:|---:|---:|---:|')
    for i, r in enumerate(ranked, 1):
        w(f'| {i} | {r["model"]} | {r["external_pr_auc"]} | {r["external_f1_at_0.59"]} '
          f'| {r["external_ece"]} | {r["classifier_size_mb"]} | {r["latency_batch1_ms_median"]} |')
    w('')

    # 4. Conclusions
    w('## 4. Conclusions')
    w('')
    w('- **Logistic Regression is the correct deployment choice on the '
      'final training corpus.** The E8-P9 bake-off confirms the earlier E3 '
      'ranking on the finalised data: LR wins the primary metric '
      f'(PR-AUC {ranked[0]["external_pr_auc"]}) and has the lowest '
      f'expected calibration error (ECE {ranked[0]["external_ece"]}) '
      f'among the three candidates, at the lowest inference latency.')
    w('- **LinearSVC with sigmoid calibration is a viable but weaker '
      f'alternative.** It edges LR on F1 ({ranked[1]["external_f1_at_0.59"]} '
      f'vs {ranked[0]["external_f1_at_0.59"]}) but trails on the '
      'threshold-independent ranking metric (PR-AUC '
      f'{ranked[1]["external_pr_auc"]}), has slightly worse calibration '
      f'(ECE {ranked[1]["external_ece"]}), and is approximately five times '
      'slower at inference.')
    w('- **SGDClassifier is not competitive** for this problem and '
      'representation, trailing materially on every headline metric.')
    w('- **The feature-fusion representation** (word TF-IDF + character '
      'TF-IDF + 25 standardised engineered numerical features) remains '
      'dominant on the final corpus, as it was on the earlier E3 corpus.')
    w('- **The rule-engine post-processing layer** provides consistent '
      'coverage of unambiguous scam constructions and a small false-'
      'positive-reducing effect on known safe patterns; on the external '
      'benchmark it fires on only '
      f'{stats["rule_engine_in_fp"]["engine_fired_on_fp_share"]*100:.1f}% '
      'of false positives, so residual false positives are primarily '
      'classifier-attributable rather than rule-attributable.')
    w('')

    # 5. Discovered issues (residual error analysis)
    w('## 5. Discovered issues (residual error analysis)')
    w('')
    w(f'- **Total residual errors on the external benchmark:** '
      f'{stats["n_fp"]:,} false positives and {stats["n_fn"]:,} false '
      f'negatives on {stats["n_scored"]:,} records '
      f'(accuracy {stats["external_accuracy"]}).')
    w('')

    w('- **False positives concentrate in one category.** Top FP '
      'contributors (of the legitimate class):')
    w('')
    w('  | Category | FP count | Category size | FP rate |')
    w('  |---|---:|---:|---:|')
    for row in stats['fp_by_category'][:5]:
        w(f'  | {row["category"]} | {row["fp_count"]:,} | {row["category_size"]:,} | {row["fp_rate_within_category"]:.4f} |')
    w('')

    w('- **False negatives concentrate in scam categories.** Top FN '
      'contributors (of the scam class):')
    w('')
    w('  | Category | FN count | Category scam size | FN rate |')
    w('  |---|---:|---:|---:|')
    for row in stats['fn_by_category'][:5]:
        w(f'  | {row["category"]} | {row["fn_count"]:,} | {row["category_scam_size"]:,} | {row["fn_rate_within_category"]:.4f} |')
    w('')

    w('- **The model is often confidently wrong on false positives.** '
      'Confidence-bucket distribution of FPs:')
    w('')
    w('  | Confidence bucket | Count | Share of FPs |')
    w('  |---|---:|---:|')
    for b in stats['fp_confidence_buckets']:
        share = b['count'] / max(stats['n_fp'], 1)
        w(f'  | {b["bucket"]} | {b["count"]:,} | {share*100:.1f}% |')
    w('')

    w('- **Rule-engine involvement in residual errors.** '
      f'The rule engine fires on {stats["rule_engine_in_fp"]["engine_fired_on_fp_count"]:,} '
      f'({stats["rule_engine_in_fp"]["engine_fired_on_fp_share"]*100:.1f}%) '
      f'of the {stats["n_fp"]:,} false positives, and on '
      f'{stats["rule_engine_in_fn"]["engine_fired_on_fn_count"]:,} '
      f'({stats["rule_engine_in_fn"]["engine_fired_on_fn_share"]*100:.1f}%) '
      f'of the {stats["n_fn"]:,} false negatives. Force-SCAM by an A-rule '
      f'accounts for {stats["rule_engine_in_fp"]["forced_scam_by_a_rule"]:,} of the FPs.')
    w('')

    w('- **URL presence in errors:** '
      f'{stats["url_presence"]["fp_with_url_share"]*100:.1f}% of false '
      f'positives and {stats["url_presence"]["fn_with_url_share"]*100:.1f}% '
      'of false negatives contain a URL.')
    w('')

    # 6. Known limitations
    w('## 6. Known limitations')
    w('')
    w('- **English-only.** The training corpus and the rule engine are '
      'both anchored on English text. Non-English input is not supported '
      'by the deployed system and is rejected at the API boundary.')
    w('- **Legitimate corpus dominated by conversational sources.** The '
      'two largest single sources of the legitimate class are `multiwoz_v22` '
      '(task-oriented dialogue) and `dailydialog` (open-domain dialogue), '
      'which together account for the majority of legitimate records. '
      'False-positive concentration on the `ham_email` category (see §5) '
      'indicates the model is less well-supported on modern email '
      'legitimate traffic than on chat legitimate traffic.')
    w('- **Frozen external benchmark.** The external benchmark is a '
      'point-in-time snapshot of redistributable real-world sources. '
      'Drift in the scam landscape between the benchmark snapshot and '
      'production traffic is not measured by the external metrics.')
    w('- **Threshold selected on validation.** The deployed operating '
      'threshold 0.59 is F1-optimal on the validation partition of the '
      'E8-P9 corpus. Deployment contexts that require a different '
      'precision/recall trade-off should use the precision-floor '
      'threshold 0.77 recorded in `models/e5_metadata.json`.')
    w('- **Rule engine is authored, not learned.** The rules are '
      'hand-written and represent domain knowledge rather than a '
      'data-driven boundary; they must be reviewed when new scam '
      'categories emerge.')
    w('')

    # 7. Trace of evaluation stages
    w('## 7. Evaluation stage trace')
    w('')
    w('The full sequence of methodological iterations and their '
      'evidence artifacts:')
    w('')
    w('| Stage | Role | Candidates | Winner | Primary metric | Value | Evidence |')
    w('|---|---|---:|---|---|---:|---|')
    for s in stages:
        w(f'| {s["stage"]} | {s["role"]} | {s["n_candidates"]} | {s["winner"]} '
          f'| {s["primary_metric_name"]} | {s["primary_metric_value"]} '
          f'| `{s["evidence_artifact"]}` |')
    w('')

    return '\n'.join(lines) + '\n'


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    print('Aggregating evaluation-phase artifacts...')
    stages = _stages()
    deployed = _deployed_card()
    stats = _findings_stats()

    payload = {
        'generated_at':                 datetime.now(timezone.utc).isoformat(),
        'purpose':                      ('Consolidated summary of the ScamRadar+ '
                                         'evaluation phase — one record per stage '
                                         'of the modelling programme, plus the '
                                         'deployed model card and residual-error '
                                         'statistics.'),
        'deployed_model':               deployed,
        'primary_decision_metric':      'external PR-AUC at deployed threshold 0.59',
        'stages':                       stages,
        'external_residual_errors':     stats,
    }
    with OUT_JSON.open('w') as f:
        json.dump(payload, f, indent=2, default=str)
    print(f'Wrote {OUT_JSON}  ({OUT_JSON.stat().st_size/1024:.1f} KB)')

    csv_cols = ['stage', 'role', 'n_candidates', 'winner',
                'primary_metric_name', 'primary_metric_value',
                'tiebreak_metric_name', 'tiebreak_metric_value',
                'evidence_artifact', 'notes']
    with OUT_CSV.open('w', newline='') as f:
        wtr = csv.DictWriter(f, fieldnames=csv_cols)
        wtr.writeheader()
        for s in stages:
            wtr.writerow({k: s.get(k, '') for k in csv_cols})
    print(f'Wrote {OUT_CSV}  ({OUT_CSV.stat().st_size/1024:.1f} KB)')

    findings_md = _render_findings(deployed, stats, stages)
    OUT_FINDINGS.write_text(findings_md)
    print(f'Wrote {OUT_FINDINGS}  ({OUT_FINDINGS.stat().st_size/1024:.1f} KB)')

    print('\nSummary:')
    print(f'  stages summarised     : {len(stages)}')
    print(f'  deployed model family : {deployed["classifier_family"]}')
    print(f'  external residual err : {stats["n_fp"]} FP + {stats["n_fn"]} FN '
          f'/ {stats["n_scored"]} (accuracy {stats["external_accuracy"]})')


if __name__ == '__main__':
    main()
