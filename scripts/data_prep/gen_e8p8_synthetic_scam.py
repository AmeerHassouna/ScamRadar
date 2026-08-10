"""
E8-P8 — Synthetic MODERN scam corpus targeting E8-P7's recall weaknesses.

Target: 15-20k realistic scam messages balanced across the categories
where recall is currently weak (investment/crypto, romance, emergency,
refund, threat/authority, sextortion, gift-card CEO, advanced phishing).

Design principles (per project spec)
-----------------------------------
* MODERN scam patterns only. Zero 2005-era viagra/inches/CD spam.
* Focus categories = current weakness map: investment_crypto,
  romance, emergency, refund, sextortion, threat_authority,
  gift_card_ceo, modern_phishing.
* PAIRED generation for adversarial learning — for many scam
  templates, generate a legit twin sharing surface vocabulary but
  differing in the discriminative signal (verifiable business
  context vs vague personal outreach, real utility statement vs
  fake refund pitch, etc.).
* LANGUAGE DIVERSITY — rich placeholder pools + paraphrase pools.
* TOKEN GUARDRAILS — hard cap on how often risky conversational
  tokens ("mom", "dad", "sorry to bother", "hey stranger") can
  appear. Prevents E8-P8 from re-creating an FP problem on real
  family / casual chat.
* SAFETY VALIDATORS — reuse E8-P2's validators. Every message must
  be a coherent scam pattern; can't be gibberish or unlabeled legit.
* Do NOT retrain here — this script only generates. Review the
  output samples + stats before merging into training.

Output
------
data/synthetic_scam/e8p8/
  scam_dataset.parquet           — validated scam messages (label=1)
  legit_pairs_dataset.parquet    — adversarial legit twins (label=0)
  samples.txt                    — human-review samples per category
  generation_stats.json          — per-category / per-template counts
  token_frequency_report.json    — audit of risky-token usage
"""
from __future__ import annotations

import json
import os
import random
import re
import string
import sys
from collections import Counter, defaultdict

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Reuse safety validators + region + amount + paraphrase infrastructure
from scripts.data_prep.gen_e8p2_synthetic_legit import (
    RNG as _P2_RNG,
    validate as _p2_validate,
    pick_region, rand_amount_kind, rand_currency_kind, rand_name, rand_full_name,
    rand_date, rand_last4, rand_code, rand_amazon_order_id, rand_apple_receipt_id,
    rand_txn_id, rand_invoice_id, rand_tracking, DEVICES, BROWSERS, PRODUCTS_TECH,
    STORES, CITIES_UK, CITIES_US, CITIES_EU,
)

OUT_DIR = os.path.join(_ROOT, 'data', 'synthetic_scam', 'e8p8')
os.makedirs(OUT_DIR, exist_ok=True)

# Fresh RNG so this run is deterministic-independent from the legit run
RNG = random.Random(20260804)


# ══════════════════════════════════════════════════════════════════════════
# ANTI-FP TOKEN GUARDRAILS
# ══════════════════════════════════════════════════════════════════════════
# Conversational tokens whose over-use in scam corpus would teach the LR
# that normal chat = scam. Max % of the entire scam corpus each token may
# appear in — once hit, further templates using this token are skipped.
RISKY_TOKEN_CAPS: dict = {
    'mom':              0.06,   # max 6% of all scam messages
    'dad':              0.06,
    'grandma':          0.02,
    'grandson':         0.02,
    'sorry to bother':  0.03,
    'hey stranger':     0.01,
    'wrong number':     0.02,
    'we matched':       0.02,
    'hospital':         0.04,
    'jail':             0.02,
    'arrested':         0.02,
    'bail':             0.02,
}
_token_counter: Counter = Counter()
_total_generated = 0


def _risky_tokens_ok(text: str) -> bool:
    """Check if adding this text would exceed any risky-token cap."""
    global _total_generated
    text_l = text.lower()
    hits = []
    for tok, cap in RISKY_TOKEN_CAPS.items():
        if tok in text_l:
            hits.append((tok, cap))
    if not hits:
        return True
    # Would-be counts if we added this
    projected_total = _total_generated + 1
    for tok, cap in hits:
        projected_share = (_token_counter[tok] + 1) / projected_total
        # Only allow if projected share <= cap OR we haven't accumulated enough
        # baseline yet (first 500 messages ignore the cap so we don't cold-start-fail)
        if projected_total > 500 and projected_share > cap:
            return False
    return True


def _record_tokens(text: str):
    global _total_generated
    _total_generated += 1
    text_l = text.lower()
    for tok in RISKY_TOKEN_CAPS:
        if tok in text_l:
            _token_counter[tok] += 1


# ══════════════════════════════════════════════════════════════════════════
# MODERN SCAM PLACEHOLDER POOLS
# ══════════════════════════════════════════════════════════════════════════
MODERN_BRANDS = [
    # 2020+ SaaS brands frequently impersonated
    'Notion', 'Vercel', 'Cloudflare', 'Substack', 'Linear', 'Figma', 'Canva',
    'Loom', 'Airtable', 'Coda', 'Miro', 'Roam', 'ClickUp', 'Todoist',
    'GitHub', 'GitLab', 'Bitbucket', 'DigitalOcean', 'Heroku', 'Railway',
    'Supabase', 'PlanetScale', 'MongoDB', 'Auth0', 'Stripe', 'Paddle',
    # Consumer
    'Netflix', 'Spotify', 'Adobe', 'Dropbox', 'Discord', 'Slack', 'Zoom',
    'Coinbase', 'Binance', 'Kraken', 'Metamask', 'Uphold',
    'Uber', 'Lyft', 'DoorDash', 'Airbnb', 'Booking.com',
    'Amazon', 'Apple', 'Google', 'Microsoft', 'PayPal', 'Venmo',
    # Regional
    'Revolut', 'Monzo', 'Wise', 'Starling',
]
FAKE_TLDS = ['.co', '.tk', '.click', '.link', '.xyz', '.top', '.online',
             '.info', '.help', '.support', '.io', '.app']
CRYPTO_ADDR_PREFIXES = ['bc1q', '1', '3', '0x', 'tb1q']
CRYPTO_TOKENS = ['Bitcoin', 'BTC', 'Ethereum', 'ETH', 'USDT', 'USDC',
                  'stablecoin', 'crypto', 'Solana', 'SOL', 'Cardano']


def rand_fake_url(brand_hint: str = None, path: str = None) -> str:
    """Generate a plausible fake phishing URL — brand-lookalike root +
    suspicious TLD."""
    brand = (brand_hint or RNG.choice(MODERN_BRANDS)).lower()
    suffixes = ['-secure', '-verify', '-support', '-billing', '-restore',
                '-alert', '-notice', '-portal', '-help', '-recovery',
                '-review', '-appeal', '-refund']
    root = f'{brand}{RNG.choice(suffixes)}'
    tld = RNG.choice(FAKE_TLDS)
    p = path or RNG.choice(['/login', '/verify', '/pay', '/appeal',
                             '/restore', '/claim', '/id', '/settle'])
    return f'https://{root}{tld}{p}'


def rand_crypto_wallet() -> str:
    prefix = RNG.choice(CRYPTO_ADDR_PREFIXES)
    body_len = 34 if prefix in ('bc1q', '1', '3', 'tb1q') else 40
    body = ''.join(RNG.choices(string.ascii_lowercase + string.digits, k=body_len))
    return f'{prefix}{body}'[:42] + '…'


