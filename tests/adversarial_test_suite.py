"""
ScamRadar+ | Adversarial Test Suite
50 real-world messages across all scam and legit categories.
Run with:  python tests/adversarial_test_suite.py
Results saved to:  tests/adversarial_results.txt
"""

import os, sys, pickle, time, textwrap
from datetime import datetime

import faiss
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MODELS_PATH, DEFAULT_THRESHOLD
from src._09_prediction_pipeline import predict_message

# ── Colour codes (terminal) ────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


# ══════════════════════════════════════════════════════════════════════════
#  TEST CASES  (label: 1=SCAM  0=LEGIT)
# ══════════════════════════════════════════════════════════════════════════

TEST_CASES = [

    # ── PHISHING (5) ───────────────────────────────────────────────────────
    {
        "id": 1, "category": "Phishing", "label": 1,
        "message": "URGENT: Your PayPal account has been suspended verify now at http://paypal-secure-verify.tk/login",
    },
    {
        "id": 2, "category": "Phishing", "label": 1,
        "message": "Dear customer your Apple ID has been locked visit apple-id-verify.com/unlock to restore access within 24 hours",
    },
    {
        "id": 3, "category": "Phishing", "label": 1,
        "message": "Your Netflix account payment failed update your billing at netflix-billing-update.net/pay or lose access tonight",
    },
    {
        "id": 4, "category": "Phishing", "label": 1,
        "message": "Dear Ameer your Google account was accessed from Russia click http://google-security-alert.xyz/verify to secure it now",
    },
    {
        "id": 5, "category": "Phishing", "label": 1,
        "message": "IT Department: Your Emek Yezreel College account will expire verify at yvc-student-portal.net/verify within 2 hours",
    },

    # ── INVESTMENT / CRYPTO (5) ────────────────────────────────────────────
    {
        "id": 6, "category": "Investment/Crypto", "label": 1,
        "message": "I turned $500 into $12000 in 6 weeks with this crypto strategy DM me for the link no experience needed",
    },
    {
        "id": 7, "category": "Investment/Crypto", "label": 1,
        "message": "Not trying to sell you anything just paying it forward happy to share what worked for me in the market let me know",
    },
    {
        "id": 8, "category": "Investment/Crypto", "label": 1,
        "message": "Our AI trading bot guarantees 15% monthly returns minimum investment $1000 spots filling up fast",
    },
    {
        "id": 9, "category": "Investment/Crypto", "label": 1,
        "message": "My uncle taught me a forex strategy that made me $40k last month I can show you if interested no pressure",
    },
    {
        "id": 10, "category": "Investment/Crypto", "label": 1,
        "message": "Passive income opportunity work from anywhere be your own boss $500 daily guaranteed start today with just $100",
    },

    # ── ROMANCE / ADVANCE FEE (5) ─────────────────────────────────────────
    {
        "id": 11, "category": "Romance/Advance Fee", "label": 1,
        "message": "Hi beautiful I am US Army officer deployed in Syria I have gold bars need help transferring out of country will give you 30%",
    },
    {
        "id": 12, "category": "Romance/Advance Fee", "label": 1,
        "message": "I am Dr Emmanuel Okafor senior banker Lagos Nigeria business proposal $15.5 million USD requires your assistance 40% commission",
    },
    {
        "id": 13, "category": "Romance/Advance Fee", "label": 1,
        "message": "Hey I think we matched on Tinder I am Linda forex trader Singapore made $40k last month can show you my strategy",
    },
    {
        "id": 14, "category": "Romance/Advance Fee", "label": 1,
        "message": "My late husband left $8.5 million I need trusted person to help transfer funds you will receive 35% please send bank details",
    },
    {
        "id": 15, "category": "Romance/Advance Fee", "label": 1,
        "message": "I fell in love with your profile I am widower doctor in US Army need your help with financial transfer will reward generously",
    },

    # ── EMERGENCY / GRANDPARENT (3) ───────────────────────────────────────
    {
        "id": 16, "category": "Emergency/Grandparent", "label": 1,
        "message": "Grandma its me Jake I got arrested in Mexico need bail money urgently please do not tell mom and dad wire $3500 immediately",
    },
    {
        "id": 17, "category": "Emergency/Grandparent", "label": 1,
        "message": "Dad I lost my wallet and phone in Paris I am stranded need you to wire $800 urgently do not call me use this number",
    },
    {
        "id": 18, "category": "Emergency/Grandparent", "label": 1,
        "message": "Mom it is Sarah I am in hospital abroad insurance not covering emergency surgery need $2000 transferred immediately please hurry",
    },

    # ── JOB / MONEY MULE (3) ─────────────────────────────────────────────
    {
        "id": 19, "category": "Job/Money Mule", "label": 1,
        "message": "HIRING NOW work from home data entry $500 per day guaranteed no experience needed send full name address bank details to start",
    },
    {
        "id": 20, "category": "Job/Money Mule", "label": 1,
        "message": "Hi got your number from mutual friend looking for trustworthy person to help receive payments on my behalf pays $300 per transaction",
    },
    {
        "id": 21, "category": "Job/Money Mule", "label": 1,
        "message": "Remote position available $24/hour 3-4 hours daily before we proceed verify identity at hrverify-staffing.com/apply within 48 hours",
    },

    # ── DELIVERY SCAM (2) ─────────────────────────────────────────────────
    {
        "id": 22, "category": "Delivery Scam", "label": 1,
        "message": "Your package could not be delivered unpaid customs fee $2.99 pay now to avoid return http://delivery-fees-pay.com/track?id=9823",
    },
    {
        "id": 23, "category": "Delivery Scam", "label": 1,
        "message": "DHL Notice: Your shipment is held at customs pay release fee of $4.50 at dhl-customs-clearance.net/pay within 24 hours",
    },

    # ── TECH SUPPORT (2) ─────────────────────────────────────────────────
    {
        "id": 24, "category": "Tech Support", "label": 1,
        "message": "WARNING your computer infected with virus call Microsoft Support immediately 1-888-248-3941 do not turn off your computer personal data at risk",
    },
    {
        "id": 25, "category": "Tech Support", "label": 1,
        "message": "Your iPhone has been hacked call Apple Support now 1-800-275-9999 your photos and passwords are being stolen act immediately",
    },

    # ── CORPORATE EMAILS (5) ─────────────────────────────────────────────
    {
        "id": 26, "category": "Corporate Email", "label": 0,
        "message": "Your Amazon order of Apple AirPods Pro has shipped estimated delivery Thursday May 1 track at amazon.com/orders order total $249",
    },
    {
        "id": 27, "category": "Corporate Email", "label": 0,
        "message": "Invoice from Adobe Systems due May 15 amount $54.99 Creative Cloud subscription pay at adobe.com/account/billing",
    },
    {
        "id": 28, "category": "Corporate Email", "label": 0,
        "message": "Your FedEx package is out for delivery today no signature required track at fedex.com/tracking questions call 1-800-463-3339",
    },
    {
        "id": 29, "category": "Corporate Email", "label": 0,
        "message": "Receipt from Apple Apple Music subscription $10.99 April 28 2026 if you did not authorize visit reportaproblem.apple.com",
    },
    {
        "id": 30, "category": "Corporate Email", "label": 0,
        "message": "Your Uber trip total $12.40 from Netanya Central to Emek Yezreel College payment Visa ending 4521 view at uber.com/trips",
    },

    # ── SECURITY ALERTS (5) ──────────────────────────────────────────────
    {
        "id": 31, "category": "Security Alert", "label": 0,
        "message": "Your Google Account signed in from Chrome on Windows if this was you ignore this if not visit myaccount.google.com/security",
    },
    {
        "id": 32, "category": "Security Alert", "label": 0,
        "message": "Chase Bank Alert transaction of $1250 on account ending 4521 at Best Buy if not you visit chase.com/fraud or call 1-800-935-9935",
    },
    {
        "id": 33, "category": "Security Alert", "label": 0,
        "message": "Dear customer sign-in to your account from new device April 28 if this was you no action needed if not visit bankofamerica.com/security",
    },
    {
        "id": 34, "category": "Security Alert", "label": 0,
        "message": "Your Apple ID was used to sign in to iCloud on a new iPhone if this was you no action required if not visit appleid.apple.com",
    },
    {
        "id": 35, "category": "Security Alert", "label": 0,
        "message": "Microsoft account unusual sign-in activity from Israel if this was you no further action needed otherwise visit account.microsoft.com/security",
    },

    # ── OTP / VERIFICATION (3) ────────────────────────────────────────────
    {
        "id": 36, "category": "OTP/Verification", "label": 0,
        "message": "Your WhatsApp code is 847-291 do not share this code with anyone WhatsApp will never call you to verify your code",
    },
    {
        "id": 37, "category": "OTP/Verification", "label": 0,
        "message": "Your verification code is 394821 this code expires in 10 minutes do not share it with anyone",
    },
    {
        "id": 38, "category": "OTP/Verification", "label": 0,
        "message": "Use 739-284 as your Microsoft account verification code. Do not share this code.",
    },

    # ── MEMBERSHIP / SUBSCRIPTIONS (3) ───────────────────────────────────
    {
        "id": 39, "category": "Membership/Subscription", "label": 0,
        "message": "Hi Sarah your annual membership auto-renews May 1st locking in your current rate of $89 per year no action needed thanks for being a loyal member",
    },
    {
        "id": 40, "category": "Membership/Subscription", "label": 0,
        "message": "Your Netflix subscription renews on May 5 for $15.49 no action needed to continue your membership manage at netflix.com/account",
    },
    {
        "id": 41, "category": "Membership/Subscription", "label": 0,
        "message": "Reminder your Spotify Premium subscription renews May 3 for $9.99 manage your subscription at spotify.com/account",
    },

    # ── MESSAGING INVITES (2) ─────────────────────────────────────────────
    {
        "id": 42, "category": "Messaging Invite", "label": 0,
        "message": "Moatasem has added you to the group ScamRadar Plus Team tap the link chat.whatsapp.com/ABC123 automated notification from WhatsApp",
    },
    {
        "id": 43, "category": "Messaging Invite", "label": 0,
        "message": "You have been invited to join the Zoom meeting Project Review tap to join zoom.us/j/928374 hosted by Hanan Lev",
    },

    # ── UNIVERSITY / WORK (3) ─────────────────────────────────────────────
    {
        "id": 44, "category": "University/Work", "label": 0,
        "message": "Dear student final exam registration closes May 5 log in to student portal at students.yvc.ac.il to confirm your exam schedule",
    },
    {
        "id": 45, "category": "University/Work", "label": 0,
        "message": "Hi Ameer I came across your profile I am recruiter at Microsoft Israel we have Data Scientist opening would you be open to 15 minute call",
    },
    {
        "id": 46, "category": "University/Work", "label": 0,
        "message": "Meeting tomorrow at 3pm works for me see you then",
    },

    # ── RECEIPTS / ORDERS (4) ─────────────────────────────────────────────
    {
        "id": 47, "category": "Receipt/Order", "label": 0,
        "message": "Thank you for your purchase order 84729 confirmed total $29.99 you will receive shipping confirmation when order ships reply with questions",
    },
    {
        "id": 48, "category": "Receipt/Order", "label": 0,
        "message": "Your Wolt order from Dominos Pizza is on its way estimated arrival 25 minutes order total 89 NIS track at wolt.com/orders",
    },
    {
        "id": 49, "category": "Receipt/Order", "label": 0,
        "message": "Your reservation at Tel Aviv Beach Apartment confirmed May 3-7 check in 3pm host Sarah will meet you booking AIR-928374 view at airbnb.com/trips",
    },
    {
        "id": 50, "category": "Receipt/Order", "label": 0,
        "message": "Hi this is a reminder that your dentist appointment is scheduled for Thursday May 2 at 10am please call 03-555-1234 to reschedule if needed",
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  LOAD PIPELINE
# ══════════════════════════════════════════════════════════════════════════

def load_pipeline():
    print(f"{CYAN}Loading ScamRadar+ pipeline…{RESET}")
    payload    = pickle.load(open(os.path.join(MODELS_PATH, 'scamradar_model.pkl'),  'rb'))
    tfidf      = pickle.load(open(os.path.join(MODELS_PATH, 'tfidf_vectorizer.pkl'), 'rb'))
    char_tfidf = pickle.load(open(os.path.join(MODELS_PATH, 'char_vectorizer.pkl'),  'rb'))
    scaler     = pickle.load(open(os.path.join(MODELS_PATH, 'scaler.pkl'),            'rb'))
    faiss_idx  = faiss.read_index(os.path.join(MODELS_PATH, 'scam_faiss.index'))
    model      = payload['model'] if isinstance(payload, dict) else payload
    threshold  = payload.get('threshold', DEFAULT_THRESHOLD) if isinstance(payload, dict) else DEFAULT_THRESHOLD

    from sentence_transformers import SentenceTransformer
    st_model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"{GREEN}✓ Pipeline loaded  (threshold={threshold:.2f}){RESET}\n")
    return model, tfidf, char_tfidf, scaler, faiss_idx, st_model, threshold


# ══════════════════════════════════════════════════════════════════════════
#  RUN SUITE
# ══════════════════════════════════════════════════════════════════════════

def run_suite(model, tfidf, char_tfidf, scaler, faiss_idx, st_model, threshold):
    results = []
    total   = len(TEST_CASES)

    print(f"{BOLD}{'─'*72}{RESET}")
    print(f"{BOLD}  #  {'CATEGORY':<22} {'EXPECTED':<12} {'GOT':<12} {'CONF':>6}  {'STATUS'}{RESET}")
    print(f"{BOLD}{'─'*72}{RESET}")

    for tc in TEST_CASES:
        r = predict_message(
            tc['message'], model, tfidf, char_tfidf, scaler,
            faiss_idx, st_model, threshold=threshold,
        )

        verdict   = r['verdict']
        conf      = r['confidence']
        expected  = 'SCAM' if tc['label'] == 1 else 'LEGIT'

        # A true positive: expected SCAM → got SCAM or SUSPICIOUS
        # A true negative: expected LEGIT → got LEGIT or SUSPICIOUS (gray area)
        # We count SUSPICIOUS as the model's "uncertain" band:
        #   - if expected SCAM  and got SUSPICIOUS → PARTIAL PASS (fp for legit, fn for scam)
        #   - if expected LEGIT and got SUSPICIOUS → PARTIAL PASS

        if tc['label'] == 1:
            if verdict == 'SCAM':
                status = 'PASS'
            elif verdict == 'SUSPICIOUS':
                status = 'PARTIAL'   # caught something but below SCAM threshold
            else:
                status = 'FAIL'      # false negative
        else:  # label == 0
            if verdict == 'LEGIT':
                status = 'PASS'
            elif verdict == 'SUSPICIOUS':
                status = 'PARTIAL'   # borderline false positive
            else:
                status = 'FAIL'      # false positive

        colour = GREEN if status == 'PASS' else (YELLOW if status == 'PARTIAL' else RED)

        print(
            f"  {tc['id']:>2}  {tc['category']:<22} "
            f"{expected:<12} {verdict:<12} {conf:>5.1f}%  "
            f"{colour}{status}{RESET}"
        )

        results.append({**tc, 'verdict': verdict, 'confidence': conf, 'status': status})

    return results


# ══════════════════════════════════════════════════════════════════════════
#  REPORT GENERATION
# ══════════════════════════════════════════════════════════════════════════

def generate_report(results, threshold):
    scam_cases  = [r for r in results if r['label'] == 1]
    legit_cases = [r for r in results if r['label'] == 0]

    # ── overall ────────────────────────────────────────────────────────────
    # Hard pass: full correct verdict
    hard_pass   = sum(1 for r in results if r['status'] == 'PASS')
    partial     = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail        = sum(1 for r in results if r['status'] == 'FAIL')
    total       = len(results)

    # False negatives: scam classified as LEGIT
    fn = [r for r in scam_cases  if r['status'] == 'FAIL']
    # False positives: legit classified as SCAM
    fp = [r for r in legit_cases if r['status'] == 'FAIL']
    # Partial FN (scam → SUSPICIOUS)
    partial_fn = [r for r in scam_cases  if r['status'] == 'PARTIAL']
    # Partial FP (legit → SUSPICIOUS)
    partial_fp = [r for r in legit_cases if r['status'] == 'PARTIAL']

    fn_rate_strict = len(fn) / len(scam_cases) * 100
    fp_rate_strict = len(fp) / len(legit_cases) * 100
    accuracy_strict = hard_pass / total * 100
    accuracy_soft   = (hard_pass + partial) / total * 100

    # ── per-category ───────────────────────────────────────────────────────
    cat_map = {}
    for r in results:
        c = r['category']
        cat_map.setdefault(c, []).append(r)

    lines = []

    lines.append("=" * 72)
    lines.append(f"  ScamRadar+  |  Adversarial Test Suite Report")
    lines.append(f"  Generated:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Threshold:  {threshold:.2f}  (≥0.60 = SCAM, {threshold:.2f}–0.60 = SUSPICIOUS)")
    lines.append("=" * 72)
    lines.append("")

    # ── overall summary ────────────────────────────────────────────────────
    lines.append("OVERALL SUMMARY")
    lines.append("─" * 40)
    lines.append(f"  Total messages tested : {total}")
    lines.append(f"  Full passes (PASS)    : {hard_pass}  ({accuracy_strict:.1f}%)")
    lines.append(f"  Partial (SUSPICIOUS)  : {partial}")
    lines.append(f"  Failures (wrong tier) : {fail}")
    lines.append(f"  Soft accuracy         : {accuracy_soft:.1f}%  (PASS + PARTIAL counted)")
    lines.append(f"  Strict accuracy       : {accuracy_strict:.1f}%  (PASS only)")
    lines.append("")
    lines.append(f"  Scam messages  ({len(scam_cases):>2} total)")
    lines.append(f"    Correctly flagged (SCAM)     : {sum(1 for r in scam_cases if r['verdict']=='SCAM')}")
    lines.append(f"    Caught but borderline (SUSP) : {len(partial_fn)}")
    lines.append(f"    Missed (LEGIT)               : {len(fn)}  ← False Negatives")
    lines.append(f"    False Negative Rate          : {fn_rate_strict:.1f}%")
    lines.append("")
    lines.append(f"  Legit messages ({len(legit_cases):>2} total)")
    lines.append(f"    Correctly cleared (LEGIT)    : {sum(1 for r in legit_cases if r['verdict']=='LEGIT')}")
    lines.append(f"    Borderline (SUSPICIOUS)      : {len(partial_fp)}")
    lines.append(f"    Over-flagged (SCAM)          : {len(fp)}   ← False Positives")
    lines.append(f"    False Positive Rate          : {fp_rate_strict:.1f}%")
    lines.append("")

    # ── per-category breakdown ─────────────────────────────────────────────
    lines.append("CATEGORY BREAKDOWN")
    lines.append("─" * 72)
    lines.append(f"  {'Category':<26} {'N':>3}  {'PASS':>6}  {'PARTIAL':>7}  {'FAIL':>5}  {'Pass%':>6}")
    lines.append("  " + "─" * 60)

    cat_rows = []
    for cat, items in sorted(cat_map.items()):
        n       = len(items)
        passes  = sum(1 for r in items if r['status'] == 'PASS')
        parts   = sum(1 for r in items if r['status'] == 'PARTIAL')
        fails   = sum(1 for r in items if r['status'] == 'FAIL')
        pct     = passes / n * 100
        cat_rows.append((pct, cat, n, passes, parts, fails))

    for pct, cat, n, passes, parts, fails in sorted(cat_rows, key=lambda x: x[0]):
        bar = "██" if pct == 100 else ("▓▓" if pct >= 60 else "░░")
        lines.append(f"  {cat:<26} {n:>3}  {passes:>6}  {parts:>7}  {fails:>5}  {pct:>5.0f}% {bar}")

    lines.append("")

    # ── full result table ──────────────────────────────────────────────────
    lines.append("DETAILED RESULTS")
    lines.append("─" * 72)
    lines.append(f"  {'#':>2}  {'Category':<22} {'Expected':<10} {'Got':<12} {'Conf':>6}  Status")
    lines.append("  " + "─" * 62)
    for r in results:
        expected = 'SCAM' if r['label'] == 1 else 'LEGIT'
        marker = "  " if r['status'] == 'PASS' else ("⚠ " if r['status'] == 'PARTIAL' else "✗ ")
        lines.append(
            f"  {r['id']:>2}  {r['category']:<22} {expected:<10} {r['verdict']:<12} "
            f"{r['confidence']:>5.1f}%  {marker}{r['status']}"
        )
    lines.append("")

    # ── failures deep-dive ─────────────────────────────────────────────────
    if fn or fp or partial_fn or partial_fp:
        lines.append("FAILURES AND BORDERLINE CASES")
        lines.append("─" * 72)

        if fn:
            lines.append(f"\n  FALSE NEGATIVES  ({len(fn)} scam(s) missed — classified as LEGIT)")
            for r in fn:
                lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
                wrapped = textwrap.fill(r['message'], width=64, initial_indent='    ', subsequent_indent='    ')
                lines.append(wrapped)

        if partial_fn:
            lines.append(f"\n  BORDERLINE SCAMS  ({len(partial_fn)} caught as SUSPICIOUS, not SCAM)")
            for r in partial_fn:
                lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
                wrapped = textwrap.fill(r['message'], width=64, initial_indent='    ', subsequent_indent='    ')
                lines.append(wrapped)

        if fp:
            lines.append(f"\n  FALSE POSITIVES  ({len(fp)} legit message(s) flagged as SCAM)")
            for r in fp:
                lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
                wrapped = textwrap.fill(r['message'], width=64, initial_indent='    ', subsequent_indent='    ')
                lines.append(wrapped)

        if partial_fp:
            lines.append(f"\n  BORDERLINE LEGIT  ({len(partial_fp)} legit message(s) classified as SUSPICIOUS)")
            for r in partial_fp:
                lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
                wrapped = textwrap.fill(r['message'], width=64, initial_indent='    ', subsequent_indent='    ')
                lines.append(wrapped)
    else:
        lines.append("FAILURES AND BORDERLINE CASES")
        lines.append("─" * 72)
        lines.append("  None — perfect suite score!")

    lines.append("")
    lines.append("=" * 72)
    lines.append(f"  ScamRadar+ Adversarial Test Suite  |  {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 72)

    return "\n".join(lines), {
        'total':            total,
        'hard_pass':        hard_pass,
        'partial':          partial,
        'fail':             fail,
        'accuracy_strict':  accuracy_strict,
        'accuracy_soft':    accuracy_soft,
        'fn_rate':          fn_rate_strict,
        'fp_rate':          fp_rate_strict,
        'fn':               fn,
        'fp':               fp,
        'partial_fn':       partial_fn,
        'partial_fp':       partial_fp,
    }


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    model, tfidf, char_tfidf, scaler, faiss_idx, st_model, threshold = load_pipeline()

    results = run_suite(model, tfidf, char_tfidf, scaler, faiss_idx, st_model, threshold)

    elapsed = time.time() - t0
    print(f"\n{DIM}Suite completed in {elapsed:.1f}s{RESET}\n")

    report_text, stats = generate_report(results, threshold)

    # ── Print report ───────────────────────────────────────────────────────
    print("\n" + report_text)

    # ── Save to file ───────────────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), 'adversarial_results.txt')
    with open(out_path, 'w') as f:
        f.write(report_text)
    print(f"\n{GREEN}Results saved → {out_path}{RESET}")

    # ── Final scorecard banner ─────────────────────────────────────────────
    pct = stats['accuracy_strict']
    colour = GREEN if pct >= 90 else (YELLOW if pct >= 70 else RED)
    print(f"\n{BOLD}{colour}{'═'*50}{RESET}")
    print(f"{BOLD}{colour}  Strict accuracy : {pct:.1f}%  ({stats['hard_pass']}/{stats['total']} PASS){RESET}")
    print(f"{BOLD}{colour}  Soft accuracy   : {stats['accuracy_soft']:.1f}%  (includes PARTIAL){RESET}")
    print(f"{BOLD}{colour}  False Negatives : {stats['fn_rate']:.1f}%  |  False Positives : {stats['fp_rate']:.1f}%{RESET}")
    print(f"{BOLD}{colour}{'═'*50}{RESET}\n")


if __name__ == '__main__':
    main()
