"""
Analyzes tests/comparison_results.json to build the per-category win map.

Rules (per user's spec):
- For each message, ground_truth is SCAM or LEGIT.
- A model's verdict is "correct" if:
    - ground_truth == SCAM  and verdict in {SCAM, SUSPICIOUS}
    - ground_truth == LEGIT and verdict == LEGIT
  This mirrors how the production UI treats SUSPICIOUS (visually red).
- Per-category winner: strictly higher accuracy wins; equal accuracy is TIE.

Emits:
- Console table of per-category accuracy for both models + winner.
- Detailed breakdown of disagreements (where local ≠ deployed).
- tests/comparison_summary.json for durable record.
"""
import json
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(BASE, 'tests', 'comparison_results.json')
SUMMARY_PATH = os.path.join(BASE, 'tests', 'comparison_summary.json')

CATEGORIES_ORDERED = [
    'obvious_phishing',
    'delivery_scams',
    'crypto_investment',
    'recruitment_scams',
    'romance_social',
    'normal',
    'business',
    'gaming_discord',
]

CATEGORY_LABEL = {
    'obvious_phishing': 'Obvious phishing',
    'delivery_scams':   'Delivery scams',
    'crypto_investment':'Crypto/investment',
    'recruitment_scams':'Recruitment scams',
    'romance_social':   'Romance / social eng.',
    'normal':           'Completely normal',
    'business':         'Business emails',
    'gaming_discord':   'Gaming/Discord',
}


def is_correct(verdict, ground_truth):
    if verdict is None:
        return None  # unknown — model errored
    if ground_truth == 'SCAM':
        return verdict in ('SCAM', 'SUSPICIOUS')
    return verdict == 'LEGIT'


def per_category(results):
    stats = defaultdict(lambda: {
        'n': 0, 'local_correct': 0, 'deployed_correct': 0,
        'local_errors': 0, 'deployed_errors': 0,
    })
    for r in results:
        c = r['category']
        gt = r['ground_truth']
        stats[c]['n'] += 1

        loc_v = r['local'].get('verdict') if r['local'].get('ok') else None
        dep_v = r['deployed'].get('verdict') if r['deployed'].get('ok') else None

        loc_ok = is_correct(loc_v, gt)
        dep_ok = is_correct(dep_v, gt)

        if loc_ok is None:
            stats[c]['local_errors'] += 1
        elif loc_ok:
            stats[c]['local_correct'] += 1

        if dep_ok is None:
            stats[c]['deployed_errors'] += 1
        elif dep_ok:
            stats[c]['deployed_correct'] += 1

    return stats


def winner(local_acc, deployed_acc):
    if abs(local_acc - deployed_acc) < 1e-9:
        return 'TIE'
    return 'LOCAL (11866bb)' if local_acc > deployed_acc else 'DEPLOYED (v1.3)'


def print_table(stats):
    print(f"\n{'='*88}")
    print(f"PER-CATEGORY WIN MAP  —  ORIGINAL (11866bb) vs v1.3")
    print(f"{'='*88}")
    print(f"{'Category':24s} {'n':>4s}  {'orig acc':>9s} {'v1.3 acc':>9s}  {'orig OK':>7s} {'v1.3 OK':>7s}   {'Winner'}")
    print(f"{'-'*88}")

    totals = {'n': 0, 'l': 0, 'd': 0}

    for cat in CATEGORIES_ORDERED:
        s = stats.get(cat)
        if not s or s['n'] == 0:
            continue
        n = s['n']
        la = s['local_correct'] / n
        da = s['deployed_correct'] / n
        w = winner(la, da)
        totals['n'] += n
        totals['l'] += s['local_correct']
        totals['d'] += s['deployed_correct']
        print(f"{CATEGORY_LABEL[cat]:24s} {n:>4d}  {la:>9.1%} {da:>9.1%}  "
              f"{s['local_correct']:>7d} {s['deployed_correct']:>7d}   {w}")
    print(f"{'-'*88}")
    la = totals['l'] / totals['n']
    da = totals['d'] / totals['n']
    print(f"{'OVERALL':24s} {totals['n']:>4d}  {la:>9.1%} {da:>9.1%}  "
          f"{totals['l']:>7d} {totals['d']:>7d}   {winner(la, da)}")

    return totals


