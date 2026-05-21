"""
ScamRadar+ | Step 02: Feature Engineering  (v5)
Improved tone detection (phrase-level + negation), 9 new features,
full adversarial preprocessing pipeline.
"""

import re
import unicodedata
import string
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import BRAND_NAMES, ACTION_WORDS, SCAM_PHRASES, URL_SHORTENERS
from urllib.parse import urlparse


# ══════════════════════════════════════════════════════════════════════════
#  ADVERSARIAL PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════

# Common scam-relevant emoji → text mappings
_EMOJI_MAP = {
    '🎁': ' gift ', '🚨': ' alert ', '⚠️': ' warning ', '💰': ' money ',
    '🏆': ' trophy ', '🎉': ' prize ', '💵': ' cash ', '🔐': ' secure ',
    '⏰': ' urgent ', '📧': ' email ', '🎊': ' prize ', '💳': ' card ',
    '🔒': ' locked ', '✅': ' verified ', '❌': ' error ', '🆓': ' free ',
    '💎': ' diamond ', '🌟': ' star ', '🎰': ' lottery ', '📱': ' phone ',
    '🏦': ' bank ', '💸': ' money ', '🎯': ' target ', '🔑': ' key ',
}

_HTML_TAG_RE    = re.compile(r'<[^>]+>')
_MULTI_SPACE_RE = re.compile(r'\s+')
_URL_SHORTENER_RE = re.compile(
    r'https?://(?:' + '|'.join(re.escape(s) for s in URL_SHORTENERS) + r')/\S*',
    re.IGNORECASE,
)


def preprocess_text(text: str) -> str:
    """Full adversarial preprocessing pipeline."""
    if not isinstance(text, str):
        return ''
    # 1. Unicode normalisation (NFKC catches lookalike chars, e.g. а→a)
    text = unicodedata.normalize('NFKC', text)
    # 2. Replace emojis with text tokens
    for emoji, token in _EMOJI_MAP.items():
        text = text.replace(emoji, token)
    # 3. Strip HTML tags
    text = _HTML_TAG_RE.sub(' ', text)
    # 4. Mark URL shorteners before URL extraction
    text = _URL_SHORTENER_RE.sub(' SHORTURL ', text)
    # 5. Collapse extra whitespace
    text = _MULTI_SPACE_RE.sub(' ', text).strip()
    return text


# ══════════════════════════════════════════════════════════════════════════
#  L33T NORMALISATION
# ══════════════════════════════════════════════════════════════════════════

_LEET_MAP = {
    '0': 'o', '1': 'i', '3': 'e', '4': 'a',
    '5': 's', '6': 'g', '7': 't', '8': 'b',
    '@': 'a', '$': 's',
    # '+' intentionally omitted — maps to 't' in leet but breaks percentage
    # patterns like "20%+" which are common in investment scam messages
}


def normalize_leet(text: str) -> str:
    if not isinstance(text, str):
        return text
    return ''.join(_LEET_MAP.get(c, c) for c in text.lower())


# ══════════════════════════════════════════════════════════════════════════
#  IMPROVED TONE DETECTION  (phrase-level + negation)
# ══════════════════════════════════════════════════════════════════════════

_NEGATION_WORDS = frozenset({
    'not', 'no', "don't", "doesn't", "didn't", "isn't", "aren't",
    "wasn't", "weren't", "never", "neither", "nor", "nothing", "none",
    "cannot", "can't", "won't", "wouldn't", "shouldn't", "couldn't",
})

# Phrase patterns: more specific than single words to reduce false positives.
# Each list entry is a compiled regex or a plain substring (strings are
# matched as whole-word patterns).

_URGENCY_PATTERNS = [
    r'\bact now\b', r'\blimited time\b', r'\bexpires (today|soon|midnight)\b',
    r'\blast chance\b', r'\bfinal notice\b', r'\brespond (now|immediately|asap)\b',
    r'\bdeadline\b', r'\basap\b', r'\bright away\b', r'\bimmediately\b',
    r'\bdo not (wait|delay|ignore)\b', r'\burgent(ly)?\b',
    r'\bhurry\b', r'\btime( is)? running out\b', r'\btoday only\b',
]

_FEAR_PATTERNS = [
    r'\b(account|card|access).{0,25}(suspended|blocked|locked|compromised)\b',
    r'\bsuspicious (activity|login|access|transaction)\b',
    r'\bverify your (account|identity|information|card|details)\b',
    r'\bunauthorized (access|login|transaction|charge)\b',
    r'\bsecurity (alert|warning|breach|notice)\b',
    r'\byour (account|card) (will be|has been) (suspended|blocked|locked|closed)\b',
    r'\bcompromised\b',
    r'\bunusual (sign-in|activity|login|access)\b',
    r'\bfailed (login|attempt|payment)\b',
]

