"""
v1.7 error mining — pulls FP/FN from every eval output we have and from
our new 180-msg A/B, deduplicates by SHA-1 on normalized text, and dumps
a single JSONL of hard cases with full provenance.

Sources:
  - outputs/eval/v1.4_candidate_external.json  (v1.4 FP/FN on 400 external)
  - outputs/eval/v1.5_candidate_external.json  (v1.5 FP/FN on 400 external)
  - outputs/eval/v1.6_candidate_external.json  (v1.6 FP/FN on 400 external)
  - tests/comparison_results.json              (180-msg A/B — errors from
                                                both original 11866bb and v1.3)

Priority tiers:
  - tier=high_conf_wrong  : model was ≥80% confident and wrong
  - tier=shared_miss      : multiple models got same item wrong
  - tier=mid_conf_wrong   : otherwise wrong

Output: data/v1.7_augmentation/mined_errors/errors.jsonl
Each row: {text, label, sources[], tier, notes}
"""
import json
import os
import hashlib
import re
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(BASE, 'data', 'v1.7_augmentation', 'mined_errors')
os.makedirs(OUT_DIR, exist_ok=True)


def norm_key(text):
    """Lowercase + strip whitespace + collapse spaces → SHA-1."""
    s = re.sub(r'\s+', ' ', (text or '').strip().lower())
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


def mine_external_json(path, tag):
    """v1.4/1.5/1.6_candidate_external.json format."""
    if not os.path.exists(path):
        return []
    d = json.load(open(path))
    out = []
    for e in d.get('false_positives', []):
        out.append({
            'text': e['text'],
            'label': 0,  # LEGIT — model wrongly said SCAM
            'source': tag,
            'wrong_model': tag,
            'confidence': e.get('confidence'),
            'error_type': 'FP',
        })
    for e in d.get('false_negatives', []):
        out.append({
            'text': e['text'],
            'label': 1,  # SCAM — model wrongly said LEGIT
            'source': tag,
            'wrong_model': tag,
            'confidence': e.get('confidence'),
            'error_type': 'FN',
        })
    return out


def mine_comparison(path):
    """tests/comparison_results.json — both models scored per row."""
    if not os.path.exists(path):
        return []
    d = json.load(open(path))
    out = []
    for r in d['results']:
        gt = r['ground_truth']
        label = 1 if gt == 'SCAM' else 0
        for model_key, model_tag in (('local', 'orig_11866bb'), ('deployed', 'v1.3_deployed')):
            b = r[model_key]
            if not b.get('ok'):
                continue
            v = b.get('verdict')
            pred = 'SCAM' if v in ('SCAM', 'SUSPICIOUS') else 'LEGIT'
            if pred == gt:
                continue
            out.append({
                'text': r['text'],
                'label': label,
                'source': f'comparison_180_ab',
                'wrong_model': model_tag,
                'confidence': b.get('confidence'),
                'error_type': 'FN' if gt == 'SCAM' else 'FP',
                'category': r.get('category'),
            })
    return out


def merge_by_hash(items):
    """Group errors by normalized text hash. If multiple models missed the
    same item, keep highest-conf record but list every source."""
    buckets = defaultdict(list)
    for it in items:
        k = norm_key(it['text'])
        buckets[k].append(it)

    merged = []
    for k, group in buckets.items():
        # Label consistency check — if any disagreement, drop
        labels = {g['label'] for g in group}
        if len(labels) > 1:
            continue
        label = labels.pop()

        # Pick the record with highest confidence for the primary
        primary = max(group, key=lambda g: (g.get('confidence') or 0))

        sources = sorted({g['source'] for g in group})
        wrong_models = sorted({g['wrong_model'] for g in group})
        max_conf = max((g.get('confidence') or 0) for g in group)
        error_types = sorted({g['error_type'] for g in group})

        # Tier assignment
        if max_conf >= 80:
            tier = 'high_conf_wrong'
        elif len(wrong_models) >= 2:
            tier = 'shared_miss'
        else:
            tier = 'mid_conf_wrong'

        merged.append({
            'hash': k,
            'text': primary['text'],
            'label': label,
            'label_name': 'SCAM' if label == 1 else 'LEGIT',
            'tier': tier,
            'sources': sources,
            'wrong_models': wrong_models,
            'max_confidence_wrong': max_conf,
            'error_types': error_types,
            'category_hint': primary.get('category'),
        })
    return merged


def main():
    items = []
    items += mine_external_json(f'{BASE}/outputs/eval/v1.4_candidate_external.json', 'v1.4_external')
    items += mine_external_json(f'{BASE}/outputs/eval/v1.5_candidate_external.json', 'v1.5_external')
    items += mine_external_json(f'{BASE}/outputs/eval/v1.6_candidate_external.json', 'v1.6_external')
    items += mine_comparison(f'{BASE}/tests/comparison_results.json')

    print(f'Raw error rows collected: {len(items)}')
    merged = merge_by_hash(items)
    print(f'After hash-dedup + label-consistency filter: {len(merged)}')

    # Save
    out_path = os.path.join(OUT_DIR, 'errors.jsonl')
    with open(out_path, 'w') as f:
        for m in merged:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')

    # Breakdown by tier + label
    from collections import Counter
    print(f'\nBy tier: {Counter(m["tier"] for m in merged)}')
    print(f'By label: {Counter(m["label_name"] for m in merged)}')
    print(f'By source combo: {Counter(tuple(m["sources"]) for m in merged).most_common(6)}')

    # Save a summary sidecar
    summary = {
        'total': len(merged),
        'by_tier': dict(Counter(m['tier'] for m in merged)),
        'by_label': dict(Counter(m['label_name'] for m in merged)),
        'by_source_combo': {'/'.join(k): v for k, v in Counter(tuple(m['sources']) for m in merged).items()},
    }
    json.dump(summary, open(os.path.join(OUT_DIR, 'errors_summary.json'), 'w'), indent=2)
    print(f'\nWrote {out_path} + errors_summary.json')


if __name__ == '__main__':
    main()
