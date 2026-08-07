"""
E5 parity test — verifies the production inference pipeline produces IDENTICAL
probabilities and verdicts to the frozen E5 bundle on a diverse message set.

For each test message, this script:
  1. Calls the frozen E5 bundle directly (loaded from models/e5_bundle.joblib):
     p_bundle = pipe.predict_proba([text])[0, 1]
  2. Calls the production API: POST /predict {text} → confidence
  3. Compares:
     - Probability: p_bundle vs (confidence/100), tolerance 1e-4
     - Verdict:      SCAM/LEGIT match, computed as (p >= 0.59)

Any mismatch → fail the test with a diagnostic.
"""
import json
import os
import ssl
import sys
import urllib.request
import warnings

import certifi
import joblib

warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE_PATH = os.path.join(BASE, 'models', 'e5_bundle.joblib')
API_URL = 'http://127.0.0.1:8000/predict'
E5_THRESHOLD = 0.59
TOL = 1e-4

SSL_CTX = ssl.create_default_context(cafile=certifi.where())


# Representative test set — 12 messages across categories the user named:
# legitimate, scam, OTP, promotional, business, conversational.
TESTS = [
    # (tag, text)
    ('legit_chat',          "Hey, are we still on for coffee tomorrow at 10am? Let me know if the time still works."),
    ('legit_business',      "Hi team, please note the office will be closed Monday 26 August for the bank holiday. Have a great long weekend. HR"),
    ('legit_recruiter',     "Hi Ameer, I saw your profile on LinkedIn. We have a Senior ML Engineer role that might interest you. Available for a 30-min chat next week?"),
    ('legit_delivery',      "Your Amazon package will arrive Wednesday between 10am and 2pm. Track it in your Amazon account."),
    ('legit_otp',           "Your Google verification code is 483920. Do not share this code with anyone."),
    ('legit_promo',         "Your Netflix subscription will auto-renew on May 1st at $15.99. Cancel anytime in Settings > Account > Billing."),

    ('scam_obvious_phish',  "URGENT: Your account has been suspended. Verify immediately at http://bit.ly/verify-now or lose access permanently!"),
    ('scam_delivery',       "USPS: Your parcel could not be delivered. Pay a $1.99 rescheduling fee here: https://usps-redelivery.info/schedule"),
    ('scam_crypto',         "Guaranteed 3% daily returns on your USDT staking. No lock-up period. Already 47,000 members. Start now at quantum-staking.finance"),
    ('scam_romance',        "My love, my contract in the North Sea ends next month. My accountant needs proof of a joint bank account to release my final settlement. Would you send me your account details? It's only for verification."),
    ('scam_bec',            "Hi, are you at your desk? I need you to handle a confidential wire transfer of $45,200 for a new vendor before end of day. Please respond ASAP. — Sent from my iPhone"),
    ('scam_recruitment',    "Congratulations! You have been shortlisted for a Product Reviewer position at Amazon Home Testing. Please share your bank details so we can add you to the payroll before we send the first task."),

    ('conversational_long', "Hi, I know we've only been chatting for a few days but I feel like I've found something real. I've been thinking about you all day. I told my sister about you tonight — she said she can hear the difference in my voice when I talk about you. I hope that's not too much."),
]


def load_frozen_e5():
    """Load the frozen E5 bundle from disk (word+char TF-IDF → LogReg)."""
    b = joblib.load(BUNDLE_PATH)
    return b['model'], float(b['threshold_f1'])


def call_api(text):
    body = json.dumps({'text': text}).encode('utf-8')
    req = urllib.request.Request(
        API_URL, data=body, method='POST',
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main():
    pipe, thresh = load_frozen_e5()
    print(f'Frozen E5 bundle loaded. threshold_f1 = {thresh}')
    print(f'Local API      : {API_URL}')
    print(f'Tolerance      : {TOL}')
    print()

    hdr = f"{'tag':22s} {'p_bundle':>8s} {'p_api':>8s} {'Δ':>10s}  {'v_bund':>7s} {'v_api':>7s}  match?"
    print(hdr)
    print('-' * len(hdr))

    n = 0
    n_pass_prob = 0
    n_pass_verdict = 0
    failures = []

    for tag, text in TESTS:
        n += 1
        # Frozen E5 bundle probability + verdict
        p_bundle = float(pipe.predict_proba([text])[0, 1])
        v_bundle = 'SCAM' if p_bundle >= thresh else 'LEGIT'

        # Production API probability + verdict
        r = call_api(text)
        v_api = r.get('verdict')
        conf = r.get('confidence', 0)
        p_api = conf / 100.0

        # Compare
        d = abs(p_bundle - p_api)
        prob_match = (d < TOL)
        verdict_match = (v_bundle == v_api)
        both = prob_match and verdict_match

        if prob_match: n_pass_prob += 1
        if verdict_match: n_pass_verdict += 1
        if not both:
            failures.append((tag, p_bundle, p_api, v_bundle, v_api, text[:80]))

        mark = 'OK' if both else ('PROB✗' if not prob_match else 'VERDICT✗')
        print(f'{tag:22s} {p_bundle:>8.4f} {p_api:>8.4f} {d:>10.2e}  '
              f'{v_bundle:>7s} {v_api:>7s}  {mark}')

    print()
    print(f'Probability parity: {n_pass_prob}/{n}')
    print(f'Verdict parity:     {n_pass_verdict}/{n}')

    if failures:
        print('\n=== FAILURES ===')
        for tag, pb, pa, vb, va, txt in failures:
            print(f'  [{tag}] p_bundle={pb:.6f}  p_api={pa:.6f}  Δ={abs(pb-pa):.2e}')
            print(f'    v_bundle={vb}  v_api={va}')
            print(f'    text: {txt}')
        sys.exit(1)

    print('\nPARITY CONFIRMED: production API matches the frozen E5 bundle within tolerance.')


if __name__ == '__main__':
    main()