_REWARD_PATTERNS = [
    r'\byou (have won|are a winner|have been selected|have been chosen)\b',
    r'\b(claim|collect) your (prize|reward|gift|winnings|bonus)\b',
    r'\bfree (gift card|gift|iphone|ipad|vacation|cruise|cash|money|trial offer)\b',
    r'\bcongratulations.{0,40}(won|winner|selected|prize|chosen)\b',
    r'\b\$[\d,]+ (gift card|reward|cash prize|voucher)\b',
    r'\blucky (winner|draw|number|ticket)\b',
    r'\byou have been (selected|chosen|awarded)\b',
    r'\bclaim your (free|prize|reward|gift)\b',
    # Investment / crypto scam patterns
    r'\b(put in|invest).{0,35}(got back|get back|return|double|triple)\b',
    r'\$[\d,]+.{0,15}\b(guaranteed|promise)\b',
    r'\bguaranteed? (returns?|profits?|income|gain|money|result)\b',
    r'\b(profits?|returns?|income|gain|earning)s? (daily|weekly|monthly)\b',
    r'\b(turned?|made|flipped)\s*\$[\d,]+.{0,30}into\s+\$[\d,]+\b',
    r'\$[\d,]+\s+into\s+\$[\d,]+\s+in\s+\d+\s+(day|week|month)s?\b',
    r'\b(make|earn|making|earning)\s+\$[\d,]+\s+(a|per)\s+(week|month|day)\b',
    r'\bguarantees?\s+\d+\s*%\s+(monthly|weekly|daily|annual)\s+returns?\b',
    r'\b\d+\s*%\S?\s+(guaranteed\s+)?(monthly|weekly|daily|annual)\s+returns?\b',
    r'\bguaranteed?\s+(weekly|daily|monthly|annual)\s+returns?\b',
    r'\bguaranteed?\s+\d+x\s*(returns?|profit|gain|roi)\b',
    r'\b(ai|bot|algorithm).{0,30}(trading bot|does.{0,10}trading|handles.{0,10}trading)\b',
]

_THREAT_PATTERNS = [
    r'\blegal action\b', r'\bwill be arrested\b',
    r'\b(criminal|civil) (charge|lawsuit|case|proceeding)\b',
    r'\bdebt collector\b', r'\bcourt (order|hearing|summons|date)\b',
    r'\bprosecuted\b', r'\bwarrant (for your arrest|issued)\b',
    r'\bpenalty (fee|charge|fine)\b', r'\bfined\b',
    r'\btax (lien|warrant|penalty|fraud)\b',
]

_COMPILED = {
    'urgency': [re.compile(p, re.IGNORECASE) for p in _URGENCY_PATTERNS],
    'fear':    [re.compile(p, re.IGNORECASE) for p in _FEAR_PATTERNS],
    'reward':  [re.compile(p, re.IGNORECASE) for p in _REWARD_PATTERNS],
    'threat':  [re.compile(p, re.IGNORECASE) for p in _THREAT_PATTERNS],
}


def _is_negated(text: str, match_start: int, window: int = 40) -> bool:
    """Return True if the match is preceded by a negation word within `window` chars."""
    preceding = text[max(0, match_start - window): match_start]
    words = preceding.lower().split()[-6:]
    return any(w in _NEGATION_WORDS for w in words)


def compute_tone_features(text: str):
    """
    Phrase-level tone scoring with negation handling.
    Returns (urgency, fear, reward, threat) integer scores.
    """
    if not isinstance(text, str):
        text = ''
    scores = {}
    for tone, patterns in _COMPILED.items():
        count = 0
        for pat in patterns:
            for m in pat.finditer(text):
                if not _is_negated(text, m.start()):
                    count += 1
        scores[tone] = count
    return scores['urgency'], scores['fear'], scores['reward'], scores['threat']


# ══════════════════════════════════════════════════════════════════════════
#  LOOKALIKE DOMAIN DETECTION
# ══════════════════════════════════════════════════════════════════════════

# Brands whose name appearing in a non-official domain signals impersonation
_LOOKALIKE_BRANDS = frozenset({
    'apple', 'google', 'microsoft', 'amazon', 'paypal', 'netflix',
    'facebook', 'instagram', 'whatsapp', 'samsung', 'adobe', 'dropbox', 'linkedin',
})

# Action verbs / nouns that phishing / scam sites embed in their hostnames
_LOOKALIKE_ACTIONS = frozenset({
    'verify', 'unlock', 'login', 'signin', 'secure', 'confirm',
    'validate', 'authenticate', 'portal', 'apply', 'activate',
    'restore', 'update', 'claim',
    # Extended set — recovery/refund/approval scam domains
    'recovery', 'refund', 'approval', 'renewal', 'dispute',
})

# Canonical parent domains for each brand.
# Subdomains of these are always legitimate (e.g. myaccount.google.com).
_REAL_BRAND_DOMAINS: dict = {
    'apple':     {'apple.com', 'icloud.com'},
    'google':    {'google.com'},
    'microsoft': {'microsoft.com', 'live.com'},
    'amazon':    {'amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.co.jp'},
    'paypal':    {'paypal.com'},
    'netflix':   {'netflix.com'},
    'facebook':  {'facebook.com', 'fb.com'},
    'instagram': {'instagram.com'},
    'whatsapp':  {'whatsapp.com', 'wa.me'},
    'samsung':   {'samsung.com'},
    'adobe':     {'adobe.com'},
    'dropbox':   {'dropbox.com'},
    'linkedin':  {'linkedin.com'},
    'github':    {'github.com', 'githubusercontent.com'},
    'binance':   {'binance.com'},
    'zoom':      {'zoom.us'},
    'spotify':   {'spotify.com'},
    'twitter':   {'twitter.com', 'x.com'},
    'tiktok':    {'tiktok.com'},
    'ebay':      {'ebay.com'},
}


