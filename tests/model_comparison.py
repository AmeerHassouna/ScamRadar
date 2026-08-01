"""
Head-to-head A/B: original model (git 11866bb, running on localhost:8000)
vs v1.3 (deployed at scamradar-api-l2vv.onrender.com) across 180 messages
in 8 categories.

Emits tests/comparison_results.json (raw per-message verdicts + confidences
for both models) which feeds tests/analyze_comparison.py for the win-map
report.

Notes:
- Local API has no rate limit (self-hosted). Deployed API is on Render's
  free tier so we sleep 0.3s between requests to stay polite.
- Both APIs reject non-English text with HTTP 400 — corpus is authored
  English-only to avoid this.
- Timeout is deliberately generous on the deployed API for cold-start
  and per-message tail latency.
"""
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error

import certifi

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSL_CTX = ssl.create_default_context(cafile=certifi.where())
CORPUS_PATH = os.path.join(BASE, 'tests', 'comparison_corpus.json')
OUT_PATH = os.path.join(BASE, 'tests', 'comparison_results.json')

LOCAL_URL = 'http://127.0.0.1:8000/predict'
DEPLOYED_URL = 'https://scamradar-api-l2vv.onrender.com/predict'

# Both endpoints rate-limit /predict at 20/minute → 3s between calls each.
# We serialize local then deployed → sleep 3.2s per full round-trip pair
# to stay just under the local limit; deployed is behind a Render LB whose
# per-client keying is more permissive, so it rarely 429s.
LOCAL_SLEEP_S = 3.2
DEPLOYED_SLEEP_S = 0.3


def call_predict(url, text, timeout, max_retries=6):
    """POST to /predict with retry-on-429 (rate limit). Sleeps ~4s per retry
    (limit is 20/min, so waiting 4s clears one slot in the token bucket)."""
    body = json.dumps({'text': text}).encode('utf-8')
    req = urllib.request.Request(
        url, data=body, method='POST',
        headers={'Content-Type': 'application/json'}
    )
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return {
                    'ok': True,
                    'verdict': data.get('verdict'),
                    'confidence': data.get('confidence'),
                    'scam_type': data.get('scam_type'),
                    'threshold_used': data.get('threshold_used'),
                    'http': resp.status,
                }
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                # honour Retry-After if present, else 4s (limit resets every 60s / 20 = 3s + buffer)
                retry_after = e.headers.get('Retry-After')
                sleep_s = float(retry_after) if retry_after else 4.0
                time.sleep(sleep_s)
                continue
            try:
                payload = json.loads(e.read().decode('utf-8'))
            except Exception:
                payload = None
            return {'ok': False, 'http': e.code, 'error': str(e), 'payload': payload}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
                continue
            return {'ok': False, 'error': str(e)}
    return {'ok': False, 'error': 'max_retries_exhausted'}


def main():
    corpus = json.load(open(CORPUS_PATH))
    msgs = corpus['messages']
    print(f'Loaded {len(msgs)} messages')

    # Warmup deployed API in case Render container is cold
    print('Warming up deployed API...', flush=True)
    warm = call_predict(DEPLOYED_URL, 'Hello, this is a test message.', timeout=120)
    print(f'  deployed warmup: {warm}')

    print('Warming up local API...', flush=True)
    warm_local = call_predict(LOCAL_URL, 'Hello, this is a test message.', timeout=30)
    print(f'  local warmup: {warm_local}')

    results = []
    t0 = time.time()
    for i, m in enumerate(msgs, 1):
        local = call_predict(LOCAL_URL, m['text'], timeout=30)
        time.sleep(DEPLOYED_SLEEP_S)
        deployed = call_predict(DEPLOYED_URL, m['text'], timeout=90)
        time.sleep(LOCAL_SLEEP_S)
        rec = {
            'id': m['id'],
            'category': m['category'],
            'ground_truth': m['ground_truth'],
            'text': m['text'],
            'local': local,
            'deployed': deployed,
        }
        results.append(rec)

        # brief progress
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed else 0
        eta = (len(msgs) - i) / rate if rate else 0
        marker_l = local.get('verdict', '?') if local.get('ok') else f"ERR{local.get('http','')}"
        marker_d = deployed.get('verdict', '?') if deployed.get('ok') else f"ERR{deployed.get('http','')}"
        if i % 10 == 0 or i <= 3:
            print(f'  [{i:3d}/{len(msgs)}] cat={m["category"]:20s} gt={m["ground_truth"]:5s} '
                  f'L={marker_l:12s} D={marker_d:12s}  ({rate:.1f} msg/s, ETA {eta:.0f}s)',
                  flush=True)
        # checkpoint every 20 results so a crash doesn't lose everything
        if i % 20 == 0:
            with open(OUT_PATH, 'w') as f:
                json.dump({
                    'meta': {
                        'local_url': LOCAL_URL, 'deployed_url': DEPLOYED_URL,
                        'n_messages': i, 'partial': True,
                        'duration_s': round(time.time() - t0, 1),
                    },
                    'results': results,
                }, f, indent=2, ensure_ascii=False)

    with open(OUT_PATH, 'w') as f:
        json.dump({
            'meta': {
                'local_url': LOCAL_URL,
                'deployed_url': DEPLOYED_URL,
                'n_messages': len(results),
                'duration_s': round(time.time() - t0, 1),
            },
            'results': results,
        }, f, indent=2, ensure_ascii=False)

    print(f'\nWrote {OUT_PATH}  ({len(results)} rows, {time.time()-t0:.1f}s)')


if __name__ == '__main__':
    main()
