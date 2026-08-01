"""
Prepare external phishing data for Intervention 4 (v1.3 External Real-World Phishing Data Expansion).

Renamed from "Modern Data Expansion" — the available evidence no longer supports the
"modern" claim (see docs/intervention_4_decisions.md for the full data-source rationale).

Pipeline:
  1. Load zefang-liu/phishing-email-dataset (Phishing subset only, 7,328 items).
  2. Algorithmic filter:
       - langdetect == 'en'
       - length 100–2000 chars
       - keep only items with normal capitalisation (has at least one uppercase letter
         AND not fully uppercase) — filters out lowercase-tokenized preprocessing style
       - drop duplicates within the source
  3. Load the 650 already-scraped Reddit legit items from data/reddit_raw/.
  4. SHA-1 overlap check against every existing training/test row in db 4.db
     using the same normalise_text() as src/_00_dedup.py. Drop any hash matches.
  5. Split into:
       - data/external_training/*.csv  → items added to v1.3's training set
       - data/external_evaluation/*.csv → reserved for rung-3 evaluation only
  6. Verify zero cluster_id overlap between training additions and external eval.

No Claude judgment applied to individual items. Every decision (keep/drop, split
assignment) is deterministic from the input + a fixed random seed.
"""
import os, sys, csv, hashlib, random
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src._00_dedup import normalise_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAIN_OUT = os.path.join(BASE_DIR, 'data', 'external_training')
EVAL_OUT  = os.path.join(BASE_DIR, 'data', 'external_evaluation')
DB_PATH   = os.path.join(BASE_DIR, 'data', 'db 4.db')
REDDIT_DIR = os.path.join(BASE_DIR, 'data', 'reddit_raw')

os.makedirs(TRAIN_OUT, exist_ok=True)
os.makedirs(EVAL_OUT,  exist_ok=True)

SEED = 42
TARGET_TRAIN_SCAM = 800
TARGET_EVAL_SCAM  = 250
random.seed(SEED)


def _sha1_norm(text: str) -> str:
    return hashlib.sha1(normalise_text(text).encode('utf-8')).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Load existing training corpus for overlap check
# ══════════════════════════════════════════════════════════════════════════════
print("STEP 1: Load existing corpus for overlap verification")
import sqlite3
conn = sqlite3.connect(DB_PATH)
existing = pd.read_sql_query("SELECT raw_text FROM Message", conn)
conn.close()
existing['hash'] = existing['raw_text'].fillna('').apply(_sha1_norm)
existing_hashes = set(existing['hash'].tolist())
print(f"  Existing corpus: {len(existing):,} rows, {len(existing_hashes):,} unique clusters")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Load + filter zefang-liu phishing dataset
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2: Load + algorithmically filter zefang-liu/phishing-email-dataset")
from datasets import load_dataset
from langdetect import detect, DetectorFactory, LangDetectException
DetectorFactory.seed = SEED

ds = load_dataset('zefang-liu/phishing-email-dataset', split='train')
phishing_raw = [r for r in ds if r['Email Type'] == 'Phishing Email']
print(f"  Phishing-labelled items: {len(phishing_raw):,}")

kept_scam = []
stats = {'total': len(phishing_raw), 'empty': 0, 'wrong_length': 0,
         'wrong_case': 0, 'not_english': 0, 'kept': 0}

for r in phishing_raw:
    text = (r['Email Text'] or '').strip()
    if not text:
        stats['empty'] += 1; continue
    if not (100 <= len(text) <= 2000):
        stats['wrong_length'] += 1; continue
    # Case check: at least one uppercase AND not fully uppercase → normal-cap style
    has_upper = any(c.isupper() for c in text)
    fully_upper = text.isupper()
    if not has_upper or fully_upper:
        stats['wrong_case'] += 1; continue
    try:
        if detect(text) != 'en':
            stats['not_english'] += 1; continue
    except LangDetectException:
        stats['not_english'] += 1; continue
    kept_scam.append({
        'source':   'zefang_liu_phishing',
        'raw_text': text,
        'label':    1,
    })
    stats['kept'] += 1