def rand_investment_return() -> str:
    """Realistic investment scam return claim."""
    r = RNG.choice([
        f'{RNG.randint(10, 45)}% monthly',
        f'${RNG.randint(500, 45_000)} in {RNG.randint(4, 12)} weeks',
        f'£{RNG.randint(300, 30_000)} in the last {RNG.randint(30, 90)} days',
        f'{RNG.randint(100, 1500)}% in {RNG.randint(2, 12)} months',
        f'${RNG.randint(1500, 50_000)}/month passive',
    ])
    return r


def rand_gift_card_brand() -> str:
    return RNG.choice(['Apple', 'Google Play', 'Amazon', 'Steam', 'Xbox',
                        'PlayStation', 'Sephora', 'Target', 'Walmart', 'eBay'])


def rand_modern_utility() -> str:
    return RNG.choice(['Ovo Energy', 'British Gas', 'EDF Energy', 'E.ON',
                        'PG&E', 'Duke Energy', 'ConEd', 'Southern California Edison',
                        'Thames Water', 'Anglian Water', 'Comcast Xfinity',
                        'Verizon Fios', 'AT&T', 'BT Broadband', 'Virgin Media'])


def rand_authority() -> str:
    return RNG.choice(['IRS', 'HMRC', 'CRA', 'ATO', 'Israel Tax Authority',
                        'Social Security Administration', 'DVLA',
                        'Ministry of Justice', 'State Bar', 'Immigration Enforcement',
                        'FBI Cyber Division', 'National Insurance Bureau',
                        'Petah Tikva Police', 'City of London Police'])


def rand_amount_ish(low: int, high: int) -> str:
    """Realistic-looking amount with cents."""
    return f'{RNG.uniform(low, high):.2f}'


# ══════════════════════════════════════════════════════════════════════════
# SCAM TEMPLATES — by category (paired legit twins added separately)
# ══════════════════════════════════════════════════════════════════════════
# Each template: {id, category, n, body, ?url_gen, ?pair_id (link to legit)}

SCAM_TEMPLATES: list = []

# ─── INVESTMENT / CRYPTO SCAMS (target ~2,500) ────────────────────────────
INVESTMENT_TEMPLATES = [
    ('inv_ai_bot', 60, "Our AI trading bot generates consistent {ret} for members. "
                        "Minimum ${min_inv} to join, first-month refund guaranteed. "
                        "{spots_left} spots open — DM 'AI' to reserve yours."),
    ('inv_signals_dm', 60, "Hey — my private signal group closed +{pct}% last month. "
                            "Opening 5 slots to serious traders. Not for tire kickers. "
                            "DM 'SIGNALS' if you want in this cycle."),
    ('inv_retired_pro', 55, "Retired {profession} here, sharing the system I built over "
                             "{years} years with a small group for free this month. "
                             "Consistent {ret}. Message me on {app} if curious."),
    ('inv_personal_story', 55, "Turned ${start} into ${end} in {mon} months using this "
                                "{strategy} strategy — no experience needed, everything "
                                "is automated. DM me for the link."),
    ('inv_forex_mentor', 45, "My mentor helped me pull ${monthly}/month trading {market}. "
                              "Now taking on {n_students} new students at a discounted rate. "
                              "Interested? Reply 'START'."),
    ('inv_web3_airdrop', 50, "{brand} airdrop claim window closes {when}. "
                              "Verify your wallet at {url} and receive up to "
                              "${airdrop} in tokens for early participants."),
    ('inv_meme_coin', 45, "New {meme_coin_name} launching {day} — my team's private allocation "
                           "is $0.{decimal} per token. DM '{code}' to reserve your "
                           "spot before the public sale at ${public_price}."),
    ('inv_recovery', 40, "Lost access to your crypto wallet? Our recovery service has "
                          "helped {n_helped}+ clients recover ${total_recovered}+ in "
                          "the past year. Small consultation fee of ${fee}. Visit {url}."),
    ('inv_soft_ask', 50, "Not trying to sell anything — genuinely just sharing what "
                          "worked for me. Left {old_job} last year, now trade "
                          "{market} full-time. Happy to talk if you're curious."),
    ('inv_skeptic', 45, "I was skeptical too but after {mon} months of consistent "
                         "profits I feel obligated to share this with people who "
                         "deserve financial freedom. DM 'REAL' for details."),
    ('inv_bank_fear', 40, "The next bank crash will wipe out most savings accounts. "
                           "My {method} moved 3 clients into safety last week. "
                           "Ping me on {app} if you want the strategy."),
    ('inv_paycheck', 40, "Tired of living paycheck to paycheck? I was too until "
                          "{mon} months ago — now I make more in a week than I "
                          "used to in a month. All through this system. Message me."),
    ('inv_one_trick', 35, "The banks don't want you to know this one simple trick to "
                           "grow your savings {mult}× faster. I learned it from a "
                           "retired hedge fund guy. DM 'INTEREST' for the guide."),
    ('inv_family_success', 35, "My {family} thought I was crazy when I invested our "
                                "savings — now they thank me every day. ${start} "
                                "turned into ${end} in {mon} days. Anyone can do this."),
    ('inv_defi_yield', 35, "New DeFi protocol offering {pct}% APY on stablecoins, "
                            "audited by {audit}. Early access closing this week — "
                            "visit {url} to lock in your allocation."),
]

for tid, n, body in INVESTMENT_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'investment_crypto', 'body': body, 'n': n})


# ─── ROMANCE SCAMS (target ~2,000) ────────────────────────────────────────
ROMANCE_TEMPLATES = [
    ('rom_wrong_num', 40, "So sorry to bother you — I think I texted the wrong number. "
                           "But now that I'm here, tell me about yourself? I'm {name} "
                           "from {city_far}."),
    ('rom_friend_ref', 40, "Hi is this still {addressee}? I got your contact from my "
                            "friend {friend_name} — she said you'd be someone I might "
                            "really connect with. Would love to chat if you're open."),
    ('rom_matched_ago', 40, "Hey, I think we might have matched on {app} a while back? "
                             "Been meaning to reach out. If not, sorry for the random "
                             "message — you seem interesting from your profile."),
    ('rom_conference', 40, "Hi, I think we met at {event} last month? I didn't get your "
                            "contact properly. I'm {name}, I work in {industry}. Hope "
                            "this is the right number."),
    ('rom_widowed_prof', 40, "You seem genuine, unlike most people on here. I'm a "
                              "widowed {profession} posted with {org} in {country_far}, "
                              "my late husband left me an inheritance I'm having trouble "
                              "accessing from abroad. Would you be open to helping?"),
    ('rom_army_gold', 40, "Hello — I'm {rank} {name} deployed in {conflict_zone}. "
                           "I have gold bars I need help transferring out of the country. "
                           "Will share {pct}% with someone I can trust. Are you serious?"),
    ('rom_forex_partner', 35, "Hey, I saw your profile — I'm {name}, a {market} trader "
                               "based in {city_far}. Made ${monthly} last month. Could "
                               "show you how if you're curious to learn."),
    ('rom_entrepreneur', 35, "I'm a successful entrepreneur based in {city_far} looking "
                              "for a genuine connection. Tired of fake people. Hope you "
                              "don't mind me reaching out — you look like someone real."),
    ('rom_sudden', 30, "I know this might sound sudden but I've been thinking about you "
                        "since we matched. Are you free to move our conversation to "
                        "{app}? Feels more personal there."),
    ('rom_msf_nurse', 30, "Hi, I found your number through a mutual — I'm {name}, a "
                           "nurse working with MSF in {country_far}. Would love to chat "
                           "and get to know you when I have a signal."),
    ('rom_oil_rig', 30, "Hi, working on an oil rig off the coast of {country_far} for "
                         "the next {mon} months. Reaching out because I saw your bio "
                         "and thought we'd get along. What's your story?"),
    ('rom_wedding_photog', 25, "I'm a wedding photographer traveling to {city_far} next "
                                "month for a shoot. Saw your work and thought — this "
                                "person would be great to grab coffee with while I'm there."),
]

