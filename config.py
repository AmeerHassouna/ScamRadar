"""ScamRadar+ | Central configuration — change values here, not scattered across files."""

import os
from dotenv import load_dotenv

# Load .env from the project root (no-op if the file doesn't exist)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, 'data', 'db 4.db')
MODELS_PATH = os.path.join(BASE_DIR, 'models')
OUTPUT_PATH = os.path.join(BASE_DIR, 'outputs')

# ── Index rebuilding ───────────────────────────────────────────────────────
# Set True to force re-encode all 45 k messages via Sentence Transformers.
# False = skip encoding if embeddings.npy already exists (saves ~2 min).
REBUILD_INDEX = False

# ── FAISS search depth ─────────────────────────────────────────────────────
FAISS_K_SCAM  = 10
FAISS_K_LEGIT = 10

# ── VirusTotal API key ─────────────────────────────────────────────────────
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')

# ── Google Safe Browsing API key ───────────────────────────────────────────
GOOGLE_SAFEBROWSING_API_KEY = os.environ.get('GOOGLE_SAFEBROWSING_API_KEY', '')

# ── Decision threshold ─────────────────────────────────────────────────────
DEFAULT_THRESHOLD = 0.40  # overwritten by threshold optimisation; never goes below 0.40

# ── Input validation ───────────────────────────────────────────────────────
MIN_MESSAGE_LENGTH = 20
MAX_MESSAGE_LENGTH = 5_000

# ── Trusted domains — all-trusted URL set caps scam prob at 0.35 ──────────
TRUSTED_DOMAINS = {
    # Banking / finance
    'bankofamerica.com', 'chase.com', 'wellsfargo.com', 'citibank.com',
    'hsbc.com', 'barclays.com', 'americanexpress.com',
    'visa.com', 'mastercard.com', 'stripe.com', 'squareup.com', 'paypal.com',
    # Big tech
    'google.com', 'apple.com', 'microsoft.com', 'amazon.com',
    'meta.com', 'yahoo.com', 'adobe.com', 'icloud.com', 'dropbox.com',
    'github.com', 'youtube.com',
    # Social / streaming
    'linkedin.com', 'twitter.com', 'instagram.com', 'facebook.com', 'tiktok.com',
    'netflix.com', 'spotify.com', 'hulu.com', 'disneyplus.com', 'playstation.com',
    # Shopping
    'ebay.com', 'etsy.com', 'shopify.com',
    # Amazon regional
    'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.co.jp',
    # Messaging / conferencing
    'whatsapp.com', 'wa.me', 't.me', 'zoom.us', 'webex.com',
    'teams.microsoft.com', 'meet.google.com',
}

# ── Brand / action word lists used by impersonation scorer ────────────────
BRAND_NAMES   = ['paypal', 'amazon', 'apple', 'microsoft', 'netflix',
                 'bank', 'fedex', 'irs', 'google', 'dhl', 'hsbc', 'chase']
ACTION_WORDS  = ['verify', 'confirm', 'suspended', 'login', 'update',
                 'locked', 'blocked', 'validate', 'reactivate', 'authenticate']

