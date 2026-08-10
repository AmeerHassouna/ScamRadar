"""
E6 Tier 2 collector — permissively-licensed transactional email template libraries.

Reads pre-cloned repos in /tmp/e6_repos/ and extracts real production-grade
transactional email templates. Writes items to
    data/raw/e6/tier2_templates/items/tier2.jsonl
with full provenance.

Each item: {text, category, source_name, source_url, source_licence,
            source_commit, acquired_at, era, platform, provenance_note}.
"""
import json, os, re, hashlib, subprocess, sys
from html.parser import HTMLParser
from datetime import datetime

BASE = '/Users/ameer/Downloads/ScamRadar'
REPOS = '/tmp/e6_repos'
OUT = f'{BASE}/data/raw/e6/tier2_templates/items/tier2.jsonl'
os.makedirs(os.path.dirname(OUT), exist_ok=True)

REPOS_META = {
    'mailgen':            {'url': 'https://github.com/eladnava/mailgen', 'licence': 'MIT'},
    'postmark-templates': {'url': 'https://github.com/wildbit/postmark-templates', 'licence': 'MIT'},
    'mjml':               {'url': 'https://github.com/mjmlio/mjml', 'licence': 'MIT'},
    'email-templates':    {'url': 'https://github.com/sendgrid/email-templates', 'licence': 'MIT'},
    'django':             {'url': 'https://github.com/django/django', 'licence': 'BSD-3-Clause'},
    'framework':          {'url': 'https://github.com/laravel/framework', 'licence': 'MIT'},
    'Ghost':              {'url': 'https://github.com/TryGhost/Ghost', 'licence': 'MIT'},
}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script', 'head'):
            self.skip = True
    def handle_endtag(self, tag):
        if tag in ('style', 'script', 'head'):
            self.skip = False
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        return ''
    txt = ' '.join(p.parts)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def strip_template_placeholders(text: str) -> str:
    """Remove obvious template variables so tokens don't leak into feature
    space. Leaves the natural-language template content intact."""
    text = re.sub(r'\{\{[^}]{0,200}\}\}', ' <VAR> ', text)  # Handlebars/Mustache
    text = re.sub(r'\{%[^%]{0,300}%\}', ' ', text)          # Django/Jinja
    text = re.sub(r'\$\{[^}]{0,200}\}', ' <VAR> ', text)    # ES6 template literals
    text = re.sub(r'@\w+\s*\(.*?\)', ' ', text, flags=re.DOTALL)  # Blade @if @section etc — best-effort
    text = re.sub(r'@?\{\{[^}]{0,200}\}\}', ' <VAR> ', text)
    text = re.sub(r'\{[^}]{2,100}\}', ' <VAR> ', text)      # generic braces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def infer_category(path: str) -> tuple[str, str]:
    p = path.lower()
    tests = [
        ('otp',                  ['otp', 'verif', 'signin-verify', 'two.?factor', '2fa', 'mfa', 'auth.?code']),
        ('order_confirmation',   ['order', 'purchase.*confirm', 'checkout']),
        ('shipping',             ['ship', 'delivery', 'tracking', 'dispatched']),
        ('receipt',              ['receipt', 'invoice', 'paid', 'billing']),
        ('password_reset',       ['password', 'reset', 'recover']),
        ('security_alert',       ['security', 'sign.?in', 'login', 'new.?device']),
        ('subscription_renewal', ['subscription', 'renew', 'trial', 'plan']),
        ('welcome',              ['welcome', 'onboard', 'invitation', 'invite', 'signup', 'sign.?up']),
        ('newsletter',           ['newsletter', 'digest', 'news.?feed']),
        ('notification',         ['notif', 'comment', 'mention', 'reply', 'activity']),
        ('gift_purchase',        ['gift', 'purchase.*gift']),
    ]
    for cat, pats in tests:
        if any(re.search(pat, p) for pat in pats):
            return cat, path
    return 'general_transactional', path


def get_git_commit(repo_path: str) -> str:
    try:
        return subprocess.check_output(['git', '-C', repo_path, 'rev-parse', 'HEAD'],
                                        text=True).strip()[:12]
    except Exception:
        return 'unknown'