for tid, n, body in ROMANCE_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'romance_scam', 'body': body, 'n': n})


# ─── EMERGENCY / GRANDPARENT (target ~1,500) ──────────────────────────────
# CAREFUL: risky-token cap will keep "mom/dad/grandma" limited.
EMERGENCY_TEMPLATES = [
    ('emg_new_num', 40, "Hey it's me — different number, my phone broke and I'm using "
                         "a friend's. Kind of an emergency — my landlord's saying rent "
                         "didn't clear. Can you cover £{amt} this month? I'll pay you "
                         "back next paycheck. Please don't tell {family_other}."),
    ('emg_wallet_abroad', 35, "Hi, I'm stranded in {city_far} — lost my wallet and "
                               "phone in a mugging. I need £{amt} wired urgently for a "
                               "hotel and a flight home. Please use {method}. Don't call, "
                               "I don't have my phone."),
    ('emg_arrested', 35, "This is your {relation} — I got into some trouble here in "
                          "{city_far}. It's a mix-up but I need £{amt} for bail. Please "
                          "buy {gc_brand} gift cards and text me the codes. Please please "
                          "don't tell {family_other}."),
    ('emg_accident', 35, "I've been in a small accident on the {road}, at hospital now. "
                          "Insurance card isn't accepted here. Can you {method} £{amt} "
                          "to this number for the deposit? Explain everything when I "
                          "get home."),
    ('emg_hospital_surgery', 30, "This is your {relation}, I'm in hospital abroad — "
                                  "insurance isn't covering the emergency surgery. Need "
                                  "£{amt} transferred immediately. The situation is time "
                                  "sensitive, please help."),
    ('emg_visa_detained', 30, "I've been detained at {city_far} airport, they're saying "
                               "my visa isn't valid. I need £{amt} wired for a lawyer "
                               "within {hours} hours or they'll deport me. Don't call, "
                               "they took my phone."),
    ('emg_kidnap_fake', 25, "URGENT: your {relation} is with us. Do not contact police. "
                             "Transfer £{amt} to the account below within {hours} hours. "
                             "We will send instructions once we confirm receipt. Any deviation "
                             "will have consequences."),
    ('emg_travel_stuck', 25, "Hey, I got stuck in {city_far} — flight cancelled, hotel "
                              "wouldn't take my card. Can you {method} £{amt} to cover "
                              "one night + a new flight? I'll sort out the card when "
                              "I get back."),
    ('emg_med_bill', 25, "Hi, need your help urgently — my medical bill came back higher "
                          "than my card limit allows. Can you cover £{amt} today? Hospital "
                          "won't discharge me otherwise. I'll pay back next week."),
]

for tid, n, body in EMERGENCY_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'emergency_scam', 'body': body, 'n': n})


# ─── REFUND SCAMS (target ~1,500) ─────────────────────────────────────────
REFUND_TEMPLATES = [
    ('ref_utility_over', 55, "{utility}: your account was overcharged by £{amt} in the "
                              "last billing cycle. Claim your refund at {url} within "
                              "14 days or the credit will be forfeited to unclaimed funds."),
    ('ref_amazon_dupe', 50, "Amazon Refunds: a duplicate charge of £{amt} on order "
                             "#{order_id} was identified. Confirm your card details at "
                             "{url} to process the reversal within 3-5 business days."),
    ('ref_netflix_twice', 50, "Netflix accidentally billed your card twice this month "
                                "(£{amt}). To receive the refund, re-verify your payment "
                                "method at {url}."),
    ('ref_tax_overpaid', 45, "{authority} refund notice: our records show you overpaid "
                              "{tax_type} by £{amt} in the previous tax year. Submit "
                              "bank details at {url} within {days} days to receive your "
                              "refund."),
    ('ref_gov_stimulus', 40, "You qualify for an unclaimed {country} government relief "
                              "payment of ${amt}. Applications close {when}. Verify your "
                              "identity at {url} to receive funds via direct deposit."),
    ('ref_paypal_return', 40, "PayPal: a merchant refund of £{amt} is pending. "
                                "To release the funds to your account, confirm your "
                                "email address at {url} within 48 hours."),
    ('ref_domain_expire_refund', 35, "Your unused domain {domain} qualifies for a "
                                       "prorated refund of ${amt}. Claim within 7 days "
                                       "at {url} before the credit lapses."),
    ('ref_flight_cancel', 35, "{airline}: your recent flight cancellation qualifies you "
                                "for a refund of ${amt}. Complete the reimbursement form "
                                "at {url} within 14 days to receive payment."),
    ('ref_subscription_dupe', 35, "{svc}: we detected a duplicate charge of ${amt} on "
                                    "your recent renewal. Confirm your card at {url} to "
                                    "process the automatic reversal."),
    ('ref_hospital_over', 30, "Your recent insurance claim was reprocessed — an overpayment "
                                "of ${amt} has been identified. Claim at {url} within "
                                "10 days to route to your bank."),
]

for tid, n, body in REFUND_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'refund_scam', 'body': body, 'n': n})


# ─── SEXTORTION (target ~1,000) ───────────────────────────────────────────
SEXTORTION_TEMPLATES = [
    ('sxt_webcam', 40, "I've had access to your device for {mon} months. I have footage "
                        "from your camera and browsing history. Send ${amt} in {crypto} "
                        "to {wallet} within {hours} hours or your entire contact list "
                        "receives everything."),
    ('sxt_history', 40, "Your browsing history has been captured and compiled into a "
                         "very detailed report. Payment of ${amt} in {crypto} to the "
                         "address below within {hours} hours buys my silence."),
    ('sxt_family_threat', 30, "We know what you did. Your workplace and family will "
                               "find out unless we hear from you within {hours} hours. "
                               "Details follow if you fail to respond."),
    ('sxt_ad_infected', 30, "Your device was infected via a compromised ad. Recent "
                             "messages, browser tabs, and camera captures are in our "
                             "possession. Wallet address below — ${amt} in {crypto}, "
                             "or family sees everything."),
    ('sxt_router_hack', 25, "We accessed your home network through your router firmware. "
                             "We have everything from the past {mon} months. Transfer "
                             "${amt} in {crypto} to the address below or the material "
                             "goes to every contact on your device."),
    ('sxt_password_leaked', 25, "Your password {fake_pw} was used to install monitoring "
                                 "software on your devices {mon} months ago. Every "
                                 "keystroke and camera moment is recorded. ${amt} in "
                                 "{crypto} to the wallet below buys full deletion."),
    ('sxt_time_pressure', 20, "The clock is ticking. You have {hours} hours to send "
                                "${amt} to {wallet}. After the deadline the video "
                                "goes public — no negotiations, no second chances."),
    ('sxt_specific_site', 20, "We recorded you on the site you visited on {date}. The "
                                "footage is time-stamped and clear. Pay ${amt} in "
                                "{crypto} within {hours} hours or the video is sent "
                                "to all your contacts."),
]

for tid, n, body in SEXTORTION_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'sextortion', 'body': body, 'n': n})


