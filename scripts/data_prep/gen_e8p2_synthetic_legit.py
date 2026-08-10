"""
E8-P2 — Synthetic legitimate data generation pipeline.

Goal
----
Fill the exact region of the feature space where the E7-P1-full classifier
currently produces false positives: modern transactional legitimate messages
that look phishing-adjacent (shipping/order/security/banking/OTP/subscription
notifications) but are objectively legitimate.

Design principles (per project spec)
-----------------------------------
* Template-based, not random. ~60 hand-crafted realistic templates.
* ~40 variations per template via placeholder substitution. Target 2,000-3,000
  high-quality messages, NOT 20k random ones.
* Brand-diverse (25+ real brands, no Amazon monoculture).
* Near-boundary: each message should look phishing-adjacent enough that a
  human might glance-mistake it for one — while being genuinely legit.
* URLs ONLY use official domains (amazon.com, netflix.com, etc.).
* Validation reuses the rule-engine regex helpers so no synthetic message
  can contain dangerous action patterns (credential ask, OTP theft, gift-
  card demand, crypto seed ask, remote-access install request).
* Do NOT retrain, merge, or evaluate here — this script only generates.

Output
------
data/synthetic_legit/e8p2/
  dataset.parquet         — final validated dataset (columns: text, label,
                            category, brand, template_id, has_url)
  samples.txt             — 200 sampled messages for human review
  rejection_report.json   — how many candidates each validator rejected
  generation_stats.json   — per-category / per-brand counts
"""
from __future__ import annotations

import json
import os
import random
import re
import string
import sys
from collections import Counter

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Reuse the rule engine's own regex helpers so validation and rule
# detection stay in sync forever.
from src.rule_engine.patterns import (
    has_credential_request,
    has_otp_theft,
    has_gift_card_payment,
    has_crypto_seed_request,
    has_remote_access_request,
)

OUT_DIR = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p2')
os.makedirs(OUT_DIR, exist_ok=True)

RNG = random.Random(42)   # deterministic


