"""
E7 Phase 1 — evaluation of 5 numerical-fusion variants against E5 baseline.

Evaluates each variant on:
  1. E5 external benchmark (n=25,306, locked)
  2. Manual acceptance test (32 real-world transactional messages)
  3. E6 authentic corpus (66 legit + 31 scam)

For each variant × benchmark:
  - accuracy, precision, recall, F1, ROC-AUC, PR-AUC, ECE, Brier
  - confusion matrix
  - per-category scam recall + per-category FP rate (external benchmark)
  - at PRIMARY threshold 0.59 (E5's) AND at variant-optimal F1-max on val

For interpretability:
  - LR coefficients on all 25 numerical features (+ inspection)
  - LR coefficients on 12 flagged lexical tokens (verify, account, payment, etc.)
  - Case-level flip analysis: for every acceptance-test message whose prediction
    differs between E5 and a variant, decompose the probability delta into
    numerical vs TF-IDF contributions
  - Per-feature-group role classification (FP-reducer / FN-reducer / both / neither)

Writes:
  outputs/e7_p1_report.md — full research report
  outputs/eval/e7_p1_results.json — raw metric matrix
"""
from __future__ import annotations

import os, sys, json, warnings, time
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, roc_auc_score, average_precision_score,
                              confusion_matrix, brier_score_loss)

warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BASE_A = _ROOT
CANONICAL_BENCHMARK = os.path.join(_ROOT, 'data', 'canonical', 'external_benchmark.parquet')
VARIANTS_DIR = os.path.join(BASE_A, 'models', 'e7_p1_variants')
FEAT_PARQUET = os.path.join(BASE_A, 'data', 'interim', 'e7_p1_features.parquet')
OUT_REPORT = os.path.join(BASE_A, 'outputs', 'e7_p1_report.md')
OUT_JSON = os.path.join(BASE_A, 'outputs', 'eval', 'e7_p1_results.json')