# ─── THREAT / AUTHORITY (target ~1,500) ───────────────────────────────────
THREAT_TEMPLATES = [
    ('thr_police', 45, "{authority} notice: you are named in an active investigation "
                        "into {crime}. Cease all social media activity and appear at "
                        "the {city} station Monday {time}. Failure results in prosecution. "
                        "File {file_id}."),
    ('thr_court', 45, "Court summons: you were named a defendant in a civil suit filed "
                       "{days} days ago. Ignoring this notice results in default judgment. "
                       "Retrieve documents at {url}."),
    ('thr_ssn', 40, "Your Social Security Number has been flagged for fraudulent activity "
                     "linked to {crime}. To avoid arrest, verify at {url} or press 1 to "
                     "speak with an officer immediately."),
    ('thr_bar', 40, "Notice from your state bar association: a professional-conduct "
                     "complaint has been filed against your license. You have 14 days to "
                     "respond via the portal below or face suspension. {url}"),
    ('thr_tax_arrest', 40, "{authority} FINAL NOTICE: outstanding tax liability of "
                            "£{amt} will result in arrest warrant issued {when}. Settle "
                            "immediately at {url} or call our recovery line."),
    ('thr_immigration', 35, "Immigration Enforcement: your visa status is under review. "
                             "Failure to attend an interview at the {city} office on "
                             "{date} will result in your deportation order being finalised. "
                             "Confirm at {url}."),
    ('thr_dvla_fine', 30, "DVLA notice: unpaid vehicle excise duty of £{amt} for "
                           "registration {plate}. Pay at {url} within 7 days to avoid "
                           "prosecution and vehicle clamping."),
    ('thr_ni_fraud', 30, "{country} National Insurance Bureau: your NI number is under "
                          "investigation for {crime}. Confirm your identity at {url} "
                          "within 5 working days to avoid suspension of benefits."),
    ('thr_arrest_warrant', 30, "Final warning: an arrest warrant will be issued in your "
                                "name in {hours} hours for {crime}. Pay ${amt} at {url} "
                                "to close the case immediately."),
    ('thr_fbi_cyber', 25, "FBI Cyber Division notice: your IP address was flagged in "
                           "connection with {crime}. Immediate cooperation required. "
                           "Confirm identity at {url} within {days} days."),
]

for tid, n, body in THREAT_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'threat_authority', 'body': body, 'n': n})


# ─── GIFT CARD / CEO / IT WORKFLOW (target ~1,000) ────────────────────────
GIFTCARD_TEMPLATES = [
    ('gc_ceo_meeting', 40, "{addressee}, I'm in a boardroom right now and can't take "
                            "calls. Can you grab me {n_cards} {gc_brand} gift cards "
                            "(${amt} each) urgently? Reply is fine. Reimburse tomorrow. "
                            "— {exec_name}, {title}"),
    ('gc_it_mfa', 40, "This is your IT department. To complete your MFA re-registration "
                       "by EOD, please purchase {n_cards} × ${amt} {gc_brand} gift cards "
                       "and email photos of the codes to it-vendor@{fake_domain}. Standard "
                       "vendor procedure."),
    ('gc_charity_urgent', 35, "Hi — quick favor. I'm helping a family in {situation} and "
                               "the fastest way to send them help is {gc_brand} gift cards. "
                               "Can you buy ${amt} worth and text me the codes? I'll "
                               "reimburse before Friday."),
    ('gc_client_gift', 30, "Team, I need help with a same-day client gift. Please buy "
                            "{n_cards} {gc_brand} gift cards (${amt} each) and forward "
                            "the codes to {fake_email}. This needs to happen before {time}. "
                            "Thanks — {exec_name}"),
    ('gc_grandma_repair', 25, "Hi it's your grandmother. My computer is being fixed at "
                               "a repair shop, they want payment in {gc_brand} cards. "
                               "Can you buy ${amt} worth and send me the codes? Love you."),
]
for tid, n, body in GIFTCARD_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'gift_card_workflow', 'body': body, 'n': n})


# ─── ADVANCED / MODERN PHISHING (target ~2,500) ───────────────────────────
PHISHING_TEMPLATES = [
    ('phish_workspace_delete', 55, "{brand}: your workspace '{workspace}' is scheduled "
                                    "for deletion in {hours}h due to unpaid billing. "
                                    "Restore access immediately at {url} before your "
                                    "data is wiped."),
    ('phish_signin_far', 55, "{brand} alert: unusual sign-in from {city_far} detected. "
                              "If this wasn't you, secure your account within 1 hour "
                              "at {url} or funds may be frozen."),
    ('phish_suspended_review', 50, "Your {brand} account has been suspended pending "
                                    "review. Re-enable posting/access privileges at "
                                    "{url} within 48 hours."),
    ('phish_billing_failed', 50, "{brand}: your deployment quota was exceeded and "
                                  "payment failed on your primary card. Update billing "
                                  "at {url} to keep production sites online."),
    ('phish_policy_review', 45, "Your {brand} account is under review for policy "
                                  "violations. Confirm identity at {url} or your account "
                                  "will be de-listed within 24 hours."),
    ('phish_new_login_device', 45, "Someone signed in to your {brand} from a {device} in "
                                    "{city_far}. If this wasn't you, review activity at "
                                    "{url} within 1 hour to prevent account takeover."),
    ('phish_2fa_reset', 40, "{brand}: your two-factor authentication was reset by an "
                             "unrecognised device. If this wasn't you, restore 2FA at "
                             "{url} immediately."),
    ('phish_api_key_leaked', 40, "{brand}: our systems detected your API key was "
                                   "publicly exposed on {leak_source}. Rotate immediately "
                                   "at {url} to prevent unauthorised charges."),
    ('phish_payment_failed_svc', 40, "Your {svc} subscription payment failed. To avoid "
                                       "service interruption, update your payment method "
                                       "at {url} within 24 hours."),
    ('phish_ip_login_alert', 35, "IP {fake_ip} accessed your {brand} account from "
                                  "{city_far} — {browser} on {device}. Not you? Secure "
                                  "at {url} now."),
    ('phish_email_delete_60d', 35, "{brand}: your inbox will be permanently deleted in "
                                    "60 days per new storage policy. Extend retention "
                                    "at {url} within 7 days."),
    ('phish_bank_verify', 35, "{bank}: an outgoing transfer of £{amt} to a new payee "
                                "requires online verification. Complete at {url} within "
                                "1 hour to prevent freeze."),
    ('phish_action_required', 30, "Action required — {brand}: two failed sign-in attempts "
                                    "from {country_far} in the last 10 minutes. Confirm "
                                    "your identity at {url} to keep your account active."),
    ('phish_storage_full', 30, "{brand} storage 99% full — you'll be unable to receive "
                                "new email/files after tomorrow. Add storage at {url} to "
                                "avoid service disruption."),
    ('phish_deleted_recovery', 30, "{brand}: your account was deleted 20 minutes ago per "
                                     "your recovery-email request. If this wasn't you, "
                                     "restore within 12h at {url}."),
]
for tid, n, body in PHISHING_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'modern_phishing', 'body': body, 'n': n})


