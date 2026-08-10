"""
E8-P2 synthetic legit dataset — QA report.

Runs FOUR quality checks. Does NOT retrain, merge, or evaluate model
performance. Writes qa_report.txt for review.

  1. Length distribution per category (chars + words).
  2. TF-IDF vocabulary comparison vs. the current training-legit corpus
     (data/interim/e7_p1_features.parquet, split='train', label=0).
     Reports:
        - vocab overlap
        - cosine similarity of mean TF-IDF vectors
        - top terms that gained / lost weight (synthetic vs. training)
        - per-category cosine similarity vs. training-legit
  3. Random sample of 100 messages from the FINAL dataset for manual review.
  4. Re-run all safety validators on a 200-message random sample.

Output: data/synthetic_legit/e8p2/qa_report.txt
"""
from __future__ import annotations

import os
import re
import sys
import warnings
from collections import Counter

import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

SYNTH_PATH   = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p2', 'dataset.parquet')
TRAIN_PATH   = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features.parquet')
REPORT_PATH  = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p2', 'qa_report.txt')

# Reuse the same validators used at generation time
from scripts.data_prep.gen_e8p2_synthetic_legit import validate

RNG = np.random.default_rng(42)


def sec(title: str) -> str:
    bar = '═' * 80
    return f'\n{bar}\n  {title}\n{bar}\n'


def word_count(t: str) -> int:
    return len(re.findall(r'\S+', t))


