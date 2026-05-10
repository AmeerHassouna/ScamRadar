"""
ScamRadar+ | Adversarial Test Suite v2
100 messages — harder, more diverse, with edge cases and sophisticated attacks.
Run with:  python tests/adversarial_test_suite_v2.py
Results saved to:  tests/adversarial_results_v2.txt
"""

import os, sys, pickle, time, textwrap
from datetime import datetime

import faiss
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MODELS_PATH, DEFAULT_THRESHOLD
from src._09_prediction_pipeline import predict_message

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

    # ── ADVANCED PHISHING (10) ─────────────────────────────────────────────
    {
        "id": 1, "category": "Advanced Phishing", "label": 1,
        "message": "Dear user your Binance account has been flagged for suspicious activity verify immediately at binance-security-check.com/verify or your funds will be frozen",
    },
    {
        "id": 2, "category": "Advanced Phishing", "label": 1,
        "message": "Your Amazon Prime membership could not be renewed update payment at amazon-prime-billing.net/update within 24 hours to avoid cancellation",
    },
    {
        "id": 3, "category": "Advanced Phishing", "label": 1,
        "message": "LinkedIn Security Alert: someone tried to access your account from China secure your profile at linkedin-account-secure.com/verify now",
    },
    {
        "id": 4, "category": "Advanced Phishing", "label": 1,
        "message": "Your Instagram account will be permanently deleted due to copyright violation appeal at instagram-copyright-appeal.com/dispute within 48 hours",
    },
    {
        "id": 5, "category": "Advanced Phishing", "label": 1,
        "message": "Dropbox: your shared files will be deleted unless you verify your account at dropbox-account-verify.net/confirm today",
    },
    {
        "id": 6, "category": "Advanced Phishing", "label": 1,
        "message": "Dear Ameer your Emek Yezreel College student ID expires this semester renew at yvc-registration-portal.com/renew before May 31",
    },
    {
        "id": 7, "category": "Advanced Phishing", "label": 1,
        "message": "Your GitHub repository has been flagged for malicious code review required at github-security-review.net/inspect within 24 hours",
    },
    {
        "id": 8, "category": "Advanced Phishing", "label": 1,
        "message": "Spotify Premium payment failed update billing at spotify-payment-update.com/billing or lose your subscription tonight",
    },
    {
        "id": 9, "category": "Advanced Phishing", "label": 1,
        "message": "Your Zoom account has been suspended due to policy violation restore access at zoom-account-restore.net/verify immediately",
    },
    {
        "id": 10, "category": "Advanced Phishing", "label": 1,
        "message": "Adobe Creative Cloud license expired renew at adobe-license-renewal.com/activate within 48 hours to keep access",
    },

    # ── SOPHISTICATED INVESTMENT (10) ──────────────────────────────────────
    {
        "id": 11, "category": "Sophisticated Investment", "label": 1,
        "message": "Hey I noticed you follow finance accounts thought you might appreciate this strategy my mentor showed me turned my $300 into $9000 in 8 weeks happy to share",
    },
    {
        "id": 12, "category": "Sophisticated Investment", "label": 1,
        "message": "Not spam I promise just a regular person who found something that actually works for building wealth no MLM no pyramid just solid returns DM me",
    },
    {
        "id": 13, "category": "Sophisticated Investment", "label": 1,
        "message": "I was skeptical too but after 3 months of consistent profits I feel obligated to share this with people who deserve financial freedom reach out if curious",
    },
    {
        "id": 14, "category": "Sophisticated Investment", "label": 1,
        "message": "My portfolio manager has 94% win rate last 18 months minimum $500 to get started he only takes 10 clients at a time 2 spots left",
    },
    {
        "id": 15, "category": "Sophisticated Investment", "label": 1,
        "message": "Tired of living paycheck to paycheck I was too until 6 months ago now I make more in a week than I used to in a month all legal all legitimate",
    },
    {
        "id": 16, "category": "Sophisticated Investment", "label": 1,
        "message": "The banks do not want you to know this one simple trick to grow your savings 10x faster I learned it from a retired hedge fund manager",
    },
    {
        "id": 17, "category": "Sophisticated Investment", "label": 1,
        "message": "Exclusive invitation only investment club 8% guaranteed weekly returns verified track record 3 years running limited membership available",
    },
    {
        "id": 18, "category": "Sophisticated Investment", "label": 1,
        "message": "My wife thought I was crazy when I invested our savings now she thanks me every day $200 turned into $4500 in 60 days simple system",
    },
    {
        "id": 19, "category": "Sophisticated Investment", "label": 1,
        "message": "Financial advisor here not giving advice just sharing what I personally do with my own money and seeing 20%+ monthly returns consistently",
    },
    {
        "id": 20, "category": "Sophisticated Investment", "label": 1,
        "message": "Crypto arbitrage opportunity zero risk guaranteed profit $500 minimum I handle everything you just sit back and collect",
    },

    # ── ROMANCE / SOCIAL ENGINEERING (5) ──────────────────────────────────
    {
        "id": 21, "category": "Romance/Social Engineering", "label": 1,
        "message": "Hi I found your number through a friend of a friend I am a nurse working with MSF in Yemen would love to chat and get to know you better",
    },
    {
        "id": 22, "category": "Romance/Social Engineering", "label": 1,
        "message": "Hey stranger sorry to bother you I accidentally texted the wrong number but now I am glad I did you seem really interesting want to talk",
    },
    {
        "id": 23, "category": "Romance/Social Engineering", "label": 1,
        "message": "I am a successful entrepreneur based in Dubai looking for a genuine connection tired of fake people hope you do not mind me reaching out directly",
    },
    {
        "id": 24, "category": "Romance/Social Engineering", "label": 1,
        "message": "Hi I think we met at the conference last month I did not get your contact properly I am Sarah I work in finance hope this is the right number",
    },
    {
        "id": 25, "category": "Romance/Social Engineering", "label": 1,
        "message": "My name is Captain James Wilson US Navy currently on peacekeeping mission in Afghanistan would love to connect with someone genuine back home",
    },

    # ── BLACKMAIL / SEXTORTION (3) ─────────────────────────────────────────
    {
        "id": 26, "category": "Blackmail/Sextortion", "label": 1,
        "message": "I have footage from your webcam recorded over the past 3 months send $2000 in Bitcoin to this address within 72 hours or I send it to your contacts",
    },
    {
        "id": 27, "category": "Blackmail/Sextortion", "label": 1,
        "message": "We have hacked your device and recorded you through your camera pay $1500 cryptocurrency within 48 hours or your private videos go public",
    },
    {
        "id": 28, "category": "Blackmail/Sextortion", "label": 1,
        "message": "Your browsing history has been captured and will be sent to your employer and family unless you pay $800 Bitcoin in 24 hours",
    },

    # ── FAKE GOVERNMENT / AUTHORITY (5) ───────────────────────────────────
    {
        "id": 29, "category": "Fake Government/Authority", "label": 1,
        "message": "Israel National Insurance Institute: you have an unclaimed benefit of 3200 NIS claim at bitsuach-leumi-refund.com/claim before it expires",
    },
    {
        "id": 30, "category": "Fake Government/Authority", "label": 1,
        "message": "IRS Final Notice: you owe $4,823 in back taxes call 1-888-555-0192 immediately or face arrest warrant do not ignore this notice",
    },
    {
        "id": 31, "category": "Fake Government/Authority", "label": 1,
        "message": "US Customs and Border Protection: your international package has been seized call 1-800-555-9834 to pay clearance fee and release",
    },
    {
        "id": 32, "category": "Fake Government/Authority", "label": 1,
        "message": "Ministry of Finance Israel: tax refund of 1840 NIS approved submit bank details at misrad-hachasot-refund.net/claim within 30 days",
    },
    {
        "id": 33, "category": "Fake Government/Authority", "label": 1,
        "message": "FBI Cybercrime Division: your IP address has been linked to illegal activity call 1-888-555-7291 immediately to avoid arrest",
    },

    # ── FAKE PRIZE / LOTTERY (5) ──────────────────────────────────────────
    {
        "id": 34, "category": "Fake Prize/Lottery", "label": 1,
        "message": "Samsung 50th Anniversary: you have been randomly selected to receive Galaxy S24 Ultra claim at samsung-50th-prize.com/claim code SAMS50 expires 24 hours",
    },
    {
        "id": 35, "category": "Fake Prize/Lottery", "label": 1,
        "message": "You have won the WhatsApp Anniversary Lottery prize of $850,000 contact claim agent at whatsapplottery2026@gmail.com with your details",
    },
    {
        "id": 36, "category": "Fake Prize/Lottery", "label": 1,
        "message": "Congratulations your email was selected in the Microsoft Annual Draw you have won $500,000 contact claims@microsoft-lottery.net immediately",
    },
    {
        "id": 37, "category": "Fake Prize/Lottery", "label": 1,
        "message": "Your phone number was selected for Vodafone Lucky Draw prize $10,000 to claim send your full name address and ID to vodafone-prize@hotmail.com",
    },
    {
        "id": 38, "category": "Fake Prize/Lottery", "label": 1,
        "message": "Amazon Customer Appreciation: complete this 30 second survey and claim your free $100 Amazon voucher at amazon-survey-reward.net/claim",
    },

    # ── FAKE CHARITY (3) ──────────────────────────────────────────────────
    {
        "id": 39, "category": "Fake Charity", "label": 1,
        "message": "Children in Gaza need your help donate $10 via Western Union to Ahmed Hassan Gaza City every dollar saves a life please share this message",
    },
    {
        "id": 40, "category": "Fake Charity", "label": 1,
        "message": "Hurricane relief fund urgent donations needed send via MoneyGram to Relief Coordinator John Smith Miami FL God bless your generosity",
    },
    {
        "id": 41, "category": "Fake Charity", "label": 1,
        "message": "Cancer patient needs urgent help for treatment costs please send whatever you can via Zelle to 555-234-8821 God will reward your kindness",
    },

    # ── NEW SCAM TYPES (9) ────────────────────────────────────────────────
    {
        "id": 42, "category": "New Scam Types", "label": 1,
        "message": "Your car warranty is about to expire call 1-888-555-3421 immediately to extend coverage before it lapses completely",
    },
    {
        "id": 43, "category": "New Scam Types", "label": 1,
        "message": "Student loan forgiveness program you may qualify for up to $20,000 in relief apply now at student-loan-relief-gov.com/apply deadline May 31",
    },
    {
        "id": 44, "category": "New Scam Types", "label": 1,
        "message": "You have been pre-approved for a personal loan of $50,000 no credit check required apply at fast-loan-approval.net/apply today",
    },
    {
        "id": 45, "category": "New Scam Types", "label": 1,
        "message": "Work from home opportunity Amazon needs product testers earn $300-500 per day testing products keep the products too apply at amazon-tester-jobs.net",
    },
    {
        "id": 46, "category": "New Scam Types", "label": 1,
        "message": "Your electricity provider has overpaid you a refund of $284 claim at electricity-refund-portal.com/claim within 14 days or forfeit",
    },
    {
        "id": 47, "category": "New Scam Types", "label": 1,
        "message": "Crypto wallet recovery service lost access to your Bitcoin we can recover it for a small fee of $199 visit crypto-wallet-recovery.net",
    },
    {
        "id": 48, "category": "New Scam Types", "label": 1,
        "message": "Exclusive pre-sale NFT opportunity only 100 spots whitelist closes tonight invest $200 get guaranteed 10x returns within 30 days",
    },
    {
        "id": 49, "category": "New Scam Types", "label": 1,
        "message": "Your domain ameer.com expires in 3 days renew at domain-renewal-service.net/renew immediately to avoid losing your website and email",
    },
    {
        "id": 50, "category": "New Scam Types", "label": 1,
        "message": "Congratulations you have been selected for our mystery shopper program earn $400 per assignment apply at mystery-shopper-jobs.net/apply",
    },

    # ── TRUSTED COMPANY NOTIFICATIONS (10) ────────────────────────────────
    {
        "id": 51, "category": "Trusted Company", "label": 0,
        "message": "Your GitHub Actions workflow completed successfully 3 tests passed 0 failed view results at github.com/ameer/scamradar/actions",
    },
    {
        "id": 52, "category": "Trusted Company", "label": 0,
        "message": "Slack notification Moatasem mentioned you in ScamRadar channel view message at slack.com/archives/C8821",
    },
    {
        "id": 53, "category": "Trusted Company", "label": 0,
        "message": "Your Airbnb booking is confirmed Tel Aviv Beach May 3-7 host Sarah will meet you at 3pm view details at airbnb.com/trips/928374",
    },
    {
        "id": 54, "category": "Trusted Company", "label": 0,
        "message": "Google Calendar reminder ScamRadar presentation tomorrow 10am Emek Yezreel College Room 204 added by Hanan Lev",
    },
    {
        "id": 55, "category": "Trusted Company", "label": 0,
        "message": "Your Wise transfer of $250 to Moatasem Khalifeh has been sent it will arrive within 1-2 business days view at wise.com/transactions",
    },
    {
        "id": 56, "category": "Trusted Company", "label": 0,
        "message": "PayPal receipt you sent $45 to ameer@gmail.com transaction ID 8K921837HN view details at paypal.com/activity",
    },
    {
        "id": 57, "category": "Trusted Company", "label": 0,
        "message": "Your Fiverr order from DataScienceExpert has been delivered review the work and leave feedback at fiverr.com/orders/FO928374",
    },
    {
        "id": 58, "category": "Trusted Company", "label": 0,
        "message": "Booking confirmation Hotel Indigo Tel Aviv check in May 5 check out May 7 2 nights total $280 view at booking.com/confirmation",
    },
    {
        "id": 59, "category": "Trusted Company", "label": 0,
        "message": "Your Coursera certificate for Machine Learning Specialization is ready download at coursera.org/account/accomplishments",
    },
    {
        "id": 60, "category": "Trusted Company", "label": 0,
        "message": "Discord notification you have been added to ScamRadar Dev server by Moatasem view at discord.com/channels/928374",
    },

    # ── BANK AND FINANCIAL (5) ────────────────────────────────────────────
    {
        "id": 61, "category": "Bank/Financial", "label": 0,
        "message": "Bank Hapoalim: transaction approved 450 NIS at Super-Pharm April 28 if not you call 03-650-7777 or visit bankhapoalim.co.il",
    },
    {
        "id": 62, "category": "Bank/Financial", "label": 0,
        "message": "Your Revolut card was used for $12.50 at Starbucks London if this was not you freeze your card at revolut.com/app",
    },
    {
        "id": 63, "category": "Bank/Financial", "label": 0,
        "message": "American Express: a charge of $89.99 was made at Apple Store if you did not make this purchase call 1-800-528-4800 immediately",
    },
    {
        "id": 64, "category": "Bank/Financial", "label": 0,
        "message": "Your mortgage payment of $1,240 has been processed successfully view statement at wellsfargo.com/mortgage/account",
    },
    {
        "id": 65, "category": "Bank/Financial", "label": 0,
        "message": "Venmo: Moatasem paid you $35 for dinner last night view transaction at venmo.com/account/transactions",
    },

    # ── ACADEMIC AND PROFESSIONAL (5) ─────────────────────────────────────
    {
        "id": 66, "category": "Academic/Professional", "label": 0,
        "message": "Dear Ameer your research paper has been accepted for publication in the Journal of Information Systems congratulations from the editorial team",
    },
    {
        "id": 67, "category": "Academic/Professional", "label": 0,
        "message": "Reminder your thesis submission deadline is May 15 please upload your final document to the student portal at students.yvc.ac.il",
    },
    {
        "id": 68, "category": "Academic/Professional", "label": 0,
        "message": "Your LinkedIn connection request was accepted by Dr. Rachel Cohen Head of Computer Science at Technion view profile at linkedin.com/in/rachel-cohen",
    },
    {
        "id": 69, "category": "Academic/Professional", "label": 0,
        "message": "Zoom meeting starting in 10 minutes ScamRadar Final Presentation with Hanan Lev join at zoom.us/j/928374821",
    },
    {
        "id": 70, "category": "Academic/Professional", "label": 0,
        "message": "Your Google Scholar citation alert 3 papers cited your work on scam detection view at scholar.google.com/citations",
    },

    # ── PERSONAL AND CASUAL (10) ──────────────────────────────────────────
    {
        "id": 71, "category": "Personal/Casual", "label": 0,
        "message": "Hey Ameer are you coming to the BBQ on Friday at Moatasem place starts at 7pm let me know if you need a ride",
    },
    {
        "id": 72, "category": "Personal/Casual", "label": 0,
        "message": "Can you send me the notes from yesterday class I missed it because of the doctor appointment thanks",
    },
    {
        "id": 73, "category": "Personal/Casual", "label": 0,
        "message": "The pizza place near campus is open until midnight if you want to order later tonight just let me know",
    },
    {
        "id": 74, "category": "Personal/Casual", "label": 0,
        "message": "Mom wanted me to remind you about grandma birthday dinner on Sunday at 6pm do not forget to bring the cake",
    },
    {
        "id": 75, "category": "Personal/Casual", "label": 0,
        "message": "Your package from AliExpress has shipped tracking number LY928374121CN estimated delivery 15-20 business days",
    },
    {
        "id": 76, "category": "Personal/Casual", "label": 0,
        "message": "Good morning reminder to take your medication today have a great day",
    },
    {
        "id": 77, "category": "Personal/Casual", "label": 0,
        "message": "Your electricity bill for April is ready view and pay at iec.co.il/account amount due 342 NIS due date May 15",
    },
    {
        "id": 78, "category": "Personal/Casual", "label": 0,
        "message": "Congratulations on completing the 5K run your finish time was 28 minutes 42 seconds view your certificate at sportstats.com",
    },
    {
        "id": 79, "category": "Personal/Casual", "label": 0,
        "message": "Your library book The Art of Statistics is due back on May 5 renew online at library.yvc.ac.il or return to main desk",
    },
    {
        "id": 80, "category": "Personal/Casual", "label": 0,
        "message": "Happy birthday Ameer wishing you all the best hope you have an amazing day from the whole ScamRadar team",
    },

    # ── HEALTH AND SERVICES (5) ───────────────────────────────────────────
    {
        "id": 81, "category": "Health/Services", "label": 0,
        "message": "Reminder your annual checkup is scheduled for Thursday May 2 at 10am with Dr. Cohen Clalit clinic Netanya call 04-860-7777 to reschedule",
    },
    {
        "id": 82, "category": "Health/Services", "label": 0,
        "message": "Your prescription is ready for pickup at Super-Pharm Netanya branch open until 10pm tonight",
    },
    {
        "id": 83, "category": "Health/Services", "label": 0,
        "message": "Maccabi health services your test results are available view securely at maccabi4u.co.il log in with your ID number",
    },
    {
        "id": 84, "category": "Health/Services", "label": 0,
        "message": "Your Wolt order from Hummus Abu Hassan is confirmed estimated delivery 35 minutes order total 67 NIS",
    },
    {
        "id": 85, "category": "Health/Services", "label": 0,
        "message": "Gym membership renewal reminder your Planet Fitness membership renews May 1 for $24.99 manage at planetfitness.com/account",
    },

    # ── GOVERNMENT AND UTILITIES (5) ──────────────────────────────────────
    {
        "id": 86, "category": "Government/Utilities", "label": 0,
        "message": "Your arnona payment for April has been received thank you reference number 928374 view receipt at jerusalem.muni.il/account",
    },
    {
        "id": 87, "category": "Government/Utilities", "label": 0,
        "message": "Israel Post: your registered package is ready for pickup at Netanya post office branch 3 ID required bring this SMS",
    },
    {
        "id": 88, "category": "Government/Utilities", "label": 0,
        "message": "Your Bezeq bill for April is ready amount due 189 NIS due May 20 view and pay at bezeq.co.il/myaccount",
    },
    {
        "id": 89, "category": "Government/Utilities", "label": 0,
        "message": "National Insurance Institute: your monthly benefit of 2,840 NIS has been transferred to your account view at btl.gov.il",
    },
    {
        "id": 90, "category": "Government/Utilities", "label": 0,
        "message": "Your Taavura bus monthly pass renewal is available purchase at rav-kav.co.il/renew valid from May 1",
    },

    # ── EDGE CASES (10) ───────────────────────────────────────────────────
    {
        "id": 91, "category": "Edge Case", "label": 0,
        "message": "URGENT: your domain expires tomorrow renew at namecheap.com/renewals or lose it forever order ID 928374",
    },
    {
        "id": 92, "category": "Edge Case", "label": 0,
        "message": "Your trial period ends in 3 days upgrade to premium at notion.so/pricing or lose access to your workspace",
    },
    {
        "id": 93, "category": "Edge Case", "label": 0,
        "message": "Security alert: new login to your Figma account from Tel Aviv if this was you no action needed otherwise visit figma.com/security",
    },
    {
        "id": 94, "category": "Edge Case", "label": 0,
        "message": "Your Binance withdrawal of 0.05 BTC has been processed transaction hash 0x8821 view at binance.com/en/my/wallet/history",
    },
    {
        "id": 95, "category": "Edge Case", "label": 0,
        "message": "Warning your SSL certificate for scamradar.com expires in 7 days renew at letsencrypt.org or your site will show security warnings",
    },
    {
        "id": 96, "category": "Edge Case", "label": 0,
        "message": "Your OpenAI API usage has reached 80% of monthly limit view usage and upgrade plan at platform.openai.com/account/usage",
    },
    {
        "id": 97, "category": "Edge Case", "label": 0,
        "message": "Reminder: Hanan Lev has scheduled a meeting with you for project review Monday May 4 at 2pm confirm at calendly.com/hananlev/review",
    },
    {
        "id": 98, "category": "Edge Case", "label": 0,
        "message": "Your Canva Pro subscription renews May 3 for $12.99 manage subscription at canva.com/settings/billing",
    },
    {
        "id": 99, "category": "Edge Case", "label": 0,
        "message": "Two-factor authentication code for your Anthropic account: 847291 expires in 10 minutes do not share this code",
    },
    {
        "id": 100, "category": "Edge Case", "label": 0,
        "message": "Your pull request ScamRadar feature/adversarial-robustness has been merged into main by Moatasem view at github.com/team/scamradar/pull/42",
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  PIPELINE LOADER
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
    st_model   = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"{GREEN}✓ Pipeline loaded  (threshold={threshold:.2f}){RESET}\n")
    return model, tfidf, char_tfidf, scaler, faiss_idx, st_model, threshold