# ─── COLD-CALL / JOB MULE (target ~500) ───────────────────────────────────
JOB_TEMPLATES = [
    ('job_amazon_reviewer', 40, "Amazon flexible-hours opportunity — earn $500–$900 "
                                 "weekly reviewing products from home. No experience "
                                 "needed. Register at {url} with a small onboarding "
                                 "fee of ${fee}."),
    ('job_linkedin_pa', 40, "We reviewed your LinkedIn profile and want to offer you a "
                             "Personal Assistant role at £{rate}/hr, fully remote. "
                             "First task: purchase equipment (laptop + printer) with "
                             "funds we transfer. Reply if interested."),
    ('job_data_entry', 30, "Congratulations, you have been shortlisted for our Data "
                            "Entry role at ${rate}/hr. Secure the position by completing "
                            "the certification at {url} (${fee} refundable after 30 days)."),
    ('job_product_tester', 30, "Work from home opportunity — {brand} needs product "
                                "testers. Earn $300-500 per day, keep the products too. "
                                "Apply at {url} with a small verification fee of ${fee}."),
    ('job_mystery_shopper', 25, "Mystery shopper role open: $180 per assignment, "
                                 "3 stores per week. To get your first assignment "
                                 "packet, verify identity at {url} (${fee} refundable)."),
]
for tid, n, body in JOB_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'job_mule', 'body': body, 'n': n})


# ─── OTP THEFT (target ~500) ──────────────────────────────────────────────
OTP_TEMPLATES = [
    ('otp_amazon_reply', 40, "Amazon Security: we detected suspicious activity and sent a "
                              "6-digit verification code to your phone. Please reply to "
                              "this message with the code so we can secure your account."),
    ('otp_bank_verify', 35, "This is {bank} fraud team. We messaged a one-time passcode "
                             "to confirm you are the account holder. Read the code back "
                             "to us now to block the pending transfer."),
    ('otp_ig_forward', 35, "{brand} Support: a code was sent to your phone. Forward it "
                            "to us at helpdesk-verify@{fake_domain} within 5 minutes to "
                            "restore your locked account."),
    ('otp_dm_code', 30, "Hey, I'm trying to add you as a backup for {brand}. Can you "
                         "DM me the 6-digit code you'll get in a second? Takes 2 minutes."),
    ('otp_boss_urgent', 25, "It's {exec_name}. I need the verification code you just "
                             "received on your phone — forwarding a wire and it's timing "
                             "out. Text it to this number now."),
]
for tid, n, body in OTP_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'otp_theft', 'body': body, 'n': n})


# ─── ADVANCE FEE / LOTTERY (target ~500) ──────────────────────────────────
AFRICAN_TEMPLATES = [
    ('afr_barrister', 30, "I am Barrister {name} of {city_far}, private counsel to a "
                           "late {country_far} oil executive. My client's family requires "
                           "a trusted foreign partner for a ${millions} million transfer. {pct}% is yours."),
    ('afr_unclaimed_bank', 25, "Good day. I write from Standard Chartered {country_far}. "
                                 "An unclaimed inheritance from a deceased client bearing "
                                 "your surname requires next-of-kin verification urgently."),
    ('afr_un_settlement', 25, "Attention beneficiary — a dormant UN humanitarian "
                                "settlement of ${millions_thousands} has been assigned to you. Kindly "
                                "reply with your full name and phone to initiate release."),
]
for tid, n, body in AFRICAN_TEMPLATES:
    SCAM_TEMPLATES.append({'id': tid, 'category': 'advance_fee', 'body': body, 'n': n})


# ══════════════════════════════════════════════════════════════════════════
# PAIRED LEGIT TWINS — adversarial pairs that share surface vocabulary
# but differ in the discriminative signal
# ══════════════════════════════════════════════════════════════════════════
LEGIT_PAIRS = [
    # Investment pair — real "made money" content from a legit source
    ('inv_pair_property', 25, 'investment_pair', "I finally closed on the rental "
                                                  "property last week — after 3 years "
                                                  "of holding the numbers work out. Not "
                                                  "financial advice, just excited to share."),
    ('inv_pair_newsletter', 25, 'investment_pair', "This week's Stratechery note: what "
                                                    "the {brand} earnings mean for the "
                                                    "broader sector. Free readers get "
                                                    "the first half, paid subscribers get "
                                                    "the full analysis."),
    ('inv_pair_401k', 20, 'investment_pair', "Reminder: your {company} 401(k) enrollment "
                                              "window closes {when}. Log in to your Fidelity "
                                              "account to review or change your contribution "
                                              "rate."),
    # Romance pair — legit cold outreach (recruitment, networking)
    ('rom_pair_recruiter', 25, 'romance_pair', "Hi {addressee}, I got your contact from "
                                                "your former colleague {friend_name}. "
                                                "I'm a recruiter at {company} — we have "
                                                "a Senior Engineer role that fits your "
                                                "background. Interview slots this Wednesday."),
    ('rom_pair_conf_followup', 25, 'romance_pair', "Hi, we met at {event} last month at "
                                                    "the {brand} panel. I'm {name} from "
                                                    "{company}. Following up on our "
                                                    "conversation about your roadmap — "
                                                    "let me know if a 30-min call works."),
    ('rom_pair_alum_intro', 20, 'romance_pair', "Hi, apologies for the cold outreach — "
                                                 "our mutual {friend_name} suggested "
                                                 "connecting. I'm working on a similar "
                                                 "problem to what you built at {company} "
                                                 "and would love your perspective."),
    # Refund pair — real utility statement or subscription refund
    ('ref_pair_utility_real', 30, 'refund_pair', "{utility}: your latest bill of £{amt} "
                                                  "was lower than last month due to reduced "
                                                  "usage. View your statement at your "
                                                  "account portal — no action needed."),
    ('ref_pair_amazon_real', 25, 'refund_pair', "Amazon: your return for order #{order_id} "
                                                 "was received on {date}. Refund of £{amt} "
                                                 "will appear on your original payment "
                                                 "method within 3-5 business days."),
    ('ref_pair_paypal_real', 25, 'refund_pair', "PayPal: refund of £{amt} from {merchant} "
                                                 "has been received. Available in your "
                                                 "PayPal balance. Transaction ID: {txn_id}."),
    # Threat pair — real corporate/legal communication
    ('thr_pair_hmrc_real', 25, 'threat_pair', "HMRC: your self-assessment for 2024/25 is "
                                                "due by 31 January 2026. File online at "
                                                "gov.uk. Late filing incurs a £100 penalty."),
    ('thr_pair_dvla_real', 20, 'threat_pair', "DVLA: your vehicle tax for {plate} is due "
                                                "for renewal on {date}. Renew at gov.uk/"
                                                "vehicle-tax or set up direct debit to "
                                                "avoid future reminders."),
    ('thr_pair_court_real', 15, 'threat_pair', "Notice from HM Courts & Tribunals Service: "
                                                 "the hearing for case {case_id} has been "
                                                 "rescheduled to {date} at {time}. Confirm "
                                                 "attendance via the portal at gov.uk."),
    # Phishing pair — real modern brand notification with genuine URL
    ('phish_pair_notion_real', 25, 'phishing_pair', "Notion: {full_name} invited you to "
                                                     "collaborate on '{workspace}'. Accept "
                                                     "the invite in your Notion inbox or at "
                                                     "notion.so/invites."),
    ('phish_pair_vercel_real', 25, 'phishing_pair', "Vercel: deployment {stripe_id} for "
                                                     "project {gh_user}/{repo} completed "
                                                     "in {mins} seconds. Live at your "
                                                     "production URL."),
    ('phish_pair_github_real', 25, 'phishing_pair', "GitHub: {full_name} added you to the "
                                                     "{gh_user}/{repo} repository as a "
                                                     "collaborator. Accept the invite at "
                                                     "github.com/{gh_user}/{repo}/invitations."),
    # Emergency pair — legit family communication (rare, keep small)
    ('emg_pair_car_real', 15, 'emergency_pair', "Hey, running late — car needed a jump. "
                                                 "Should be at the restaurant by 8:15. "
                                                 "Order me the usual if you're already there."),
    # Gift card pair — legit corporate gift-card-related email (very rare)
    ('gc_pair_bday_real', 10, 'giftcard_pair', "Hi team, {name}'s birthday is Friday. "
                                                "I've ordered a {gc_brand} card via the "
                                                "corporate portal. Sign the card if you're "
                                                "in the office tomorrow."),
]