def main():
    out: list = []
    write = out.append

    write('E8-P2 synthetic legit dataset — QA report')
    write(f'Generated: {pd.Timestamp.now()}')
    write('')

    # ────────────────────────────────────────────────────────────────────
    # 1. LENGTH DISTRIBUTION PER CATEGORY
    # ────────────────────────────────────────────────────────────────────
    df = pd.read_parquet(SYNTH_PATH)
    df['chars'] = df.text.str.len()
    df['words'] = df.text.apply(word_count)

    write(sec('1. LENGTH DISTRIBUTION PER CATEGORY'))
    write(f'{"category":26s}  {"n":>5s}  {"chars mean±sd":>16s}  '
          f'{"chars p10-p50-p90":>22s}  {"words mean":>10s}  {"words min-max":>14s}')
    write('-' * 100)
    for cat in sorted(df.category.unique()):
        sub = df[df.category == cat]
        cmean = sub.chars.mean(); csd = sub.chars.std()
        cmin  = int(sub.chars.min()); cmax = int(sub.chars.max())
        cp10  = int(sub.chars.quantile(0.10)); cp50 = int(sub.chars.quantile(0.50)); cp90 = int(sub.chars.quantile(0.90))
        wmean = sub.words.mean()
        wmin  = int(sub.words.min()); wmax = int(sub.words.max())
        write(f'  {cat:24s}  {len(sub):>5d}  {cmean:>7.0f}±{csd:>5.0f}   '
              f'{cp10:>4d}-{cp50:>4d}-{cp90:>4d}    {wmean:>7.1f}    '
              f'{wmin:>4d}-{wmax:<5d}')
    write('')
    write(f'  Overall: n={len(df):,}   '
          f'char mean={df.chars.mean():.0f}  words mean={df.words.mean():.1f}')
    write(f'  Comparison baselines:  OTP notifications typically 50-150 chars, '
          f'security notifications 200-500 chars, order confirmations 150-400 chars.')

    # ────────────────────────────────────────────────────────────────────
    # 4. SAFETY VALIDATOR RESAMPLE (moved before slower TF-IDF section)
    # ────────────────────────────────────────────────────────────────────
    write(sec('4. SAFETY VALIDATORS — random sample re-check (n=200)'))
    n_check = min(200, len(df))
    idx = RNG.choice(len(df), size=n_check, replace=False)
    check = df.iloc[idx]
    rejects = Counter()
    for _, r in check.iterrows():
        ok, reason = validate(r.text)
        if not ok:
            rejects[reason] += 1
    write(f'  sampled: {n_check} messages')
    if not rejects:
        write(f'  ✓ 0 rejections (0/{n_check}). All safety validators clean.')
    else:
        write(f'  ✗ {sum(rejects.values())} rejections:')
        for r, n in rejects.most_common():
            write(f'    {r}: {n}')

    # ────────────────────────────────────────────────────────────────────
    # 2. TF-IDF VOCAB COMPARISON
    # ────────────────────────────────────────────────────────────────────
    write(sec('2. TF-IDF VOCABULARY COMPARISON (synthetic vs. training-legit)'))
    write(f'  Loading training corpus: {TRAIN_PATH}')
    tr = pd.read_parquet(TRAIN_PATH, columns=['text', 'label', 'split'])
    tr_legit = tr[(tr.split == 'train') & (tr.label == 0)].reset_index(drop=True)
    write(f'    training-legit rows: {len(tr_legit):,}')

    # Fit ONE TF-IDF on the union of both corpora so vocab is comparable.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    write(f'  Fitting shared TfidfVectorizer (ngram 1-2, min_df=5, max_features=30k)...')
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_features=30_000,
                          sublinear_tf=True, lowercase=True)
    # Sample training-legit down for speed if huge; take a stratified 30k sample
    tr_sample = tr_legit.sample(n=min(30_000, len(tr_legit)), random_state=42)
    all_texts = list(tr_sample.text) + list(df.text)
    X = vec.fit_transform(all_texts)
    X_tr = X[:len(tr_sample)]
    X_sy = X[len(tr_sample):]

    write(f'    shared vocab size: {len(vec.get_feature_names_out()):,}')

    # Vocab overlap: fraction of synthetic-vocab terms that also appear
    # (>= min_df) in the training set
    tr_terms = set()
    sy_terms = set()
    # Non-zero column indices for each subcorpus
    tr_nonzero = np.asarray((X_tr > 0).sum(axis=0)).ravel() > 0
    sy_nonzero = np.asarray((X_sy > 0).sum(axis=0)).ravel() > 0
    feat = vec.get_feature_names_out()
    tr_terms = set(feat[tr_nonzero])
    sy_terms = set(feat[sy_nonzero])
    overlap = tr_terms & sy_terms
    write(f'  Vocab overlap:')
    write(f'    training-legit-only terms:  {len(tr_terms - sy_terms):,}')
    write(f'    synthetic-only terms:       {len(sy_terms - tr_terms):,}')
    write(f'    shared terms:               {len(overlap):,}')
    write(f'    synthetic overlap ratio:    {len(overlap)/len(sy_terms):.1%}   '
          f'(fraction of synthetic vocab found in training)')

    # Cosine similarity of MEAN tf-idf vectors
    tr_mean = np.asarray(X_tr.mean(axis=0)).ravel()
    sy_mean = np.asarray(X_sy.mean(axis=0)).ravel()
    cos = float(cosine_similarity(tr_mean.reshape(1, -1), sy_mean.reshape(1, -1))[0, 0])
    write(f'  Cosine similarity of mean TF-IDF vectors:  {cos:.4f}')
    write(f'    (1.0 = same distribution, 0.0 = orthogonal)')

    # Top shifted terms — largest positive delta (synthetic > training)
    # and largest negative delta (training > synthetic).
    delta = sy_mean - tr_mean
    order_pos = np.argsort(-delta)[:30]
    order_neg = np.argsort( delta)[:30]
    write(f'')
    write(f'  TOP 30 TERMS OVERWEIGHTED IN SYNTHETIC (positive shift; new signal we\'re adding):')
    for i, ix in enumerate(order_pos, 1):
        write(f'    {i:>2}. {feat[ix]:32s}  Δ={delta[ix]:+.4f}   '
              f'tr={tr_mean[ix]:.4f}  sy={sy_mean[ix]:.4f}')
    write(f'')
    write(f'  TOP 30 TERMS UNDERWEIGHTED IN SYNTHETIC (negative shift; not in synthetic):')
    for i, ix in enumerate(order_neg, 1):
        write(f'    {i:>2}. {feat[ix]:32s}  Δ={delta[ix]:+.4f}   '
              f'tr={tr_mean[ix]:.4f}  sy={sy_mean[ix]:.4f}')

    # Per-category cosine vs. training-legit — flag anything abnormal
    write(f'')
    write(f'  PER-CATEGORY cosine similarity vs. training-legit mean:')
    write(f'  {"category":26s}  {"n":>5s}  {"cos-sim":>8s}  {"synth-only vocab %":>20s}')
    write(f'  ' + '-' * 65)
    per_cat_stats: list = []
    for cat in sorted(df.category.unique()):
        cat_mask = df.category.values == cat
        X_cat = X_sy[cat_mask]
        cat_mean = np.asarray(X_cat.mean(axis=0)).ravel()
        cat_cos = float(cosine_similarity(tr_mean.reshape(1, -1), cat_mean.reshape(1, -1))[0, 0])
        cat_nonzero = np.asarray((X_cat > 0).sum(axis=0)).ravel() > 0
        cat_terms = set(feat[cat_nonzero])
        cat_only = cat_terms - tr_terms
        cat_only_pct = 100 * len(cat_only) / max(len(cat_terms), 1)
        per_cat_stats.append((cat, len(X_cat.data) // max(int(cat_mask.sum()), 1), cat_cos, cat_only_pct))
        write(f'  {cat:24s}  {int(cat_mask.sum()):>5d}  {cat_cos:>8.4f}   {cat_only_pct:>18.1f}%')
    write(f'')
    outliers = [c for c, _, cos_, _ in per_cat_stats if cos_ < 0.25]
    if outliers:
        write(f'  ⚠ CATEGORIES WITH LOW COS-SIM (<0.25) vs training-legit: {outliers}')
        write(f'    These are the most "novel" — expected, since they fill the missing region.')
    else:
        write(f'  ✓ All categories have reasonable cos-sim overlap with training-legit.')

    # ────────────────────────────────────────────────────────────────────
    # 3. MANUAL REVIEW SAMPLE — 100 random messages from FINAL dataset
    # ────────────────────────────────────────────────────────────────────
    write(sec('3. MANUAL REVIEW SAMPLE — 100 messages from FINAL dataset'))
    write(f'  Random-seed=42 selection. Read for realism / repetitiveness / AI-tells.')
    write(f'')
    sample = df.sample(n=min(100, len(df)), random_state=42).reset_index(drop=True)
    for i, r in sample.iterrows():
        write(f'  #{i+1:>3}  [{r.category}]  [{r.brand}]  [{r.template_id}]')
        for line in r.text.split('\n'):
            write(f'       {line}')
        write('')

    # ────────────────────────────────────────────────────────────────────
    # Write report
    # ────────────────────────────────────────────────────────────────────
    with open(REPORT_PATH, 'w') as f:
        f.write('\n'.join(out))
    print(f'Wrote {REPORT_PATH}  ({os.path.getsize(REPORT_PATH):,} bytes)')


if __name__ == '__main__':
    main()