# ── Exact scam phrases (case-insensitive substring match) ─────────────────
SCAM_PHRASES = [
    'you have been selected', 'claim your prize', 'verify your account',
    'limited time offer', 'act now', 'you are a winner', 'you have won',
    'click here to claim', 'your account has been', 'you have been chosen',
    'congratulations you', 'free gift card', 'free iphone',
    'wire transfer', 'western union', 'send money now',
    # Investment / trading scam phrases
    'no experience needed', 'ai does all the trading', 'dm me for the link',
    'passive income', 'financial freedom', 'invest now', 'work from anywhere',
    'be your own boss', 'spots fill up', 'spots are limited',
    'guaranteed returns', 'guaranteed profits', 'guaranteed income',
    'guarantees returns', 'guarantees profits', 'guaranteed monthly returns',
    'monthly returns minimum', 'spots filling up fast', 'ai trading bot',
    'trading bot guarantees',
    # Credential / spear-phishing phrases
    'account will be locked in', 'verify credentials', 'verify your credentials',
    'will be locked unless', 'suspended unless you verify',
    # Emergency / grandparent scam phrases
    'please do not tell', 'do not tell mom', 'do not tell dad', 'do not tell anyone',
    'i got arrested', 'i am in jail', 'i am in trouble', 'bail money',
    'wire money', 'wire transfer urgently', 'i am scared', 'please hurry',
    'need bail', 'stranded abroad', 'lost my wallet', 'lost my phone', 'emergency wire',
    # Delivery / customs fee scam phrases
    'unpaid customs fee', 'customs fee', 'delivery fee unpaid', 'package on hold',
    'release your package', 'pay to receive your package',
    'failed delivery attempt', 'reschedule your delivery',
    'release fee', 'held at customs', 'customs release', 'clearance fee',
    'customs clearance fee', 'pay release fee', 'shipment is held', 'package is held',
    # Investment extra phrases
    'guaranteed weekly returns', 'guaranteed daily returns',
    'spots left', 'limited spots',
    # Threat / authority scam phrases
    'arrest warrant', 'face arrest', 'to avoid arrest', 'irs final notice',
    'linked to illegal activity',
    # Charity / payment fraud
    'moneygram', 'via zelle', 'send via zelle', 'via western union',
    # Blackmail / sextortion
    'unless you pay', 'browsing history has been', 'will be sent to your employer',
    'your employer and family',
    # Warranty / loan / recovery scams
    'car warranty', 'warranty is about to expire', 'no credit check required',
    'wallet recovery', 'crypto recovery', 'recover your bitcoin',
    # Government benefit fraud
    'student loan forgiveness',
    # Social media investment scam phrases
    'click the link in my bio', 'link in bio', 'link in my bio',
    'was broke', 'changed my life', 'i am not a financial advisor but',
    'start today with just', 'simple system', 'from home thanks to',
    'paying it forward', 'what worked for me', 'happy to share the strategy',
    'saw your comment', 'taught me a strategy', 'uncle taught me',
    'friend showed me how', 'forex trader in', 'currency trader',
    # Romance / advance-fee scam phrases
    'think we matched on tinder', 'matched on tinder', 'we matched on tinder',
    'gold bars', 'transfer out of the country', 'business proposal',
    'commission percentage', 'i will give you', 'deployed in',
    'us army officer', 'us soldier', 'currently deployed',
    'millions of dollars', 'need your assistance', 'bank account details',
    'next of kin', 'inheritance fund', 'classified gold', 'secret funds',
    'diplomat', 'widower', 'late husband', 'late wife',
    'bank details', 'out of the country',
    # Gift card payment requests
    'itunes gift card', 'google play card', 'amazon gift card',
    'steam gift card', 'ebay gift card', 'buy gift cards',
    'send the card numbers', 'scratch the back of the card',
    'gift card numbers', 'send gift card', 'pay with gift card',
    'gift card code', 'redeem gift card',
    # Crypto payment scam phrases
    'send bitcoin to', 'send crypto to', 'pay in bitcoin',
    'pay in cryptocurrency', 'bitcoin wallet address', 'crypto wallet',
    'ethereum address', 'usdt transfer', 'send usdt', 'trc20',
    'withdrawal fee', 'withdrawal limit reached', 'unlock your funds',
    'release your funds', 'platform fee to withdraw', 'tax to withdraw',
    'insurance fee', 'activation fee to withdraw',
    # Pig butchering scam phrases
    'i use this platform', 'i can guide you personally',
    'let me show you my portfolio', 'my profits this month',
    'start with as little as', 'you can withdraw anytime',
    'i made so much', 'my broker', 'put in a small amount',
    'trusted trading platform', 'i have been using this platform',
    'you will see the returns', 'minimum deposit',
    # QR code phishing
    'scan this qr', 'scan the qr code', 'scan qr code to verify',
    'use your camera to scan', 'qr code to complete',
    'scan to confirm', 'scan to login', 'scan to pay',
    # Refund / overpayment scam phrases
    'accidentally overpaid', 'sent you too much', 'excess amount',
    'please refund the difference', 'send back the extra',
    'overpayment was made', 'refund the excess', 'return the overpaid',
    # SIM swap / verification code theft
    'share the code we sent', 'forward the code',
    'read me the code', 'what is the code you received',
    'verification code sent to your phone', 'code we just texted',
    'tell me the code', 'give me the otp',
    # Fake job interview payment
    'pay for background check', 'purchase training materials',
    'equipment deposit required', 'buy your starter kit',
    'refunded in first paycheck', 'processing fee for the job',
    'registration fee to start', 'onboarding fee',
    # Romance scam openers — cold-contact social engineering before money request
    'accidentally texted the wrong number',
    'texted the wrong number',
    'found your number through a friend of a friend',
    'found your contact through a friend',
    'peacekeeping mission',
    'currently deployed in',
    'currently stationed in',
    'nurse working with msf',
    'working with msf',
    'doctors without borders',
    'hope you do not mind me reaching out',
    'hope you dont mind me reaching out',
    'tired of fake people',
    'looking for a genuine connection',
    'looking for a real connection',
    'looking for an honest connection',
    'would love to get to know you better',
    'us navy currently',
    'us army currently',
    'currently on a peacekeeping',
    'humanitarian mission',
    # Soft-sell investment / social media scam openers
    'not spam i promise',
    'not a spam i promise',
    'just a regular person who found',
    'no mlm no pyramid',
    'not mlm not pyramid',
    'solid returns dm',
    'building wealth dm',
    'what actually works for building wealth',
    'what works for building wealth',
    'found something that actually works',
]

