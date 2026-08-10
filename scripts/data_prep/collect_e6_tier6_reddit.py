"""
E6 Tier 6 collector — Reddit community-shared authentic examples.

Uses PRAW with credentials in .env. Queries specific subreddits for posts
that quote real transactional messages users received. Extracts the quoted
message body, filters for authenticity + length, categorises, and writes
to data/raw/e6/tier6_reddit/items/tier6.jsonl.

Also collects LEGIT-side (transactional-service subreddits) AND SCAM-side
(r/Scams brand-impersonation posts) for the acceptance benchmark.
"""
import os, re, json, sys, time, hashlib
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv()
import praw

BASE = '/Users/ameer/Downloads/ScamRadar'
OUT_LEGIT = f'{BASE}/data/raw/e6/tier6_reddit/items/tier6_legit.jsonl'
OUT_SCAM  = f'{BASE}/data/raw/e6/tier6_reddit/items/tier6_scam_for_benchmark.jsonl'
os.makedirs(os.path.dirname(OUT_LEGIT), exist_ok=True)

reddit = praw.Reddit(
    client_id=os.environ['REDDIT_CLIENT_ID'],
    client_secret=os.environ['REDDIT_CLIENT_SECRET'],
    user_agent=f'ScamRadar-Research/2.0 by u/{os.environ.get("REDDIT_USERNAME","research")}',
)

# Regex helpers
CODEBLOCK   = re.compile(r'>\s?.+', re.MULTILINE)       # Reddit blockquotes
EMAIL_BOILER= re.compile(r'\b(?:from:|to:|subject:|dear|hi|hello|good\s+(?:morning|afternoon|evening)|thank\s+you)\b', re.I)
GREETING_HDR= re.compile(r'^\s*(?:hi|hello|dear|greetings|good\s+(?:morning|afternoon|evening))[\s,]', re.I | re.M)
SIGNATURE   = re.compile(r'\b(?:regards|sincerely|thanks|thank\s+you|the\s+.{2,30}\s+team|customer\s+support|from\s+the\s+.{2,30}\s+team)\b[\s,\.-]', re.I)

BAD_PROSE   = re.compile(r'\b(?:im wondering|does anyone know|any idea|has anyone|help me|please help|edit:|update:|update 2|tldr|tl;dr)\b', re.I)


def extract_quoted_email(text: str) -> str | None:
    """Given a Reddit post/comment body, extract the quoted email portion if
    it looks like an actual message the user received."""
    if not text: return None
    # 1. Look for blockquote-style paste (>) — Reddit's convention
    blocks = CODEBLOCK.findall(text)
    if blocks:
        quoted = '\n'.join(re.sub(r'^>\s?', '', b) for b in blocks).strip()
        if 40 <= len(quoted) <= 3000 and EMAIL_BOILER.search(quoted):
            return quoted
    # 2. Look for triple-fenced code blocks
    m = re.search(r'```([\s\S]{40,3000})```', text)
    if m and EMAIL_BOILER.search(m.group(1)):
        return m.group(1).strip()
    # 3. Look for "Subject:" as the first line pattern
    m = re.search(r'((?:Subject:|Dear|Hi\s|Hello\s|Good\s+(?:morning|afternoon|evening))[\s\S]{40,3000})', text)
    if m and SIGNATURE.search(m.group(1) or ''):
        return m.group(1).strip()
    return None


def looks_authentic(text: str) -> bool:
    """Heuristic: authentic transactional email, not user prose or bug-report chatter."""
    if len(text) < 40 or len(text) > 3000: return False
    if BAD_PROSE.search(text): return False  # user asking a question, not showing an email
    # Must have greeting or signature or subject-like structure
    if not (GREETING_HDR.search(text) or SIGNATURE.search(text) or 'Subject:' in text):
        # Fallback: has strong transactional indicators
        indicators = sum(bool(re.search(p, text, re.I)) for p in [
            r'\border\s*#|\btracking\b|\bverification\s*code\b|\btransaction\s*id\b',
            r'thank\s+you\s+for\s+your\s+(?:order|purchase|payment)',
            r'has\s+been\s+(?:delivered|dispatched|shipped)',
            r'\bwe\s+noticed\s+a\s+new\s+sign', r'unusual\s+(?:sign|login|activity)',
        ])
        if indicators < 1:
            return False
    return True


def normalize(text: str) -> str:
    text = re.sub(r'^\s*Subject:.*$', '', text, flags=re.M).strip()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


