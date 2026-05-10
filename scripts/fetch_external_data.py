"""
ScamRadar+ | Fetch external phishing/scam URL data.

Sources:
  - OpenPhish  (free tier): https://openphish.com/feed.txt
  - PhishTank  (free):      https://data.phishtank.com/data/online-valid.csv.gz

Each phishing URL is wrapped in a realistic lure message and inserted into
the DB as label=1, channel=url so the model learns real-world phishing URL
patterns beyond its existing PhishTank subset.

Usage:
    python scripts/fetch_external_data.py [--phishtank-key YOUR_KEY]

PhishTank key is optional — omit it and the script skips PhishTank.
Register for a free key at https://www.phishtank.com/register.php
"""

import argparse
import gzip
import io
import random
import re
import sqlite3
import sys
import os
import time
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db 4.db')

SOURCE_NAME = 'external_phishing_feeds'
CHANNEL_URL = 4  # channel_id for 'url' in the DB

# Lure templates — wrap a bare URL in realistic delivery text so the model
# sees it in context rather than as a naked URL.
_LURE_TEMPLATES = [
    "Click here to verify your account: {url}",
    "Your account has been suspended. Restore access: {url}",
    "Confirm your identity to continue: {url}",
    "Your payment failed. Update your details: {url}",
    "You have a pending package. Pay the fee: {url}",
    "Action required: sign in to secure your account: {url}",
    "Your subscription is expiring. Renew now: {url}",
    "We noticed unusual activity. Verify here: {url}",
    "Complete your verification: {url}",
    "Your account will be closed unless you act: {url}",
    "Log in to resolve your account issue: {url}",
    "Important security update required: {url}",
    "Claim your reward here: {url}",
    "One last step to receive your prize: {url}",
]

_URL_RE = re.compile(r'^https?://', re.IGNORECASE)


def _wrap_url(url: str) -> str:
    return random.choice(_LURE_TEMPLATES).format(url=url)


def fetch_openphish(limit: int = 2000) -> list[str]:
    """Return up to `limit` phishing URLs from the OpenPhish free feed."""
    print("Fetching OpenPhish free feed...")
    try:
        r = requests.get('https://openphish.com/feed.txt', timeout=30,
                         headers={'User-Agent': 'ScamRadar-Research/1.0'})
        r.raise_for_status()
        urls = [ln.strip() for ln in r.text.splitlines()
                if ln.strip() and _URL_RE.match(ln.strip())]
        print(f"  OpenPhish: {len(urls)} URLs fetched")
        return urls[:limit]
    except Exception as exc:
        print(f"  OpenPhish fetch failed: {exc}")
        return []


def fetch_phishtank(api_key: str, limit: int = 5000) -> list[str]:
    """Return up to `limit` phishing URLs from PhishTank online-valid CSV."""
    print("Fetching PhishTank online-valid feed...")
    url = f'https://data.phishtank.com/data/{api_key}/online-valid.csv.gz'
    try:
        r = requests.get(url, timeout=60,
                         headers={'User-Agent': 'ScamRadar-Research/1.0'})
        r.raise_for_status()
        with gzip.open(io.BytesIO(r.content), 'rt', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        # CSV columns: phish_id,url,phish_detail_url,submission_time,...
        urls = []
        for line in lines[1:]:  # skip header
            parts = line.split(',')
            if len(parts) >= 2 and _URL_RE.match(parts[1].strip()):
                urls.append(parts[1].strip())
        print(f"  PhishTank: {len(urls)} URLs fetched")
        return urls[:limit]
    except Exception as exc:
        print(f"  PhishTank fetch failed: {exc}")
        return []


def _compute_basic_features(text: str) -> dict:
    words = text.split()
    urls = re.findall(r'https?://\S+', text)
    urgency_words = ['urgent', 'immediately', 'asap', 'expire', 'suspended',
                     'verify', 'confirm', 'act now']
    urgency = sum(1 for w in urgency_words if w in text.lower())
    return {
        'text_length': len(text),
        'word_count': len(words),
        'has_url': int(bool(urls)),
        'url_count': len(urls),
        'exclamation_count': text.count('!'),
        'uppercase_ratio': round(sum(1 for c in text if c.isupper()) / max(len(text), 1), 4),
        'digit_ratio': round(sum(1 for c in text if c.isdigit()) / max(len(text), 1), 4),
        'urgency_score': urgency,
    }


def ingest(conn: sqlite3.Connection, messages: list[str], label: int, source_id: int):
    c = conn.cursor()
    max_id = c.execute('SELECT MAX(message_id) FROM Message').fetchone()[0] or 0
    inserted = 0
    for text in messages:
        text = text.strip()
        if not text or len(text) < 20:
            continue
        # Deduplicate against existing messages
        exists = c.execute('SELECT 1 FROM Message WHERE raw_text=?', (text,)).fetchone()
        if exists:
            continue
        max_id += 1
        c.execute(
            'INSERT INTO Message (message_id, source_id, channel_id, raw_text, label) VALUES (?,?,?,?,?)',
            (max_id, source_id, CHANNEL_URL, text, label),
        )
        f = _compute_basic_features(text)
        c.execute(
            'INSERT INTO MessageFeatures VALUES (?,?,?,?,?,?,?,?,?)',
            (max_id, f['text_length'], f['word_count'], f['has_url'], f['url_count'],
             f['exclamation_count'], f['uppercase_ratio'], f['digit_ratio'], f['urgency_score']),
        )
        inserted += 1
    conn.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phishtank-key', default='', help='PhishTank API key (optional)')
    parser.add_argument('--openphish-limit', type=int, default=2000)
    parser.add_argument('--phishtank-limit', type=int, default=5000)
    args = parser.parse_args()

    random.seed(42)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure source row exists
    c.execute('SELECT source_id FROM DataSource WHERE name=?', (SOURCE_NAME,))
    row = c.fetchone()
    if row:
        source_id = row[0]
    else:
        c.execute('INSERT INTO DataSource (name) VALUES (?)', (SOURCE_NAME,))
        source_id = c.lastrowid
        conn.commit()
    print(f"Source '{SOURCE_NAME}' id={source_id}")

    total_inserted = 0

    # OpenPhish
    op_urls = fetch_openphish(args.openphish_limit)
    if op_urls:
        messages = [_wrap_url(u) for u in op_urls]
        n = ingest(conn, messages, label=1, source_id=source_id)
        print(f"  Inserted {n} OpenPhish messages")
        total_inserted += n

    # PhishTank (optional)
    if args.phishtank_key:
        pt_urls = fetch_phishtank(args.phishtank_key, args.phishtank_limit)
        if pt_urls:
            messages = [_wrap_url(u) for u in pt_urls]
            n = ingest(conn, messages, label=1, source_id=source_id)
            print(f"  Inserted {n} PhishTank messages")
            total_inserted += n
    else:
        print("  PhishTank skipped (no --phishtank-key provided)")

    conn.close()
    print(f"\nDone. Total inserted: {total_inserted}")
    print("Run `python main.py` to retrain the model with the new data.")


if __name__ == '__main__':
    main()