# ══════════════════════════════════════════════════════════════════════════
#  RUN SUITE
# ══════════════════════════════════════════════════════════════════════════

def run_suite(model, tfidf, char_tfidf, scaler, faiss_idx, st_model, threshold):
    results = []
    print(f"{BOLD}{'─'*76}{RESET}")
    print(f"{BOLD}  {'#':>3}  {'CATEGORY':<28} {'EXPECTED':<10} {'GOT':<12} {'CONF':>6}  STATUS{RESET}")
    print(f"{BOLD}{'─'*76}{RESET}")

    for tc in TEST_CASES:
        r = predict_message(
            tc['message'], model, tfidf, char_tfidf, scaler,
            faiss_idx, st_model, threshold=threshold,
        )
        verdict = r['verdict']
        conf    = r['confidence']
        expected = 'SCAM' if tc['label'] == 1 else 'LEGIT'

        if tc['label'] == 1:
            status = 'PASS' if verdict == 'SCAM' else ('PARTIAL' if verdict == 'SUSPICIOUS' else 'FAIL')
        else:
            status = 'PASS' if verdict == 'LEGIT' else ('PARTIAL' if verdict == 'SUSPICIOUS' else 'FAIL')

        colour = GREEN if status == 'PASS' else (YELLOW if status == 'PARTIAL' else RED)
        print(
            f"  {tc['id']:>3}  {tc['category']:<28} {expected:<10} {verdict:<12} "
            f"{conf:>5.1f}%  {colour}{status}{RESET}"
        )
        results.append({**tc, 'verdict': verdict, 'confidence': conf, 'status': status})

    return results