def process_file(path: str, repo: str, commit: str) -> dict | None:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()
    except Exception:
        return None

    fn = os.path.basename(path).lower()
    is_html = fn.endswith(('.html', '.hbs', '.handlebars', '.blade.php', '.ejs', '.mjml'))
    if is_html:
        text = html_to_text(raw)
    else:
        text = raw

    text = strip_template_placeholders(text)

    # Filter: length + minimum content
    if not (40 <= len(text) <= 3000):
        return None
    # Filter: must have some prose (letters), not just markup residue
    if len(re.findall(r'[a-zA-Z]', text)) < 30:
        return None
    # Filter: skip if the file is obviously documentation (README, CONTRIBUTING)
    if any(k in fn for k in ('readme', 'contribut', 'license', 'code_of_conduct', 'usage', 'changelog', 'security.md')):
        return None
    # Filter: skip technical docs with lots of code fences
    if raw.count('```') > 4 or text.count('function ') > 3:
        return None

    category, provenance = infer_category(path)
    rel_path = path.split(REPOS + '/', 1)[-1]
    meta = REPOS_META.get(repo, {})
    return {
        'text': text,
        'label': 0,
        'category': category,
        'platform': 'email',
        'source_name': f'tier2_template_{repo}',
        'source_url': f"{meta.get('url','?')}/blob/{commit}/{'/'.join(rel_path.split('/')[1:])}" if commit != 'unknown' else meta.get('url', '?'),
        'source_licence': meta.get('licence', 'unknown'),
        'source_commit': commit,
        'acquired_at': datetime.utcnow().isoformat() + 'Z',
        'era': 'modern',
        'is_synthetic': False,
        'provenance_note': f'file={rel_path}',
    }


def walk_repo(repo_name: str, wanted_exts: tuple[str, ...],
              include_patterns: tuple[str, ...] | None = None,
              exclude_patterns: tuple[str, ...] = ('node_modules', 'dist/', 'build/',
                                                     '.git/', 'test/', 'tests/',
                                                     '__pycache__', 'coverage/',
                                                     'benchmark', 'legal/', 'meta/')):
    repo_path = f'{REPOS}/{repo_name}'
    commit = get_git_commit(repo_path)
    results = []
    for root, dirs, files in os.walk(repo_path):
        # prune excluded dirs
        dirs[:] = [d for d in dirs if not any(x in os.path.join(root, d) for x in exclude_patterns)]
        for fn in files:
            if not fn.lower().endswith(wanted_exts):
                continue
            path = os.path.join(root, fn)
            if include_patterns and not any(pat in path.lower() for pat in include_patterns):
                continue
            item = process_file(path, repo_name, commit)
            if item:
                results.append(item)
    return results


def main():
    all_items = []
    # Mailgen: theme index files
    all_items += walk_repo('mailgen', ('.html', '.txt'), include_patterns=('themes/',))
    # Postmark: content.html/txt in templates/
    all_items += walk_repo('postmark-templates', ('.html', '.txt'),
                            include_patterns=('templates/', 'templates-inlined/'))
    # MJML: docs/*.md + any templates
    all_items += walk_repo('mjml', ('.md', '.mjml'),
                            include_patterns=('template', 'example'))
    # SendGrid: paste-templates + merriweather-templates + dynamic-templates
    all_items += walk_repo('email-templates', ('.html', '.txt'),
                            include_patterns=('templates/',))
    # Django: registration templates for password_reset
    all_items += walk_repo('django', ('.html', '.txt'),
                            include_patterns=('registration/password_reset', 'templates/emails/'))
    # Laravel: Notifications resources/views/email + Mail resources
    all_items += walk_repo('framework', ('.blade.php',),
                            include_patterns=('resources/views/',))
    # Ghost: email-templates + member-welcome + gifts
    all_items += walk_repo('Ghost', ('.hbs', '.html'),
                            include_patterns=('email-templates/', 'welcome', 'gift'))

    # dedup within tier by exact text
    seen = set(); unique = []
    for it in all_items:
        h = hashlib.sha1(it['text'].encode()).hexdigest()
        if h in seen: continue
        seen.add(h); it['tier'] = 'tier2'; it['sample_id'] = h[:16]; unique.append(it)

    print(f'Tier 2 total (pre-QC, unique-in-tier): {len(unique)}')
    from collections import Counter
    print('By source:',   dict(Counter(it['source_name']  for it in unique)))
    print('By category:', dict(Counter(it['category']     for it in unique)))
    print('Lengths — min:', min((len(it['text']) for it in unique), default=0),
          '  max:', max((len(it['text']) for it in unique), default=0),
          '  median:', sorted(len(it['text']) for it in unique)[len(unique)//2] if unique else 0)

    with open(OUT, 'w') as f:
        for it in unique:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print(f'\nWrote: {OUT}  ({len(unique)} items)')


if __name__ == '__main__':
    main()
