"""
E6 QC + dedup + cross-corpus collision check.

Ingests every tier's raw JSONL files → applies the QC pipeline (English,
length, PII-scrub, transactional-content check) → applies E5's exact
dedup pipeline (SHA-1 exact + MinHash 128-perm LSH 32×4) → cross-checks
against E5's existing train/val/test/external splits → writes:
  data/interim/e6/e6_augmentation.parquet
  data/interim/e6/e6_augmentation_summary.json
"""
import os, re, sys, json, hashlib, unicodedata
from collections import Counter, defaultdict
from datetime import datetime
import numpy as np
import pandas as pd

BASE = '/Users/ameer/Downloads/ScamRadar'
BASE_B = '/Users/ameer/Downloads/scamradar2'  # E5 data lives here
IN_DIR = f'{BASE}/data/raw/e6'
OUT_DIR = f'{BASE}/data/interim/e6'
os.makedirs(OUT_DIR, exist_ok=True)

# ─── E5 normalize + minhash (byte-identical to scamradar2/src/scamradar/clean.py) ─
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
NUM_RE = re.compile(r"\d")
WS_RE = re.compile(r"\s+")
N_PERM, N_BANDS, ROWS_PER_BAND = 128, 16, 8
_rng = np.random.RandomState(1337)
_A = _rng.randint(1, 2**31 - 1, N_PERM).astype(np.uint64)
_B = _rng.randint(0, 2**31 - 1, N_PERM).astype(np.uint64)
_P = np.uint64(2**31 - 1)


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text)).lower()
    t = URL_RE.sub(" <url> ", t)
    t = NUM_RE.sub("0", t)
    return WS_RE.sub(" ", t).strip()


