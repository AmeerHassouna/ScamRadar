"""
Scrape modern Reddit data for Intervention 4 (v1.3 modern-data expansion).

Sources:
  * r/Scams              → scam-labeled items (label=1)
  * r/personalfinance    → legit financial discussion (label=0)
  * r/technology         → legit tech discussion (label=0)

Strict algorithmic filtering — no Claude / no manual judgment applied
to individual items. All keep/reject decisions are made by:
  * Subreddit source (determines label)
  * Reddit flair (for r/Scams: must be an explicit scam category)
  * Upvote score (for legit subreddits: ≥50)
  * Presence of a markdown code block or blockquote (for r/Scams:
    the extracted scam text must be clearly quoted, not just prose)
  * Text length (≥20 chars, ≤5000 chars)

Uses PRAW read-only OAuth (application-only client credentials) — no
Reddit password needed, only client_id + client_secret from a script-type
app registered at reddit.com/prefs/apps. Credentials read from .env.
"""
import os, sys, time, re, csv
from dotenv import load_dotenv
import praw

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR  = os.path.join(BASE_DIR, 'data', 'reddit_raw')
os.makedirs(OUT_DIR, exist_ok=True)

load_dotenv(os.path.join(BASE_DIR, '.env'))

_CLIENT_ID     = os.environ['REDDIT_CLIENT_ID']
_CLIENT_SECRET = os.environ['REDDIT_CLIENT_SECRET']
_USERNAME      = os.environ.get('REDDIT_USERNAME', 'anon')

reddit = praw.Reddit(
    client_id=_CLIENT_ID,
    client_secret=_CLIENT_SECRET,
    user_agent=f'ScamRadarThesis/1.0 by u/{_USERNAME} (academic research)',
    ratelimit_seconds=300,
)
reddit.read_only = True
print(f'PRAW initialised (read-only, u/{_USERNAME})')

# Scam-flair strings on r/Scams that indicate a real received scam.
SCAM_FLAIRS = {
    'sms', 'email', 'phone', 'phone call', 'cryptocurrency', 'crypto',
    'romance scam', 'romance', 'employment', 'job scam',
    'impersonation', 'wire fraud', 'investment', 'social media',
    'shopping', 'phishing', 'medical', 'ransomware', 'delivery',
    'gift card', 'tech support', 'irs', 'tax scam',
    # r/Scams uses shorter tags too
    'sim swap', 'venmo', 'zelle', 'paypal', 'apple', 'amazon',
    'bank', 'facebook', 'instagram', 'whatsapp', 'text', 'call',
    'malware', 'refund', 'lottery',
}

# ── Extraction helpers ─────────────────────────────────────────────────────

_CODE_BLOCK_RE = re.compile(r'```([^`]+?)```', re.DOTALL)
_CODE_BLOCK_ALT_RE = re.compile(r'`([^`\n]{20,})`')
_BLOCKQUOTE_RE = re.compile(r'(?:^|\n)((?:> +[^\n]*\n?){1,})', re.MULTILINE)


def extract_quoted_scam_text(selftext: str) -> str | None:
    """
    Extract the most-likely-scam-text region from an r/Scams post.
    Fully algorithmic — no judgment.
      1. Largest triple-backtick code block
      2. Else, largest blockquote region
      3. Else, longest inline `code` block ≥20 chars
      4. Else, None
    """
    if not selftext:
        return None

    fences = [b.strip() for b in _CODE_BLOCK_RE.findall(selftext)]
    fences = [f for f in fences if len(f) >= 20]
    if fences:
        return max(fences, key=len).strip()

    quotes = _BLOCKQUOTE_RE.findall(selftext)
    cleaned = []
    for q in quotes:
        lines = [re.sub(r'^> ?', '', ln) for ln in q.strip().split('\n')]
        text  = ' '.join(l for l in lines if l.strip())
        if len(text) >= 20:
            cleaned.append(text.strip())
    if cleaned:
        return max(cleaned, key=len).strip()

    inline = [c.strip() for c in _CODE_BLOCK_ALT_RE.findall(selftext) if len(c.strip()) >= 20]
    if inline:
        return max(inline, key=len).strip()

    return None


def clean_comment_body(body: str) -> str:
    """Strip Reddit markdown from comment; keep the substance."""
    if not body:
        return ''
    body = re.sub(r'^> ?[^\n]*\n?', '', body, flags=re.MULTILINE)   # drop blockquotes
    body = re.sub(r'\*\*?([^\*]+)\*\*?', r'\1', body)                # strip bold
    body = re.sub(r'_([^_]+)_', r'\1', body)                          # strip italic
    body = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', body)             # links → visible text
    body = re.sub(r'\s+', ' ', body).strip()
    return body