# ── URL shortener hostnames ────────────────────────────────────────────────
URL_SHORTENERS = ['bit.ly', 'tinyurl.com', 't.co', 'ow.ly', 'goo.gl',
                  'short.link', 'rb.gy', 'cutt.ly', 'is.gd', 'buff.ly']

# ── Feature column lists ───────────────────────────────────────────────────
# V4 — original feature set (kept for reference / backward compat)
NUMERICAL_FEATURES_V4 = [
    'text_length', 'word_count', 'has_url', 'url_count',
    'exclamation_count', 'uppercase_ratio', 'digit_ratio', 'urgency_score',
    'tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat',
    'url_suspicious_tld', 'url_suspicious_keyword', 'url_has_ip',
    'proximity_scam_score',
]

# V5 — improved feature set (25 features; legit_proximity_score and
#       proximity_delta removed — they caused false positives on corporate emails)
NUMERICAL_FEATURES_V5 = [
    # original DB features
    'text_length', 'word_count', 'has_url', 'url_count',
    'exclamation_count', 'uppercase_ratio', 'digit_ratio', 'urgency_score',
    # improved tone / URL
    'tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat',
    'url_suspicious_tld', 'url_suspicious_keyword', 'url_has_ip',
    # 9 new engineered features
    'scam_phrase_score', 'sender_impersonation_score',
    'avg_word_length', 'capitalized_word_count',
    'punctuation_density', 'question_mark_count', 'currency_symbol_count',
    'readability_score', 'unique_word_ratio',
    # scam proximity only (scaled ×0.5 before feature matrix to prevent dominance)
    'proximity_scam_score',
    # legit signal — security / automated-message phrases reduce scam probability
    'legit_phrase_score',
]

# ── Scam type labels ───────────────────────────────────────────────────────
SCAM_TYPES = [
    'phishing', 'credential_phishing', 'prize_fraud', 'bank_impersonation',
    'job_scam', 'investment_scam', 'romance_scam', 'advance_fee_scam',
    'delivery_scam', 'social_media_scam', 'emergency_scam',
    'threat_scam', 'pig_butchering', 'qr_phishing', 'refund_scam',
    'sim_swap', 'general_spam',
]
