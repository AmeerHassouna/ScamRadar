"""
Extract two held-out evaluation slices from the existing baseline corpus for
v1.7 improvement measurement:

  1. enron_hard_legit.jsonl     — 263 Enron ham messages containing any
                                  scam-adjacent signal ($ amounts, urgent,
                                  verify, deadline, account, etc). Used
                                  post-training to measure whether v1.7
                                  false-positive rate on real business
                                  emails improves vs 11866bb / v1.3.

  2. spamassassin_hard_legit.jsonl — 62 SpamAssassin ham messages with
                                     same filter.

These are NOT added to v1.7 training — they are already in the baseline
db 4.db and would collapse via SHA-1 dedup. Extracting them separately
lets us score the retrained model on the exact real-business slice
where over-firing hurt the user's experience.

Provenance: both source corpora are public and already present in the
baseline database (enron, spamassassin). No external download needed.
"""
import sqlite3
import re
import json
import hashlib
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(BASE, 'data', 'v1.7_augmentation', 'real_world')
os.makedirs(OUT_DIR, exist_ok=True)

HARD_LEGIT_PAT = re.compile(
    r'\$\s*[0-9]|\burgent|\bverif|\bconfirm|\bdeadline|\bdue\s+(?:by|on|next)|'
    r'\baccount|\binvoice|\bpayment|\bpassword|\blogin|\brefund|\bwire\s+transfer|'
    r'\bpurchase\s+order|\bapproval|\bimmediate|\bASAP|\battention',
    re.I
)


def norm_hash(t):
    return hashlib.sha1(re.sub(r'\s+', ' ', (t or '').strip().lower()).encode()).hexdigest()


def extract(conn, source_name, out_path, tag):
    rows = conn.execute(
        '''SELECT m.message_id, m.raw_text FROM Message m
           JOIN DataSource ds ON m.source_id=ds.source_id
           WHERE ds.name=? AND m.label=0''',
        (source_name,)
    ).fetchall()

    seen_hashes = set()
    kept = []
    for mid, text in rows:
        text = text or ''
        if not (40 <= len(text) <= 2500):
            continue
        if not HARD_LEGIT_PAT.search(text):
            continue
        h = norm_hash(text)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        kept.append({
            'baseline_message_id': mid,
            'hash': h,
            'text': text,
            'label': 0,
            'label_name': 'LEGIT',
            'category': f'{tag}_hard_legit',
            'source': f'{source_name} (baseline db 4.db, hard-slice extract)',
            'role': 'held_out_eval_only',
        })

    with open(out_path, 'w') as f:
        for k in kept:
            f.write(json.dumps(k, ensure_ascii=False) + '\n')
    print(f'  {source_name}: extracted {len(kept)} → {out_path}')
    return len(kept)


def main():
    conn = sqlite3.connect(os.path.join(BASE, 'data', 'db 4.db'))
    total = 0
    total += extract(conn, 'enron',
                     os.path.join(OUT_DIR, 'enron_hard_legit.jsonl'),
                     tag='business')
    total += extract(conn, 'spamassassin',
                     os.path.join(OUT_DIR, 'spamassassin_hard_legit.jsonl'),
                     tag='business')
    conn.close()

    provenance = {
        'purpose': 'Held-out evaluation slice for v1.7 improvement measurement',
        'training_use': 'NONE — these items are already in the baseline db 4.db and would collapse via SHA-1 dedup if added to training. Extracted separately for evaluation only.',
        'evaluation_use': 'Score 11866bb, v1.3, and v1.7 on this slice to measure false-positive rate on real business emails containing scam-adjacent language (dollar amounts, urgent, verify, account, etc).',
        'sources': [
            {
                'name': 'enron_hard_legit',
                'origin': 'Enron corpus (CALO project public release, 2004)',
                'license': 'Public research corpus, no license restrictions',
                'baseline_presence': 'Present in data/db 4.db as source_id=enron, label=0',
                'kaggle_involvement': 'None',
            },
            {
                'name': 'spamassassin_hard_legit',
                'origin': 'SpamAssassin public corpus (Apache Software Foundation, 2002-2003 archive)',
                'license': 'Apache License (public research)',
                'baseline_presence': 'Present in data/db 4.db as source_id=spamassassin, label=0',
                'kaggle_involvement': 'None',
            },
        ],
        'filter': 'Regex: dollar-amount OR one of {urgent, verify, confirm, deadline, account, invoice, payment, password, login, refund, wire transfer, purchase order, approval, immediate, ASAP, attention}',
        'length_bounds': '40 to 2500 characters (post-filter)',
        'total_extracted': total,
    }
    with open(os.path.join(OUT_DIR, 'PROVENANCE.json'), 'w') as f:
        json.dump(provenance, f, indent=2)

    print(f'\nTotal held-out hard-legit eval slice: {total}')
    print(f'PROVENANCE.json written.')


if __name__ == '__main__':
    main()