# ══════════════════════════════════════════════════════════════════════════
# Placeholder value pools
# ══════════════════════════════════════════════════════════════════════════
# ── Geographic pools (region-consistent city+country pairing) ────────────
# When a template needs both a city and a country, they must come from the
# same region — no more "Paris, United States". `pick_region()` returns a
# single region so both placeholders draw from the same pool.
REGION_POOLS: list = [
    {'country': 'United Kingdom',
     'cities': ['London', 'Manchester', 'Birmingham', 'Edinburgh', 'Bristol',
                'Leeds', 'Glasgow', 'Cardiff', 'Liverpool', 'Sheffield',
                'Reading', 'Newcastle', 'Cambridge', 'Oxford', 'Nottingham']},
    {'country': 'United States',
     'cities': ['New York', 'San Francisco', 'Chicago', 'Austin', 'Seattle',
                'Boston', 'Denver', 'Los Angeles', 'Atlanta', 'Portland',
                'Miami', 'Dallas', 'Minneapolis', 'Phoenix', 'Nashville']},
    {'country': 'Germany',      'cities': ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne']},
    {'country': 'Netherlands',  'cities': ['Amsterdam', 'Rotterdam', 'Utrecht', 'The Hague']},
    {'country': 'France',       'cities': ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Bordeaux']},
    {'country': 'Spain',        'cities': ['Barcelona', 'Madrid', 'Valencia', 'Seville', 'Bilbao']},
    {'country': 'Italy',        'cities': ['Rome', 'Milan', 'Turin', 'Florence', 'Bologna']},
    {'country': 'Ireland',      'cities': ['Dublin', 'Cork', 'Galway']},
    {'country': 'Denmark',      'cities': ['Copenhagen', 'Aarhus']},
    {'country': 'Sweden',       'cities': ['Stockholm', 'Gothenburg', 'Malmö']},
    {'country': 'Austria',      'cities': ['Vienna', 'Salzburg', 'Graz']},
    {'country': 'Czechia',      'cities': ['Prague', 'Brno']},
    {'country': 'Poland',       'cities': ['Warsaw', 'Kraków', 'Wrocław']},
    {'country': 'Portugal',     'cities': ['Lisbon', 'Porto']},
    {'country': 'Switzerland',  'cities': ['Zurich', 'Geneva', 'Bern']},
    {'country': 'Canada',       'cities': ['Toronto', 'Vancouver', 'Montreal', 'Calgary']},
    {'country': 'Australia',    'cities': ['Sydney', 'Melbourne', 'Brisbane', 'Perth']},
]


def pick_region() -> tuple:
    """Return (city, country) drawn from the same region."""
    region = RNG.choice(REGION_POOLS)
    return RNG.choice(region['cities']), region['country']


# Legacy exports kept for backwards compat (only used internally now)
FIRST_NAMES = [
    'Ameer', 'Sarah', 'Michael', 'Priya', 'Jamal', 'Emma', 'Chen', 'Sofia',
    'Marcus', 'Aiko', 'David', 'Fatima', 'Liam', 'Zara', 'Noah', 'Aisha',
    'Ethan', 'Yuki', 'Ryan', 'Olivia', 'Kwame', 'Isla', 'Diego', 'Amara',
    'Sanjay', 'Hana', 'Miles', 'Beatriz', 'Omar', 'Nia', 'Rohan', 'Elena',
    'Kai', 'Amina', 'Theo', 'Lena', 'Jasper', 'Rania', 'Finn', 'Anya',
    'Levi', 'Nour', 'Idris', 'Mira', 'Arun', 'Elise', 'Kian', 'Selin',
    'Callum', 'Yara',
]
LAST_NAMES = [
    'Chen', 'Patel', 'Nguyen', 'Rodriguez', 'Kim', 'Ahmed', 'Silva', 'Kumar',
    'Brown', 'Johansson', 'Okafor', 'Yılmaz', 'Suzuki', 'Al-Farsi', 'Novak',
    'Kowalski', 'Alonso', 'Tanaka', 'Bergstrom', 'Fernandez',
]
CITIES_UK = ['London', 'Manchester', 'Birmingham', 'Edinburgh', 'Bristol',
             'Leeds', 'Glasgow', 'Cardiff', 'Liverpool', 'Sheffield',
             'Reading', 'Newcastle', 'Cambridge', 'Oxford', 'Nottingham']
CITIES_US = ['New York', 'San Francisco', 'Chicago', 'Austin', 'Seattle',
             'Boston', 'Denver', 'Los Angeles', 'Atlanta', 'Portland',
             'Miami', 'Dallas', 'Minneapolis', 'Phoenix', 'Nashville']
CITIES_EU = ['Berlin', 'Amsterdam', 'Paris', 'Barcelona', 'Munich',
             'Copenhagen', 'Dublin', 'Rome', 'Vienna', 'Prague',
             'Stockholm', 'Lisbon', 'Warsaw', 'Zurich']
DEVICES  = ['MacBook Pro', 'MacBook Air', 'iPhone 15', 'iPhone 14 Pro',
            'iPad Air', 'Windows PC', 'Pixel 8', 'Galaxy S24',
            'Chromebook', 'Surface Laptop', 'iPad Pro']
BROWSERS = ['Chrome on macOS', 'Safari on iOS', 'Firefox on Windows',
            'Edge on Windows', 'Chrome on Windows', 'Safari on macOS',
            'Chrome on Android', 'Samsung Internet']
CURRENCIES = ['£', '$', '€']

PRODUCTS_TECH = [
    'Sony WH-1000XM5 Wireless Headphones', 'Anker USB-C Hub',
    'Apple AirPods Pro (2nd gen)', 'Logitech MX Master 3S',
    'Kindle Paperwhite (16GB)', 'Samsung T7 Portable SSD 1TB',
    'Bose QuietComfort Earbuds', 'Fitbit Charge 6',
    'Nintendo Switch OLED', 'Nespresso Vertuo Next',
]
PRODUCTS_HOME = [
    'Dyson V15 Detect', 'IKEA Malm Bedside Table', 'Instant Pot Duo 7-in-1',
    'Le Creuset 24cm Casserole', 'Philips Hue Starter Kit',
    'Nest Learning Thermostat', 'Ring Video Doorbell Pro',
]
FOOD_ITEMS = [
    'Pret A Manger', 'Starbucks', 'Wagamama', 'Nando\'s', 'Byron Burger',
    'Five Guys', 'Pizza Express', 'Costa Coffee', 'Leon', 'YO! Sushi',
    'Chipotle', 'Panera Bread', 'Sweetgreen', 'Cava', 'Blue Bottle Coffee',
]
STORES = [
    'Tesco Extra Kensington', 'Sainsbury\'s Local', 'M&S Food',
    'Whole Foods Market', 'Target', 'Walmart Neighborhood Market',
    'Trader Joe\'s', 'Waitrose', 'Aldi',
]
STREAMING_TITLES = [
    'Wednesday: Season 2', 'The Bear: Season 3', 'Slow Horses: Season 4',
    'Fallout: Season 1', 'Only Murders in the Building: Season 4',
]
NEWSLETTERS = [
    'Weekly Digest', 'Product Updates', 'What\'s New This Week',
    'The Monday Briefing', 'This Week in Design',
]


def rand_name() -> str:
    return RNG.choice(FIRST_NAMES)


def rand_full_name() -> str:
    return f'{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}'


def rand_city() -> str:
    return RNG.choice(CITIES_UK + CITIES_US + CITIES_EU)


def rand_country() -> str:
    return RNG.choice(['United Kingdom', 'United States', 'Germany',
                        'France', 'Netherlands', 'Ireland', 'Canada',
                        'Australia', 'Spain', 'Sweden'])


def rand_amount(low: float = 3.0, high: float = 350.0, cents: bool = True) -> str:
    v = RNG.uniform(low, high)
    return f'{v:.2f}' if cents else f'{int(v)}'


# ── Category-specific realistic amount ranges ────────────────────────────
# Templates declare an `amount_kind` (or `balance_kind`) so subscription /
# order / bank / P2P values fall in realistic ranges instead of a uniform
# [3, 480]. Values outside a service's real pricing corridor are the kind
# of "off-by-a-lot" clue that would tip off a human reader — we want
# amounts that read as plausibly real bills / receipts / transfers.
AMOUNT_KINDS: dict = {
    # ── Consumer subscriptions (monthly) ─────────────────────────────────
    'netflix_month':          (6.99,  22.99),
    'spotify_month':          (10.99, 16.99),
    'apple_music_month':      (10.99, 16.99),
    'icloud_month':           (0.99,   9.99),
    'youtube_premium':        (13.99, 22.99),
    'adobe_creative':         (22.99, 59.99),
    'notion_plus':            (8.00,  20.00),
    'dropbox_plus':           (11.99, 21.99),
    'apple_app_sub':          (0.99,  14.99),
    'google_play_sub':        (0.99,  14.99),
    # ── Food delivery (a single order) ───────────────────────────────────
    'doordash_order':         (12.00, 65.00),
    'ubereats_order':         (10.00, 60.00),
    # ── E-commerce (a single order) ──────────────────────────────────────
    'amazon_order':           (8.00,  480.00),
    'etsy_order':             (12.00, 120.00),
    'shopify_order':          (20.00, 350.00),
    'stripe_receipt':         (20.00, 500.00),
    # ── P2P / bank transfers ─────────────────────────────────────────────
    'paypal_transfer':        (15.00,  400.00),
    'venmo_transfer':         (8.00,   250.00),
    'wise_transfer':          (50.00,  3000.00),
    'revolut_transfer':       (15.00,  500.00),
    'stripe_payout':          (100.00, 2500.00),
    'starling_incoming':      (25.00,  1500.00),
    'barclays_outgoing':      (25.00,  2000.00),
    'wells_fargo_deposit':    (100.00, 4500.00),
    # ── Card / bank activity (single card purchase) ──────────────────────
    'bank_debit_purchase':    (3.00,   180.00),
    'low_bal_threshold':      (50.00,  500.00),
    # ── Fallback ─────────────────────────────────────────────────────────
    'generic':                (3.00,   480.00),
}
BALANCE_KINDS: dict = {
    'checking':          (200.00,   12_000.00),
    'boa_low_balance':   (20.00,     280.00),
    'monzo_running':     (30.00,    3_500.00),
    'starling_running':  (75.00,   10_000.00),
    'generic':           (50.00,   12_000.00),
}


import math


# ── Special-case amount distributions ────────────────────────────────────
# For a few kinds the uniform distribution produces unrealistic values
# (e.g. Amazon orders are heavy-tailed — most orders are small; a uniform
# [8, 480] over-represents mid/large orders). These generators produce
# more faithful distributions and are consulted before AMOUNT_KINDS.
def _amount_amazon_order() -> str:
    # Log-normal: median ~$35, long tail up to ~$500. Matches how real
    # order values are distributed (Pareto-like: many small, few large).
    v = RNG.lognormvariate(math.log(35.0), 0.85)
    return f'{max(4.99, min(499.00, v)):.2f}'


def _amount_shopify_order() -> str:
    v = RNG.lognormvariate(math.log(45.0), 0.75)
    return f'{max(9.00, min(349.00, v)):.2f}'


def _amount_etsy_order() -> str:
    v = RNG.lognormvariate(math.log(28.0), 0.65)
    return f'{max(9.00, min(180.00, v)):.2f}'


def _amount_doordash_order() -> str:
    v = RNG.gauss(28.0, 12.0)      # more concentrated around a lunch/dinner order
    return f'{max(10.00, min(75.00, v)):.2f}'


def _amount_ubereats_order() -> str:
    v = RNG.gauss(26.0, 11.0)
    return f'{max(9.00, min(70.00, v)):.2f}'


def _amount_bank_debit_purchase() -> str:
    # Card purchases: strong right-skew (mostly small groceries/coffees).
    v = RNG.lognormvariate(math.log(18.0), 0.85)
    return f'{max(2.50, min(220.00, v)):.2f}'


SPECIAL_AMOUNT_GENERATORS: dict = {
    'amazon_order':          _amount_amazon_order,
    'shopify_order':         _amount_shopify_order,
    'etsy_order':            _amount_etsy_order,
    'doordash_order':        _amount_doordash_order,
    'ubereats_order':        _amount_ubereats_order,
    'bank_debit_purchase':   _amount_bank_debit_purchase,
}


def rand_amount_kind(kind: str) -> str:
    fn = SPECIAL_AMOUNT_GENERATORS.get(kind)
    if fn is not None:
        return fn()
    lo, hi = AMOUNT_KINDS.get(kind, AMOUNT_KINDS['generic'])
    return f'{RNG.uniform(lo, hi):.2f}'


def rand_balance_kind(kind: str) -> str:
    lo, hi = BALANCE_KINDS.get(kind, BALANCE_KINDS['generic'])
    return f'{RNG.uniform(lo, hi):.2f}'


# ── Currency-per-brand ───────────────────────────────────────────────────
# Templates declare a `currency_kind` so brand+region drive the currency
# symbol (e.g. Monzo/HSBC/Barclays → £, Chase/BoA/Wells Fargo/Venmo → $,
# Amazon.co.uk → £). Templates without a strong brand-currency tie
# (global brands like Netflix/Apple/Google) default to `multi`.
CURRENCY_KINDS: dict = {
    'gbp_only':  ['£'],
    'usd_only':  ['$'],
    'eur_only':  ['€'],
    'multi':     ['£', '$', '€'],
    'uk_bias':   ['£', '£', '£', '$', '€'],
    'us_bias':   ['$', '$', '$', '£', '€'],
    'eu_bias':   ['€', '€', '£', '$'],
}


def rand_currency_kind(kind: str) -> str:
    pool = CURRENCY_KINDS.get(kind, CURRENCY_KINDS['multi'])
    return RNG.choice(pool)


# ── Wording-diversity phrase pools ───────────────────────────────────────
# Common notification phrases that would otherwise appear verbatim across
# many templates ("If this was you, no action is needed") are resolved
# from these pools at render time so the LR sees varied surface forms.
PHRASE_POOLS: dict = {
    'if_this_was_you': [
        'If this was you',
        'If you recognise this activity',
        'If you initiated this',
        'If this looks familiar',
        'If this activity was yours',
        'If you made this change',
        'If you recognise this sign-in',
    ],
    'no_action': [
        'no action is needed',
        'no further action is required',
        "you're all set",
        'nothing more to do',
        'no further action required from you',
        'you can safely ignore this message',
    ],
    'ignore_safely': [
        'you can safely ignore this message',
        'you can ignore this notification',
        'no further action is needed',
        "you're all set — nothing more to do",
        'it is safe to disregard this alert',
    ],
    'if_not_you': [
        'If not',
        "If this wasn't you",
        'If you did not do this',
        'If you did not initiate this',
        "If this wasn't your action",
        "If you don't recognise this",
    ],
    'take_action': [
        'please review activity',
        'please review your recent activity',
        'sign in and review your account activity',
        'review your account',
        'secure your account',
    ],
    'dont_share_code': [
        'Do not share this code with anyone else',
        'Never share this code with anyone',
        'Keep this code private — do not share it',
        "Don't share this code, even with support",
        'This code is confidential — do not share',
    ],
    'thank_you_for_order': [
        'thank you for your order',
        'thanks for your order',
        "we've received your order",
        'thanks for shopping with us',
        'your order is confirmed',
    ],
    'greeting': [
        'Hello {name}',
        'Hi {name}',
        'Dear {name}',
        '{name}',                # bare vocative (template already adds a comma)
        'Hey {name}',
        'Hi there {name}',
    ],
}


def paraphrase(key: str, **kwargs) -> str:
    """Return a random variant from the phrase pool; format with kwargs."""
    return RNG.choice(PHRASE_POOLS[key]).format(**kwargs)


def rand_currency() -> str:
    return RNG.choice(CURRENCIES)


def rand_last4() -> str:
    return ''.join(RNG.choices(string.digits, k=4))


def rand_code(digits: int = 6) -> str:
    return ''.join(RNG.choices(string.digits, k=digits))


def rand_date() -> str:
    day = RNG.randint(1, 28)
    month = RNG.choice(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    # Spread years across 2024-2027 so the LR does not overfit to "2026"
    # (which would otherwise appear in almost every message that renders
    # a date, since 2026 is when this dataset was generated).
    year = RNG.choice([2024, 2025, 2026, 2027])
    return f'{day} {month} {year}'


def rand_date_range() -> str:
    start = RNG.randint(1, 25)
    end   = start + RNG.randint(1, 3)
    month = RNG.choice(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    return f'{start}–{end} {month}'


def rand_time_gmt() -> str:
    h = RNG.randint(0, 23)
    m = RNG.randint(0, 59)
    return f'{h:02d}:{m:02d} GMT'


def rand_amazon_order_id() -> str:
    a = ''.join(RNG.choices(string.digits, k=3))
    b = ''.join(RNG.choices(string.digits, k=7))
    c = ''.join(RNG.choices(string.digits, k=7))
    return f'{a}-{b}-{c}'


def rand_apple_receipt_id() -> str:
    return ''.join(RNG.choices(string.ascii_uppercase + string.digits, k=10))


def rand_tracking(carrier: str) -> str:
    if carrier == 'fedex':
        return ''.join(RNG.choices(string.digits, k=12))
    if carrier == 'ups':
        return '1Z' + ''.join(RNG.choices(string.ascii_uppercase + string.digits, k=16))
    if carrier == 'usps':
        digits = ''.join(RNG.choices(string.digits, k=20))
        return ' '.join(digits[i:i+4] for i in range(0, 20, 4))
    if carrier == 'dhl':
        return ''.join(RNG.choices(string.digits, k=10))
    if carrier == 'royalmail':
        return ''.join(RNG.choices(string.ascii_uppercase, k=2)) + \
               ''.join(RNG.choices(string.digits, k=9)) + 'GB'
    return ''.join(RNG.choices(string.digits, k=14))   # generic


def rand_invoice_id() -> str:
    return 'INV-' + ''.join(RNG.choices(string.digits, k=8))


def rand_txn_id() -> str:
    return ''.join(RNG.choices(string.ascii_lowercase + string.digits, k=12))


# ══════════════════════════════════════════════════════════════════════════
# Templates
# ══════════════════════════════════════════════════════════════════════════
# Each template:
#   id       — unique
#   category — logical bucket
#   brand    — origin brand (informational)
#   body     — template with {slot} placeholders
#   url      — optional; if present, is a REAL brand-official URL
#   n        — target number of variations
# ══════════════════════════════════════════════════════════════════════════

TEMPLATES = [
    # ── SHIPPING & DELIVERY (10) ──────────────────────────────────────────
    {'id': 'ship_amazon_dispatched',   'category': 'shipping', 'brand': 'amazon',
     'currency_kind': 'gbp_only',    # Amazon.co.uk → GBP
     'url': 'https://www.amazon.co.uk/gp/your-orders/orders',
     'body': ('Your Amazon.co.uk order has been dispatched. '
              'Order #{amazon_id} — {product}. Delivery expected between '
              '{date_range}. Track your package in Your Orders.'), 'n': 40},

    {'id': 'ship_amazon_delivered',    'category': 'shipping', 'brand': 'amazon',
     'body': ('Your Amazon package was delivered on {date} to your address. '
              'If you have not received your package, please check with '
              'neighbours or contact Amazon Customer Service. Order #{amazon_id}.'),
     'n': 40},

    {'id': 'ship_amazon_out_for_delivery', 'category': 'shipping', 'brand': 'amazon',
     'body': ('Your Amazon order is out for delivery today. Estimated arrival '
              'window: {time_range}. You will receive a photo confirmation once '
              'delivered. Order #{amazon_id}.'), 'n': 35},

    {'id': 'ship_fedex_pickup',        'category': 'shipping', 'brand': 'fedex',
     'url': 'https://www.fedex.com/fedextrack/',
     'body': ('FedEx: Your shipment has been picked up in {city}, {country}. '
              'Tracking number: {fedex_tracking}. Estimated delivery: {date}. '
              'Track your package on fedex.com.'), 'n': 35},

    {'id': 'ship_ups_transit',         'category': 'shipping', 'brand': 'ups',
     'url': 'https://www.ups.com/track',
     'body': ('UPS: Your package is in transit and expected to arrive on {date}. '
              'Tracking number: {ups_tracking}. Delivery to {city}. '
              'Track at ups.com.'), 'n': 35},

    {'id': 'ship_usps_delivered',      'category': 'shipping', 'brand': 'usps',
     'body': ('USPS Tracking Update: Your package with tracking number '
              '{usps_tracking} was delivered to your mailbox at {time_gmt} on '
              '{date}. Thank you for using USPS.'), 'n': 35},

    {'id': 'ship_dhl_transit',         'category': 'shipping', 'brand': 'dhl',
     'url': 'https://www.dhl.com/en/express/tracking.html',
     'body': ('DHL Express notification: Waybill {dhl_tracking} has been '
              'picked up in {city} and is on its way. Estimated delivery: '
              '{date}. Track your shipment on dhl.com.'), 'n': 35},

    {'id': 'ship_dpd_ontheway',        'category': 'shipping', 'brand': 'dpd',
     'url': 'https://www.dpd.co.uk/tracking/',
     'body': ('DPD: Your parcel from {retailer} is on its way. '
              'Track your parcel at dpd.co.uk with reference {generic_tracking}. '
              'Estimated delivery: {date}, between {time_range}.'), 'n': 30},

    {'id': 'ship_royalmail_ready',     'category': 'shipping', 'brand': 'royal_mail',
     'body': ('Royal Mail: Your item {royalmail_tracking} has been received at '
              'our {city} Delivery Office and is ready for delivery. Please '
              'allow up to 2 working days.'), 'n': 30},

    {'id': 'ship_evri_delivered',      'category': 'shipping', 'brand': 'evri',
     'body': ('Evri: Your parcel was delivered today at {time_gmt}. Left in '
              'safe place: front porch. If this does not look right, please '
              'get in touch via the Evri app.'), 'n': 25},

    # ── ORDER CONFIRMATIONS (8) ──────────────────────────────────────────
    {'id': 'order_amazon_confirm',     'category': 'order_confirmation', 'brand': 'amazon',
     'amount_kind': 'amazon_order',
     'body': ('{greeting}, {thank_you_for_order}! We will send a '
              'confirmation when your item ships. Order #{amazon_id} — '
              '{product} — {currency}{amount}. Expected delivery: {date_range}.'),
     'n': 40},

    {'id': 'order_amazon_invoice',     'category': 'order_confirmation', 'brand': 'amazon',
     'amount_kind': 'amazon_order',
     'body': ('Your Amazon invoice is now available. Order #{amazon_id}, '
              '{currency}{amount}. Download the VAT invoice in Your Orders '
              '> Invoice > Print invoice.'), 'n': 30},

    {'id': 'order_shopify_thanks',     'category': 'order_confirmation', 'brand': 'shopify',
     'amount_kind': 'shopify_order',
     'body': ('Order confirmation #{shopify_id}. {thank_you_for_order}, '
              '{name}! We\'ll be in touch when your order ships. Total: '
              '{currency}{amount}.'), 'n': 30},

    {'id': 'order_doordash_placed',    'category': 'order_confirmation', 'brand': 'doordash',
     'amount_kind': 'doordash_order', 'currency_kind': 'us_bias',    # US-primary service
     'body': ('DoorDash: We\'ve got your order from {food_place}. Estimated '
              'delivery: {mins} minutes. Total: {currency}{amount}. '
              'Track your Dasher in the app.'), 'n': 30},

    {'id': 'order_ubereats_placed',    'category': 'order_confirmation', 'brand': 'uber_eats',
     'amount_kind': 'ubereats_order', 'currency_kind': 'multi',     # global service
     'body': ('Uber Eats: Your order from {food_place} is being prepared. '
              'Estimated delivery: {mins}–{mins2} min. Order total: '
              '{currency}{amount}. Track your order in the Uber Eats app.'), 'n': 30},

    {'id': 'order_etsy_placed',        'category': 'order_confirmation', 'brand': 'etsy',
     'amount_kind': 'etsy_order',
     'body': ('{thank_you_for_order}! Order #{etsy_id} from {shopname}. '
              'Your item will ship within 3–5 business days. Total: '
              '{currency}{amount}.'), 'n': 25},

    {'id': 'order_stripe_receipt',     'category': 'order_confirmation', 'brand': 'stripe',
     'amount_kind': 'stripe_receipt',
     'body': ('Receipt from {merchant} via Stripe. Amount charged: '
              '{currency}{amount}. Receipt #{stripe_id}. If you have any '
              'questions, contact {merchant} directly.'), 'n': 25},

    {'id': 'order_ubereats_delivered', 'category': 'order_confirmation', 'brand': 'uber_eats',
     'body': ('Your Uber Eats order has been delivered. Enjoy your meal from '
              '{food_place}! Rate your delivery and food in the app.'), 'n': 20},

    # ── APP STORE / SUBSCRIPTION RECEIPTS (8) ────────────────────────────
    {'id': 'receipt_apple_appstore',   'category': 'receipt', 'brand': 'apple',
     'amount_kind': 'apple_app_sub',
     'body': ('Your App Store receipt. Order ID: {apple_id}. {app_name} '
              '1-Month subscription, {currency}{amount}. Your Apple ID: '
              '{email}. Save the receipt for your records.'), 'n': 30},

    {'id': 'receipt_apple_icloud',     'category': 'receipt', 'brand': 'apple',
     'amount_kind': 'icloud_month',
     'body': ('Thank you for your purchase. iCloud+ with 200GB storage · '
              '{currency}{amount}/month · Renews {date}. Your subscription can '
              'be managed in Settings > [your name] > Subscriptions on any '
              'Apple device.'), 'n': 30},

    {'id': 'receipt_google_play',      'category': 'receipt', 'brand': 'google',
     'amount_kind': 'google_play_sub',
     'body': ('Google Play receipt. {app_name} subscription — {currency}{amount}. '
              'Order number: GPA.{google_id}. Manage subscriptions at '
              'play.google.com/subscriptions.'), 'n': 30},

    {'id': 'receipt_spotify_renew',    'category': 'receipt', 'brand': 'spotify',
     'amount_kind': 'spotify_month',
     'body': ('Your Spotify Premium subscription renews on {date} for '
              '{currency}{amount}. Payment method: Visa ending in {last4}. '
              'Manage your plan at spotify.com/account.'), 'n': 30},

    {'id': 'receipt_netflix_renew',    'category': 'receipt', 'brand': 'netflix',
     'amount_kind': 'netflix_month',
     'body': ('Netflix: Your subscription of {currency}{amount}/month renews '
              'on {date}. Payment method: card ending {last4}. Update your '
              'plan or payment info at netflix.com/YourAccount.'), 'n': 30},

    {'id': 'receipt_adobe_creative',   'category': 'receipt', 'brand': 'adobe',
     'amount_kind': 'adobe_creative',
     'body': ('Adobe Creative Cloud: Your monthly plan of {currency}{amount} '
              'renews on {date}. Invoice #{invoice_id}. View your plan and '
              'invoices at account.adobe.com.'), 'n': 25},

    {'id': 'receipt_notion_plus',      'category': 'receipt', 'brand': 'notion',
     'amount_kind': 'notion_plus',
     'body': ('Notion Plus: Your monthly subscription of {currency}{amount} is '
              'now active. Next renewal: {date}. View invoices in your '
              'workspace at notion.so.'), 'n': 25},

    {'id': 'receipt_dropbox_plus',     'category': 'receipt', 'brand': 'dropbox',
     'amount_kind': 'dropbox_plus',
     'body': ('Dropbox Plus: Your subscription of {currency}{amount} renewed '
              'today. Next billing date: {date}. Manage your plan at '
              'dropbox.com/account.'), 'n': 25},

    # ── PAYMENT ACTIVITY (7) ─────────────────────────────────────────────
    {'id': 'pay_paypal_received',      'category': 'payment_activity', 'brand': 'paypal',
     'amount_kind': 'paypal_transfer',
     'body': ('You\'ve got money. {full_name} sent you {currency}{amount} '
              'GBP. This payment is now in your PayPal balance and available '
              'to transfer to your bank.'), 'n': 30},

    {'id': 'pay_paypal_sent',          'category': 'payment_activity', 'brand': 'paypal',
     'amount_kind': 'paypal_transfer',
     'body': ('You sent {currency}{amount} to {full_name}. Transaction ID: '
              '{txn_id}. Payment will be reflected in your bank statement '
              'as PAYPAL *{merchant}.'), 'n': 30},

    {'id': 'pay_venmo_received',       'category': 'payment_activity', 'brand': 'venmo',
     'amount_kind': 'venmo_transfer', 'currency_kind': 'usd_only',   # Venmo is US-only
     'body': ('Venmo: {full_name} paid you {currency}{amount}. Note: '
              '"{venmo_note}". Available in your Venmo balance now.'), 'n': 30},

    {'id': 'pay_stripe_paid',          'category': 'payment_activity', 'brand': 'stripe',
     'amount_kind': 'stripe_payout',
     'body': ('Payment received: {currency}{amount} from {full_name} via '
              'Stripe. Payout of {currency}{amount} will arrive in your bank '
              'account on {date}.'), 'n': 25},

    {'id': 'pay_wise_received',        'category': 'payment_activity', 'brand': 'wise',
     'amount_kind': 'wise_transfer',
     'body': ('Wise: You received {currency}{amount} from {full_name}. '
              'Reference: {reference}. View your transaction on wise.com.'), 'n': 25},

    {'id': 'pay_monzo_spent',          'category': 'payment_activity', 'brand': 'monzo',
     'amount_kind': 'bank_debit_purchase', 'balance_kind': 'monzo_running',
     'currency_kind': 'gbp_only',           # Monzo is UK-only
     'body': ('Monzo: You just spent {currency}{amount} at {store}. '
              'Available balance: {currency}{balance}.'), 'n': 30},

    {'id': 'pay_revolut_received',     'category': 'payment_activity', 'brand': 'revolut',
     'amount_kind': 'revolut_transfer', 'currency_kind': 'eu_bias',  # UK/EU fintech
     'body': ('Revolut: {full_name} sent you {currency}{amount}. '
              'Money is now in your main account.'), 'n': 25},

    # ── SECURITY / LOGIN NOTIFICATIONS (10) ──────────────────────────────
    {'id': 'sec_google_signin',        'category': 'security_notification', 'brand': 'google',
     'url': 'https://myaccount.google.com/notifications',
     'body': ('{greeting}, we noticed a new sign-in to your Google Account on '
              'a {device}. {if_this_was_you}, {no_action}. {if_not_you}, '
              '{take_action} at myaccount.google.com/notifications.'),
     'n': 40},

    {'id': 'sec_microsoft_phone',      'category': 'security_notification', 'brand': 'microsoft',
     'body': ('Microsoft account security info was added. On {date} at '
              '{time_gmt}, a new phone number was added to your Microsoft '
              'account. {if_this_was_you}, {no_action}. {if_not_you}, '
              '{take_action} at account.microsoft.com.'), 'n': 40},

    {'id': 'sec_microsoft_pwchange',   'category': 'security_notification', 'brand': 'microsoft',
     'body': ('Your Outlook.com password was successfully changed at '
              '{time_gmt} on {date}. {if_not_you}, follow the steps in the '
              'Microsoft account recovery guide.'),
     'n': 35},

    {'id': 'sec_apple_signin',         'category': 'security_notification', 'brand': 'apple',
     'url': 'https://appleid.apple.com',
     'body': ('Your Apple ID was used to sign in to iCloud via a web browser. '
              'Date and time: {date}, {time_gmt}. {if_this_was_you}, '
              '{ignore_safely}. {if_not_you}, your Apple ID may have been '
              'compromised — visit appleid.apple.com to review.'), 'n': 40},

    {'id': 'sec_github_signin',        'category': 'security_notification', 'brand': 'github',
     'url': 'https://github.com/settings/security-log',
     'body': ('A new sign-in to your GitHub account occurred from {city}, '
              '{country} using {browser}. {if_this_was_you}, {no_action}. '
              'Review your account activity at github.com/settings/security-log.'),
     'n': 30},

    {'id': 'sec_linkedin_newdevice',   'category': 'security_notification', 'brand': 'linkedin',
     'body': ('We noticed a new sign-in to your LinkedIn account. '
              'Device: {browser}. Location: {city}, {country}. '
              '{if_this_was_you}, {ignore_safely}.'), 'n': 30},

    {'id': 'sec_instagram_newlogin',   'category': 'security_notification', 'brand': 'instagram',
     'body': ('Instagram: We noticed a new login. Someone just logged into '
              'your Instagram account from {device} in {city}, {country}. '
              '{if_this_was_you}, {ignore_safely}. {if_not_you}, please '
              'secure your account.'), 'n': 30},

    {'id': 'sec_discord_newdevice',    'category': 'security_notification', 'brand': 'discord',
     'body': ('Discord: A new device signed into your account. Device: '
              '{browser}. Location: {city}. {if_not_you}, review your '
              'authorised devices in Discord Settings > Devices.'), 'n': 25},

    {'id': 'sec_x_newlogin',           'category': 'security_notification', 'brand': 'x',
     'body': ('New login to your X account. Device: {browser}. Location: '
              '{city}, {country}. {if_this_was_you}, {no_action}.'), 'n': 25},

    {'id': 'sec_slack_signin',         'category': 'security_notification', 'brand': 'slack',
     'body': ('You signed in to Slack. Workspace: {workspace}. Device: '
              '{browser}. Time: {time_gmt} on {date}. {if_not_you}, '
              'contact your workspace admin.'), 'n': 25},

    # ── BANKING ALERTS (7) ───────────────────────────────────────────────
    {'id': 'bank_chase_debit',         'category': 'banking_alert', 'brand': 'chase',
     'amount_kind': 'bank_debit_purchase', 'balance_kind': 'checking',
     'currency_kind': 'usd_only',                                    # US bank
     'body': ('Chase alert: A {currency}{amount} debit card purchase was '
              'made at {store} on {date}. Available balance: '
              '{currency}{balance}. {if_not_you}, please contact Chase '
              'immediately at the number on the back of your card.'), 'n': 30},

    {'id': 'bank_hsbc_statement',      'category': 'banking_alert', 'brand': 'hsbc',
     'currency_kind': 'gbp_only',                                    # HSBC UK
     'body': ('Your HSBC UK monthly statement for account ending {last4} '
              'is now available. Please log in to online banking or the '
              'mobile app to view your statement. Your next statement will '
              'be issued on {date}.'), 'n': 30},

    {'id': 'bank_monzo_spent',         'category': 'banking_alert', 'brand': 'monzo',
     'amount_kind': 'bank_debit_purchase', 'balance_kind': 'monzo_running',
     'currency_kind': 'gbp_only',                                    # Monzo UK-only
     'body': ('Monzo: You just spent {currency}{amount} at {store}, {city}. '
              'Available balance: {currency}{balance}. View this transaction '
              'in the Monzo app.'), 'n': 30},

    {'id': 'bank_wellsfargo_deposit',  'category': 'banking_alert', 'brand': 'wells_fargo',
     'amount_kind': 'wells_fargo_deposit', 'currency_kind': 'usd_only',   # US bank
     'body': ('Wells Fargo Alert: A deposit of {currency}{amount} was made to '
              'your account ending {last4} on {date}. Sign in to Wells Fargo '
              'Online at wellsfargo.com to review.'), 'n': 30},

    {'id': 'bank_boa_lowbalance',      'category': 'banking_alert', 'brand': 'bank_of_america',
     'balance_kind': 'boa_low_balance', 'currency_kind': 'usd_only',      # US bank
     'body': ('Bank of America Alert: Your account ending {last4} balance '
              'is below your alert threshold. Current balance: '
              '{currency}{balance}. Manage alerts in Online Banking.'), 'n': 25},

    {'id': 'bank_barclays_paidout',    'category': 'banking_alert', 'brand': 'barclays',
     'amount_kind': 'barclays_outgoing', 'currency_kind': 'gbp_only',     # UK bank
     'body': ('Barclays: A payment of {currency}{amount} was made from your '
              'account ending {last4} to {full_name} on {date}. If you did '
              'not authorise this payment, please contact us.'), 'n': 25},

    {'id': 'bank_starling_notice',     'category': 'banking_alert', 'brand': 'starling',
     'amount_kind': 'starling_incoming', 'balance_kind': 'starling_running',
     'currency_kind': 'gbp_only',                                    # UK bank
     'body': ('Starling Bank: {currency}{amount} was received into your '
              'account from {full_name} — reference "{reference}". '
              'Available balance: {currency}{balance}.'), 'n': 25},

    # ── OTP NOTIFICATIONS (6) ────────────────────────────────────────────
    {'id': 'otp_google',               'category': 'otp_notification', 'brand': 'google',
     'body': ('Your Google verification code is {code_6}. {dont_share_code} '
              '— Google will never ask you for it.'),
     'n': 25},

    {'id': 'otp_barclays',             'category': 'otp_notification', 'brand': 'barclays',
     'body': ('Your Barclays one-time passcode is {code_6}. Use this code '
              'to complete your online banking action. This code expires in '
              '10 minutes.'), 'n': 25},

    {'id': 'otp_discord',              'category': 'otp_notification', 'brand': 'discord',
     'body': ('Discord: {code_6} is your verification code. Enter this on '
              'Discord to verify your account. {dont_share_code}.'), 'n': 25},

    {'id': 'otp_uber',                 'category': 'otp_notification', 'brand': 'uber',
     'body': ('Uber: Your verification code is {code_4}. {dont_share_code} '
              '— even with an Uber agent.'), 'n': 25},

    {'id': 'otp_steam',                'category': 'otp_notification', 'brand': 'steam',
     'body': ('Steam Guard: your one-time code is {steam_code}. This code '
              'is required to sign in from a new device.'), 'n': 25},

    {'id': 'otp_microsoft',            'category': 'otp_notification', 'brand': 'microsoft',
     'body': ('Microsoft account security code: {code_6}. Use this code to '
              'verify sign-in. The code expires in 15 minutes.'), 'n': 25},

    # ── SUBSCRIPTION RENEWAL / BILLING (5) ───────────────────────────────
    {'id': 'sub_netflix_household',    'category': 'subscription_renewal', 'brand': 'netflix',
     'url': 'https://www.netflix.com/YourAccount',
     'body': ('Did you request to update your Netflix Household? {greeting}, '
              'we received a request to update the Netflix Household for '
              'your account on {date}, {time_gmt}. {if_this_was_you}, '
              '{no_action}. Manage your household at '
              'netflix.com/YourAccount.'), 'n': 30},

    {'id': 'sub_youtube_premium',      'category': 'subscription_renewal', 'brand': 'google',
     'amount_kind': 'youtube_premium',
     'body': ('Your YouTube Premium plan renews on {date} for '
              '{currency}{amount}. Manage your plan at '
              'youtube.com/paid_memberships.'), 'n': 25},

    {'id': 'sub_spotify_thanks',       'category': 'subscription_renewal', 'brand': 'spotify',
     'amount_kind': 'spotify_month',
     'body': ('Thanks for being a Spotify Premium subscriber. Your next '
              'payment of {currency}{amount} will be taken on {date}.'), 'n': 25},

    {'id': 'sub_apple_music_renew',    'category': 'subscription_renewal', 'brand': 'apple',
     'amount_kind': 'apple_music_month',
     'body': ('Your Apple Music subscription renews on {date}. Family plan · '
              '{currency}{amount}/month. Manage your subscription in Settings '
              '> Subscriptions.'), 'n': 25},

    {'id': 'sub_dropbox_expiring',     'category': 'subscription_renewal', 'brand': 'dropbox',
     'amount_kind': 'dropbox_plus',
     'body': ('Dropbox Plus: Your subscription expires in 7 days on {date}. '
              'Your plan will automatically renew at {currency}{amount}. '
              'Manage your plan at dropbox.com/account/plan.'), 'n': 25},

    # ── ACCOUNT ACTIVITY / NEWSLETTER (5) ────────────────────────────────
    {'id': 'act_linkedin_connect',     'category': 'account_activity', 'brand': 'linkedin',
     'body': ('LinkedIn: {full_name} sent you a message. "Hi {name}, thanks '
              'for connecting — would love to catch up when you have a '
              'moment." Reply on LinkedIn.'), 'n': 25},

    {'id': 'act_github_forked',        'category': 'account_activity', 'brand': 'github',
     'body': ('GitHub: {gh_user} forked your repository {gh_user}/{repo}. '
              'View the fork at github.com/{gh_user}/{repo}.'), 'n': 25},

    {'id': 'act_zoom_meeting',         'category': 'account_activity', 'brand': 'zoom',
     'body': ('Zoom: Your meeting "{meeting_name}" is starting soon. '
              'Meeting ID: {meeting_id}. Join at zoom.us.'), 'n': 25},

    {'id': 'act_slack_mention',        'category': 'account_activity', 'brand': 'slack',
     'body': ('Slack: {full_name} mentioned you in #{channel} in the '
              '{workspace} workspace. Reply on Slack.'), 'n': 25},

    {'id': 'act_notion_shared',        'category': 'account_activity', 'brand': 'notion',
     'body': ('{full_name} shared a page with you: "{doc_title}". Open it in '
              'Notion at notion.so.'), 'n': 25},

    # ── EXTRA-BOUNDARY: PASSWORD-CHANGED SELF-NOTIFICATION (3) ───────────
    # High phishing similarity — user-changed-password confirmation. Legit
    # provided it does not ask user to disclose or reset via a link.
    {'id': 'sec_password_changed_apple',   'category': 'security_notification', 'brand': 'apple',
     'body': ('Your Apple ID password was changed at {time_gmt} on {date}. '
              '{if_this_was_you}, {no_action}. {if_not_you}, '
              'sign in to appleid.apple.com to secure your account.'),
     'n': 25},

    {'id': 'sec_password_changed_google',  'category': 'security_notification', 'brand': 'google',
     'body': ('Your Google Account password was changed on {date}. '
              '{if_not_you}, visit myaccount.google.com to review '
              'security activity.'), 'n': 25},

    {'id': 'sec_password_changed_github',  'category': 'security_notification', 'brand': 'github',
     'body': ('Your GitHub password was changed. {if_this_was_you}, '
              '{no_action}. {if_not_you}, review your security log at '
              'github.com/settings/security-log.'), 'n': 25},
]


# ══════════════════════════════════════════════════════════════════════════
# Placeholder substitution
# ══════════════════════════════════════════════════════════════════════════

def _fill_slots(body: str, amount_kind: str = 'generic',
                balance_kind: str = 'checking',
                currency_kind: str = 'multi') -> str:
    """Substitute {slot} placeholders with random plausible values.

    Only registered slot names are substituted. Unknown slots would raise —
    which is desired: it means we forgot to seed a value pool.

    * `amount_kind` selects a realistic per-context money range for {amount}
      (e.g. netflix_month → [6.99, 22.99]). Fallback: uniform generic.
    * `balance_kind` selects a realistic range for {balance}.
    * `currency_kind` picks the currency symbol from a brand/region-tied
      pool (e.g. Monzo → £, Chase → $). Fallback: multi (£/$/€).
    * `city` and `country` are drawn from the SAME region so pairs are
      always geographically valid.
    """
    name = rand_name()
    city, country = pick_region()
    currency = rand_currency_kind(currency_kind)
    values: dict = {
        'name':               name,
        'full_name':          rand_full_name(),
        'city':               city,
        'country':            country,
        'device':             RNG.choice(DEVICES),
        'browser':            RNG.choice(BROWSERS),
        'currency':           currency,
        'amount':             rand_amount_kind(amount_kind),
        'balance':            rand_balance_kind(balance_kind),
        'date':               rand_date(),
        'date_range':         rand_date_range(),
        'time_gmt':           rand_time_gmt(),
        'time_range':         f'{RNG.randint(8, 14):02d}:00–{RNG.randint(15, 20):02d}:00',
        'last4':              rand_last4(),
        'code_4':             rand_code(4),
        'code_6':             rand_code(6),
        'steam_code':         ''.join(RNG.choices(string.ascii_uppercase + string.digits, k=5)),
        'amazon_id':          rand_amazon_order_id(),
        'shopify_id':         ''.join(RNG.choices(string.digits, k=5)),
        'etsy_id':            ''.join(RNG.choices(string.digits, k=10)),
        'stripe_id':          'ch_' + ''.join(RNG.choices(string.ascii_lowercase + string.digits, k=16)),
        'apple_id':           rand_apple_receipt_id(),
        'google_id':          ''.join(RNG.choices(string.ascii_uppercase + string.digits, k=16)),
        'fedex_tracking':     rand_tracking('fedex'),
        'ups_tracking':       rand_tracking('ups'),
        'usps_tracking':      rand_tracking('usps'),
        'dhl_tracking':       rand_tracking('dhl'),
        'royalmail_tracking': rand_tracking('royalmail'),
        'generic_tracking':   rand_tracking('generic'),
        'invoice_id':         rand_invoice_id(),
        'txn_id':             rand_txn_id(),
        'reference':          ''.join(RNG.choices(string.ascii_uppercase, k=6)),
        'product':            RNG.choice(PRODUCTS_TECH + PRODUCTS_HOME),
        'food_place':         RNG.choice(FOOD_ITEMS),
        'store':              RNG.choice(STORES),
        'app_name':           RNG.choice(['Craft — Documents & Notes Editor',
                                            'Bear Notes', 'MindNode',
                                            'Overcast', 'Fantastical',
                                            '1Password', 'Todoist Premium',
                                            'HeyGen Video', 'Halide Camera']),
        'merchant':           RNG.choice(['Northgate Studios', 'Bluewave Media',
                                            'Craft Labs', 'Riverstone Ltd',
                                            'Halo Digital', 'Foundry Design',
                                            'Meadowlark Records']),
        'retailer':           RNG.choice(['Zara', 'Nike', 'Uniqlo', 'H&M',
                                            'ASOS', 'John Lewis', 'M&S']),
        'shopname':           RNG.choice(['ArtByEllie', 'NordicWoodworks',
                                            'PrintPress', 'MerakiCandles']),
        'workspace':          RNG.choice(['Acme HQ', 'Riverside', 'Team Delta',
                                           'Product-EMEA', 'Founders']),
        'channel':             RNG.choice(['general', 'engineering',
                                            'product-launch', 'design-crit',
                                            'random']),
        'meeting_name':       RNG.choice(['Q3 planning', 'Design review',
                                           'Weekly 1:1', 'Sprint retro',
                                           'Product sync']),
        'meeting_id':          ' '.join(''.join(RNG.choices(string.digits, k=3)) for _ in range(3)),
        'gh_user':             RNG.choice(['acme-labs', 'northstar-io',
                                            'octocat', 'floworks', 'lumen-ai']),
        'repo':                RNG.choice(['api-gateway', 'design-system',
                                            'data-pipeline', 'docs',
                                            'auth-service']),
        'venmo_note':          RNG.choice(['dinner 🍝', 'utilities', 'coffee',
                                            'brunch', 'concert tix',
                                            'happy birthday', 'thanks!']),
        'doc_title':           RNG.choice(['Q3 planning notes',
                                            'Onboarding doc',
                                            '2026 roadmap', 'Hiring plan',
                                            'Design review notes']),
        'email':               RNG.choice([
                                    'user@icloud.com', 'name@gmail.com',
                                    'me@outlook.com', 'you@fastmail.com']),
        'mins':                str(RNG.randint(15, 45)),
        'mins2':               str(RNG.randint(50, 75)),
        # ── Paraphrase placeholders (wording diversity) ──────────────────
        'if_this_was_you':     paraphrase('if_this_was_you'),
        'no_action':           paraphrase('no_action'),
        'ignore_safely':       paraphrase('ignore_safely'),
        'if_not_you':          paraphrase('if_not_you'),
        'take_action':         paraphrase('take_action'),
        'dont_share_code':     paraphrase('dont_share_code'),
        'thank_you_for_order': paraphrase('thank_you_for_order'),
        'greeting':            paraphrase('greeting', name=name),
    }
    return body.format(**values)


def render_template(t: dict) -> str:
    """Build one message from a template, optionally appending the URL on
    its own line so URL extraction consistently picks it up."""
    body = _fill_slots(
        t['body'],
        amount_kind=t.get('amount_kind', 'generic'),
        balance_kind=t.get('balance_kind', 'checking'),
        currency_kind=t.get('currency_kind', 'multi'),
    )
    if t.get('url'):
        body = body.rstrip() + '\n' + t['url']
    return body


# ══════════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════════
# Every candidate is checked against the SAME regex helpers the rule engine
# uses to detect dangerous patterns. Any hit → reject. This guarantees no
# synthetic legit message can accidentally teach the model that a phishing
# action pattern is legitimate.
# ══════════════════════════════════════════════════════════════════════════

_SUSPICIOUS_TLD_RE = re.compile(
    r'\.(?:xyz|top|tk|ml|ga|cf|gq|click|link|work|buzz|zip|rest|monster|'
    r'cyou|quest|cam|shop|icu|live|online|country|space)\b',
    re.IGNORECASE,
)
_ALLOWLIST_DOMAINS = {
    # Whitelist of eTLD+1 domains permitted in synthetic legit URLs.
    # Everything else is rejected as a safety net.
    'amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.it',
    'amazon.es', 'amazon.co.jp', 'amazon.ca',
    'apple.com', 'icloud.com', 'appleid.apple.com',
    'google.com', 'gmail.com', 'youtube.com', 'play.google.com',
    'myaccount.google.com',
    'microsoft.com', 'outlook.com', 'account.microsoft.com',
    'netflix.com',
    'paypal.com', 'stripe.com', 'venmo.com', 'wise.com', 'revolut.com',
    'monzo.com', 'starlingbank.com',
    'facebook.com', 'instagram.com', 'linkedin.com', 'twitter.com', 'x.com',
    'github.com', 'gitlab.com',
    'spotify.com', 'adobe.com', 'notion.so', 'dropbox.com',
    'discord.com', 'slack.com', 'zoom.us',
    'shopify.com', 'etsy.com',
    'fedex.com', 'ups.com', 'usps.com', 'dhl.com', 'dpd.co.uk',
    'royalmail.com', 'evri.com',
    'uber.com', 'chase.com', 'wellsfargo.com', 'bankofamerica.com',
    'hsbc.co.uk', 'barclays.co.uk',
}
_URL_ANY_RE = re.compile(r'https?://([^\s/]+)', re.IGNORECASE)


def _extract_hostnames(text: str) -> list:
    hosts = []
    for m in _URL_ANY_RE.finditer(text):
        h = m.group(1).lower()
        if h.startswith('www.'):
            h = h[4:]
        hosts.append(h)
    return hosts


def _is_allowlisted(host: str) -> bool:
    return any(host == d or host.endswith('.' + d) for d in _ALLOWLIST_DOMAINS)


VALIDATORS = {
    'credential_request':   has_credential_request,
    'otp_theft':            has_otp_theft,
    'gift_card_payment':    has_gift_card_payment,
    'crypto_seed_request':  has_crypto_seed_request,
    'remote_access':        has_remote_access_request,
}


def validate(text: str) -> tuple[bool, str]:
    """Return (ok, reason). Reason empty when ok."""
    for name, fn in VALIDATORS.items():
        if fn(text):
            return False, name
    # URL safety: any URL must be an allowlisted official domain
    for host in _extract_hostnames(text):
        if not _is_allowlisted(host):
            return False, f'unallowed_domain:{host}'
    if _SUSPICIOUS_TLD_RE.search(text):
        return False, 'suspicious_tld_in_text'
    return True, ''


# ══════════════════════════════════════════════════════════════════════════
# Main generation
# ══════════════════════════════════════════════════════════════════════════

def main():
    print('=== E8-P2 synthetic legit dataset ===')
    print(f'  templates:            {len(TEMPLATES)}')
    total_target = sum(t['n'] for t in TEMPLATES)
    print(f'  target variations:    {total_target:,}')
    n_brands   = len({t["brand"] for t in TEMPLATES})
    n_cats     = len({t["category"] for t in TEMPLATES})
    print(f'  brand diversity:      {n_brands}')
    print(f'  categories:           {n_cats}')
    print()

    kept: list = []
    rejections: Counter = Counter()
    seen_texts: set = set()          # near-duplicate guard within run
    for t in TEMPLATES:
        target = t['n']
        # Try up to 3× target because some variations will duplicate/reject
        attempts = 0
        wins     = 0
        while wins < target and attempts < target * 3:
            attempts += 1
            try:
                text = render_template(t)
            except KeyError as e:
                rejections['template_missing_slot:' + str(e)] += 1
                break
            # Cheap dedupe: hash the first 120 chars
            key = text[:120]
            if key in seen_texts:
                rejections['dup'] += 1
                continue
            ok, reason = validate(text)
            if not ok:
                rejections[reason] += 1
                continue
            seen_texts.add(key)
            kept.append({
                'text':        text,
                'label':       0,                    # LEGIT
                'category':    t['category'],
                'brand':       t['brand'],
                'template_id': t['id'],
                'has_url':     bool(t.get('url')),
            })
            wins += 1

    df = pd.DataFrame(kept)
    print(f'  kept:                 {len(df):,}')
    print(f'  by category:')
    for cat, n in df.category.value_counts().items():
        print(f'    {cat:26s} {n:>5}')
    print(f'  by brand (top 15):')
    for brand, n in df.brand.value_counts().head(15).items():
        print(f'    {brand:26s} {n:>5}')
    print(f'  URLs present:         {int(df.has_url.sum())}  ({df.has_url.mean()*100:.0f}%)')
    print()
    print(f'  rejections:')
    for r, n in rejections.most_common():
        print(f'    {r:26s} {n:>5}')

    # ── Write outputs ─────────────────────────────────────────────────────
    out_parquet = os.path.join(OUT_DIR, 'dataset.parquet')
    df.to_parquet(out_parquet, index=False)
    print(f'\nWrote {out_parquet}   ({len(df):,} rows)')

    # Stratified preview samples — up to 4 per template
    sample_parts: list = []
    for tid, g in df.groupby('template_id'):
        sample_parts.append(g.sample(min(len(g), 4), random_state=42))
    sample = pd.concat(sample_parts, ignore_index=True)
    sample_lines: list = []
    for _, r in sample.iterrows():
        sample_lines.append(f'[{r["category"]}]  [{r["brand"]}]  [{r["template_id"]}]')
        sample_lines.append(r['text'])
        sample_lines.append('')
    with open(os.path.join(OUT_DIR, 'samples.txt'), 'w') as f:
        f.write('\n'.join(sample_lines))
    print(f'Wrote {OUT_DIR}/samples.txt ({len(sample):,} preview messages)')

    # Rejection report + stats
    with open(os.path.join(OUT_DIR, 'rejection_report.json'), 'w') as f:
        json.dump(dict(rejections), f, indent=2)
    stats = {
        'n_kept':              int(len(df)),
        'n_templates':         len(TEMPLATES),
        'n_brands':            n_brands,
        'n_categories':        n_cats,
        'urls_present_ratio':  round(float(df.has_url.mean()), 4),
        'per_category':        {k: int(v) for k, v in df.category.value_counts().items()},
        'per_brand':           {k: int(v) for k, v in df.brand.value_counts().items()},
        'per_template':        {k: int(v) for k, v in df.template_id.value_counts().items()},
        'rejections':          dict(rejections),
    }
    with open(os.path.join(OUT_DIR, 'generation_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    print(f'Wrote {OUT_DIR}/generation_stats.json')


if __name__ == '__main__':
    main()