LEGIT_PAIR_TEMPLATES = [
    {'id': t[0], 'category': t[2], 'body': t[3], 'n': t[1]} for t in LEGIT_PAIRS
]


# ══════════════════════════════════════════════════════════════════════════
# PLACEHOLDER FILL — extends E8-P2's _fill_slots
# ══════════════════════════════════════════════════════════════════════════
CITIES_FAR = ['Dubai', 'Lagos', 'Accra', 'Nairobi', 'Kuala Lumpur', 'Manila',
              'Bangkok', 'Ho Chi Minh City', 'Istanbul', 'Cairo', 'Karachi',
              'Delhi', 'Mumbai', 'Johannesburg', 'Cape Town', 'Abidjan',
              'Dar es Salaam', 'Kampala', 'Casablanca', 'Amman', 'Tel Aviv',
              'Riyadh', 'Doha', 'Beirut', 'Jakarta', 'Chennai', 'Hanoi',
              'Colombo', 'Dhaka', 'Islamabad', 'Nur-Sultan', 'Tashkent',
              'Baku', 'Yerevan', 'Tbilisi']
COUNTRIES_FAR = ['Nigeria', 'Ghana', 'Kenya', 'Malaysia', 'Philippines',
                 'Thailand', 'Vietnam', 'Turkey', 'Egypt', 'Pakistan',
                 'India', 'South Africa', 'Sierra Leone', 'Ivory Coast']
CONFLICT_ZONES = ['Afghanistan', 'Syria', 'Yemen', 'Libya', 'Somalia', 'Sudan']
RANKS = ['Captain', 'Major', 'Colonel', 'Lieutenant', 'Sergeant']
APPS = ['WhatsApp', 'Telegram', 'Signal', 'Instagram DM']
EVENTS = ['SaaStr', 'the Y Combinator meetup', 'the design conference',
          'DevOps Days', 'the AI summit', 'the fintech mixer']
INDUSTRIES = ['tech', 'finance', 'design', 'marketing', 'consulting']
PROFESSIONS_ROM = ['nurse', 'engineer', 'consultant', 'trader', 'lawyer']
ORGS_ROM = ['UNICEF', 'MSF', 'Red Cross', 'WHO']
PROFESSIONS_INV = ['portfolio manager', 'hedge fund analyst', 'wealth advisor',
                    'trading desk head', 'commodities trader']
MARKETS = ['forex', 'crypto', 'small caps', 'options', 'commodities', 'gold']
STRATEGIES = ['momentum', 'arbitrage', 'AI-signal', 'quant', 'trend-following']
FRIEND_NAMES = ['Rachel', 'Michael', 'Sofia', 'James', 'Priya', 'David',
                'Sarah', 'Chen', 'Marcus', 'Aiko', 'Elena', 'Diego', 'Amara',
                'Sanjay', 'Hana', 'Beatriz', 'Omar', 'Nia', 'Rohan', 'Kai',
                'Amina', 'Theo', 'Lena', 'Jasper', 'Rania', 'Finn', 'Anya',
                'Levi', 'Nour', 'Idris', 'Mira', 'Arun', 'Elise', 'Kian',
                'Selin', 'Callum', 'Yara', 'Fatima', 'Liam', 'Zara', 'Noah']
FAMILY_MEMBERS = ['mom', 'dad', 'sister', 'brother', 'wife', 'husband']
RELATIONS = ['grandson', 'granddaughter', 'nephew', 'niece', 'son', 'daughter']
ROADS = ['M6', 'M25', 'I-95', 'A40', 'A1', '405 freeway']
METHODS = ['Zelle', 'Cash App', 'wire transfer', 'Venmo', 'Western Union']
CRIMES = ['identity theft', 'wire fraud', 'money laundering', 'tax evasion',
          'cybercrime', 'illegal cash withdrawal']
EXEC_NAMES = ['Michael Chen', 'Sarah Kowalski', 'James Ahmed', 'Priya Patel',
              'Marcus Silva', 'David Kim', 'Emma Brown', 'Chen Liu',
              'Aisha Patel', 'Ethan Suzuki', 'Rachel Fernandez',
              'Noah Okafor', 'Yuki Tanaka', 'Miles Bergstrom', 'Beatriz Alonso',
              'Omar Al-Farsi', 'Rohan Kumar', 'Elena Novak', 'Kai Johansson']
EXEC_TITLES = ['CEO', 'COO', 'CFO', 'VP Sales', 'Managing Director']
WORKSPACES = ['Product Team', 'Design Ops', 'Engineering Wiki', 'Q3 Planning',
              'Marketing HQ', 'Founders']
COMPANIES = ['Acme Inc', 'Northstar Labs', 'Riverstone Ltd', 'Halo Digital',
             'Bluewave Media', 'Foundry Design', 'Meadowlark Records']
LEAK_SOURCES = ['GitHub', 'a public S3 bucket', 'a paste site', 'HackerNews']
AIRLINES = ['British Airways', 'Delta', 'United', 'Lufthansa', 'Emirates',
            'Air France', 'KLM']
SVCS = ['Netflix', 'Spotify', 'Adobe Creative Cloud', 'Dropbox Plus',
        'Notion Plus', 'GitHub Copilot']
BANKS = ['Chase', 'HSBC', 'Barclays', 'Wells Fargo', 'Monzo', 'Revolut',
         'Bank of America', 'Citi']
TAX_TYPES = ['income tax', 'VAT', 'National Insurance', 'council tax',
             'capital gains', 'PAYE']
COUNTRIES_TAX = ['UK', 'US', 'Canadian', 'Australian', 'Irish']
SITUATIONS = ['financial hardship', 'a medical emergency', 'a house fire',
              'flood displacement']
FAKE_DOMAINS = ['secure-vendor.co', 'it-mgmt.link', 'corporate-vendor.click',
                'hr-portal.xyz', 'vendor-support.online']