def detect_lookalike_domain(url: str) -> bool:
    """
    Return True if the URL's hostname looks like phishing:
      • A trusted brand name appears in the hostname but the domain is NOT
        one of the brand's real domains (e.g. apple-id-verify.com).
      • A credential-harvesting action word is embedded in the hostname
        (e.g. hrverify-staffing.com, yvc-student-portal.net).
    """
    url_lower = url.lower()
    try:
        parsed = urlparse(url_lower if url_lower.startswith('http') else 'https://' + url_lower)
        hostname = (parsed.netloc or parsed.path.split('/')[0]).split(':')[0]
        if hostname.startswith('www.'):
            hostname = hostname[4:]
    except Exception:
        hostname = url_lower

    # Brand impersonation: brand name in hostname but not the real domain
    for brand, real_domains in _REAL_BRAND_DOMAINS.items():
        if brand in hostname:
            is_real = (hostname in real_domains or
                       any(hostname.endswith('.' + rd) for rd in real_domains))
            if not is_real:
                return True   # e.g. apple-id-verify.com, netflix-billing-update.net

    # Action word in hostname (credential-harvesting structure)
    action_hits = sum(1 for a in _LOOKALIKE_ACTIONS if a in hostname)
    if action_hits >= 1:
        return True           # e.g. hrverify-staffing.com, yvc-student-portal.net

    return False


# ══════════════════════════════════════════════════════════════════════════
#  URL FEATURES  (unchanged API, same return signature)
# ══════════════════════════════════════════════════════════════════════════

_URL_P1 = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
_URL_P2 = re.compile(
    r'(?<!@)\b(?:[a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(?:com|org|net|gov|edu|io|co\.uk|ac\.il)'
    r'(?:/[^\s]*)?\b',
    re.IGNORECASE,
)


def extract_urls(text: str) -> list:
    """
    Extract URLs from text — catches both explicit http(s):// links and
    bare domain mentions (e.g. bankofamerica.com/security).
    Bare domains are normalised to https:// before returning.
    """
    if not isinstance(text, str):
        return []

    found_p1 = _URL_P1.findall(text)
    found_p2 = _URL_P2.findall(text)

    # Build final list: start with explicit URLs, then add bare domains
    # that are not already a substring of an explicit URL.
    p1_joined = ' '.join(found_p1)
    all_urls  = list(found_p1)
    for bare in found_p2:
        if bare not in p1_joined:               # avoid duplicating http://x.com → x.com
            normalised = bare if bare.startswith('http') else ('https://' + bare)
            all_urls.append(normalised)

    # Deduplicate preserving order
    seen, result = set(), []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def compute_url_features(text: str):
    if not isinstance(text, str):
        text = ''
    # Extract hostname-only for TLD check
    hostnames = re.findall(r'https?://(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})', text)
    # Extract full URL strings (scheme + host + path) for keyword check
    full_urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    # Also capture bare domains with paths for keyword scanning
    bare_urls = re.findall(
        r'\b(?:[a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+'
        r'\.(?:com|org|net|gov|edu|io|co\.uk|ac\.il)(?:/[^\s]*)?\b',
        text, re.IGNORECASE,
    )
    all_url_strings = full_urls + bare_urls

    suspicious_tlds = ['.xyz', '.top', '.club', '.online', '.site',
                       '.info', '.biz', '.tk', '.ml', '.ga', '.cf', '.pw']
    suspicious_kws  = ['login', 'verify', 'secure', 'account', 'update',
                       'confirm', 'banking', 'paypal', 'amazon', 'apple',
                       'microsoft', 'support', 'signin', 'validate',
                       'unlock', 'restore', 'reactivate', 'suspended', 'blocked',
                       'portal', 'credential', 'webmail', 'apply', 'staffing',
                       # Extended set
                       'recovery', 'refund', 'renewal', 'forgiveness', 'warranty',
                       'approval', 'relief', 'claim', 'dispute']
    ip_pattern = r'https?://\d{1,3}(?:\.\d{1,3}){3}'

    has_tld = int(any(any(u.lower().endswith(t) for t in suspicious_tlds) for u in hostnames))
    # Scan full URL string (domain + path) so keywords in subdomain/domain also fire
    has_kw  = int(any(any(k in u.lower() for k in suspicious_kws) for u in all_url_strings))
    has_ip  = int(bool(re.search(ip_pattern, text)))
    return has_tld, has_kw, has_ip


# ══════════════════════════════════════════════════════════════════════════
#  NEW ENGINEERED FEATURES
# ══════════════════════════════════════════════════════════════════════════

def _count_syllables(word: str) -> int:
    """Rough syllable count for Flesch-Kincaid."""
    word = word.lower().strip(string.punctuation)
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?<=[aeiou])e$', '', word)
    return max(1, len(re.findall(r'[aeiou]+', word)))


def compute_readability(text: str) -> float:
    """Flesch Reading Ease (higher = easier to read; scam messages tend lower)."""
    if not isinstance(text, str) or not text.strip():
        return 0.0
    sentences = max(1, len(re.split(r'[.!?]+', text)))
    words = text.split()
    if not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    score = 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))
    return round(max(0.0, min(100.0, score)), 2)


