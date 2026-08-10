"""
Snapshot LR coefficients for a set of transactional terms from a trained
e7_p1_variants bundle.

Usage:
    python scripts/training/snapshot_e7_p1_coefs.py <bundle_path> <output_json>

Writes JSON:
    {term: {word_ngram_coef, char_ngram_coef, present}, ...}

Positive coefficient = pushes toward SCAM class; negative = toward LEGIT.
This lets us diff "before/after" retrain to see if transactional vocabulary
became less strongly scam-associated after adding the synthetic legit data.
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import joblib
warnings.filterwarnings('ignore')

TERMS = [
    'your account',
    'order',
    'your order',
    'shipped',
    'delivery',
    'receipt',
    'invoice',
    'payment',
    'payment received',
    'tracking number',
    'subscription',
    'sign in',
    'verification code',
]


def _lookup_coef(vec, coef_vector, term: str, offset: int = 0):
    """Return (coef, index_in_full_matrix) for `term` if present in vec's
    vocabulary, else (None, None). `offset` shifts the index up by the
    concatenated-feature preamble (word block precedes char block)."""
    vocab = vec.vocabulary_
    if term not in vocab:
        return None, None
    col = vocab[term]
    return float(coef_vector[col + offset]), int(col + offset)


def main(bundle_path: str, out_path: str):
    print(f'Loading bundle: {bundle_path}')
    bundle = joblib.load(bundle_path)
    lr        = bundle['lr']
    word_vec  = bundle['word_vec']
    char_vec  = bundle['char_vec']
    coefs     = lr.coef_.ravel()          # shape (n_features_total,)

    n_word = len(word_vec.get_feature_names_out())
    n_char = len(char_vec.get_feature_names_out())
    print(f'  word TF-IDF vocab: {n_word:,}')
    print(f'  char TF-IDF vocab: {n_char:,}')
    print(f'  total LR coefs:    {len(coefs):,}  (positive = scam-leaning)')

    snapshot: dict = {'bundle_path': bundle_path, 'terms': {}}
    print(f'\n{"term":22s}  {"word coef":>10s}  {"char coef":>10s}  {"present":>8s}')
    print('-' * 60)
    for term in TERMS:
        w_coef, _ = _lookup_coef(word_vec, coefs, term, offset=0)
        c_coef, _ = _lookup_coef(char_vec, coefs, term, offset=n_word)
        snapshot['terms'][term] = {
            'word_coef':      w_coef,
            'char_coef':      c_coef,
            'present_word':   w_coef is not None,
            'present_char':   c_coef is not None,
        }
        pres = 'w' if w_coef is not None else '·'
        pres += 'c' if c_coef is not None else '·'
        wstr = f'{w_coef:+.4f}' if w_coef is not None else '   n/a   '
        cstr = f'{c_coef:+.4f}' if c_coef is not None else '   n/a   '
        print(f'  {term:20s}  {wstr:>10s}  {cstr:>10s}  {pres:>8s}')

    with open(out_path, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f'\nWrote {out_path}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