# ══════════════════════════════════════════════════════════════════════════
#  REPORT
# ══════════════════════════════════════════════════════════════════════════

def generate_report(results, threshold):
    scam_cases  = [r for r in results if r['label'] == 1]
    legit_cases = [r for r in results if r['label'] == 0]
    total       = len(results)

    hard_pass = sum(1 for r in results if r['status'] == 'PASS')
    partial   = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail      = sum(1 for r in results if r['status'] == 'FAIL')

    fn         = [r for r in scam_cases  if r['status'] == 'FAIL']
    fp         = [r for r in legit_cases if r['status'] == 'FAIL']
    partial_fn = [r for r in scam_cases  if r['status'] == 'PARTIAL']
    partial_fp = [r for r in legit_cases if r['status'] == 'PARTIAL']

    fn_rate = len(fn) / len(scam_cases) * 100
    fp_rate = len(fp) / len(legit_cases) * 100
    acc_strict = hard_pass / total * 100
    acc_soft   = (hard_pass + partial) / total * 100

    cat_map = {}
    for r in results:
        cat_map.setdefault(r['category'], []).append(r)

    lines = []
    lines.append("=" * 76)
    lines.append("  ScamRadar+  |  Adversarial Test Suite v2  (100 messages)")
    lines.append(f"  Generated:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Threshold:  {threshold:.2f}  (≥0.60 = SCAM, {threshold:.2f}–0.60 = SUSPICIOUS)")
    lines.append("=" * 76)
    lines.append("")

    lines.append("OVERALL SUMMARY")
    lines.append("─" * 44)
    lines.append(f"  Total messages tested : {total}")
    lines.append(f"  Full passes (PASS)    : {hard_pass}  ({acc_strict:.1f}%)")
    lines.append(f"  Partial (SUSPICIOUS)  : {partial}")
    lines.append(f"  Failures              : {fail}")
    lines.append(f"  Strict accuracy       : {acc_strict:.1f}%")
    lines.append(f"  Soft accuracy         : {acc_soft:.1f}%  (PASS + PARTIAL)")
    lines.append("")
    lines.append(f"  Scam messages  ({len(scam_cases):>2} total)")
    lines.append(f"    Correctly flagged SCAM   : {sum(1 for r in scam_cases if r['verdict']=='SCAM')}")
    lines.append(f"    Borderline SUSPICIOUS    : {len(partial_fn)}")
    lines.append(f"    Missed LEGIT (FN)        : {len(fn)}   ← False Negatives")
    lines.append(f"    False Negative Rate      : {fn_rate:.1f}%")
    lines.append("")
    lines.append(f"  Legit messages ({len(legit_cases):>2} total)")
    lines.append(f"    Correctly cleared LEGIT  : {sum(1 for r in legit_cases if r['verdict']=='LEGIT')}")
    lines.append(f"    Borderline SUSPICIOUS    : {len(partial_fp)}")
    lines.append(f"    Over-flagged SCAM (FP)   : {len(fp)}   ← False Positives")
    lines.append(f"    False Positive Rate      : {fp_rate:.1f}%")
    lines.append("")

    lines.append("CATEGORY BREAKDOWN")
    lines.append("─" * 76)
    lines.append(f"  {'Category':<30} {'N':>3}  {'PASS':>6}  {'PARTIAL':>7}  {'FAIL':>5}  {'Pass%':>6}")
    lines.append("  " + "─" * 64)

    cat_rows = []
    for cat, items in sorted(cat_map.items()):
        n      = len(items)
        passes = sum(1 for r in items if r['status'] == 'PASS')
        parts  = sum(1 for r in items if r['status'] == 'PARTIAL')
        fails  = sum(1 for r in items if r['status'] == 'FAIL')
        pct    = passes / n * 100
        cat_rows.append((pct, cat, n, passes, parts, fails))

    for pct, cat, n, passes, parts, fails in sorted(cat_rows, key=lambda x: x[0]):
        bar = "██" if pct == 100 else ("▓▓" if pct >= 60 else "░░")
        lines.append(f"  {cat:<30} {n:>3}  {passes:>6}  {parts:>7}  {fails:>5}  {pct:>5.0f}% {bar}")
    lines.append("")

    lines.append("DETAILED RESULTS")
    lines.append("─" * 76)
    lines.append(f"  {'#':>3}  {'Category':<28} {'Exp':<7} {'Got':<12} {'Conf':>6}  Status")
    lines.append("  " + "─" * 68)
    for r in results:
        exp    = 'SCAM' if r['label'] == 1 else 'LEGIT'
        marker = "  " if r['status'] == 'PASS' else ("⚠ " if r['status'] == 'PARTIAL' else "✗ ")
        lines.append(
            f"  {r['id']:>3}  {r['category']:<28} {exp:<7} {r['verdict']:<12} "
            f"{r['confidence']:>5.1f}%  {marker}{r['status']}"
        )
    lines.append("")

    lines.append("FAILURES AND ROOT CAUSE ANALYSIS")
    lines.append("─" * 76)
    any_fail = fn or fp or partial_fn or partial_fp

    if fn:
        lines.append(f"\n  FALSE NEGATIVES ({len(fn)}) — scam classified as LEGIT")
        for r in fn:
            lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
            lines.append(textwrap.fill(r['message'], 66, initial_indent='    ', subsequent_indent='    '))
    if partial_fn:
        lines.append(f"\n  BORDERLINE SCAMS ({len(partial_fn)}) — caught as SUSPICIOUS not SCAM")
        for r in partial_fn:
            lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
            lines.append(textwrap.fill(r['message'], 66, initial_indent='    ', subsequent_indent='    '))
    if fp:
        lines.append(f"\n  FALSE POSITIVES ({len(fp)}) — legit classified as SCAM")
        for r in fp:
            lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
            lines.append(textwrap.fill(r['message'], 66, initial_indent='    ', subsequent_indent='    '))
    if partial_fp:
        lines.append(f"\n  BORDERLINE LEGIT ({len(partial_fp)}) — legit classified as SUSPICIOUS")
        for r in partial_fp:
            lines.append(f"\n  [#{r['id']} {r['category']}]  conf={r['confidence']:.1f}%")
            lines.append(textwrap.fill(r['message'], 66, initial_indent='    ', subsequent_indent='    '))
    if not any_fail:
        lines.append("  None — perfect suite score!")

    lines.append("")
    lines.append("=" * 76)
    lines.append(f"  ScamRadar+ Adversarial Suite v2  |  {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 76)

    return "\n".join(lines), {
        'total': total, 'hard_pass': hard_pass, 'partial': partial, 'fail': fail,
        'acc_strict': acc_strict, 'acc_soft': acc_soft,
        'fn_rate': fn_rate, 'fp_rate': fp_rate,
        'fn': fn, 'fp': fp, 'partial_fn': partial_fn, 'partial_fp': partial_fp,
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
    print("\n" + report_text)

    out_path = os.path.join(os.path.dirname(__file__), 'adversarial_results_v2.txt')
    with open(out_path, 'w') as f:
        f.write(report_text)
    print(f"\n{GREEN}Results saved → {out_path}{RESET}")

    pct = stats['acc_strict']
    colour = GREEN if pct >= 90 else (YELLOW if pct >= 70 else RED)
    print(f"\n{BOLD}{colour}{'═'*54}{RESET}")
    print(f"{BOLD}{colour}  Strict accuracy : {pct:.1f}%  ({stats['hard_pass']}/{stats['total']} PASS){RESET}")
    print(f"{BOLD}{colour}  Soft accuracy   : {stats['acc_soft']:.1f}%  (includes PARTIAL){RESET}")
    print(f"{BOLD}{colour}  False Negatives : {stats['fn_rate']:.1f}%  |  False Positives : {stats['fp_rate']:.1f}%{RESET}")
    print(f"{BOLD}{colour}{'═'*54}{RESET}\n")


if __name__ == '__main__':
    main()