LEGIT_PHRASES = [
    'if this was you', 'if this was not you', 'you can ignore this',
    'no action is needed', 'no action required', 'no action needed',
    'this is an automated message', 'do not reply to this email',
    'sent from a no-reply address', 'you recently signed in',
    'new device detected', 'we noticed a sign-in',
    # OTP / verification code phrases
    'do not share this code', 'will never call you to verify',
    'one-time password', 'one-time code', 'one-time pin',
    'if you did not request this code', 'enter this code',
    'your verification code', 'your security code', 'your confirmation code',
    'your whatsapp code', 'your google code', 'your apple id code',
    'expires in', 'this code expires',
    # Messaging / group invite phrases
    'has added you to the group', 'tap the link to join',
    'automated notification from whatsapp', 'automated notification from telegram',
    'you have been invited to join',
    # Appointment / reminder phrases
    'dentist appointment', 'doctor appointment', 'appointment is scheduled',
    'please call to reschedule', 'appointment reminder', 'to reschedule if needed',
    'your appointment', 'scheduled for', 'call to reschedule',
    # Shipping / order confirmation
    'has shipped', 'your order has shipped', 'estimated delivery',
    'tracking number', 'order is confirmed', 'booking is confirmed',
    # Health / pharmacy
    'ready for pickup', 'prescription is ready', 'is ready for pickup',
    # Birthday / casual
    'happy birthday', 'wishing you all the best',
    # Bill / utility
    'amount due', 'view and pay', 'bill for',
    # Medication reminder
    'reminder to take your medication', 'take your medication',
    # Security — "if this was you" combos are already in LEGIT_PHRASES but
    # security alert phrasing needs explicit entries
    'if this was not you', 'no action needed', 'no action is needed',
]


def compute_new_features(text: str) -> dict:
    """
    Compute 10 engineered features for a single message (9 original + legit_phrase_score).
    Returns a dict with keys matching NUMERICAL_FEATURES_V5 additions.
    """
    if not isinstance(text, str):
        text = ''

    words = text.split()
    text_lower = text.lower()

    # avg_word_length
    avg_word_len = (sum(len(w.strip(string.punctuation)) for w in words) / len(words)
                   if words else 0.0)

    # capitalized_word_count — fully UPPER words of length >= 2
    cap_count = sum(1 for w in words if w.isupper() and len(w) >= 2)

    # scam_phrase_score — exact phrase matches (case-insensitive)
    phrase_score = sum(1 for p in SCAM_PHRASES if p in text_lower)

    # sender_impersonation_score — brand + action word co-occurrence
    has_brand  = any(b in text_lower for b in BRAND_NAMES)
    has_action = any(a in text_lower for a in ACTION_WORDS)
    impersonation = int(has_brand and has_action)

    # Lookalike domain detection — adds 2 when a URL's hostname impersonates
    # a brand or contains a credential-harvesting action word.
    # Capped at 3 so the feature stays interpretable and doesn't dominate scaling.
    for _u in extract_urls(text):
        if detect_lookalike_domain(_u):
            impersonation = min(impersonation + 2, 3)
            break

    # punctuation_density
    punct_density = (sum(1 for c in text if c in string.punctuation) / len(text)
                    if text else 0.0)

    # question_mark_count
    q_count = text.count('?')

    # currency_symbol_count
    currency_count = sum(text.count(s) for s in ['$', '€', '£', '¥'])

    # readability_score
    readability = compute_readability(text)

    # unique_word_ratio
    if words:
        unique_ratio = len(set(w.lower().strip(string.punctuation) for w in words)) / len(words)
    else:
        unique_ratio = 0.0

    # legit_phrase_score — security / automated-message phrases that indicate legitimacy
    legit_score = sum(1 for p in LEGIT_PHRASES if p in text_lower)

    return {
        'avg_word_length':            round(avg_word_len, 4),
        'capitalized_word_count':     cap_count,
        'scam_phrase_score':          phrase_score,
        'sender_impersonation_score': impersonation,
        'punctuation_density':        round(punct_density, 4),
        'question_mark_count':        q_count,
        'currency_symbol_count':      currency_count,
        'readability_score':          readability,
        'unique_word_ratio':          round(unique_ratio, 4),
        'legit_phrase_score':         legit_score,
    }


# ══════════════════════════════════════════════════════════════════════════
#  SCAM TYPE CLASSIFIER  (rule-based; no ground-truth labels needed)
# ══════════════════════════════════════════════════════════════════════════