_ALL_VARIANTS = ['e7_p1_tone', 'e7_p1_url', 'e7_p1_phrase', 'e7_p1_textstats', 'e7_p1_full']
VARIANTS = [v for v in _ALL_VARIANTS if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models', 'e7_p1_variants', f'{v}.joblib'))]
print(f'[eval init] found variants: {VARIANTS}')
FEATURE_GROUPS = {
    'tone': ['tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat'],
    'url': ['has_url', 'url_count', 'url_suspicious_tld',
            'url_suspicious_keyword', 'url_has_ip'],
    'phrase': ['scam_phrase_score', 'sender_impersonation_score', 'legit_phrase_score'],
    'textstats': ['text_length', 'word_count', 'exclamation_count', 'uppercase_ratio',
                  'digit_ratio', 'urgency_score', 'avg_word_length',
                  'capitalized_word_count', 'punctuation_density',
                  'question_mark_count', 'currency_symbol_count',
                  'readability_score', 'unique_word_ratio'],
}
LEXICAL_INSPECT_TOKENS = [
    'verify', 'account', 'payment', 'security', 'login', 'sign in',
    'invoice', 'order', 'delivery', 'transaction', 'tracking', 'confirm',
    'your account', 'your payment', 'your order',
]

# ─── Bundle loaders ────────────────────────────────────────────────────────────
def load_e5():
    b = joblib.load(f'{BASE_A}/models/e5_bundle.joblib')
    return {
        'name': 'e5',
        'model': b['model'],
        'threshold': 0.59,
        'is_e5': True,
    }


def load_variant(name):
    p = os.path.join(VARIANTS_DIR, f'{name}.joblib')
    b = joblib.load(p)
    return {
        'name': name,
        'lr': b['lr'],
        'word_vec': b['word_vec'],
        'char_vec': b['char_vec'],
        'scaler': b['scaler'],
        'feature_cols': b['feature_cols'],
        'threshold': b.get('threshold', 0.59),
        'is_e5': False,
    }


# ─── Prediction ────────────────────────────────────────────────────────────────
def predict_proba(bundle, texts, numerical_df=None):
    if bundle['is_e5']:
        return bundle['model'].predict_proba(texts)[:, 1]
    Xw = bundle['word_vec'].transform(texts)
    Xc = bundle['char_vec'].transform(texts)
    if numerical_df is None:
        raise ValueError('variant model requires numerical features')
    Xn = numerical_df[bundle['feature_cols']].values.astype(np.float64)
    Xn = bundle['scaler'].transform(Xn)
    X = hstack([Xw, Xc, csr_matrix(Xn)]).tocsr()
    return bundle['lr'].predict_proba(X)[:, 1]


# ─── Metric helpers ────────────────────────────────────────────────────────────
def score(y, p, threshold):
    y = np.asarray(y).astype(int)
    p = np.asarray(p)
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0,1]).ravel()
    m = {
        'threshold': float(threshold),
        'n': int(len(y)),
        'accuracy':  round(float(accuracy_score(y, yhat)), 4),
        'precision': round(float(precision_score(y, yhat, zero_division=0)), 4),
        'recall':    round(float(recall_score(y, yhat, zero_division=0)), 4),
        'f1':        round(float(f1_score(y, yhat, zero_division=0)), 4),
        'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    }
    if len(set(y)) > 1:
        m['roc_auc'] = round(float(roc_auc_score(y, p)), 4)
        m['pr_auc'] = round(float(average_precision_score(y, p)), 4)
        m['brier'] = round(float(brier_score_loss(y, p)), 4)
        # ECE (10 bins)
        bins = np.linspace(0, 1, 11); ece = 0.0
        for i in range(10):
            mask = (p >= bins[i]) & (p < bins[i+1])
            if mask.sum() == 0: continue
            conf = p[mask].mean(); acc = y[mask].mean()
            ece += (mask.sum() / len(y)) * abs(conf - acc)
        m['ece'] = round(float(ece), 4)
    return m


def find_f1_max_threshold(y, p, thresholds=None):
    if thresholds is None:
        thresholds = np.linspace(0.05, 0.95, 91)
    best_t, best_f1 = 0.5, 0.0
    y = np.asarray(y).astype(int)
    for t in thresholds:
        f1 = f1_score(y, (p >= t).astype(int), zero_division=0)
        if f1 > best_f1: best_f1, best_t = f1, t
    return float(best_t), float(best_f1)


def per_category_metrics(y, p, categories, threshold, mode='recall'):
    """mode='recall' for scam categories (label=1), 'fp_rate' for legit."""
    y = np.asarray(y).astype(int)
    p = np.asarray(p); yhat = (p >= threshold).astype(int)
    out = {}
    cat_arr = np.asarray(categories)
    for cat in sorted(set(categories)):
        m = cat_arr == cat
        if m.sum() == 0: continue
        y_c, yhat_c = y[m], yhat[m]
        if mode == 'recall':
            if y_c.sum() == 0: continue  # skip if no positives
            out[cat] = {'n': int(m.sum()),
                        'recall': round(float(recall_score(y_c, yhat_c, zero_division=0)), 4)}
        else:  # fp_rate
            if (y_c == 0).sum() == 0: continue
            fp_rate = ((yhat_c == 1) & (y_c == 0)).sum() / (y_c == 0).sum()
            out[cat] = {'n': int(m.sum()),
                        'fp_rate': round(float(fp_rate), 4)}
    return out


# ─── Load evaluation data ──────────────────────────────────────────────────────
def load_eval_data():
    print('Loading eval data...')
    feats = pd.read_parquet(FEAT_PARQUET)
    print(f'  features parquet: {len(feats):,} rows')

    val = feats[feats.split == 'val'].reset_index(drop=True)
    ext_feats = feats[feats.split == 'external'].reset_index(drop=True)

    # External benchmark: reload from source for category metadata
    ext_full = pd.read_parquet(CANONICAL_BENCHMARK)
    print(f'  external benchmark: {len(ext_full):,} rows')

    # Acceptance test corpus (32 real-world transactional)
    acc = []
    from tests.manual_acceptance_test import TESTS
    for cat, text in TESTS:
        acc.append({'text': text, 'label': 0, 'category': cat})
    acc = pd.DataFrame(acc)
    print(f'  acceptance test: {len(acc)} rows')

    # E6 authentic corpus
    e6 = pd.read_parquet(f'{BASE_A}/data/interim/e6/e6_augmentation.parquet')[
        ['text', 'label', 'category']].reset_index(drop=True)
    print(f'  E6 authentic: {len(e6)} rows')

    return val, ext_full, ext_feats, acc, e6


def compute_features_inline(df, text_col='text'):
    """Compute numerical features for eval-only dataframes (not in the parquet)."""
    from scripts.training.train_e7_p1 import compute_all_numerical
    feats = df[text_col].apply(compute_all_numerical)
    return pd.DataFrame(list(feats.values), index=df.index)


# ─── MAIN EVAL ─────────────────────────────────────────────────────────────────
def main():
    val_df, ext_full, ext_feats, acc_df, e6_df = load_eval_data()

    # Compute numerical features for acceptance + e6 (they aren't in the parquet)
    print('Computing numerical features for acceptance test + E6 corpus...')
    acc_feats = compute_features_inline(acc_df)
    acc_df = pd.concat([acc_df, acc_feats], axis=1)
    e6_feats = compute_features_inline(e6_df)
    e6_df = pd.concat([e6_df, e6_feats], axis=1)

    # Attach category info from ext_full onto ext_feats (align by text)
    ext_feats = ext_feats.merge(ext_full[['text', 'category']], on='text', how='left')

    # Load all bundles
    bundles = [load_e5()] + [load_variant(v) for v in VARIANTS]
    print(f'\nLoaded {len(bundles)} bundles: {[b["name"] for b in bundles]}')

    # ── Score every bundle on every benchmark
    all_results = {}   # name -> benchmark -> {primary_threshold_metrics, optimal_threshold_metrics}
    all_probs = {}     # name -> benchmark -> np.array of P(scam)

    for b in bundles:
        print(f'\n=== {b["name"]} ===')
        all_results[b['name']] = {}
        all_probs[b['name']]   = {}

        # --- External benchmark
        y_ext = ext_full.label.values
        p_ext = predict_proba(b, ext_full.text.tolist(),
                              numerical_df=ext_feats if not b['is_e5'] else None)
        all_probs[b['name']]['external'] = p_ext
        primary = score(y_ext, p_ext, 0.59)
        # per-variant optimal threshold from validation (never using ext for threshold selection)
        y_val = val_df.label.values
        p_val = predict_proba(b, val_df.text.tolist(),
                              numerical_df=val_df if not b['is_e5'] else None)
        opt_t, opt_val_f1 = find_f1_max_threshold(y_val, p_val)
        variant_opt = score(y_ext, p_ext, opt_t)
        all_results[b['name']]['external'] = {
            'primary_threshold_0.59': primary,
            'variant_optimal_threshold': variant_opt,
            'variant_optimal_threshold_value': round(opt_t, 3),
            'optimal_val_f1': round(opt_val_f1, 4),
        }
        # Per-category scam recall on external
        scam_cats = ['email_phishing', 'smishing', 'advance_fee_fraud',
                     'bec_ceo_fraud', 'romance_scam', 'marketplace_delivery_scam']
        legit_cats = ['ham_chat', 'ham_email', 'ham_sms', 'ham_job_posting']
        all_results[b['name']]['external']['per_category_scam_recall'] = per_category_metrics(
            y_ext, p_ext, ext_full.category.values, 0.59, mode='recall')
        all_results[b['name']]['external']['per_category_legit_fp_rate'] = per_category_metrics(
            y_ext, p_ext, ext_full.category.values, 0.59, mode='fp_rate')

        # --- Acceptance test
        y_acc = acc_df.label.values
        p_acc = predict_proba(b, acc_df.text.tolist(),
                              numerical_df=acc_df if not b['is_e5'] else None)
        all_probs[b['name']]['acceptance'] = p_acc
        primary_acc = score(y_acc, p_acc, 0.59)
        # For acceptance (all legit), report FP rate specifically
        yhat_acc = (p_acc >= 0.59).astype(int)
        primary_acc['fp_rate'] = round(float((yhat_acc == 1).sum() / len(y_acc)), 4)
        all_results[b['name']]['acceptance'] = {'primary_threshold_0.59': primary_acc}

        # --- E6 authentic corpus
        y_e6 = e6_df.label.values
        p_e6 = predict_proba(b, e6_df.text.tolist(),
                             numerical_df=e6_df if not b['is_e5'] else None)
        all_probs[b['name']]['e6_authentic'] = p_e6
        primary_e6 = score(y_e6, p_e6, 0.59)
        all_results[b['name']]['e6_authentic'] = {'primary_threshold_0.59': primary_e6}

        print(f'  external:   F1={primary["f1"]}  P={primary["precision"]}  R={primary["recall"]}  '
              f'PR-AUC={primary.get("pr_auc","-")}  variant_opt_t={opt_t:.2f}')
        print(f'  acceptance: FP rate={primary_acc["fp_rate"]:.2%}  ({(yhat_acc==1).sum()}/32 wrongly flagged)')
        print(f'  e6:         F1={primary_e6["f1"]}  P={primary_e6["precision"]}  R={primary_e6["recall"]}')

    # ── Coefficient inspection ────────────────────────────────────────────────
    print('\n=== Coefficient inspection ===')
    coef_report = {}
    for b in bundles:
        if b['is_e5']: continue
        n_word = len(b['word_vec'].vocabulary_)
        n_char = len(b['char_vec'].vocabulary_)
        coefs = b['lr'].coef_[0]
        # Numerical coefficients are at the tail
        n_num = len(b['feature_cols'])
        num_coefs = coefs[n_word + n_char:]
        assert len(num_coefs) == n_num, f'shape mismatch {len(num_coefs)} vs {n_num}'
        coef_report[b['name']] = {
            'intercept': round(float(b['lr'].intercept_[0]), 4),
            'numerical_coefficients': {fc: round(float(c), 4)
                                        for fc, c in zip(b['feature_cols'], num_coefs)},
        }

        # Lexical coefficient inspection
        w_vocab = b['word_vec'].vocabulary_
        w_coefs = coefs[:n_word]
        lex = {}
        for tok in LEXICAL_INSPECT_TOKENS:
            idx = w_vocab.get(tok)
            if idx is not None:
                lex[tok] = round(float(w_coefs[idx]), 4)
            else:
                lex[tok] = None
        coef_report[b['name']]['lexical_coefficients_selected'] = lex

    # E5 lexical coefs for comparison
    e5_pipe = bundles[0]['model']
    e5_w_vec = e5_pipe.named_steps['feats'].transformer_list[0][1]
    e5_clf = e5_pipe.named_steps['clf']
    e5_n_word = len(e5_w_vec.vocabulary_)
    e5_w_coefs = e5_clf.coef_[0][:e5_n_word]
    coef_report['e5'] = {
        'intercept': round(float(e5_clf.intercept_[0]), 4),
        'lexical_coefficients_selected': {
            tok: (round(float(e5_w_coefs[e5_w_vec.vocabulary_[tok]]), 4)
                  if tok in e5_w_vec.vocabulary_ else None)
            for tok in LEXICAL_INSPECT_TOKENS
        },
    }

    # ── Case-level flip analysis (acceptance test) ────────────────────────────
    print('\n=== Case-level flip analysis (acceptance test) ===')
    e5_probs_acc = all_probs['e5']['acceptance']
    e5_yhat = (e5_probs_acc >= 0.59).astype(int)

    flip_report = {}
    for variant in VARIANTS:
        var_probs = all_probs[variant]['acceptance']
        var_yhat  = (var_probs >= 0.59).astype(int)
        flips_to_legit = []   # SCAM in E5 → LEGIT in variant (FP fix)
        flips_to_scam  = []   # LEGIT in E5 → SCAM in variant (regression)
        for i in range(len(acc_df)):
            if e5_yhat[i] == 1 and var_yhat[i] == 0:
                flips_to_legit.append(i)
            elif e5_yhat[i] == 0 and var_yhat[i] == 1:
                flips_to_scam.append(i)

        # For each flip, compute contribution decomposition
        details = []
        for i in flips_to_legit + flips_to_scam:
            row = acc_df.iloc[i]
            # Recompute contributions for this variant
            bundle = load_variant(variant)
            Xw = bundle['word_vec'].transform([row['text']])
            Xc = bundle['char_vec'].transform([row['text']])
            Xn_raw = np.array([[row[fc] for fc in bundle['feature_cols']]]).astype(np.float64)
            Xn = bundle['scaler'].transform(Xn_raw)
            n_word = Xw.shape[1]; n_char = Xc.shape[1]
            coefs = bundle['lr'].coef_[0]
            # Contribution of each block
            contrib_word = (Xw.toarray()[0] * coefs[:n_word]).sum()
            contrib_char = (Xc.toarray()[0] * coefs[n_word:n_word+n_char]).sum()
            contrib_num  = (Xn[0] * coefs[n_word+n_char:]).sum()
            details.append({
                'i': int(i),
                'category': row['category'],
                'text_preview': row['text'][:150],
                'e5_prob': round(float(e5_probs_acc[i]), 4),
                'variant_prob': round(float(var_probs[i]), 4),
                'delta_prob': round(float(var_probs[i] - e5_probs_acc[i]), 4),
                'contrib_word_tfidf': round(float(contrib_word), 4),
                'contrib_char_tfidf': round(float(contrib_char), 4),
                'contrib_numerical': round(float(contrib_num), 4),
                'flip_direction': 'SCAM_to_LEGIT' if e5_yhat[i] == 1 else 'LEGIT_to_SCAM',
            })
        flip_report[variant] = {
            'flips_to_legit': len(flips_to_legit),
            'flips_to_scam': len(flips_to_scam),
            'net_fp_change': -(len(flips_to_legit) - len(flips_to_scam)),
            'details': details,
        }
        print(f'  {variant}: {len(flips_to_legit)} FP→LEGIT   {len(flips_to_scam)} LEGIT→SCAM   net FP change: {len(flips_to_scam)-len(flips_to_legit):+d}')

    # ── Per-feature-group role classification ─────────────────────────────────
    role_classification = {}
    for variant in ['e7_p1_tone', 'e7_p1_url', 'e7_p1_phrase', 'e7_p1_textstats']:
        # Compare to E5 baseline
        ext_e5 = all_results['e5']['external']['primary_threshold_0.59']
        ext_var = all_results[variant]['external']['primary_threshold_0.59']
        acc_e5 = all_results['e5']['acceptance']['primary_threshold_0.59']
        acc_var = all_results[variant]['acceptance']['primary_threshold_0.59']

        fp_change = acc_e5['fp_rate'] - acc_var['fp_rate']       # positive = FP reduced
        recall_change = ext_var['recall'] - ext_e5['recall']     # positive = recall improved

        role = 'neither'
        if fp_change > 0.02 and recall_change >= -0.005:
            role = 'FP-reducer' if recall_change <= 0.005 else 'both'
        elif recall_change > 0.005 and fp_change >= -0.005:
            role = 'FN-reducer' if fp_change <= 0.005 else 'both'
        elif fp_change > 0.02 and recall_change > 0.005:
            role = 'both'

        role_classification[variant] = {
            'role': role,
            'fp_change_on_acceptance': round(float(fp_change), 4),
            'recall_change_on_external': round(float(recall_change), 4),
            'external_f1_change': round(float(ext_var['f1'] - ext_e5['f1']), 4),
        }

    # ── Save + Report ─────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w') as f:
        json.dump({
            'results': all_results,
            'coefficient_inspection': coef_report,
            'flip_analysis': flip_report,
            'role_classification': role_classification,
        }, f, indent=2)
    print(f'\nSaved results JSON to {OUT_JSON}')

    # Compose markdown report
    compose_report(all_results, coef_report, flip_report, role_classification, bundles)


def compose_report(results, coef_report, flip_report, role_classification, bundles):
    lines = ['# E7 · Phase 1 Research Report — Numerical Feature Fusion\n']
    lines.append('**Status:** research experiment · NO production swap regardless of outcome\n')
    lines.append('## 1. Aggregate metrics — E5 baseline vs 5 variants\n')
    lines.append('### External benchmark (n=25,306) at PRIMARY threshold 0.59')
    lines.append('| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC | ECE | Brier |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for name in ['e5'] + VARIANTS:
        m = results[name]['external']['primary_threshold_0.59']
        lines.append(f'| {name} | {m["accuracy"]} | {m["precision"]} | {m["recall"]} | **{m["f1"]}** | {m.get("roc_auc","-")} | {m.get("pr_auc","-")} | {m.get("ece","-")} | {m.get("brier","-")} |')

    lines.append('\n### External benchmark at VARIANT-OPTIMAL threshold (secondary analysis)')
    lines.append('| Model | Optimal t | val F1 at t | External F1 at t | vs 0.59 F1 |')
    lines.append('|---|---:|---:|---:|---:|')
    for name in ['e5'] + VARIANTS:
        if name == 'e5':
            lines.append(f'| e5 | 0.59 | — | {results["e5"]["external"]["primary_threshold_0.59"]["f1"]} | — |')
            continue
        opt = results[name]['external']['variant_optimal_threshold']
        opt_t = results[name]['external']['variant_optimal_threshold_value']
        p_f1 = results[name]['external']['primary_threshold_0.59']['f1']
        lines.append(f'| {name} | {opt_t} | {results[name]["external"]["optimal_val_f1"]} | {opt["f1"]} | {opt["f1"] - p_f1:+.4f} |')

    lines.append('\n### Manual acceptance test (n=32 real-world legit transactional emails)')
    lines.append('| Model | FP rate | wrongly flagged | delta vs E5 |')
    lines.append('|---|---:|---:|---:|')
    e5_acc_fp = results['e5']['acceptance']['primary_threshold_0.59']['fp_rate']
    for name in ['e5'] + VARIANTS:
        m = results[name]['acceptance']['primary_threshold_0.59']
        delta = m['fp_rate'] - e5_acc_fp
        marker = '' if name == 'e5' else (' ↓' if delta < -0.02 else ' ↑' if delta > 0.02 else ' ~')
        lines.append(f'| {name} | {m["fp_rate"]:.2%} | {m["confusion"]["fp"]}/{m["n"]} | {delta:+.4f}{marker} |')

    lines.append('\n### E6 authentic corpus (n=97: 66 legit + 31 scam)')
    lines.append('| Model | Accuracy | Precision | Recall | F1 |')
    lines.append('|---|---:|---:|---:|---:|')
    for name in ['e5'] + VARIANTS:
        m = results[name]['e6_authentic']['primary_threshold_0.59']
        lines.append(f'| {name} | {m["accuracy"]} | {m["precision"]} | {m["recall"]} | {m["f1"]} |')

    # Per-category recall on external
    lines.append('\n## 2. Per-category performance (external benchmark, threshold 0.59)\n')
    lines.append('### Scam-class recall by category')
    scam_cats = sorted(results['e5']['external']['per_category_scam_recall'].keys())
    hdr = '| Model | ' + ' | '.join(scam_cats) + ' |'
    lines.append(hdr); lines.append('|' + '|'.join(['---:']*(len(scam_cats)+1)) + '|')
    for name in ['e5'] + VARIANTS:
        pcm = results[name]['external']['per_category_scam_recall']
        row = f'| {name} | ' + ' | '.join(f"{pcm.get(c,{}).get('recall','-')}" for c in scam_cats) + ' |'
        lines.append(row)

    lines.append('\n### Legit-class FP rate by category')
    legit_cats = sorted(results['e5']['external']['per_category_legit_fp_rate'].keys())
    hdr = '| Model | ' + ' | '.join(legit_cats) + ' |'
    lines.append(hdr); lines.append('|' + '|'.join(['---:']*(len(legit_cats)+1)) + '|')
    for name in ['e5'] + VARIANTS:
        pcm = results[name]['external']['per_category_legit_fp_rate']
        row = f'| {name} | ' + ' | '.join(f"{pcm.get(c,{}).get('fp_rate','-')}" for c in legit_cats) + ' |'
        lines.append(row)

    # Numerical coefficients
    lines.append('\n## 3. Numerical feature coefficients (per variant)\n')
    for name in VARIANTS:
        lines.append(f'### {name}')
        lines.append(f'Intercept: {coef_report[name]["intercept"]}\n')
        lines.append('| Feature | Coefficient |')
        lines.append('|---|---:|')
        for fc, c in sorted(coef_report[name]['numerical_coefficients'].items(),
                             key=lambda x: -abs(x[1])):
            lines.append(f'| {fc} | {c:+.4f} |')
        lines.append('')

    # Lexical coefficient comparison
    lines.append('\n## 4. Lexical coefficient comparison (E5 vs each variant)\n')
    hdr = '| Token | E5 | ' + ' | '.join(VARIANTS) + ' |'
    lines.append(hdr); lines.append('|' + '|'.join(['---:']*(len(VARIANTS)+2)) + '|')
    for tok in LEXICAL_INSPECT_TOKENS:
        row = [tok, coef_report['e5']['lexical_coefficients_selected'].get(tok, '—')]
        for v in VARIANTS:
            row.append(coef_report[v]['lexical_coefficients_selected'].get(tok, '—'))
        lines.append('| ' + ' | '.join(str(x) for x in row) + ' |')

    # Flip analysis
    lines.append('\n## 5. Case-level flip analysis on the 32 acceptance-test messages\n')
    lines.append('| Variant | FP → LEGIT (fixed) | LEGIT → SCAM (regressions) | Net FP change |')
    lines.append('|---|---:|---:|---:|')
    for v in VARIANTS:
        f = flip_report[v]
        lines.append(f'| {v} | {f["flips_to_legit"]} | {f["flips_to_scam"]} | {f["net_fp_change"]:+d} |')

    lines.append('\n### Detailed flips (top per variant)')
    for v in VARIANTS:
        details = flip_report[v]['details']
        if not details: continue
        lines.append(f'\n#### {v}')
        for d in details[:10]:  # cap at 10 per variant
            lines.append(f'- **[{d["category"]}] {d["flip_direction"]}** '
                         f'p={d["e5_prob"]:.3f}→{d["variant_prob"]:.3f} (Δ={d["delta_prob"]:+.3f})')
            lines.append(f'  - contributions: word={d["contrib_word_tfidf"]:+.3f}  char={d["contrib_char_tfidf"]:+.3f}  **numerical={d["contrib_numerical"]:+.3f}**')
            lines.append(f'  - text: {d["text_preview"]}')

    # Role classification
    lines.append('\n## 6. Per-feature-group role classification\n')
    lines.append('| Feature group | Role | Δ FP rate (acceptance) | Δ recall (external) | Δ F1 (external) |')
    lines.append('|---|---|---:|---:|---:|')
    for v in ['e7_p1_tone', 'e7_p1_url', 'e7_p1_phrase', 'e7_p1_textstats']:
        r = role_classification[v]
        lines.append(f'| {v.replace("e7_p1_","")} | **{r["role"]}** | {r["fp_change_on_acceptance"]:+.4f} | {r["recall_change_on_external"]:+.4f} | {r["external_f1_change"]:+.4f} |')

    lines.append('\n## 7. Scientific interpretation\n')
    lines.append('(populated during manual review of the report — see raw JSON for full data)\n')

    with open(OUT_REPORT, 'w') as f:
        f.write('\n'.join(lines))
    print(f'Saved report to {OUT_REPORT}')


if __name__ == '__main__':
    main()