def _fill_scam_slots(body: str) -> str:
    """Extends the shared _fill_slots with scam-specific placeholders."""
    name = rand_name()
    full_name = rand_full_name()
    city, country = pick_region()
    # Pick brand FIRST so {url} can mimic the same brand (fixes URL-brand
    # mismatch flagged in E8-P8 review — real phishing URLs mimic the
    # impersonated brand, not a random one).
    brand = RNG.choice(MODERN_BRANDS)
    values = {
        'addressee':       name,
        'name':            name,
        'full_name':       full_name,
        'friend_name':     RNG.choice(FRIEND_NAMES),
        'exec_name':       RNG.choice(EXEC_NAMES),
        'title':           RNG.choice(EXEC_TITLES),
        'city':            city,
        'country':         country,
        'city_far':        RNG.choice(CITIES_FAR),
        'country_far':     RNG.choice(COUNTRIES_FAR),
        'conflict_zone':   RNG.choice(CONFLICT_ZONES),
        'rank':            RNG.choice(RANKS),
        'app':             RNG.choice(APPS),
        'event':           RNG.choice(EVENTS),
        'industry':        RNG.choice(INDUSTRIES),
        'profession':      RNG.choice(PROFESSIONS_ROM),
        'org':             RNG.choice(ORGS_ROM),
        'device':          RNG.choice(DEVICES),
        'browser':         RNG.choice(BROWSERS),
        'gc_brand':        rand_gift_card_brand(),
        'method':          RNG.choice(METHODS),
        'road':            RNG.choice(ROADS),
        'relation':        RNG.choice(RELATIONS),
        'family_other':    RNG.choice(FAMILY_MEMBERS),
        'family':          RNG.choice(['wife', 'husband', 'family']),
        'authority':       rand_authority(),
        'crime':           RNG.choice(CRIMES),
        'workspace':       RNG.choice(WORKSPACES),
        'company':         RNG.choice(COMPANIES),
        'utility':         rand_modern_utility(),
        'airline':         RNG.choice(AIRLINES),
        'svc':             RNG.choice(SVCS),
        'bank':            RNG.choice(BANKS),
        'brand':           brand,
        'tax_type':        RNG.choice(TAX_TYPES),
        'country':         RNG.choice(COUNTRIES_TAX),
        'situation':       RNG.choice(SITUATIONS),
        'leak_source':     RNG.choice(LEAK_SOURCES),
        'fake_domain':     RNG.choice(FAKE_DOMAINS),
        'fake_email':      f'accounts-payable@{RNG.choice(FAKE_DOMAINS)}',
        # Amount + numeric
        'amt':             rand_amount_ish(45, 4800),
        'amount':          rand_amount_ish(50, 3500),
        'min_inv':         str(RNG.choice([200, 500, 1000, 2500])),
        'start':           str(RNG.choice([200, 500, 1000, 2500])),
        'end':             f'{RNG.randint(4, 60)}00',
        'mon':             str(RNG.randint(2, 12)),
        'months':          str(RNG.randint(2, 12)),
        'monthly':         str(RNG.randint(2000, 45000)),
        'ret':             rand_investment_return(),
        'pct':             str(RNG.randint(3, 45)),
        'mult':            str(RNG.choice([3, 5, 10, 15, 20])),
        'years':           str(RNG.randint(10, 35)),
        'n_students':      str(RNG.randint(3, 12)),
        'n_helped':        str(RNG.randint(80, 850)),
        'n_cards':         str(RNG.choice([3, 5, 8, 10])),
        'total_recovered': f'{RNG.randint(2, 24)}M',
        'fee':             str(RNG.choice([29, 49, 75, 99, 199])),
        'rate':            str(RNG.randint(25, 65)),
        'hours':           str(RNG.choice([12, 24, 48, 72])),
        'days':            str(RNG.randint(3, 14)),
        'file_id':         f'{RNG.choice(["2026","2025","F"])}-{RNG.randint(10000,99999)}',
        'case_id':         f'{RNG.choice(["CV","EX","CR"])}-{RNG.randint(10000,99999)}',
        'plate':           ''.join(RNG.choices(string.ascii_uppercase, k=2)) + str(RNG.randint(10,99)) + ''.join(RNG.choices(string.ascii_uppercase, k=3)),
        'fake_ip':         '.'.join(str(RNG.randint(1,254)) for _ in range(4)),
        'fake_pw':         RNG.choice(['sunshine1', 'monkey123', 'letmein!', 'summer24']),
        'when':            RNG.choice(['tomorrow', 'this Friday', 'end of week', 'in 24 hours']),
        'day':             RNG.choice(['Monday', 'Tuesday', 'Wednesday', 'Friday']),
        'time':            f'{RNG.randint(8, 20):02d}:00',
        'decimal':         str(RNG.randint(1, 8)).zfill(3),
        'code':            RNG.choice(['ALLOCATE', 'RESERVE', 'IN', 'YES']),
        'public_price':    f'0.{RNG.randint(5, 60):02d}',
        'audit':           RNG.choice(['CertiK', 'Trail of Bits', 'Quantstamp', 'PeckShield']),
        'wallet':          rand_crypto_wallet(),
        'crypto':          RNG.choice(CRYPTO_TOKENS),
        'meme_coin_name':  RNG.choice(['Solana meme coin', 'Base memecoin',
                                        'Pepe fork', 'Doge derivative',
                                        'Layer-2 utility token', 'BNB Chain gem',
                                        'AI-agent token']),
        'strategy':        RNG.choice(STRATEGIES),
        'market':          RNG.choice(MARKETS),
        'audit':           RNG.choice(['CertiK', 'Trail of Bits', 'Quantstamp']),
        'spots_left':      str(RNG.randint(2, 7)),
        'domain':          f'{RNG.choice(["mystartup","hiring","product","brand"])}.com',
        'merchant':        RNG.choice(['Northgate Studios', 'Bluewave Media',
                                        'Halo Digital', 'Foundry Design']),
        'stripe_id':       'ch_' + ''.join(RNG.choices(string.ascii_lowercase + string.digits, k=16)),
        'gh_user':         RNG.choice(['octocat', 'acme-labs', 'northstar-io']),
        'repo':            RNG.choice(['api-gateway', 'design-system', 'docs',
                                        'auth-service']),
        'mins':            str(RNG.randint(15, 60)),
        'order_id':        rand_amazon_order_id(),
        'txn_id':          rand_txn_id(),
        'date':            rand_date(),
        'url':             '',   # filled below
        'old_job':         RNG.choice(['corporate life', 'my sales job', 'consulting',
                                        'my day job']),
        'airdrop':         str(RNG.choice([1200, 2400, 4800])),
    }
    # url — fake phishing URL that MIMICS the same brand as {brand} (so
    # "Notion: your workspace deletion..." links to notion-billing.co, not
    # to a random unrelated brand). Real phishing always brand-matches.
    values['url'] = rand_fake_url(brand_hint=brand)
    # Realistic large-money formatting for advance-fee scams
    values['millions'] = RNG.choice(['3.5', '5.2', '8.4', '12.6', '18.5',
                                     '24.7', '35.1', '42.8', '56.3', '68.9',
                                     '85.4', '120', '145'])
    values['millions_thousands'] = f'{RNG.randint(2, 45)},{RNG.randint(100, 999):03d},{RNG.randint(100, 999):03d}'
    return body.format(**values)


def _fill_pair_slots(body: str) -> str:
    """Placeholder fill for LEGIT paired templates — uses REAL brand URLs."""
    name = rand_name()
    city, country = pick_region()
    values = {
        'addressee':       name,
        'name':            name,
        'full_name':       rand_full_name(),
        'friend_name':     RNG.choice(FRIEND_NAMES),
        'exec_name':       RNG.choice(EXEC_NAMES),
        'city':            city,
        'country':         country,
        'company':         RNG.choice(COMPANIES),
        'brand':           RNG.choice(['Nvidia', 'Apple', 'Microsoft', 'Google', 'Amazon']),
        'workspace':       RNG.choice(WORKSPACES),
        'utility':         rand_modern_utility(),
        'event':           RNG.choice(EVENTS),
        'amt':             rand_amount_ish(20, 400),
        'gc_brand':        rand_gift_card_brand(),
        'order_id':        rand_amazon_order_id(),
        'txn_id':          rand_txn_id(),
        'merchant':        RNG.choice(['Northgate Studios', 'Halo Digital']),
        'stripe_id':       'ch_' + ''.join(RNG.choices(string.ascii_lowercase + string.digits, k=16)),
        'gh_user':         RNG.choice(['octocat', 'acme-labs', 'northstar-io']),
        'repo':            RNG.choice(['api-gateway', 'design-system', 'docs']),
        'plate':           ''.join(RNG.choices(string.ascii_uppercase, k=2)) + str(RNG.randint(10,99)),
        'when':            RNG.choice(['31 August 2026', '15 September 2026', 'next Friday']),
        'date':            rand_date(),
        'time':            f'{RNG.randint(9, 17):02d}:00',
        'mins':            str(RNG.randint(15, 45)),
        'case_id':         f'{RNG.choice(["CV","EX"])}-{RNG.randint(10000,99999)}',
    }
    return body.format(**values)