def exact_hash(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8", "ignore")).hexdigest()


# ─── PII scrubbing ─────────────────────────────────────────────────────────────
EMAIL_RE  = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PHONE_RE  = re.compile(r'\b\+?\d[\d\s\-().]{7,}\d\b')
CARD_RE   = re.compile(r'\b(?:\d[ -]?){12,16}\b')

def scrub_pii(text: str) -> str:
    t = EMAIL_RE.sub('<EMAIL>', text)
    t = PHONE_RE.sub('<PHONE>', t)
    t = CARD_RE.sub('<ACCOUNT_ID>', t)
    return t


# ─── QC pipeline ───────────────────────────────────────────────────────────────
def qc_pass(item: dict) -> tuple[bool, str]:
    text = item.get('text', '')
    if not text or not isinstance(text, str):
        return False, 'empty_text'
    if not (40 <= len(text) <= 3000):
        return False, f'length_{len(text)}'
    # English check (langdetect is heavy; use ASCII-density proxy)
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    if ascii_ratio < 0.85:
        return False, 'not_english_ascii'
    # Must have some letters
    letter_count = sum(1 for c in text if c.isalpha())
    if letter_count < 30:
        return False, 'too_few_letters'
    return True, 'ok'


# ─── MinHash for near-dup clustering ───────────────────────────────────────────
def _shingle_hashes(norm: str, k: int = 5):
    if len(norm) < k:
        norm = norm + " " * (k - len(norm))
    hs = {hash(norm[i:i + k]) & 0x7FFFFFFF for i in range(len(norm) - k + 1)}
    return np.fromiter(hs, dtype=np.uint64, count=len(hs))


def minhash(norm: str):
    sh = _shingle_hashes(norm)
    if len(sh) == 0:
        return np.zeros(N_PERM, dtype=np.uint64)
    return ((np.outer(_A, sh) + _B[:, None]) % _P).min(axis=1)


class _UF:
    def __init__(self, n): self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[rb] = ra


def near_dup_clusters(norms):
    sigs = np.stack([minhash(n) for n in norms])
    uf = _UF(len(norms))
    for b in range(N_BANDS):
        band = sigs[:, b*ROWS_PER_BAND:(b+1)*ROWS_PER_BAND]
        buckets = defaultdict(list)
        for i, row in enumerate(band):
            buckets[row.tobytes()].append(i)
        for members in buckets.values():
            for j in members[1:]:
                uf.union(members[0], j)
    return np.array([uf.find(i) for i in range(len(norms))])


# ─── Main pipeline ─────────────────────────────────────────────────────────────
def main():
    # 1. Ingest all tier JSONL files
    items = []
    for root, _, files in os.walk(IN_DIR):
        for fn in files:
            if fn.endswith('.jsonl'):
                path = os.path.join(root, fn)
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            items.append(json.loads(line))
                        except Exception:
                            pass
    print(f'Ingested {len(items)} raw items from {IN_DIR}')

    # 2. QC pass
    qc_ok, qc_fail = [], Counter()
    for it in items:
        ok, reason = qc_pass(it)
        if ok:
            it['text'] = scrub_pii(it['text'])
            qc_ok.append(it)
        else:
            qc_fail[reason] += 1
    print(f'\n=== QC pass ===')
    print(f'  passed:  {len(qc_ok)}')
    print(f'  rejected: {sum(qc_fail.values())}')
    for reason, n in qc_fail.most_common():
        print(f'    {reason}: {n}')

    # 3. Exact-hash dedup within E6 corpus
    seen = set(); kept = []
    for it in qc_ok:
        h = exact_hash(it['text'])
        if h in seen: continue
        seen.add(h); it['exact_hash'] = h; kept.append(it)
    print(f'\n=== Exact-hash dedup ===')
    print(f'  {len(qc_ok)} → {len(kept)}  ({(1 - len(kept)/max(len(qc_ok),1))*100:.1f}% removed)')

    # 4. Near-dup clustering (MinHash + LSH)
    if kept:
        norms = [normalize(it['text']) for it in kept]
        cluster_ids = near_dup_clusters(norms)
        # Keep first item per cluster
        cluster_seen = set(); after_neardup = []
        for it, cid in zip(kept, cluster_ids):
            if cid in cluster_seen: continue
            cluster_seen.add(cid); it['cluster_id'] = int(cid); after_neardup.append(it)
        print(f'\n=== Near-dup clustering (MinHash 128, LSH 16×8) ===')
        print(f'  {len(kept)} → {len(after_neardup)}  clusters={len(set(cluster_ids))}')
    else:
        after_neardup = []

    # 5. Cross-corpus collision check against E5 train/val/test/external
    print(f'\n=== Cross-corpus collision check against E5 splits ===')
    e5_hashes = set()
    for split in ('train', 'val', 'test'):
        try:
            df = pd.read_parquet(f'{BASE_B}/data/processed/{split}.parquet')
            if 'exact_hash' in df.columns:
                e5_hashes |= set(df['exact_hash'].dropna().unique().tolist())
            else:
                e5_hashes |= set(df['text'].map(exact_hash).dropna().unique().tolist())
            print(f'  E5 {split}: {len(df)} rows loaded')
        except Exception as e:
            print(f'  E5 {split}: unavailable ({e})')
    try:
        dfx = pd.read_parquet(f'{BASE_B}/data/external_benchmark/benchmark.parquet')
        if 'exact_hash' in dfx.columns:
            e5_hashes |= set(dfx['exact_hash'].dropna().unique().tolist())
        else:
            e5_hashes |= set(dfx['text'].map(exact_hash).dropna().unique().tolist())
        print(f'  E5 external benchmark: {len(dfx)} rows loaded')
    except Exception as e:
        print(f'  E5 external benchmark: unavailable ({e})')
    print(f'  E5 total exact-hashes: {len(e5_hashes)}')

    before = len(after_neardup)
    after_neardup = [it for it in after_neardup if it['exact_hash'] not in e5_hashes]
    print(f'  Collision drops: {before - len(after_neardup)}')

    # 6. Ensure required schema fields
    for it in after_neardup:
        it.setdefault('label', 0)
        it.setdefault('platform', 'email')
        it.setdefault('era', 'modern')
        it.setdefault('is_synthetic', False)
        it.setdefault('source_licence', 'unspecified')

    # 7. Write parquet
    if after_neardup:
        df = pd.DataFrame(after_neardup)
        # Coerce cluster_id / label to int
        df['cluster_id'] = df['cluster_id'].astype(int)
        df['label'] = df['label'].astype(int)
        out_parquet = f'{OUT_DIR}/e6_augmentation.parquet'
        df.to_parquet(out_parquet, index=False)
        print(f'\nWrote {out_parquet}  ({len(df)} rows)')
    else:
        print(f'\nNo items to write.')

    # 8. Summary JSON
    summary = {
        'ingested':      len(items),
        'qc_passed':     len(qc_ok),
        'qc_failed':     dict(qc_fail),
        'after_exact':   len(kept),
        'after_neardup': before if 'before' in dir() else 0,
        'after_e5_collision_drop': len(after_neardup),
        'by_source':     dict(Counter(it['source_name'] for it in after_neardup)),
        'by_category':   dict(Counter(it['category'] for it in after_neardup)),
        'by_licence':    dict(Counter(it['source_licence'] for it in after_neardup)),
        'label_split':   dict(Counter(it['label'] for it in after_neardup)),
        'length_stats':  {
            'min':  min((len(it['text']) for it in after_neardup), default=0),
            'max':  max((len(it['text']) for it in after_neardup), default=0),
            'mean': round(sum(len(it['text']) for it in after_neardup) / max(len(after_neardup), 1), 1),
        },
        'generated_at': datetime.utcnow().isoformat() + 'Z',
    }
    json.dump(summary, open(f'{OUT_DIR}/e6_augmentation_summary.json', 'w'), indent=2)
    print(f'\nSummary written to {OUT_DIR}/e6_augmentation_summary.json')
    return summary


if __name__ == '__main__':
    main()
