"""
E8-P5 training corpus — E8-P3's clean parquet minus training-noise rows:

  1. SCAM-labeled rows that are actually legit mailing-list posts
     (Python-Dev, opensuse, TuxOnIce, perl beginners, etc.). ~343 rows
     across nazario_modern (170) + nigerian_fraud_modern (131) + others.

  2. LEGIT-labeled rows containing STRONG spam patterns (viagra, cialis,
     penis-enlargement, Nigerian 419 templates, etc.). ~200 rows across
     enron_ham_sample, ceas08, and others.

  3. Very short items (< 20 chars) — no signal.

E8-P2 synthetic legit (1,978 rows) retained as-is.
Spamassassin_ham (all splits) still filtered as in E8-P3.

Output: data/interim/e7_p1_features_e8p5.parquet
"""
from __future__ import annotations
import os, sys, hashlib, json, re, warnings
warnings.filterwarnings('ignore')
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

E5         = '/Users/ameer/Downloads/scamradar2/data'
MERGED_IN  = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p3.parquet')
MERGED_OUT = os.path.join(_ROOT, 'data', 'interim', 'e7_p1_features_e8p5.parquet')
REPORT     = os.path.join(_ROOT, 'data', 'interim', 'e8p5_cleanup_report.json')


SPAM_STRICT = re.compile(
    r'\b('
    r'viagra|c[i1]al[i1]s|v[i1]agr[a4]|'
    r'penis\s+(enlargement|growth|pump|size)|'
    r'enlarge\s+your\s+penis|'
    r'weight\s+loss\s+(pills?|shakes?|programs?)|'
    r'refinance\s+your\s+home|'
    r'lower\s+your\s+mortgage|'
    r'(?:mr\.?|dr\.?|barrister|prince|late)\s+[a-z]+\s+[a-z]+\s+(?:from|of)\s+(?:nigeria|sierra\s*leone|ivory\s*coast|liberia|abidjan)|'
    r'my\s+(?:late\s+)?(?:husband|father|uncle)\s+(?:the\s+)?(?:late\s+)?(?:president|minister|general)|'
    r'unclaimed\s+(?:funds?|inheritance|deposit)|'
    r'trapped\s+(?:in|inside)\s+(?:a\s+)?bank|'
    r'kindly\s+(?:reply|assist|contact)\s+(?:me|us|urgent)|'
    r'i\s+(?:am|need)\s+(?:god[- ]?fearing|a\s+god[- ]?fearing)|'
    r'\d{1,3}\s*(?:million|billion)\s+(?:dollars?|usd|us\$|euros?)'
    r')\b',
    re.IGNORECASE)

MAIL_LIST = re.compile(
    r'^\s*(?:Re:\s*)?\[\s*(python-?dev|python-3000|tuxonice|opensuse|opensuse-kde|opensuse-factory|'
    r'perl|centos|fedora|debian|gcc|gnu|kde|gnome|ilug|ietf|spambayes|spambayes-dev|'
    r'openoffice|apache|linux-kernel|xorg|gtk-list|beginners)\b',
    re.IGNORECASE)


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8', 'ignore')).hexdigest()


def main():
    print('=== E8-P5 training corpus: apply targeted noise cleanup ===')

    # ── Load E8-P3 merged parquet (has features, synth legit, no SA) ─────
    print(f'\nLoading {MERGED_IN}')
    df = pd.read_parquet(MERGED_IN)
    print(f'  rows: {len(df):,}')

    # ── Load source parquets to get (text, source) mapping ───────────────
    print('\nLoading source parquets for cross-label audit...')
    src_map: dict = {}     # text_hash → source
    for split in ['train', 'val', 'test']:
        s = pd.read_parquet(f'{E5}/processed/{split}.parquet',
                             columns=['text', 'source'])
        for t, src in zip(s.text, s.source):
            src_map[_hash(t)] = src
    print(f'  {len(src_map):,} unique (source-tagged) text hashes')

    # ── Attach source ────────────────────────────────────────────────────
    df['_h']     = df.text.map(_hash)
    df['source'] = df._h.map(src_map).fillna('synthetic_e8p2')

    # ── Identify rows to drop ────────────────────────────────────────────
    ml_scam    = (df.label == 1) & df.text.str.match(MAIL_LIST.pattern, na=False,
                                                       flags=re.IGNORECASE)
    spam_legit = (df.label == 0) & df.text.str.contains(SPAM_STRICT.pattern, regex=True,
                                                          na=False, case=False)
    too_short  = df.text.str.len() < 20

    drop_mask = ml_scam | spam_legit | too_short
    dropped   = df[drop_mask]
    kept      = df[~drop_mask]

    print(f'\n── Drop counts ──')
    print(f'  scam rows with mailing-list header:    {int(ml_scam.sum()):>5}')
    print(f'  legit rows with strong spam text:      {int(spam_legit.sum()):>5}')
    print(f'  very short items (< 20 chars):         {int(too_short.sum()):>5}')
    print(f'  TOTAL dropped:                          {int(drop_mask.sum()):>5}  '
          f'({100*int(drop_mask.sum())/len(df):.2f}%)')

    print(f'\n── Dropped by source ──')
    dropped_by_src = dropped.source.value_counts()
    for src, n in dropped_by_src.items():
        print(f'    {src:34s} {n:>5}')

    # ── Save ─────────────────────────────────────────────────────────────
    kept = kept.drop(columns=['_h', 'source']).reset_index(drop=True)
    print(f'\nRemaining rows: {len(kept):,}')
    print(kept.groupby(['split','label']).size().reset_index(name='n').to_string(index=False))
    kept.to_parquet(MERGED_OUT, index=False)
    print(f'\nWrote {MERGED_OUT}   ({os.path.getsize(MERGED_OUT)/1e6:.1f} MB)')

    with open(REPORT, 'w') as f:
        json.dump({
            'input_rows':      int(len(df)),
            'output_rows':     int(len(kept)),
            'dropped_total':   int(drop_mask.sum()),
            'dropped_ml_scam': int(ml_scam.sum()),
            'dropped_spam_legit': int(spam_legit.sum()),
            'dropped_too_short':  int(too_short.sum()),
            'dropped_by_source':  {k: int(v) for k, v in dropped_by_src.items()},
        }, f, indent=2)
    print(f'Wrote {REPORT}')


if __name__ == '__main__':
    main()