def print_disagreements(results, max_per_category=3):
    print(f"\n{'='*88}")
    print(f"DISAGREEMENTS  (where original and v1.3 gave different verdicts)")
    print(f"{'='*88}")

    by_cat = defaultdict(list)
    for r in results:
        loc_v = r['local'].get('verdict') if r['local'].get('ok') else None
        dep_v = r['deployed'].get('verdict') if r['deployed'].get('ok') else None
        if loc_v == dep_v:
            continue
        by_cat[r['category']].append(r)

    for cat in CATEGORIES_ORDERED:
        items = by_cat.get(cat, [])
        if not items:
            continue
        print(f"\n  [{CATEGORY_LABEL[cat]}]  {len(items)} disagreement(s)")
        for r in items[:max_per_category]:
            loc_v = r['local'].get('verdict', '?')
            loc_c = r['local'].get('confidence', 0)
            dep_v = r['deployed'].get('verdict', '?')
            dep_c = r['deployed'].get('confidence', 0)
            marker_l = '✓' if is_correct(loc_v, r['ground_truth']) else '✗'
            marker_d = '✓' if is_correct(dep_v, r['ground_truth']) else '✗'
            preview = r['text'][:120].replace('\n', ' ')
            print(f"    #{r['id']:3d}  gt={r['ground_truth']:5s}  "
                  f"orig={loc_v:11s}({loc_c:5.1f}%){marker_l}  "
                  f"v1.3={dep_v:11s}({dep_c:5.1f}%){marker_d}")
            print(f"         text: {preview}...")


def print_failure_modes(results):
    """Which model over-fires (calls LEGIT scam) vs under-fires (misses scam)?"""
    print(f"\n{'='*88}")
    print(f"FAILURE MODE PROFILE")
    print(f"{'='*88}")
    for model in ('local', 'deployed'):
        label = 'ORIGINAL (11866bb)' if model == 'local' else 'v1.3 (deployed)'
        fp = fn = tp = tn = errs = 0
        for r in results:
            block = r[model]
            if not block.get('ok'):
                errs += 1
                continue
            v = block.get('verdict')
            gt = r['ground_truth']
            pred = 'SCAM' if v in ('SCAM', 'SUSPICIOUS') else 'LEGIT'
            if gt == 'SCAM' and pred == 'SCAM':   tp += 1
            elif gt == 'SCAM' and pred == 'LEGIT': fn += 1
            elif gt == 'LEGIT' and pred == 'LEGIT': tn += 1
            else: fp += 1
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2*prec*rec/(prec+rec)) if (prec+rec) else 0.0
        print(f"\n  {label}")
        print(f"    TP={tp}  FP={fp}  TN={tn}  FN={fn}  (errors={errs})")
        print(f"    Precision={prec:.3f}  Recall={rec:.3f}  F1={f1:.3f}")
        print(f"    FP rate on LEGIT: {fp/(fp+tn):.1%}   (over-firing on normal messages)")
        print(f"    FN rate on SCAM:  {fn/(tp+fn):.1%}   (missed scams)")


def main():
    d = json.load(open(RESULTS_PATH))
    results = d['results']
    print(f"Loaded {len(results)} results ({d['meta']['duration_s']}s runtime)")

    stats = per_category(results)
    totals = print_table(stats)
    print_failure_modes(results)
    print_disagreements(results, max_per_category=4)

    summary = {
        'n_total': totals['n'],
        'local_overall_accuracy': round(totals['l'] / totals['n'], 4),
        'deployed_overall_accuracy': round(totals['d'] / totals['n'], 4),
        'per_category': {
            cat: {
                'n': stats[cat]['n'],
                'local_accuracy':    round(stats[cat]['local_correct'] / stats[cat]['n'], 4),
                'deployed_accuracy': round(stats[cat]['deployed_correct'] / stats[cat]['n'], 4),
                'local_correct':    stats[cat]['local_correct'],
                'deployed_correct': stats[cat]['deployed_correct'],
                'local_errors':    stats[cat]['local_errors'],
                'deployed_errors': stats[cat]['deployed_errors'],
                'winner': winner(
                    stats[cat]['local_correct']/stats[cat]['n'],
                    stats[cat]['deployed_correct']/stats[cat]['n'],
                ),
            }
            for cat in CATEGORIES_ORDERED if stats.get(cat)
        },
    }
    with open(SUMMARY_PATH, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {SUMMARY_PATH}")


if __name__ == '__main__':
    main()