print(f"  Filter results (of {stats['total']:,} phishing items):")
for k, v in stats.items():
    print(f"    {k:<15} {v:>6,}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Load 650 Reddit legit items (already scraped)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3: Load pre-scraped Reddit legit items")
kept_legit = []
for fn in ['personalfinance.csv', 'technology.csv']:
    path = os.path.join(REDDIT_DIR, fn)
    if not os.path.exists(path):
        print(f"  ⚠ missing {path}"); continue
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        kept_legit.append({
            'source':   r['source'],
            'raw_text': r['raw_text'],
            'label':    0,
        })
    print(f"  {fn}: +{len(rows):,}")
print(f"  Total legit: {len(kept_legit):,}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: SHA-1 overlap check against existing corpus (both classes)
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 4: SHA-1 overlap verification vs existing training/test corpus")

def dedup_and_overlap_check(items: list[dict], class_label: str) -> list[dict]:
    seen_in_batch = set()
    overlap_hits, batch_dupes, survivors = 0, 0, []
    for it in items:
        h = _sha1_norm(it['raw_text'])
        it['hash'] = h
        if h in existing_hashes:
            overlap_hits += 1; continue
        if h in seen_in_batch:
            batch_dupes += 1; continue
        seen_in_batch.add(h)
        survivors.append(it)
    print(f"  {class_label:<10}  raw={len(items):>5,}  overlap_with_existing={overlap_hits:>3}  "
          f"within_batch_dupes={batch_dupes:>3}  survivors={len(survivors):>5,}")
    return survivors

kept_scam  = dedup_and_overlap_check(kept_scam,  'scam')
kept_legit = dedup_and_overlap_check(kept_legit, 'legit')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Random shuffle + split into training / external eval
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5: Split into training additions vs external evaluation")

random.shuffle(kept_scam)
random.shuffle(kept_legit)

# Scams: TARGET_TRAIN_SCAM for training, TARGET_EVAL_SCAM reserved
n_train_scam = min(TARGET_TRAIN_SCAM, max(0, len(kept_scam) - TARGET_EVAL_SCAM))
n_eval_scam  = min(TARGET_EVAL_SCAM,  len(kept_scam) - n_train_scam)
train_scam = kept_scam[:n_train_scam]
eval_scam  = kept_scam[n_train_scam:n_train_scam + n_eval_scam]

# Legit: split roughly proportionally — keep ~500 for training, remainder for eval
n_train_legit = min(500, max(0, len(kept_legit) - 100))
n_eval_legit  = min(150, len(kept_legit) - n_train_legit)
train_legit = kept_legit[:n_train_legit]
eval_legit  = kept_legit[n_train_legit:n_train_legit + n_eval_legit]

train_all = train_scam + train_legit
eval_all  = eval_scam  + eval_legit
random.shuffle(train_all)
random.shuffle(eval_all)

print(f"  Training additions: {len(train_all):>4,}  ({n_train_scam} scam + {n_train_legit} legit)")
print(f"  External eval:      {len(eval_all):>4,}  ({n_eval_scam} scam + {n_eval_legit} legit)")

# Verify zero overlap between training and eval
train_hashes = {it['hash'] for it in train_all}
eval_hashes  = {it['hash'] for it in eval_all}
overlap = train_hashes & eval_hashes
assert not overlap, f"Overlap between training and eval: {len(overlap)} clusters"
print(f"  ✅ Zero cluster overlap between training and eval (verified)")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Write CSVs
# ══════════════════════════════════════════════════════════════════════════════
print("\nSTEP 6: Write CSVs")

def write_csv(items, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['source', 'raw_text', 'label', 'hash'],
                           quoting=csv.QUOTE_ALL)
        w.writeheader()
        for it in items:
            w.writerow(it)
    print(f"  Wrote {len(items):>5,} → {path}")

write_csv(train_all, os.path.join(TRAIN_OUT, 'external_train.csv'))
write_csv(eval_all,  os.path.join(EVAL_OUT,  'external_eval.csv'))

print("\n✅ Done.")