_TYPE_PATTERNS = {
    'phishing': [
        r'\b(paypal|amazon|apple|netflix|google|microsoft|ebay|instagram|facebook)\b.{0,60}'
        r'(verify|confirm|login|sign.?in|suspended|locked|update|validate)\b',
        r'(verify|confirm|validate).{0,40}(account|identity|details|information)\b',
        r'\bclick (here|the link|below).{0,30}(verify|confirm|login|access)\b',
    ],
    'credential_phishing': [
        r'\b(account|access).{0,40}(locked|suspended|disabled).{0,40}(hour|minute|day)s?\b',
        r'\bit department\b.{0,100}(verify|credentials|suspicious|activity)\b',
        r'\bverify (your )?(credentials?|identity|account|student)\b',
        r'\b(student portal|faculty portal|webmail|it helpdesk).{0,80}'
        r'(verify|login|credential|locked|suspended)\b',
        r'\b(locked|suspended|disabled).{0,40}unless (you )?(verify|confirm|log in|update)\b',
        r'\b(suspicious activity|unauthorized access).{0,60}(verify|confirm|credentials)\b',
        r'\b(student|faculty|staff|employee).{0,20}(portal|account).{0,80}'
        r'(verify|expire|expire|locked|suspended)\b',
        r'\b(account|access).{0,20}(will expire|expire(s|d)?).{0,40}(verify|login|confirm)\b',
        r'\b(verify|confirm|validate).{0,30}at\s+[a-z0-9\-]+\.(net|com|org|edu)\b',
        r'\b[a-z0-9]+[-][a-z0-9]*(verify|portal|login|secure|unlock)\.[a-z]+\b',
        r'\b(verify|login|portal|apply|activate)\.[a-z0-9\-]+\.(com|net|org)\b',
    ],
    'emergency_scam': [
        r'\b(bail money|need bail|post bail)\b',
        r"\b(do not tell|don't tell).{0,30}(mom|dad|anyone|family|parents)\b",
        r'\b(i got arrested|i am in jail|i am in trouble|i have been arrested)\b',
        r'\b(wire|transfer|send).{0,20}(money|\$[\d,]+).{0,30}(immediately|urgently|now|asap|right away)\b',
        r'\bit is me.{0,30}(arrested|trouble|jail|accident|hospital|hurt)\b',
        r'\b(stranded|stuck).{0,20}(abroad|overseas|airport|country)\b',
        r'\b(lost my (wallet|phone|passport)).{0,60}(need|help|money|send)\b',
    ],
    'prize_fraud': [
        r'\b(you have won|you are a winner|lucky winner|prize|lottery|sweepstake)\b',
        r'\b(claim|collect).{0,20}(prize|reward|winnings|gift card)\b',
        r'\bcongratulations.{0,40}(won|selected|chosen|winner)\b',
    ],
    'bank_impersonation': [
        r'\b(bank|irs|tax|federal|government|hmrc|inland revenue)\b.{0,50}'
        r'(suspended|locked|verify|payment|penalty|fine|owe)\b',
        r'\b(refund|tax return|overpayment).{0,40}(claim|collect|process)\b',
    ],
    'job_scam': [
        r'\b(work from home|wfh|remote (job|position|opportunity)|hiring now)\b',
        r'\b(earn|make).{0,15}\$[\d,]+.{0,20}(day|week|month|hour)\b',
        r'\b(no experience|no qualification).{0,30}required\b',
    ],
    'investment_scam': [
        r'\b(invest|investment|trading|crypto|bitcoin|ethereum|forex|nft)\b.{0,40}'
        r'(profit|return|gain|double|triple|guarantee)\b',
        r'\b(guaranteed|risk.?free).{0,30}(return|profit|income)\b',
        r'\b(turned?|made|flipped)\s*\$[\d,]+.{0,30}into\s+\$[\d,]+\b',
        r'\$[\d,]+.{0,20}(turned|flipped|grew|became).{0,10}(into\s+)?\$[\d,]+\b',
        r'\b(ai|bot|algorithm).{0,30}(does|doing|handles|runs?).{0,20}(all.{0,5})?trading\b',
        r'\b(dm|message|text) me.{0,20}(link|info|join|details)\b',
        r'\b(passive income|financial freedom|be your own boss)\b',
        r'\bguaranteed?\s+\d+x\s*(returns?|profit|gain)\b',
        r'\b\d+\s*%\S?\s+(guaranteed\s+)?(monthly|weekly|daily)\s+returns?\b',
        # Works after leet-normalisation: $ → s, so $200 → s200
        r'\b(invested?).{0,80}savings?.{0,80}(turned?|became|grew)\b',
        r'\b[s$][\d,]+.{0,25}(turned?|flipped).{0,10}into.{0,5}[s$][\d,]+\b',
    ],
    'romance_scam': [
        r'\b(lonely|single|beautiful|attractive|military|widowed)\b',
        r'\b(meet me|let\'s chat|send me|i love you|my darling|my dear)\b.{0,30}'
        r'(money|gift|send|transfer|help)\b',
        r'\b(us army|us soldier|us military|army officer|deployed in)\b.{0,80}'
        r'(transfer|gold|fund|money|help|commission)\b',
        r'\bgold bars?\b.{0,80}(transfer|help|commission|country)\b',
        r'\bi will give you \d+\s*%\b',
        r"\b(couldn't stop thinking about you|fell in love).{0,80}(send|money|help|transfer|fund)\b",
        r"\b(i am a|i'm a)\s+(doctor|soldier|engineer|officer|nurse)\b.{0,80}(money|send|help|fund|transfer)\b",
        r'\b(matched|connected|met).{0,20}(tinder|bumble|hinge|dating)\b',
        r'\btinder.{0,60}(forex|trader|crypto|invest|strategy|market)\b',
        r'\b(forex|crypto|currency).{0,20}trader.{0,60}(singapore|london|dubai|nigeria)\b',
        r'\b(i can show you|let me show you).{0,30}(strategy|method|system|trade|invest)\b',
        r'\b(made me|making me|earned).{0,10}\$[\d,]+.{0,20}(month|week|day|year)\b',
        # ── Cold-contact opener patterns (before money request) ──────────────
        r'\b(accidentally|mistakenly).{0,20}texted? (the )?wrong number\b',
        r'\btexted?.{0,5}wrong number\b',
        r'\bfound (your|this) (number|contact|profile).{0,40}(friend of a friend|mutual friend|randomly|by chance)\b',
        r'\b(nurse|doctor|surgeon|physician).{0,30}(msf|m.decins|doctors without borders|conflict zone|war zone|yemen|iraq|afghanistan|syria|nigeria|ghana)\b',
        r'\b(captain|colonel|lieutenant|commander|sergeant|major|general).{0,30}(us navy|us air force|us coast guard|nato|un peacekeeping|united nations|armed forces)\b',
        r'\bcurrently (deployed|stationed|serving).{0,30}(on |in )(a )?(peacekeeping|humanitarian|nato|un).{0,20}(mission|force)\b',
        r'\b(peacekeeping mission|humanitarian mission|un mission)\b',
        r'\b(us navy|us air force|nato force|united nations force).{0,40}(mission|deployed|stationed|serving)\b',
        r'\blooking for (a )?(genuine|real|honest|serious|meaningful).{0,20}(connection|relationship|partner|person|friend)\b',
        r'\b(tired|sick).{0,10}of.{0,10}(fake|dishonest|shallow|superficial).{0,20}(people|connections|relationships)\b',
        r'\bhope you (don.t|do not) mind.{0,20}(reaching out|contacting|messaging|me reaching)\b',
        r'\b(entrepreneur|businessman|businesswoman|investor|professional).{0,50}(dubai|lagos|abuja|nigeria|ghana|accra|nairobi|kenya).{0,80}(connection|genuine|real|honest|single|lonely|someone special)\b',
    ],
    'advance_fee_scam': [
        r'\b\d+\s*(million|billion).{0,30}(dollar|usd|eur|gbp)\b',
        r'\b\d+\s*%\s*commission\b',
        r'\bbusiness proposal\b.{0,80}(million|amount|fund|transfer|assist)\b',
        r'\b(transfer|move).{0,30}(fund|money|gold).{0,80}(commission|percent|%)\b',
        r'\b(diplomat|barrister|attorney|solicitor).{0,60}(fund|money|million|transfer)\b',
        r'\bnext of kin\b',
        r'\binheritance fund\b',
        r'\bgold bars?\b',
        r'\bclassified gold\b',
        r'\bsecret funds?\b',
        r'\b(send|provide).{0,20}bank.{0,15}details\b',
        r'\bi will give you \d+\s*%\b',
        r'\bout of the country\b.{0,60}(commission|gold|fund|help|transfer)\b',
        # Charity fraud — money transfer to individual
        r'\b(moneygram|western union|zelle).{0,80}(relief|coordinator|donation|fund|charity)\b',
        r'\b(send|donate).{0,40}(moneygram|western union|zelle).{0,40}(coordinator|relief|charity)\b',
    ],
    'delivery_scam': [
        r'\b(package|parcel|shipment).{0,80}(customs fee|delivery fee|unpaid|held|release)\b',
        r'\btrack\?id=',
        r'\b(customs fee|delivery fee|delivery charge).{0,50}(pay|unpaid|required|pending)\b',
        r'\b(unpaid customs|customs charge|release.{0,15}package)\b',
        r'\b(pay now|payment required|immediate payment).{0,60}(package|parcel|delivery)\b',
        r'\b(failed delivery|could not be delivered|delivery attempt).{0,60}(fee|pay|customs)\b',
        r'\bheld at customs\b',
        r'\b(release fee|clearance fee|customs clearance fee)\b',
        r'\b(shipment|package).{0,30}(held|on hold).{0,30}(pay|fee|customs|release)\b',
        r'\b(pay|settle).{0,20}(release fee|clearance fee|customs fee)\b',
        r'\bdhl.{0,40}(customs|clearance|fee|pay|held)\b',
    ],
    'social_media_scam': [
        r'\blink in (my )?bio\b',
        r'\b(was broke|was struggling|was nothing|was poor).{0,80}\$[\d,]+\b',
        r'\b(make|earn)\s+\$[\d,]+\s+(a|per)\s+(week|month|day)\s+from home\b',
        r'\b\d+\s*(months?|years?)\s+ago.{0,30}(broke|nothing|struggling|poor)\b',
        r'\bnot a financial advisor\b',
        r'\bstart (today |now )?with just\s+\$[\d,]+\b',
        r'\b(simple system|proven system|secret system).{0,60}(earn|make|income|money)\b',
        r'\b(changed my life|transformed my life).{0,60}(money|\$[\d,]+|income)\b',
        # ── Soft-sell opener patterns ────────────────────────────────────────
        r'\b(not spam|not a spam).{0,20}(i promise|i swear|honest|trust me|genuinely)\b',
        r'\bjust (a )?regular (person|guy|girl|individual).{0,60}(wealth|returns?|dm me|found something|something that works)\b',
        r'\b(no mlm|not mlm|not (a )?pyramid scheme?|no pyramid)\b.{0,60}(returns?|wealth|income|money|dm|message)\b',
        r'\b(dm|inbox|message|reach out|contact).{0,15}me.{0,30}(if (you.re |you are )interested|to learn|for (info|details|the link|the strategy|more))\b',
        r'\b(building|build|grow|growing).{0,15}wealth.{0,40}(dm|message|reach out|contact|found|share|help)\b',
        r'\bfound something that (actually |really )?(works?|changed)\b.{0,60}(wealth|returns?|income|dm|message)\b',
    ],
    'threat_scam': [
        r'\b(legal action|arrest warrant|criminal charge|lawsuit|prosecute)\b',
        r'\b(debt collector|collection agency|court order|court summons)\b',
        r'\b(irs|tax authority).{0,30}(lawsuit|warrant|arrest|criminal)\b',
        r'\b(avoid arrest|face arrest|to avoid arrest|warrant for your arrest)\b',
        r'\b(fbi|irs|federal|authority).{0,40}(illegal activity|linked to|cybercrime)\b',
        r'\b(irs|hmrc|tax).{0,20}(final notice|back taxes|owe.{0,10}\$[\d,]+)\b',
        # Car warranty scam
        r'\bcar warranty.{0,40}(expire|extend|lapse|cover|call)\b',
        r'\b(warranty|coverage).{0,30}(expire|lapse|end(s|ed)?).{0,30}(call|extend|renew)\b',
        # Blackmail / sextortion
        r'\b(webcam|camera|footage|recording|video).{0,60}(send|contacts|employer|family|pay)\b',
        r'\b(browsing history|private video|footage).{0,60}(pay|bitcoin|cryptocurrency|send)\b',
        r'\bunless you pay.{0,40}(bitcoin|crypto|hour|within)\b',
        r'\b(recorded|captured|hacked).{0,60}(pay|bitcoin|hours?|send)\b',
    ],
    'pig_butchering': [
        # Platform introduction — core pig butchering signal
        r'\b(i use|i.ve been using|i.m using).{0,30}(platform|app|trading site|trading app)\b',
        r'\b(trusted|reliable|legit|good).{0,20}(trading platform|investment platform|crypto platform)\b',
        r'\b(my broker|my trader|my mentor).{0,60}(platform|invest|fund|profit|crypto)\b',
        # Personal guidance offer
        r'\b(let me show you|i can show you|i.ll guide|guide you|walk you through).{0,40}(platform|invest|trade|step|portfolio|profit)\b',
        r'\b(i.ll guide|guide you|help you|walk you through).{0,30}(platform|invest|trade|step)\b',
        # Profit claims used to build trust
        r'\b(i made|i.ve made|i.ve been making).{0,20}\$[\d,]+.{0,30}(month|week|platform|trading|last)\b',
        r'\bmy profits?.{0,30}(this month|this week|last month)\b',
        # Low-barrier entry pitch
        r'\b(start with|deposit).{0,20}(as little as|\$[\d,]+).{0,30}(and (see|watch)|platform|returns?|grow)\b',
        r'\bminimum deposit.{0,50}(platform|account|invest|start)\b',
        r'\b(put in|invest).{0,20}(small amount|\$[\d,]+).{0,40}(see|watch|returns?|grow|double)\b',
        # Anytime-withdrawal reassurance (before the withdrawal fee trap)
        r'\b(you can withdraw|withdrawal).{0,30}(anytime|any time|whenever)\b',
        # Withdrawal fee trap — the defining pig butchering mechanic
        r'\b(withdrawal fee|tax|insurance fee|activation fee).{0,50}(to withdraw|before (you can )?withdraw|release|unlock).{0,30}(fund|profit|earning|money)\b',
        r'\b(pay.{0,20}fee|fee.{0,10}required|fee.{0,10}needed).{0,40}(withdraw|release|unlock|access).{0,30}(fund|profit|money|earning)\b',
        r'\b(funds?|profit|earning|money).{0,40}(locked|frozen|on hold|held).{0,40}(pay|fee|tax|insurance)\b',
    ],
    'qr_phishing': [
        r'\bscan (this |the )?(qr|qr.?code)\b',
        r'\bqr.?code.{0,40}(verify|confirm|login|sign.?in|pay|access|claim|complete)\b',
        r'\b(use|open).{0,20}(camera|phone).{0,30}(scan|qr)\b',
        r'\bscan to (verify|confirm|login|pay|access|complete|claim|activate)\b',
        r'\b(verify|confirm|login|pay).{0,30}(by scanning|via qr|using qr|scan the)\b',
        r'\bqr.?code.{0,30}(below|attached|above|included|link)\b',
        r'\b(point your (camera|phone)|scan with (your )?(camera|phone))\b',
    ],
    'refund_scam': [
        r'\b(accidental(ly)?|mistakenly|by mistake).{0,30}(overpaid|sent|transferred|deposited).{0,30}(you|your|extra|too much)\b',
        r'\b(overpayment|excess (amount|funds?|money)).{0,60}(refund|return|send back|transfer back)\b',
        r'\b(send|return|refund|transfer).{0,20}(back|the difference|excess|extra|overpaid).{0,50}(gift card|zelle|venmo|paypal|wire|western union|crypto|bitcoin)\b',
        r'\b(too much|extra|excess).{0,30}(credited|deposited|transferred|sent).{0,30}(account|you)\b',
        r'\b(refund|reimburse|return).{0,20}(the (extra|excess|difference|overpaid|remaining))\b',
        r'\b(please|kindly).{0,20}(return|send back|refund).{0,30}(\$[\d,]+|the amount|the difference)\b',
    ],
    'sim_swap': [
        # Direct code extraction attempts
        r'\b(read|tell|give|share|send|forward).{0,20}(me|us).{0,10}(the )?(code|otp|pin|number)\b',
        r'\bgive (me|us).{0,20}(the )?(otp|one.?time.?(code|password|pin)|verification code|security code|pin)\b',
        r'\bforward.{0,20}(the )?(code|otp|pin|sms|text).{0,30}(to (me|us)|back)\b',
        # Asking "what is the code"
        r'\b(what (is|was|s)|what.s).{0,10}(the )?(code|otp|number|pin).{0,30}(you received|on your phone|that was sent|we sent|we texted|just sent)\b',
        r'\b(what.s|what is).{0,5}the.{0,5}(code|otp|pin|number).{0,30}(you (got|received|see))\b',
        # Code sent to phone, asking to relay
        r'\b(verification|confirmation|security|one.?time).{0,15}code.{0,30}(we sent|we texted|sent to your phone|you received|you just got)\b',
        r'\b(code|otp).{0,20}(sent to|messaged to|texted to).{0,20}(your (phone|number|device))\b',
        r'\b(code|otp|pin).{0,30}(we just sent|just sent to|just texted).{0,30}(read|tell|share|give|send|type|enter)\b',
    ],
}

