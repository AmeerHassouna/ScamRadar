"""Diff two coefficient snapshots produced by snapshot_e7_p1_coefs.py.

Usage:
    python scripts/training/diff_coefs.py <before.json> <after.json>
"""
import json
import sys


def main(before_path: str, after_path: str):
    b = json.load(open(before_path))['terms']
    a = json.load(open(after_path))['terms']
    all_terms = list(b.keys())
    print(f'{"term":22s}  {"before":>10s}  {"after":>10s}  {"Δ":>10s}   direction')
    print('-' * 75)
    for t in all_terms:
        bw = b[t].get('word_coef')
        aw = a[t].get('word_coef')
        if bw is None or aw is None:
            print(f'  {t:20s}  {"n/a":>10s}  {"n/a":>10s}  {"":>10s}')
            continue
        d = aw - bw
        # Direction narrative
        if bw > 0 and aw > 0:
            direction = 'still SCAM-leaning' + ('  ↓ weaker' if d < 0 else '  ↑ stronger')
        elif bw > 0 and aw <= 0:
            direction = '  ↓ flipped to LEGIT'
        elif bw <= 0 and aw > 0:
            direction = '  ↑ flipped to SCAM'
        else:
            direction = 'still LEGIT-leaning' + ('  ↑ weaker' if d > 0 else '  ↓ stronger')
        print(f'  {t:20s}  {bw:+10.4f}  {aw:+10.4f}  {d:+10.4f}   {direction}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2])