LEGIT_QUERIES = [
    # (subreddit, query, category)
    ('personalfinance', 'chase alert transaction OR "debit card purchase"', 'banking'),
    ('personalfinance', 'chase deposit OR "direct deposit"', 'banking'),
    ('personalfinance', '"credit card statement"', 'banking'),
    ('personalfinance', 'monzo notification', 'banking'),
    ('AmazonPrime', '"your order" OR "order confirmation"', 'order_confirmation'),
    ('amazon', '"order confirmation"', 'order_confirmation'),
    ('amazon', '"has shipped" OR "has been delivered"', 'shipping'),
    ('UPS', 'notification', 'shipping'),
    ('USPS', 'tracking notification', 'shipping'),
    ('FedEx', 'tracking notification', 'shipping'),
    ('paypal', 'notification receipt', 'payment_receipt'),
    ('stripe', 'receipt', 'payment_receipt'),
    ('sysadmin', '"password reset" email', 'password_reset'),
    ('webdev', '"transactional email"', 'general_transactional'),
    ('EmailMarketing', 'transactional example', 'general_transactional'),
    ('androidapps', 'notification code verification', 'otp'),
    ('techsupport', 'verification code text OR sms', 'otp'),
    ('AppleHelp', '"apple id" sign in notification', 'security_alert'),
    ('gsuite', 'new sign-in google account', 'security_alert'),
]

SCAM_QUERIES = [
    ('Scams', 'amazon phishing text OR "example of scam"', 'brand_amazon_phishing'),
    ('Scams', 'paypal phishing email', 'brand_paypal_phishing'),
    ('Scams', 'microsoft phishing email', 'brand_ms_phishing'),
    ('Scams', 'google credential phishing', 'brand_google_phishing'),
    ('Scams', 'apple id phishing', 'brand_apple_phishing'),
    ('Scams', 'usps delivery smishing OR "usps text scam"', 'brand_shipping_phishing'),
    ('Scams', 'dhl scam text', 'brand_shipping_phishing'),
    ('Scams', 'chase phishing OR "bank of america phishing"', 'brand_bank_phishing'),
    ('phishing', 'sample phishing email', 'brand_generic_phishing'),
]


def collect(queries, out_path, label, limit_per_query=50):
    seen_hashes = set()
    kept = []
    for sub, query, category in queries:
        print(f'  r/{sub}  "{query}"  category={category}', flush=True)
        try:
            results = reddit.subreddit(sub).search(query, sort='relevance', time_filter='all',
                                                    limit=limit_per_query)
            n_page = 0; n_kept_here = 0
            for submission in results:
                n_page += 1
                # Try selftext then top comments
                candidates = []
                if getattr(submission, 'selftext', None):
                    candidates.append(submission.selftext)
                try:
                    submission.comments.replace_more(limit=0)
                    for c in submission.comments.list()[:15]:
                        if getattr(c, 'body', None):
                            candidates.append(c.body)
                except Exception:
                    pass

                for candidate in candidates:
                    extracted = extract_quoted_email(candidate)
                    if not extracted: continue
                    text = normalize(extracted)
                    if not looks_authentic(text): continue
                    h = hashlib.sha1(text.lower().encode()).hexdigest()
                    if h in seen_hashes: continue
                    seen_hashes.add(h)
                    kept.append({
                        'text': text,
                        'label': label,
                        'category': category,
                        'platform': 'email' if 'email' in query.lower() or 'phishing email' in query.lower() else 'sms' if 'sms' in query.lower() or 'text' in query.lower() else 'email',
                        'source_name': f'reddit_r_{sub}',
                        'source_url': f'https://www.reddit.com{submission.permalink}',
                        'source_licence': 'reddit_user_content_public',
                        'source_commit': None,
                        'acquired_at': datetime.utcnow().isoformat() + 'Z',
                        'era': 'modern',
                        'is_synthetic': False,
                        'provenance_note': f'query={query}',
                        'tier': 'tier6',
                        'sample_id': h[:16],
                    })
                    n_kept_here += 1
                if n_kept_here >= 30: break
            print(f'    seen={n_page}  kept={n_kept_here}', flush=True)
            time.sleep(1.0)  # polite pacing
        except Exception as e:
            print(f'    ERROR: {e}', flush=True)
            time.sleep(2.0)

    with open(out_path, 'w') as f:
        for it in kept:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print(f'\nWrote {out_path}  ({len(kept)} items)')
    return kept


if __name__ == '__main__':
    print('=== Collecting LEGIT transactional examples ===')
    legit = collect(LEGIT_QUERIES, OUT_LEGIT, label=0)
    print()
    print('=== Collecting SCAM brand-impersonation examples (for acceptance benchmark) ===')
    scam = collect(SCAM_QUERIES, OUT_SCAM, label=1)
    print()
    print(f'Totals — legit: {len(legit)}   scam (for benchmark): {len(scam)}')