_COMPILED_TYPES = {
    t: [re.compile(p, re.IGNORECASE) for p in patterns]
    for t, patterns in _TYPE_PATTERNS.items()
}


def classify_scam_type(text: str) -> str:
    """
    Rule-based scam type classifier.
    Returns one of the SCAM_TYPES strings, or 'general_spam'.
    """
    if not isinstance(text, str):
        return 'general_spam'
    scores = {t: 0 for t in _TYPE_PATTERNS}
    for t, patterns in _COMPILED_TYPES.items():
        for pat in patterns:
            if pat.search(text):
                scores[t] += 1
    best_type = max(scores, key=scores.get)
    return best_type if scores[best_type] > 0 else 'general_spam'


# ══════════════════════════════════════════════════════════════════════════
#  VIRUSTOTAL  (unchanged)
# ══════════════════════════════════════════════════════════════════════════

def check_url_virustotal(url: str, api_key: str):
    """Returns (malicious, suspicious, total). Raises on API / network error."""
    import requests, base64
    url_id  = base64.urlsafe_b64encode(url.encode()).decode().strip('=')
    headers = {'x-apikey': api_key}
    r = requests.get(
        f'https://www.virustotal.com/api/v3/urls/{url_id}',
        headers=headers, timeout=5,
    )
    if r.status_code != 200:
        raise RuntimeError(f"VirusTotal returned HTTP {r.status_code}")
    stats = r.json()['data']['attributes']['last_analysis_stats']
    m, s  = stats.get('malicious', 0), stats.get('suspicious', 0)
    return m, s, m + s


