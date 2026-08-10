"""
Manual acceptance test — real-world LEGITIMATE messages.

Purpose: confirm the E5 production model does NOT exhibit the false-positive
behaviour previously observed in the legacy v1.3 model on messages users
actually receive from real services (Google, Amazon, PayPal, banks, etc.).

This is a quality-control-only step. It is NEVER used for:
  * training
  * threshold tuning
  * model optimisation
  * calibration

Every message here is authored to mimic real-world legitimate notifications
in style and structure. Ground truth is LEGIT for all items — a SCAM verdict
means a false positive.

Usage: `python tests/manual_acceptance_test.py` (requires local API on port 8000).
"""
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict

import certifi

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_URL = os.environ.get('SCAMRADAR_API', 'http://127.0.0.1:8000/predict')
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# ─────────────────────────────────────────────────────────────────────────────
# 32 real-world legitimate messages across 10 categories.
# Every item is a message a normal user would receive from a real service.
# ─────────────────────────────────────────────────────────────────────────────
TESTS: list[tuple[str, str]] = [
    # ── Google account emails ────────────────────────────────────────────────
    ("google_account", "Hi Ameer, we noticed a new sign-in to your Google Account on a MacBook Pro. If this was you, no action is needed. If not, please review activity at https://myaccount.google.com/notifications — Google"),
    ("google_account", "Your Google Account will run out of storage in about 30 days. You are currently using 14.2 GB of your 15 GB. Manage your storage in Google One to keep your files, photos, and emails safe."),
    ("google_account", "Ameer shared a document with you: 'Q3 planning notes'. Open it in Google Docs to view or edit. This message was sent by Google on behalf of Ameer."),

    # ── Microsoft account emails ─────────────────────────────────────────────
    ("microsoft_account", "Microsoft account security info was added. On Wednesday, 30 July 2026 at 10:42 (GMT), a new phone number was added to your Microsoft account. If this was you, no action needed. If not, review your account at account.microsoft.com."),
    ("microsoft_account", "Your Outlook.com password was successfully changed at 14:07 on 29 July 2026. If you did not make this change, follow the steps in the Microsoft account recovery guide."),
    ("microsoft_account", "OneDrive is almost full. You're using 4.9 GB of your 5 GB free storage. Free up space or upgrade your plan to keep your files backed up."),

    # ── Apple emails ─────────────────────────────────────────────────────────
    ("apple", "Your Apple ID was used to sign in to iCloud via a web browser. Date and time: 30 Jul 2026, 09:12 GMT. If you recently signed in, you can ignore this notification. If you did not sign in, your Apple ID may have been compromised — visit appleid.apple.com to review."),
    ("apple", "Thank you for your purchase. iCloud+ with 200GB storage · £2.49/month · Renews 15 Aug 2026. Your subscription can be managed in Settings > [your name] > Subscriptions on any Apple device."),
    ("apple", "Your App Store receipt. Order ID: MHVX9K42QP. Craft — Documents & Notes Editor, 1-Month subscription, £6.99. Your Apple ID: amerrhassouna@icloud.com. Save the receipt for your records."),

    # ── Amazon order confirmations ───────────────────────────────────────────
    ("amazon_order", "Hello Ameer, thank you for your order! We'll send a confirmation when your item ships. Order #204-9382173-4477263 — Sony WH-1000XM5 Wireless Headphones — £299.00. Expected delivery: Wed, 5 Aug — Fri, 7 Aug."),
    ("amazon_order", "Your Amazon.co.uk order has been dispatched. Order #204-3384019-7621488 — Anker USB-C hub. Track your package in Your Orders. Delivery expected tomorrow between 10am and 2pm."),
    ("amazon_order", "Your Amazon package was delivered. It was handed to a resident. If you have not received your package, please check with neighbours or contact Amazon Customer Service."),
    ("amazon_order", "Your Amazon invoice is now available. Order #204-1298721-8452221, £47.60. Download the VAT invoice in Your Orders > Invoice > Print invoice."),

    # ── PayPal notifications ─────────────────────────────────────────────────
    ("paypal", "You sent £45.00 GBP to Sarah Johnson. Transaction ID: 8XR9223K44RN2. If you did not authorise this payment, contact PayPal Customer Service immediately from paypal.com."),
    ("paypal", "You've got money. Michael Chen sent you £120.00 GBP. This payment is now in your PayPal balance and available to transfer to your bank."),
    ("paypal", "Your monthly PayPal activity summary — July 2026. 8 payments sent, 3 payments received. Total spend: £487.20. Sign in at paypal.com to see the full statement."),

    # ── OTP / verification codes ─────────────────────────────────────────────
    ("otp", "Your Google verification code is 483920. Do not share this code with anyone, including Google support. This code expires in 5 minutes."),
    ("otp", "Your Barclays one-time passcode is 728194. Use this code to complete your online payment. Never share it with anyone. Barclays will never call to ask for this code."),
    ("otp", "Discord: 592013 is your verification code. Enter this on Discord to verify your account. Do not share this code with anyone else."),
    ("otp", "Uber: Your verification code is 4837. Never share this code — even with Uber employees. Reply STOP to opt out."),

    # ── Shipping and delivery notifications ──────────────────────────────────
    ("shipping", "DPD: Your parcel from Zara is on its way. Track your parcel at dpd.co.uk with reference 12345678901234. Estimated delivery: Wednesday, 30 July, between 09:00 and 11:00."),
    ("shipping", "DHL Express notification: Waybill 4128473921 has been picked up in Rotterdam, Netherlands, and is on its way to your address in London. Expected delivery: Thursday, 31 July."),
    ("shipping", "USPS Tracking Update: Your package with tracking number 9400 1102 1298 3722 3831 74 was delivered to your mailbox at 14:07 on July 30. Thank you for using USPS."),

    # ── Promotional newsletters ──────────────────────────────────────────────
    ("newsletter", "Substack Weekly · What our writers are reading. This week's picks include Casey Newton on the OpenAI board saga, Anne Helen Petersen on the four-day work week, and a longread from The Atlantic on the ethics of AI voice cloning. Open the newsletter in your browser."),
    ("newsletter", "Airbnb: Your July travel inspiration. Cosy cottages in the Cotswolds from £68/night, historic apartments in Lisbon, and beachfront stays in Cornwall — all handpicked by our editorial team. Browse listings and book by Aug 15 to save 15% on stays over 7 nights."),
    ("newsletter", "Uber Eats: Save 20% on your next 3 orders. Order from any of our 5,000+ restaurants and get 20% off (up to £5 per order). Offer valid until Sunday. Terms apply. Open the app to redeem."),

    # ── Banking notifications ────────────────────────────────────────────────
    ("banking", "Chase alert: A £47.60 debit card purchase was made at TESCO GROCERY on 30 Jul 2026. Available balance: £2,847.19. If you did not make this purchase, please contact Chase immediately at the number on the back of your card."),
    ("banking", "Monzo: You just spent £12.40 at Pret A Manger, London. Available balance: £682.15. See the transaction in your Monzo app."),
    ("banking", "Your HSBC UK monthly statement for account ending 4421 is now available. Please log in to online banking or the mobile app to view your statement. Your next statement will be issued on 31 August 2026."),

    # ── Social media security alerts ─────────────────────────────────────────
    ("social_alert", "Instagram: We noticed a new login. Someone just logged into your Instagram account from an iPhone in London, United Kingdom. If this was you, you can safely ignore this message. If not, please secure your account."),
    ("social_alert", "New login to your X account. Device: Chrome on Windows. Location: London, United Kingdom. If this was you, no action is needed. If not, please reset your password at twitter.com/settings/password."),
    ("social_alert", "LinkedIn: Rachel Wong sent you a message. 'Hi Ameer, thanks for connecting last week — I wanted to follow up on your work on ML evaluation…'. Open the message on LinkedIn to reply."),
]