# ── Main workflows ─────────────────────────────────────────────────────────

def scrape_scams(target_kept: int = 800) -> list[dict]:
    """Pull top r/Scams posts across multiple time windows until we have enough kept items."""
    print(f'\n══ r/Scams ══')
    sub  = reddit.subreddit('Scams')
    seen = set()
    kept = []

    for source_name, listing in [
        ('top-year',  sub.top(time_filter='year',  limit=1000)),
        ('top-month', sub.top(time_filter='month', limit=1000)),
        ('top-all',   sub.top(time_filter='all',   limit=1000)),
    ]:
        print(f'  Scanning {source_name}…')
        try:
            for p in listing:
                if p.id in seen:
                    continue
                seen.add(p.id)
                flair = (p.link_flair_text or '').lower().strip()
                if not any(sf in flair for sf in SCAM_FLAIRS):
                    continue
                extracted = extract_quoted_scam_text(getattr(p, 'selftext', '') or '')
                if not extracted or not (20 <= len(extracted) <= 5000):
                    continue
                kept.append({
                    'item_id':     p.id,
                    'source':      'r/Scams',
                    'subreddit':   'Scams',
                    'permalink':   f'https://www.reddit.com{p.permalink}',
                    'created_utc': int(p.created_utc or 0),
                    'flair':       flair,
                    'score':       int(p.score or 0),
                    'raw_text':    extracted,
                    'label':       1,
                })
                if len(kept) >= target_kept:
                    break
        except Exception as e:
            print(f'    listing error on {source_name}: {e}')
        print(f'    kept so far: {len(kept):,}')
        if len(kept) >= target_kept:
            break
    return kept


def scrape_legit(subreddit_name: str, target_comments: int, post_limit: int = 400) -> list[dict]:
    """Fetch top posts of the year, then top comments per post. Score ≥50, length ≥100."""
    print(f'\n══ r/{subreddit_name} (legit) ══')
    sub  = reddit.subreddit(subreddit_name)
    kept = []
    seen = set()

    try:
        posts = list(sub.top(time_filter='year', limit=post_limit))
    except Exception as e:
        print(f'  listing error: {e}')
        return []
    print(f'  Fetched {len(posts):,} posts. Reading comments…')

    for i, p in enumerate(posts):
        if len(kept) >= target_comments:
            break
        if i and i % 20 == 0:
            print(f'    {i}/{len(posts)}  kept: {len(kept):,}')
        try:
            p.comments.replace_more(limit=0)   # skip "load more" placeholders
            top_level = [c for c in p.comments if hasattr(c, 'body')]
            top_level.sort(key=lambda c: -(c.score or 0))
            for c in top_level[:3]:
                if c.id in seen:
                    continue
                seen.add(c.id)
                if (c.score or 0) < 50:
                    continue
                body = clean_comment_body(c.body or '')
                if not (100 <= len(body) <= 5000):
                    continue
                kept.append({
                    'item_id':     c.id,
                    'source':      f'r/{subreddit_name}',
                    'subreddit':   subreddit_name,
                    'permalink':   f'https://www.reddit.com{c.permalink}',
                    'created_utc': int(c.created_utc or 0),
                    'flair':       '',
                    'score':       int(c.score or 0),
                    'raw_text':    body,
                    'label':       0,
                })
                if len(kept) >= target_comments:
                    break
        except Exception as e:
            print(f'    comment fetch error on post {p.id}: {e}')
            continue
    return kept


def write_csv(items: list[dict], filename: str) -> None:
    path = os.path.join(OUT_DIR, filename)
    if not items:
        print(f'  ⚠ nothing to write to {filename}')
        return
    fields = list(items[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for it in items:
            w.writerow(it)
    print(f'  ✅ Wrote {len(items):,} rows → {path}')


if __name__ == '__main__':
    t0 = time.time()

    scams = scrape_scams(target_kept=800)
    write_csv(scams, 'scams.csv')

    pf = scrape_legit('personalfinance', target_comments=450, post_limit=300)
    write_csv(pf, 'personalfinance.csv')

    tech = scrape_legit('technology', target_comments=200, post_limit=200)
    write_csv(tech, 'technology.csv')

    print(f'\n════ Summary ════')
    print(f'  r/Scams:           {len(scams):,}')
    print(f'  r/personalfinance: {len(pf):,}')
    print(f'  r/technology:      {len(tech):,}')
    print(f'  Wall time:         {(time.time()-t0)/60:.1f} min')