# ══════════════════════════════════════════════════════════════════════════
# GENERATION + VALIDATION
# ══════════════════════════════════════════════════════════════════════════
def main():
    print(f'=== E8-P8 synthetic scam corpus generation ===')
    scam_target = sum(t['n'] for t in SCAM_TEMPLATES)
    pair_target = sum(t['n'] for t in LEGIT_PAIR_TEMPLATES)
    print(f'  scam templates:      {len(SCAM_TEMPLATES)}   target: ~{scam_target:,}')
    print(f'  legit-pair templates: {len(LEGIT_PAIR_TEMPLATES)}  target: ~{pair_target:,}')
    print(f'  risky-token caps:    {len(RISKY_TOKEN_CAPS)} monitored')
    print()

    # ── Scams ─────────────────────────────────────────────────────────────
    scams: list = []
    rejects: Counter = Counter()
    seen: set = set()
    for t in SCAM_TEMPLATES:
        # Scale every template's target 5× to reach the 15-20k goal — richer
        # placeholder pools + longer attempt budget lets templates that CAN
        # produce more variations do so.
        target = t['n'] * 5
        attempts = 0
        wins = 0
        while wins < target and attempts < target * 6:
            attempts += 1
            try:
                text = _fill_scam_slots(t['body'])
            except KeyError as e:
                rejects[f'template_missing_slot:{e}'] += 1
                break
            if text in seen:
                rejects['dup'] += 1
                continue
            # Safety check — must NOT be caught by legit-side validators
            # (scam messages naturally contain dangerous patterns; the E8-P2
            # legit validator rejects those, which is the opposite of what
            # we want here). Instead do our own quick sanity: reject only
            # if text is < 30 chars or contains no recognisable substance.
            if len(text) < 30 or text.strip().count(' ') < 3:
                rejects['too_short_or_thin'] += 1
                continue
            # Token guardrail — refuse if adding would push a risky token
            # past its cap
            if not _risky_tokens_ok(text):
                rejects['risky_token_cap'] += 1
                continue
            seen.add(text)
            _record_tokens(text)
            scams.append({
                'text':        text,
                'label':       1,   # SCAM
                'category':    t['category'],
                'template_id': t['id'],
                'has_url':     'http' in text,
            })
            wins += 1

    # ── Paired legit twins ────────────────────────────────────────────────
    print(f'\nGenerating paired legit twins...')
    legit_pairs: list = []
    pair_seen: set = set()
    for t in LEGIT_PAIR_TEMPLATES:
        target = t['n'] * 4    # scale pairs similarly
        attempts = 0
        wins = 0
        while wins < target and attempts < target * 4:
            attempts += 1
            try:
                text = _fill_pair_slots(t['body'])
            except KeyError as e:
                rejects[f'pair_missing_slot:{e}'] += 1
                break
            if text in pair_seen or text in seen:
                rejects['pair_dup'] += 1
                continue
            if len(text) < 30:
                rejects['pair_too_short'] += 1
                continue
            # Reuse E8-P2 legit validator on pairs — they must pass as legit
            ok, reason = _p2_validate(text)
            if not ok:
                rejects[f'pair_validator:{reason}'] += 1
                continue
            pair_seen.add(text)
            legit_pairs.append({
                'text':        text,
                'label':       0,   # LEGIT
                'category':    t['category'],
                'template_id': t['id'],
                'has_url':     'http' in text or '.com' in text,
            })
            wins += 1

    df_scam = pd.DataFrame(scams)
    df_pair = pd.DataFrame(legit_pairs)

    print(f'\n── Generation stats ──')
    print(f'  scam messages kept:  {len(df_scam):,}')
    print(f'  legit pairs kept:    {len(df_pair):,}')
    print(f'  by scam category:')
    for cat, n in df_scam.category.value_counts().items():
        print(f'    {cat:20s} {n:>5}')
    print(f'  by pair category:')
    for cat, n in df_pair.category.value_counts().items():
        print(f'    {cat:20s} {n:>5}')
    print(f'\n  rejections:')
    for r, n in rejects.most_common():
        print(f'    {r:26s} {n:>5}')

    print(f'\n── Risky-token audit ──')
    print(f'  {"token":24s}  {"count":>6s}  {"share of scam":>14s}  cap')
    for tok, cap in RISKY_TOKEN_CAPS.items():
        share = _token_counter[tok] / max(len(df_scam), 1)
        marker = '⚠' if share > cap else '✓'
        print(f'  {tok:24s}  {_token_counter[tok]:>6}  {share*100:>12.1f}%   {cap*100:.0f}%  {marker}')

    # ── Write outputs ─────────────────────────────────────────────────────
    df_scam.to_parquet(os.path.join(OUT_DIR, 'scam_dataset.parquet'), index=False)
    df_pair.to_parquet(os.path.join(OUT_DIR, 'legit_pairs_dataset.parquet'), index=False)

    # Stratified samples for review — up to 3 per template
    def stratified_sample(df: pd.DataFrame, k: int = 3) -> pd.DataFrame:
        parts = []
        for tid, g in df.groupby('template_id'):
            parts.append(g.sample(min(len(g), k), random_state=42))
        return pd.concat(parts, ignore_index=True) if parts else df

    lines = []
    lines.append('══════════════════════════════════════════════════════════════════════')
    lines.append('  SCAM SAMPLES (3 per template)')
    lines.append('══════════════════════════════════════════════════════════════════════')
    for _, r in stratified_sample(df_scam, 3).iterrows():
        lines.append(f'[{r["category"]}]  [{r["template_id"]}]')
        lines.append(r['text'])
        lines.append('')
    lines.append('\n══════════════════════════════════════════════════════════════════════')
    lines.append('  LEGIT-PAIR SAMPLES (3 per template)')
    lines.append('══════════════════════════════════════════════════════════════════════')
    for _, r in stratified_sample(df_pair, 3).iterrows():
        lines.append(f'[{r["category"]}]  [{r["template_id"]}]')
        lines.append(r['text'])
        lines.append('')
    with open(os.path.join(OUT_DIR, 'samples.txt'), 'w') as f:
        f.write('\n'.join(lines))
    print(f'\nWrote:')
    print(f'  {OUT_DIR}/scam_dataset.parquet         ({len(df_scam):,} rows)')
    print(f'  {OUT_DIR}/legit_pairs_dataset.parquet  ({len(df_pair):,} rows)')
    print(f'  {OUT_DIR}/samples.txt')

    stats = {
        'n_scam':          int(len(df_scam)),
        'n_legit_pairs':   int(len(df_pair)),
        'n_scam_templates': len(SCAM_TEMPLATES),
        'n_pair_templates': len(LEGIT_PAIR_TEMPLATES),
        'scam_per_category': {k: int(v) for k, v in df_scam.category.value_counts().items()},
        'pair_per_category': {k: int(v) for k, v in df_pair.category.value_counts().items()},
        'rejections':      dict(rejects),
        'risky_tokens':    {tok: {'count': _token_counter[tok],
                                    'share': round(_token_counter[tok]/max(len(df_scam),1), 4),
                                    'cap': cap}
                             for tok, cap in RISKY_TOKEN_CAPS.items()},
    }
    with open(os.path.join(OUT_DIR, 'generation_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    print(f'  {OUT_DIR}/generation_stats.json')


if __name__ == '__main__':
    main()