# ══════════════════════════════════════════════════════════════════════════
#  APPLY TO DATAFRAME
# ══════════════════════════════════════════════════════════════════════════

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    print("Preprocessing text...")
    df['raw_text'] = df['raw_text'].fillna('').apply(preprocess_text)

    print("Adding tone features (phrase-level, negation-aware)...")
    tone = df['raw_text'].apply(compute_tone_features)
    df['tone_urgency'] = tone.apply(lambda x: x[0])
    df['tone_fear']    = tone.apply(lambda x: x[1])
    df['tone_reward']  = tone.apply(lambda x: x[2])
    df['tone_threat']  = tone.apply(lambda x: x[3])

    print("Adding URL features...")
    url_feats = df['raw_text'].apply(compute_url_features)
    df['url_suspicious_tld']     = url_feats.apply(lambda x: x[0])
    df['url_suspicious_keyword'] = url_feats.apply(lambda x: x[1])
    df['url_has_ip']             = url_feats.apply(lambda x: x[2])

    print("Adding 10 new engineered features...")
    new_feats = df['raw_text'].apply(compute_new_features)
    for col in ['avg_word_length', 'capitalized_word_count', 'scam_phrase_score',
                'sender_impersonation_score', 'punctuation_density',
                'question_mark_count', 'currency_symbol_count',
                'readability_score', 'unique_word_ratio', 'legit_phrase_score']:
        df[col] = new_feats.apply(lambda x: x[col])

    print("✅ All features added!")
    return df


# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db 4.db')
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT m.message_id, m.raw_text, m.label, c.type AS channel,
               ds.name AS source, mf.text_length, mf.word_count, mf.has_url,
               mf.url_count, mf.exclamation_count, mf.uppercase_ratio,
               mf.digit_ratio, mf.urgency_score
        FROM Message m
        JOIN Channel c ON m.channel_id = c.channel_id
        JOIN DataSource ds ON m.source_id = ds.source_id
        JOIN MessageFeatures mf ON m.message_id = mf.message_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df = add_features(df)
    print('\nNegation test:')
    test_cases = [
        ('You are free to leave anytime.',          0),
        ('GET YOUR FREE GIFT NOW — CLAIM TODAY!',   1),
        ('No prize has been awarded.',              0),
        ('You have won a prize! Claim now!',        1),
        ('I won\'t verify my account for scammers.',0),
    ]
    for txt, expected_label in test_cases:
        _, _, reward, _ = compute_tone_features(txt)
        print(f'  reward={reward:2d} (expected~{expected_label}) | {txt[:60]}')
    print('\nFeature engineering complete!')
