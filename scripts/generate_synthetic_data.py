"""
ScamRadar+ | Synthetic training data generator via Claude API.

Generates realistic scam messages for under-represented scam types using
Claude, then inserts them into the training DB. Covers:

  - pig_butchering   : slow crypto grooming with withdrawal fee trap
  - qr_phishing      : QR code lures for credential/payment theft
  - refund_scam      : overpayment fraud pushing gift card returns
  - sim_swap         : social engineering to extract OTP codes
  - gift_card_scam   : authority/emergency scam demanding gift cards
  - whatsapp_crypto  : WhatsApp/Telegram group crypto pump scams

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/generate_synthetic_data.py

Optional flags:
    --count N          messages per scam type (default 60)
    --legit-count N    balancing legit messages generated (default 20)
    --dry-run          print generated messages without inserting into DB
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db 4.db')

SOURCE_NAME = 'synthetic_claude_generated'

CHANNEL_MAP = {'email': 1, 'sms': 3, 'url': 4}


# ── Prompts for each scam type ────────────────────────────────────────────

SCAM_TYPE_PROMPTS = {
    'pig_butchering': {
        'channel': 'sms',
        'prompt': (
            "Generate {n} realistic pig butchering scam text messages. "
            "Pig butchering is a long-running scam where the fraudster builds a relationship "
            "over days or weeks (posing as a friendly stranger, wrong number, or dating match) "
            "before introducing a crypto/investment platform. Key features: "
            "(1) starts casual and friendly, not obviously scammy; "
            "(2) mentions a specific trading platform or app; "
            "(3) offers to 'guide' the victim personally; "
            "(4) mentions their own profits to build trust; "
            "(5) some messages include a withdrawal fee trap at the end. "
            "Vary the opening scenario: wrong number, dating app match, LinkedIn, "
            "conference contact, friendly neighbour. "
            "Vary length from 2 to 8 sentences. "
            "Return a JSON array of strings — only the message text, nothing else."
        ),
    },
    'qr_phishing': {
        'channel': 'sms',
        'prompt': (
            "Generate {n} realistic QR code phishing messages (smishing). "
            "These are SMS or email messages that trick the recipient into scanning a QR code "
            "to steal credentials, payment info, or install malware. Features: "
            "(1) impersonates a trusted brand (bank, delivery company, government, parking, etc.); "
            "(2) creates urgency (account locked, fee due, package held, fine pending); "
            "(3) instructs victim to scan a QR code rather than clicking a link; "
            "(4) some include a fake URL that supposedly hosts the QR. "
            "Vary impersonated entities: USPS, FedEx, DHL, HMRC, IRS, NHS, banks, "
            "parking enforcement, Netflix, Apple, Microsoft, PayPal, toll roads. "
            "Return a JSON array of strings — only the message text, nothing else."
        ),
    },
    'refund_scam': {
        'channel': 'email',
        'prompt': (
            "Generate {n} realistic refund/overpayment scam messages (email or SMS). "
            "These scams claim the sender accidentally overpaid or deposited too much money "
            "into the victim's account and ask them to 'return' the difference, usually via "
            "gift card, wire transfer, Zelle, Venmo, or cryptocurrency. Features: "
            "(1) claims an overpayment or mistaken transfer occurred; "
            "(2) pressures the victim to return the money quickly; "
            "(3) specifies an unusual payment method (gift card, crypto, Zelle); "
            "(4) sometimes posed as Craigslist buyer, Facebook Marketplace buyer, mystery shopper. "
            "Vary scenarios: Craigslist sale, Facebook Marketplace, mystery shopper cheque, "
            "employer payroll error, government rebate cheque. "
            "Return a JSON array of strings — only the message text, nothing else."
        ),
    },
    'sim_swap': {
        'channel': 'sms',
        'prompt': (
            "Generate {n} realistic SIM swap / OTP theft scam messages. "
            "These are social engineering messages that trick the victim into forwarding or "
            "reading aloud a one-time password (OTP) or verification code that was just sent "
            "to their phone. Features: "
            "(1) impersonates the victim's bank, carrier, employer, or a tech company; "
            "(2) creates a plausible reason why they need the code (verification, security, etc.); "
            "(3) asks the victim to share, text back, or read out the code they just received; "
            "(4) some are from a 'friend in trouble' who needs to borrow the code. "
            "Vary scenarios: bank security team, account recovery, employer IT, "
            "carrier customer service, friend in emergency. "
            "Return a JSON array of strings — only the message text, nothing else."
        ),
    },
    'gift_card_scam': {
        'channel': 'sms',
        'prompt': (
            "Generate {n} realistic gift card payment scam messages. "
            "These scams demand payment in gift cards (iTunes, Google Play, Amazon, Steam) "
            "by impersonating authorities, employers, or creating fake emergencies. Features: "
            "(1) creates urgency or fear (legal trouble, owed taxes, account locked); "
            "(2) instructs victim to buy gift cards from a store; "
            "(3) asks victim to scratch off the back and share the code numbers; "
            "(4) often impersonates IRS, Social Security, police, employer, tech support. "
            "Vary the impersonated authority: IRS, Social Security Administration, FBI, "
            "local police, employer CEO, grandchild in trouble, tech support. "
            "Return a JSON array of strings — only the message text, nothing else."
        ),
    },
    'whatsapp_crypto': {
        'channel': 'sms',
        'prompt': (
            "Generate {n} realistic WhatsApp/Telegram crypto scam recruitment messages. "
            "These are messages inviting victims to join private crypto/investment groups "
            "or channels, often after building brief rapport. Features: "
            "(1) offers to add victim to a 'private', 'VIP', or 'closed' investment group; "
            "(2) claims the group has a successful track record; "
            "(3) mentions a specific Telegram or WhatsApp group, or a private trading channel; "
            "(4) uses social proof ('my friends made money', 'only 5 spots left'); "
            "(5) some start with a 'wrong number' or 'I met you at...' opener. "
            "Vary the investment type: crypto, forex, binary options, NFTs, stocks. "
            "Return a JSON array of strings — only the message text, nothing else."
        ),
    },
}

LEGIT_PROMPT = (
    "Generate {n} realistic legitimate messages that could be mistaken for scam messages "
    "but are actually genuine. These help train the model to avoid false positives. Include: "
    "real two-factor authentication codes, genuine bank security alerts, "
    "real package delivery notifications with tracking, legitimate employer payroll corrections, "
    "real app verification codes, genuine security warnings from Apple/Google/Microsoft, "
    "real appointment reminders, legitimate subscription renewal notices. "
    "IMPORTANT: these must be clearly legitimate — not ambiguous. "
    "Return a JSON array of strings — only the message text, nothing else."
)


def _call_claude(client, prompt: str, n: int) -> list[str]:
    filled = prompt.format(n=n)
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=4096,
        messages=[{'role': 'user', 'content': filled}],
    )
    raw = msg.content[0].text.strip()
    # Extract JSON array from response
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        print(f"    Warning: could not parse JSON array from response")
        return []
    try:
        result = json.loads(match.group())
        return [str(x).strip() for x in result if str(x).strip()]
    except json.JSONDecodeError as e:
        print(f"    Warning: JSON decode error: {e}")
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


def ingest_messages(conn: sqlite3.Connection, messages: list[str], label: int,
                    source_id: int, channel: str):
    c = conn.cursor()
    ch_id = CHANNEL_MAP.get(channel, 3)
    max_id = c.execute('SELECT MAX(message_id) FROM Message').fetchone()[0] or 0
    inserted = 0
    for text in messages:
        text = text.strip()
        if not text or len(text) < 20:
            continue
        exists = c.execute('SELECT 1 FROM Message WHERE raw_text=?', (text,)).fetchone()
        if exists:
            continue
        max_id += 1
        c.execute(
            'INSERT INTO Message (message_id, source_id, channel_id, raw_text, label) VALUES (?,?,?,?,?)',
            (max_id, source_id, ch_id, text, label),
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
    parser.add_argument('--count', type=int, default=60,
                        help='Number of scam messages per type (default 60)')
    parser.add_argument('--legit-count', type=int, default=20,
                        help='Number of legit balancing messages (default 20)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print messages without inserting into DB')
    args = parser.parse_args()

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed.")
        print("Install with: pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    conn = None
    source_id = None
    if not args.dry_run:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
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

    for scam_type, cfg in SCAM_TYPE_PROMPTS.items():
        print(f"\nGenerating {args.count} '{scam_type}' messages...")
        try:
            messages = _call_claude(client, cfg['prompt'], args.count)
            print(f"  Got {len(messages)} messages")
        except Exception as exc:
            print(f"  Failed: {exc}")
            messages = []

        if args.dry_run:
            for i, m in enumerate(messages[:5], 1):
                print(f"  [{i}] {m[:120]}")
            if len(messages) > 5:
                print(f"  ... and {len(messages) - 5} more")
        elif messages and conn is not None:
            n = ingest_messages(conn, messages, label=1,
                                source_id=source_id, channel=cfg['channel'])
            print(f"  Inserted {n} into DB")
            total_inserted += n

        time.sleep(1)  # polite rate limit

    # Generate legit balancing messages
    print(f"\nGenerating {args.legit_count} legit balancing messages...")
    try:
        legit_msgs = _call_claude(client, LEGIT_PROMPT, args.legit_count)
        print(f"  Got {len(legit_msgs)} legit messages")
    except Exception as exc:
        print(f"  Failed: {exc}")
        legit_msgs = []

    if args.dry_run:
        for i, m in enumerate(legit_msgs[:3], 1):
            print(f"  [{i}] {m[:120]}")
    elif legit_msgs and conn is not None:
        n = ingest_messages(conn, legit_msgs, label=0,
                            source_id=source_id, channel='sms')
        print(f"  Inserted {n} legit messages into DB")
        total_inserted += n

    if conn is not None:
        conn.close()

    if args.dry_run:
        print("\nDry run complete — no data was inserted.")
    else:
        print(f"\nDone. Total inserted: {total_inserted} messages.")
        print("Run `python main.py` to retrain the model.")


if __name__ == '__main__':
    main()
