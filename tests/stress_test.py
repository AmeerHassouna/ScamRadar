"""
ScamRadar+ stress test — covers obvious scams, borderline spam,
legitimate messages, edge cases, and adversarial inputs.
Run from the project root:  python tests/stress_test.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src._09_prediction_pipeline import load_pipeline, predict_message
from config import DEFAULT_THRESHOLD

# ── Load pipeline once ─────────────────────────────────────────────────────
print("Loading pipeline…")
model, tfidf, char_tfidf, scaler, scam_idx, st_model = load_pipeline()
print(f"Threshold: {DEFAULT_THRESHOLD}\n")

# ── Test cases ─────────────────────────────────────────────────────────────
# Format: (category, expected_verdict, label, message)
TESTS = [

    # ══ CLEAR SCAMS — must be SCAM ══════════════════════════════════════════

    ("CLEAR_SCAM", "SCAM",
     "Classic PayPal phishing",
     "URGENT: Your PayPal account has been suspended! Verify now at http://paypal-secure-verify.tk/login or lose access permanently."),

    ("CLEAR_SCAM", "SCAM",
     "Nigerian advance-fee",
     "I am the late Dr. Joseph Mensah's next of kin with access to $8.5 million in classified gold. I need your bank account details to transfer these secret funds out of the country. You will receive 30% commission percentage for your assistance."),

    ("CLEAR_SCAM", "SCAM",
     "Lottery prize fraud",
     "CONGRATULATIONS! You have been selected as the winner of our $500,000 sweepstakes. You have been chosen from millions of entries. Click here to claim your prize NOW before it expires! Act now — limited time offer!"),

    ("CLEAR_SCAM", "SCAM",
     "Investment bot scam",
     "AI does all the trading — no experience needed. Guaranteed returns of 40% monthly. Financial freedom is just one click away. Work from anywhere! Passive income. Be your own boss. Spots are limited — invest now before spots fill up fast."),

    ("CLEAR_SCAM", "SCAM",
     "Delivery customs fee",
     "Your package is held at customs. Unpaid customs fee of $3.50 required to release your package. Pay the customs clearance fee within 24 hours or your shipment will be returned. Failed delivery attempt — reschedule your delivery now."),

    ("CLEAR_SCAM", "SCAM",
     "Emergency grandparent scam",
     "Mom please do not tell anyone but I got arrested last night and I am in jail. I am scared. Need bail money urgently. Please wire transfer the money now, please hurry. Do not tell Dad. I lost my phone so use this number."),

    ("CLEAR_SCAM", "SCAM",
     "IRS threat scam",
     "IRS FINAL NOTICE: You are linked to illegal activity. An arrest warrant has been issued. To avoid arrest and legal action you must call immediately. Face arrest if you ignore this notice. This is your last warning."),

    ("CLEAR_SCAM", "SCAM",
     "Crypto wallet drain",
     "Send bitcoin to this wallet address: 3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5. Unlock your funds by paying the withdrawal fee. Platform fee to withdraw is $200. Insurance fee required. Activation fee to withdraw your earnings."),

    ("CLEAR_SCAM", "SCAM",
     "Gift card payment request",
     "You owe outstanding taxes. Buy $500 in iTunes gift cards and send the card numbers to settle your debt. Scratch the back of the card and read me the code. Pay with gift card to avoid legal action."),

    ("CLEAR_SCAM", "SCAM",
     "Romance scam opener",
     "Hi, I accidentally texted the wrong number but I'm glad I did. I'm a US army officer currently deployed in Afghanistan on a peacekeeping mission. I'm a widower looking for a genuine connection. Would love to get to know you better. Hope you don't mind me reaching out."),

    ("CLEAR_SCAM", "SCAM",
     "Pig butchering opener",
     "I have been using this platform for 6 months and I can guide you personally. Let me show you my portfolio — my profits this month are incredible. Start with as little as $100, trusted trading platform. You can withdraw anytime. I made so much and I want to help you too. Put in a small amount and you will see the returns."),

    ("CLEAR_SCAM", "SCAM",
     "Sextortion blackmail",
     "Unless you pay $1500 in Bitcoin within 48 hours, your browsing history has been recorded and will be sent to your employer and family. Your employer and family will receive a full report. Do not try to contact police."),


    # ══ SPAM (not scam) — should NOT be SCAM ════════════════════════════════

    ("SPAM_NOT_SCAM", "LEGIT",
     "Marketing promotional email",
     "Summer Sale is HERE! Get up to 50% off everything in our store this weekend only. Use code SUMMER50 at checkout. Free shipping on orders over $30. Shop now at our website. Unsubscribe at any time."),

    ("SPAM_NOT_SCAM", "LEGIT",
     "Gym membership upsell",
     "Hey! Your current gym plan doesn't include access to our new spin classes. Upgrade to Premium for just $15/month extra and get unlimited classes, towel service, and sauna access. Reply YES to upgrade or NO to keep your current plan."),

    ("SPAM_NOT_SCAM", "LEGIT",
     "Newsletter with passive income mention",
     "This month in the newsletter: 5 side hustles that actually work in 2024. From freelancing to rental income, we cover passive income strategies that real people use. No get-rich-quick schemes — just honest advice. Read the full issue here."),

    ("SPAM_NOT_SCAM", "LEGIT",
     "Restaurant promotional text",
     "Hi! It's Pete's Pizza. We're running a BOGO deal today only — buy one large pizza, get one free! Show this text in store or use code BOGO online. Valid until 10pm. We hope to see you soon!"),

    ("SPAM_NOT_SCAM", "LEGIT",
     "Retail flash sale",
     "Flash sale alert! 30% off all shoes today only. Limited stock — grab yours before it's gone! Shop at our store or visit our website. Opt out: reply STOP."),

    ("SPAM_NOT_SCAM", "LEGIT",
     "Subscription renewal reminder",
     "Your magazine subscription renews in 7 days. No action needed if you'd like to continue. Annual rate: $29.99. To cancel, log in to your account or call our customer service. Thank you for being a subscriber."),


    # ══ LEGITIMATE MESSAGES — must be LEGIT ════════════════════════════════

    ("LEGIT", "LEGIT",
     "Real PayPal email with trusted domain",
     "You sent a payment of $47.50 to John Smith. If you didn't authorise this, please review your account at https://www.paypal.com/activity. Transaction ID: 5DY61849KN2234512. This email was sent from a notification-only address."),

    ("LEGIT", "LEGIT",
     "Bank statement notification",
     "Your monthly statement for account ending 4521 is ready to view. Log in to your online banking at https://www.chase.com to review your transactions. Your current balance is $1,247.33. Contact us at 1-800-935-9935 if you have questions."),

    ("LEGIT", "LEGIT",
     "OTP verification code",
     "Your ScamRadar verification code is 847-291. Do not share this code with anyone. This code expires in 10 minutes. If you did not request this, please ignore this message."),

    ("LEGIT", "LEGIT",
     "Amazon order confirmation",
     "Your order #112-3456789-1234567 has been shipped. Expected delivery: Thursday, July 17. Track your package at https://www.amazon.com/orders. Sold by: Amazon.com. Questions? Visit our help pages."),

    ("LEGIT", "LEGIT",
     "Doctor appointment reminder",
     "Reminder: You have an appointment with Dr. Sarah Chen on Wednesday July 16 at 2:30pm. Please arrive 10 minutes early. To reschedule call 555-0123. Bring your insurance card and a photo ID."),

    ("LEGIT", "LEGIT",
     "GitHub notification",
     "A pull request was opened on your repository. Title: Fix authentication bug in login handler. Review and merge at https://github.com. You are receiving this because you are subscribed to this repository."),

    ("LEGIT", "LEGIT",
     "Job offer from recruiter",
     "Hi, I came across your profile and I think you'd be a great fit for a Senior Software Engineer role at our company in London. The role offers £85,000 base salary plus equity. Would you be open to a 20-minute call this week to discuss?"),

    ("LEGIT", "LEGIT",
     "Utility bill",
     "Your electricity bill for July is £68.42. Payment due by 28 July. Your usage this month was 312 kWh, which is 8% lower than last month. Pay online at our website, by phone, or by direct debit. Account reference: 1234567890."),

    ("LEGIT", "LEGIT",
     "University admission email",
     "Congratulations! We are pleased to offer you a place on the BSc Computer Science programme commencing September 2025. Please log in to the student portal to accept your offer by 31 July. We look forward to welcoming you."),


    # ══ EDGE CASES — tricky borderline messages ══════════════════════════════

    ("EDGE_CASE", "LEGIT",
     "Crypto exchange — real platform",
     "Your Coinbase account shows unusual sign-in activity from a new device in Berlin, Germany. If this was you, no action needed. If not, secure your account immediately at https://www.coinbase.com/security. Coinbase will never ask for your password."),

    ("EDGE_CASE", "LEGIT",
     "HR urgent deadline email",
     "URGENT: Benefits enrolment closes Friday. You must log in to the HR portal and confirm your selections by 5pm or you will be auto-enrolled in the default plan. Contact HR at benefits@company.com if you need help."),

    ("EDGE_CASE", "LEGIT",
     "Financial newsletter with invest language",
     "Markets update: tech stocks rallied 2.3% today after strong earnings. Our analysts see opportunity in semiconductor names given AI demand. Invest wisely and always diversify. Past performance is not indicative of future returns. This is not financial advice."),

    ("EDGE_CASE", "SUSPICIOUS",
     "Vague investment DM",
     "Hey I just wanted to share something with you. I've been making really good money online the last few months, not spam I promise. Just a regular person who found something that works. Happy to share the strategy if you're interested. DM me."),

    ("EDGE_CASE", "SUSPICIOUS",
     "Suspicious account warning no URL",
     "Your account has been suspended due to suspicious activity. Verify your credentials immediately to avoid permanent closure. This is your final notice before we take further action."),

    ("EDGE_CASE", "LEGIT",
     "Gym trainer personal message",
     "Hi! I'm Alex, your new personal trainer at the gym. I noticed you've been coming in consistently — great work! I'd love to offer you a free 30-minute fitness assessment this week. Let me know what time works best for you."),

    ("EDGE_CASE", "LEGIT",
     "Charity donation request",
     "Dear supporter, as the year ends we ask for your help. Children in conflict zones need food and medical care. Your donation of any amount makes a difference. Donate securely at our charity website. Thank you for your kindness and generosity."),

    ("EDGE_CASE", "LEGIT",
     "Real estate agent follow-up",
     "Hi, I'm following up on the property you viewed last Tuesday at 42 Oak Street. The sellers have received another offer and are looking for best and final offers by noon Friday. Let me know if you'd like to proceed. Happy to answer any questions."),


    # ══ ADVERSARIAL — evasion attempts ══════════════════════════════════════

    ("ADVERSARIAL", "SCAM",
     "Leet speak phishing",
     "URG3NT: Y0ur P4yP4l 4cc0unt h4s b33n SUSP3ND3D! V3r1fy n0w 4t http://p4yp4l-s3cur3.tk/l0g1n 0r l0s3 4cc3ss p3rm4n3ntly!!!"),

    ("ADVERSARIAL", "SCAM",
     "Emoji-padded scam",
     "🎉 CONGRATULATIONS 🎉 You have been selected 🏆 as the WINNER of our $500,000 💰 prize! You have won! 🎰 Click here to claim your prize 👉 before it expires! Act now ⏰ limited time offer!"),

    ("ADVERSARIAL", "SCAM",
     "Mixed case evasion",
     "yOuR pAyPaL aCcOuNt HaS bEeN sUspeNdEd. VeRiFy NoW oR yOuR aCcOuNt WiLl Be LoCkEd PeRmAnEnTlY. ClIcK hErE tO vErIfY yOuR cReDenTiAlS iMmEdIaTeLy."),

    ("ADVERSARIAL", "SCAM",
     "Extra whitespace evasion",
     "Y o u r  a c c o u n t  h a s  b e e n  s u s p e n d e d.  V e r i f y  y o u r  c r e d e n t i a l s  n o w  o r  f a c e  a r r e s t.  I R S  f i n a l  n o t i c e."),

    ("ADVERSARIAL", "SCAM",
     "Soft-sell investment, no hard keywords",
     "This isn't a sales pitch. I'm just a normal person who figured out what actually works for building wealth. No MLM, no pyramid scheme. Just a simple system I use from home. If you're tired of the grind and want to know more, DM me. No pressure at all."),
]

# ── Runner ─────────────────────────────────────────────────────────────────
PASS = FAIL = NEAR_MISS = 0
results = []

for category, expected, label, msg in TESTS:
    r = predict_message(msg, model, tfidf, char_tfidf, scaler,
                        scam_idx, st_model,
                        threshold=DEFAULT_THRESHOLD,
                        vt_api_key=None, gsb_api_key=None)
    verdict = r['verdict']
    conf    = r['confidence']
    prox    = r['proximity_score']

    # Determine pass/fail
    if verdict == expected:
        status = "PASS"
        PASS += 1
    else:
        # Near-miss: expected SCAM but got SUSPICIOUS (or vice versa — 1 tier off)
        tiers = ["LEGIT", "SUSPICIOUS", "SCAM"]
        exp_i = tiers.index(expected) if expected in tiers else -1
        got_i = tiers.index(verdict)  if verdict  in tiers else -1
        if abs(exp_i - got_i) == 1:
            status = "NEAR "
            NEAR_MISS += 1
        else:
            status = "FAIL "
            FAIL += 1

    results.append((status, category, expected, verdict, conf, prox, label))

# ── Print results ──────────────────────────────────────────────────────────
print(f"{'STATUS':<7} {'CAT':<16} {'EXPECTED':<12} {'GOT':<12} {'CONF':>6}  {'PROX':>6}  LABEL")
print("─" * 100)

for status, cat, expected, verdict, conf, prox, label in results:
    marker = "" if status == "PASS" else (" <<< NEAR MISS" if "NEAR" in status else " <<< FAIL")
    print(f"{status:<7} {cat:<16} {expected:<12} {verdict:<12} {conf:>5.1f}%  {prox:>6.3f}  {label}{marker}")

# ── Summary ────────────────────────────────────────────────────────────────
total = PASS + NEAR_MISS + FAIL
print("\n" + "═" * 100)
print(f"RESULTS:  {PASS}/{total} PASS  |  {NEAR_MISS} NEAR MISS (1 tier off)  |  {FAIL} FAIL  |  Accuracy: {PASS/total*100:.1f}%")

# ── Breakdown by category ───────────────────────────────────────────────────
print("\nBREAKDOWN BY CATEGORY:")
from collections import defaultdict
cat_stats = defaultdict(lambda: {"pass": 0, "near": 0, "fail": 0, "total": 0})
for status, cat, *_ in results:
    cat_stats[cat]["total"] += 1
    if status == "PASS":
        cat_stats[cat]["pass"] += 1
    elif "NEAR" in status:
        cat_stats[cat]["near"] += 1
    else:
        cat_stats[cat]["fail"] += 1

for cat, s in cat_stats.items():
    bar = "█" * s["pass"] + "▒" * s["near"] + "░" * s["fail"]
    print(f"  {cat:<16}  {s['pass']}/{s['total']} pass  {s['near']} near  {s['fail']} fail  [{bar}]")

print()
