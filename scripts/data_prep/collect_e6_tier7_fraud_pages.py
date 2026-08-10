"""
E6 Tier 7 collector — bank/brand anti-fraud education pages.

Uses WebFetch-equivalent (urllib) against a curated list of public
fraud-education URLs from major services. Extracts the "here's what our
real email looks like" samples they publish.

Yield is low per page (~1-5 items each) but authenticity is very high —
these are the actual services publishing their own real communications.
"""
import os, re, json, ssl, urllib.request, hashlib
from datetime import datetime
from html.parser import HTMLParser

import certifi

BASE = '/Users/ameer/Downloads/ScamRadar'
OUT = f'{BASE}/data/raw/e6/tier7_fraud_pages/items/tier7.jsonl'
os.makedirs(os.path.dirname(OUT), exist_ok=True)

SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# Curated URLs of anti-fraud education pages. Each publishes real example
# transactional emails alongside phishing warnings.
URLS = [
    ('paypal',    'https://www.paypal.com/us/security/suspicious-email',   'security_alert'),
    ('paypal',    'https://www.paypal.com/us/webapps/mpp/security/report-fraud', 'security_alert'),
    ('amazon',    'https://www.amazon.com/gp/help/customer/display.html?nodeId=201909120', 'order_confirmation'),
    ('microsoft', 'https://learn.microsoft.com/en-us/microsoft-365/security/office-365-security/report-junk-email-messages-to-microsoft', 'security_alert'),
    ('google',    'https://support.google.com/mail/answer/8253',            'security_alert'),
    ('apple',     'https://support.apple.com/en-us/102568',                'security_alert'),
    ('irs',       'https://www.irs.gov/newsroom/tax-scams-consumer-alerts', 'government'),
    ('hmrc',      'https://www.gov.uk/government/publications/genuine-hmrc-contact-and-recognising-phishing-emails', 'government'),
    ('actionfraud','https://www.actionfraud.police.uk/a-z-of-fraud/phishing', 'government'),
    ('usps',      'https://www.uspis.gov/news/scam-article/smishing-package-tracking-text-scams', 'shipping'),
    ('fedex',     'https://www.fedex.com/en-us/trust-center/report-fraud.html', 'shipping'),
    ('chase',     'https://www.chase.com/digital/resources/privacy-security/security/how-to-report-fraud', 'banking'),
]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script', 'nav', 'header', 'footer'):
            self.skip = True
    def handle_endtag(self, tag):
        if tag in ('style', 'script', 'nav', 'header', 'footer'):
            self.skip = False
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0 Safari/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=25, context=SSL_CTX) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return ''


def extract_examples(html: str) -> list[str]:
    """Look for blocks that resemble sample transactional email text:
    contains greeting + signature or subject line pattern, 60-2000 chars."""
    p = TextExtractor()
    try: p.feed(html)
    except Exception: return []
    text = ' '.join(p.parts)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 200: return []

    # Split at sentence boundaries and reassemble candidate 'email' blocks
    # by looking for greetings (Dear, Hi, Hello) that begin runs of text.
    candidates = []
    for m in re.finditer(r'\b(?:Dear|Hi|Hello|Good\s+(?:morning|afternoon|evening))\b[\s,]', text):
        start = m.start()
        # Take up to ~700 chars from that greeting
        chunk = text[start:start+800]
        # Trim at next 'Regards|Sincerely|Thanks|Thank you' phrase for a natural email boundary
        end_m = re.search(r'\b(?:Regards|Sincerely|Best\s+regards|Thanks,|Thank\s+you\.?\s+)', chunk[80:])
        if end_m:
            chunk = chunk[:80 + end_m.end() + 40]
        chunk = chunk.strip()
        if 60 <= len(chunk) <= 2000:
            candidates.append(chunk)
    return candidates


def main():
    seen = set(); kept = []
    for brand, url, category in URLS:
        print(f'  fetching {brand}: {url}')
        html = fetch(url)
        if not html:
            print(f'    fetch failed')
            continue
        examples = extract_examples(html)
        n_new = 0
        for text in examples:
            h = hashlib.sha1(text.lower().encode()).hexdigest()
            if h in seen: continue
            seen.add(h)
            kept.append({
                'text': text,
                'label': 0,
                'category': category,
                'platform': 'email',
                'source_name': f'tier7_fraud_page_{brand}',
                'source_url': url,
                'source_licence': 'public_educational_content',
                'source_commit': None,
                'acquired_at': datetime.utcnow().isoformat() + 'Z',
                'era': 'modern',
                'is_synthetic': False,
                'provenance_note': f'brand={brand}',
                'tier': 'tier7',
                'sample_id': h[:16],
            })
            n_new += 1
        print(f'    kept={n_new}')

    with open(OUT, 'w') as f:
        for it in kept:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print(f'\nWrote {OUT}  ({len(kept)} items)')


if __name__ == '__main__':
    main()