def call_api(text: str) -> dict:
    body = json.dumps({'text': text}).encode('utf-8')
    req = urllib.request.Request(
        API_URL, data=body, method='POST',
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {'error': f'HTTP {e.code}', 'body': e.read().decode('utf-8', 'ignore')[:200]}
    except Exception as e:
        return {'error': str(e)}


def main() -> int:
    print(f'Manual acceptance test — E5 production model')
    print(f'API: {API_URL}')
    print(f'Corpus: {len(TESTS)} legitimate messages across {len(set(c for c,_ in TESTS))} categories')
    print(f'Threshold: 0.59 (verdict = SCAM if confidence >= 59)')
    print()

    per_cat: dict[str, dict] = defaultdict(lambda: {'n': 0, 'legit': 0, 'scam': 0, 'items': []})
    per_row = []

    print(f'{"category":22s}  {"conf%":>6s}  {"verdict":>7s}   preview')
    print('-' * 100)
    t0 = time.time()

    for i, (category, text) in enumerate(TESTS, 1):
        # 2.1s cadence keeps us under the 30/min /predict rate limit
        if i > 1:
            time.sleep(2.1)
        r = call_api(text)
        if 'error' in r:
            print(f'{category:22s}  {"ERR":>6s}  {"ERR":>7s}   {r["error"]}')
            per_cat[category]['n'] += 1
            per_cat[category]['items'].append({'i': i, 'error': r['error']})
            continue

        verdict = r.get('verdict', '?')
        conf = float(r.get('confidence', 0))
        preview = text[:70].replace('\n', ' ')

        per_cat[category]['n'] += 1
        if verdict == 'LEGIT':
            per_cat[category]['legit'] += 1
        else:
            per_cat[category]['scam'] += 1

        per_cat[category]['items'].append({
            'i': i,
            'verdict': verdict,
            'confidence': conf,
            'text': text,
        })

        per_row.append({
            'i': i, 'category': category, 'verdict': verdict, 'confidence': conf,
        })

        marker = '✓' if verdict == 'LEGIT' else '✗'
        print(f'{category:22s}  {conf:>6.2f}  {verdict:>7s} {marker}  {preview}...')

    elapsed = time.time() - t0
    print()
    print('=' * 100)
    print(f'PER-CATEGORY SUMMARY  ·  {len(TESTS)} messages  ·  {elapsed:.1f}s elapsed')
    print('=' * 100)
    print(f'{"category":22s}  {"n":>4s}  {"LEGIT ✓":>8s}  {"SCAM ✗":>7s}  {"FP rate":>7s}')
    print('-' * 60)
    tot_n = tot_legit = tot_scam = 0
    for cat in sorted(per_cat):
        s = per_cat[cat]
        fp_rate = s['scam'] / s['n'] if s['n'] else 0
        tot_n += s['n']
        tot_legit += s['legit']
        tot_scam += s['scam']
        marker = '' if s['scam'] == 0 else '  ← FP'
        print(f'{cat:22s}  {s["n"]:>4d}  {s["legit"]:>8d}  {s["scam"]:>7d}  {fp_rate:>6.1%}{marker}')
    print('-' * 60)
    tot_fp_rate = tot_scam / tot_n if tot_n else 0
    print(f'{"TOTAL":22s}  {tot_n:>4d}  {tot_legit:>8d}  {tot_scam:>7d}  {tot_fp_rate:>6.1%}')

    # Detail of any false positives
    fps = [it for cat in per_cat.values() for it in cat['items']
           if it.get('verdict') and it['verdict'] != 'LEGIT']
    if fps:
        print()
        print('=' * 100)
        print(f'FALSE POSITIVES ({len(fps)}) — E5 called these SCAM but they are real legitimate messages')
        print('=' * 100)
        for fp in fps:
            cat = next(c for c, s in per_cat.items() if fp in s['items'])
            print(f'  [{cat}]  #{fp["i"]}  verdict={fp["verdict"]} conf={fp["confidence"]:.2f}%')
            print(f'     {fp["text"]}')
            print()

    # Save results
    out_path = os.path.join(BASE, 'tests', 'manual_acceptance_results.json')
    with open(out_path, 'w') as f:
        json.dump({
            'api_url': API_URL,
            'n_messages': len(TESTS),
            'n_categories': len(per_cat),
            'total_legit': tot_legit,
            'total_scam_false_positives': tot_scam,
            'overall_fp_rate': round(tot_fp_rate, 4),
            'per_category': {c: {
                'n': s['n'], 'legit': s['legit'], 'scam': s['scam'],
                'fp_rate': round(s['scam']/s['n'], 4) if s['n'] else 0,
            } for c, s in per_cat.items()},
            'per_row': per_row,
            'false_positives': [{
                'category': next(c for c, s in per_cat.items() if fp in s['items']),
                'i': fp['i'], 'verdict': fp['verdict'],
                'confidence': fp['confidence'], 'text': fp['text'],
            } for fp in fps],
        }, f, indent=2, ensure_ascii=False)
    print(f'\nSaved: {out_path}')
    return 0 if tot_scam == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
