"""
Augment ScamRadar training data with hard-to-detect scam messages.
Focuses on weaknesses identified in adversarial testing:
  - Romance / social engineering (0% detection)
  - Sophisticated investment scams with obfuscation
  - Job offer scams
  - Subtle phishing (no urgency language)
  - Crypto / NFT scams
  - Package / delivery scams
  - Tech support scams
  - Government impersonation (low-pressure)
  - AI-style fluent scam emails
"""

import sqlite3
import re
import math

DB_PATH = "data/db 4.db"

# source_id=6 (new), channel_id=1 (email) or 3 (sms)
NEW_SOURCE_ID   = 6
NEW_SOURCE_NAME = "augmented_hard_scams"

# ── Scam messages (label=1) ───────────────────────────────────────────────────
SCAM_MESSAGES = [

    # ── Romance / Social Engineering (subtle) ──────────────────────────────
    ("Hi, I came across your profile and thought you seemed really interesting. I'm currently working abroad as an engineer on an oil rig. Would love to get to know you better. Can we move to WhatsApp?", "sms"),
    ("Hey, this is Sarah. I think we matched a while back but I never messaged you. I've been going through a hard time lately and could really use someone to talk to. Are you still single?", "sms"),
    ("I know this is out of nowhere but I feel a real connection with you. I'm a nurse working overseas right now. Once I'm back I would love to meet. My phone plan doesn't work here — can you send me a Google Play card so I can call you?", "sms"),
    ("I've been thinking about you every day since we started talking. I have a business opportunity I wanted to share only with you because I trust you. My broker can get you in on a gold trade. Minimum is just $200.", "sms"),
    ("My name is Captain David Morris, US Army stationed in Syria. I found your contact through a mutual friend. I have $4.5M in a secured box I need help moving out of the country before I redeploy. I will give you 30%. This is completely safe and legal.", "email"),
    ("I've been investing in crypto for 3 years and recently hit big. I want to share this with someone special. I use a platform called coinvault-pro.net — you can start with as little as $100 and I can guide you personally every step.", "sms"),
    ("Sweetheart I miss you so much. The doctors here say I need surgery and I don't have insurance that covers this hospital. Can you send $800 through Zelle? I promise I will pay you back the moment I land.", "sms"),
    ("Hey beautiful. I just wanted you to know I think about you all the time. I am a widow with one son. I work in export business. Can we be friends? I don't want anything from you except conversation, I promise.", "sms"),

    # ── Investment / Crypto (sophisticated, low-pressure) ──────────────────
    ("Heads up — I've been quietly testing a new DeFi yield strategy for 6 months. Average monthly return is 11.4%. I'm not recruiting, just sharing with a few people I respect. No pressure at all. Here's the platform: defi-yield-alpha.io", "email"),
    ("A quick note from our investment desk: clients who entered BTC at our recommended entry point in Q3 saw 340% gains. We are opening a second cohort next week. Allocation is capped at 20 seats. Reply to be considered.", "email"),
    ("This isn't a sales pitch. I lost money on bad advice for years. Last year I found a quant strategy that has not had a losing month. I'm sharing the Telegram link privately: t.me/alphaquant_private — join before it fills up.", "sms"),
    ("Hi, you were referred to me by a mutual contact. I manage a private hedge fund focused on emerging market arbitrage. Minimum investment is $5,000. Annualised returns for 2023 were 87%. Happy to send you our fund prospectus.", "email"),
    ("The NFT project I told you about last week just got listed on OpenSea. Floor price is already 0.4 ETH. If you whitelist now at 0.08 ETH you're locking in 5x minimum. Link: nftwhitelist-exclusive.com/join", "sms"),
    ("Our AI-powered trading bot closed 23 consecutive profitable trades this month. Backtested across 4 years of market data with a Sharpe ratio of 3.1. We're letting early users in at $250/month, locked returns of 8% monthly guaranteed.", "email"),
    ("I don't usually reach out cold but your LinkedIn showed you're financially savvy. We have a pre-IPO allocation for a fintech startup backed by Sequoia. Minimum ticket is $2,000. This will not be available publicly for another 6 months.", "email"),
    ("Hey, not sure if you saw but Ethereum is about to go parabolic based on on-chain signals. I use a platform that auto-trades for me — made $14,200 last month. Referral link gives you a $50 bonus: eth-autotrader.net/ref/928", "sms"),

    # ── Job Offer Scams ────────────────────────────────────────────────────
    ("Congratulations! After reviewing your resume on Indeed, we would like to offer you a remote customer service role at $28/hour. No experience needed. Training provided. Please confirm your interest and we will send the offer letter.", "email"),
    ("Hi, I'm a recruiter at TalentBridge. We have a fully remote data entry position that pays $32/hr. Flexible hours, no experience required. To reserve your spot please complete a background check at: talentverify-now.com", "email"),
    ("Your application for the Amazon Work From Home Fulfillment Coordinator role has been reviewed. You've been selected for onboarding. First step is to purchase a $200 equipment kit through our vendor. It will be fully reimbursed in your first paycheck.", "email"),
    ("We found your profile on ZipRecruiter and think you'd be a great fit for our remote personal assistant role. Pay is $500/week. The job involves processing payments on behalf of our clients. Reply with your PayPal or Cashapp to get started.", "sms"),
    ("Dear candidate, you have been shortlisted for a mystery shopper position. Your first assignment pays $350. We will mail you a check. Deposit it, keep $50 for yourself, and transfer the rest to our vendor via MoneyGram. Simple!", "email"),
    ("Hiring immediately: Social media evaluators. Work from home, $18–25/hr, set your own hours. No interview required. Sign up at: remote-eval-jobs.com/register — first payment within 48 hours of completing your profile.", "email"),

    # ── Package / Delivery Phishing ────────────────────────────────────────
    ("Your parcel could not be delivered due to an incomplete address. Please update your delivery details and pay a $1.99 redelivery fee within 24 hours or your package will be returned: dhl-redelivery.net/update", "sms"),
    ("FedEx: We attempted delivery of your package but were unable to complete it. To reschedule you must confirm your address and card details at: fedex-reschedule.com/parcel/7742", "sms"),
    ("USPS Alert: Your package is on hold at the facility. A customs clearance fee of $3.50 is required. Pay here to release: usps-customs-release.com — failure to pay within 48 hours will result in return to sender.", "sms"),
    ("Your Amazon order is awaiting final delivery confirmation. There appears to be an issue with your address on file. Please verify within 2 hours: amzn-delivery-confirm.net/verify?id=8892", "sms"),
    ("Royal Mail: We have a package for you but require a small handling fee of £2.99 to release it. Pay here: royalmail-package-release.co.uk — this link expires at midnight.", "sms"),

    # ── Tech Support Scams ─────────────────────────────────────────────────
    ("We have detected unusual sign-in activity on your Microsoft account from a new device in Romania. If this was not you, please verify your identity immediately to prevent account suspension: microsoft-account-verify.net/security", "email"),
    ("Your Apple ID has been used to sign into a new iPhone 15 in Beijing. If you did not authorise this, tap here to lock your account now: apple-id-alert.com/lock?session=928371", "sms"),
    ("IMPORTANT: Your Norton subscription expired 3 days ago. Your device is no longer protected. Renew now at our special rate of $29.99/year and get a FREE virus scan: norton-renew-protection.com", "email"),
    ("McAfee Security Alert: 5 viruses were detected on your device during our scheduled scan. Your subscription has lapsed. Click to remove the viruses and reactivate your plan: mcafee-device-scan.net/remove", "email"),
    ("Google Security Notice: A third-party app is accessing your Gmail without permission. Review and revoke access here within 12 hours to protect your account: google-app-review.com/revoke", "email"),

    # ── Government / Authority Impersonation (subtle) ─────────────────────
    ("This is a notice from the Social Security Administration. Your Social Security number has been temporarily suspended due to suspicious activity linked to a vehicle found in Texas. Call 1-888-712-4524 to reactivate your SSN.", "email"),
    ("HMRC Tax Refund Notification: Following a recent review of your tax records we have identified an overpayment of £847.20. To claim your refund please complete the form at: hmrc-refund-claim.co.uk within 14 days.", "email"),
    ("The IRS has attempted to contact you regarding an underpayment on your 2022 tax return. Failure to respond may result in legal proceedings. Please call our compliance department at 1-800-291-7744 to resolve this immediately.", "email"),
    ("This is an automated notice from Medicare. Your current plan is being discontinued. You must select a new plan by the end of this month or you will lose coverage. Call 1-855-449-0028 to speak with a benefits advisor.", "sms"),
    ("US Customs and Border Protection: A package addressed to you has been intercepted containing undeclared goods. A penalty of $480 has been issued. Pay within 72 hours to avoid escalation: cbp-penalty-payment.com", "email"),
    ("Student loan forgiveness: Your application for the Federal Student Debt Relief Program has been pre-approved. To complete your application and receive up to $20,000 in relief, confirm your FSA ID at: studentaid-relief.gov.services-form.com", "email"),

    # ── Subtle Phishing (no urgency, conversational) ───────────────────────
    ("Hi there, I'm reaching out on behalf of your bank's fraud team. We noticed a small transaction on your account that we'd like to verify with you. Can you confirm the last 4 digits of your card and the amount you see?", "sms"),
    ("Just a quick check-in from PayPal customer support. We've been trying to update account records. Could you provide your email and confirm your account password so we can match it to our system?", "email"),
    ("Hi, this is David from Chase account services. We've made some updates to your account security settings. To make sure everything is properly transferred, we need to verify your online banking credentials.", "sms"),
    ("Hello, I'm following up on your recent support ticket (#TK-29183). To complete the resolution we need to remotely access your computer for 10 minutes. Please download TeamViewer and give us the ID: support-fix-now.com/download", "email"),
    ("You left a review on Trustpilot last month. We'd like to offer you a $50 gift card as a thank you. Just verify your shipping address and card details at: trustpilot-rewards.com/redeem", "email"),

    # ── Lottery / Prize Scams ─────────────────────────────────────────────
    ("You have been randomly selected from 2.4 million email addresses as the winner of our quarterly prize draw. Your prize is $85,000. To claim, reply with your full name, address, and phone number. No purchase necessary.", "email"),
    ("Congratulations, your phone number was selected in the Coca-Cola global promo. You've won a Samsung Galaxy S24 and $1,000 cash. To claim your prize please pay a $25 processing fee at: coca-cola-winners.com", "sms"),
    ("Your email was the lucky winner in the WhatsApp Anniversary Prize Draw. You have won €750,000 Euros. To claim, contact our payment agent at: prizeadmin@whatsapp-draw.com with your name and bank details.", "email"),
    ("Google Reward Program: You are today's selected user. Spin to win an iPhone 15 Pro. Claim your free prize within the next 30 seconds: google-user-reward.com/spin", "sms"),

    # ── Blackmail / Sextortion (hard to detect, low signal words) ──────────
    ("I need to talk to you about something sensitive. A few months ago malware on your device gave me access to your webcam. I have footage of you visiting certain websites. I don't want to embarrass you — send $1,400 in Bitcoin to 1A2B3C and I'll delete everything.", "email"),
    ("This is not a joke and I am not trying to scare you. I work in cybersecurity and came across your data on a breach forum. Your password was listed as [REDACTED]. I have screen recordings from your computer. Pay $900 BTC to avoid distribution.", "email"),
    ("I know this will shock you. I've had access to your email for 87 days. I've seen everything. Your contacts, your photos, your browsing history. My demand is reasonable — $1,200 in Monero. I won't contact you again after payment.", "email"),

    # ── Advance Fee / Emergency Scams ─────────────────────────────────────
    ("Hi, I'm a friend of your cousin Mark. He's been in an accident here in Mexico and is in hospital. His phone was stolen. He asked me to contact you. He needs $600 wired urgently for the hospital deposit. I'll give you my Western Union details.", "sms"),
    ("I'm a solicitor handling the estate of the late Mr. Harold T. Webb who passed without a will. He shares your surname. His estate of $2.3M will be claimed by the government unless a next of kin can be located. You may qualify. Please respond discreetly.", "email"),
    ("My name is Fatima Al-Hassan. I am the daughter of the former Minister of Petroleum in Nigeria. Following my father's death I have $14.5M frozen in an overseas account. I need a trusted foreign partner to help move these funds. You will receive 25%.", "email"),
    ("Hi, I hope you don't mind me reaching out. I'm traveling abroad and my wallet and passport were stolen. I've reported it to the embassy but they can't help until Monday. Could you lend me $400 via PayPal? I'll pay you back immediately when I get home.", "sms"),

    # ── Subscription / Billing Scams ──────────────────────────────────────
    ("Your Netflix account has been suspended due to a billing issue. Update your payment information within 24 hours to avoid losing access to your account: netflix-billing-update.com/payment", "sms"),
    ("We were unable to process your Spotify Premium payment. Your subscription will be cancelled in 48 hours. Please update your billing details here: spotify-payment-portal.com/update", "email"),
    ("Your Amazon Prime membership could not be renewed. A hold of $14.99 has been placed on your account. To resolve this and keep your benefits visit: amazon-prime-billing.net/resolve", "sms"),
    ("Subscription renewal failed: Your iCloud storage (200GB) payment of $2.99 could not be processed. To avoid losing your data, update your payment method at: icloud-payment-issue.com", "email"),

    # ── Obfuscated / adversarial style ────────────────────────────────────
    ("Hey just checking in. Hope you're well. I've been making some really good money online lately, nothing illegal just a system I found. Not trying to sell you anything just paying it forward happy to share what worked for me in the market let me know", "sms"),
    ("This is just between us. I found a way to get free Amazon gift cards — completely legit, they have a testing program. I've gotten over $800 worth. Want me to add you? Just need your email.", "sms"),
    ("Not spam I promise lol. My brother works at a bank and told me about a legal loophole for getting loan forgiveness even if you don't qualify normally. He helped me get $12k cleared. DM me if you want his contact.", "sms"),
    ("Hey I met you at the conference last month I think. Anyway I'm putting together a small group of people for a private investment round in a stealth startup. Valuation is low now but there's a big announcement coming. Want in?", "email"),
    ("Look I know this sounds weird but I'm a data analyst and I accidentally found a pattern in a sports betting algorithm. It's not gambling it's math. I've been using it for 4 months. 78% win rate. I can show you the spreadsheet.", "sms"),
    ("Totally random but I saw you're in the same city as me. I run a small digital marketing business and I'm looking for local people to do simple tasks for $80-120/day cash. No experience needed. Interested?", "sms"),
]

# ── Legitimte messages to maintain balance (label=0) ────────────────────────
LEGIT_MESSAGES = [
    ("Hi, just wanted to confirm our meeting tomorrow at 3pm is still on. Let me know if anything changes. See you then!", "sms"),
    ("Your Uber receipt for your ride on Saturday is attached. Total charged: $12.40. Thank you for riding with Uber.", "email"),
    ("Hi, your prescription is ready for pickup at our pharmacy. We're open Monday to Saturday 8am-8pm. CVS Pharmacy, Main St.", "sms"),
    ("Your Delta flight DL248 to Chicago on December 3rd is confirmed. Check-in opens 24 hours before departure. Seat: 22A.", "email"),
    ("LinkedIn: John Smith viewed your profile. He is a Software Engineer at Google. View his profile.", "email"),
    ("Your GitHub pull request #442 has been reviewed. 2 comments were left by sarah-dev. Visit github.com to view.", "email"),
    ("Reminder: Your dentist appointment is tomorrow at 10:30am with Dr. Patel. Call 555-0192 to reschedule if needed.", "sms"),
    ("Your package from Best Buy has shipped. Order #BB-29471. Estimated delivery: Tuesday, Dec 5. Track at bestbuy.com/orders.", "email"),
    ("Hi, this is a reminder that your car insurance renews on January 1st. No action needed unless you'd like to make changes. Call us at 1-800-555-0199.", "sms"),
    ("Your bank statement for November is now available to view in online banking. Log in at yourbank.com to view your statement.", "email"),
    ("Hey, just saw your email. Yes I can definitely help with the project. Let me look over the brief and I'll get back to you by end of week.", "email"),
    ("Slack notification: You have 3 new messages in #general from the team. Reply at app.slack.com.", "email"),
    ("Your Airbnb reservation at The Mill House in Edinburgh is confirmed for Dec 20-23. Check-in is at 3pm. Contact host: James M.", "email"),
    ("Two-factor authentication code for your Google account: 847291. This code expires in 10 minutes. Do not share it.", "sms"),
    ("Hi, I'm writing to follow up on our conversation last week about the open position. We'd love to invite you for a second interview next Tuesday. Please let us know your availability.", "email"),
    ("Your Duolingo streak is at risk! You haven't practiced Spanish today. Keep your 47-day streak alive: duolingo.com", "sms"),
    ("Your order from ASOS is on its way. Expected delivery: 2-3 business days. You can track your order at asos.com/myorders.", "email"),
    ("Hey, are you free this weekend? A few of us are going to the farmers market on Saturday morning if you want to join.", "sms"),
    ("Your 2023 tax documents are now available in your TurboTax account. Log in to review and file your return.", "email"),
    ("This is an automated alert: your credit card ending in 4821 was used for $42.30 at Whole Foods on Dec 1st. If this wasn't you, call the number on the back of your card.", "sms"),
]

def compute_basic_features(text):
    words = text.split()
    urls = re.findall(r'https?://\S+', text)
    urgency_words = ['urgent', 'immediately', 'asap', 'expire', 'suspended', 'verify', 'confirm', 'act now']
    urgency = sum(1 for w in urgency_words if w in text.lower())
    return {
        'text_length': len(text),
        'word_count': len(words),
        'has_url': int(len(urls) > 0),
        'url_count': len(urls),
        'exclamation_count': text.count('!'),
        'uppercase_ratio': round(sum(1 for c in text if c.isupper()) / max(len(text), 1), 4),
        'digit_ratio': round(sum(1 for c in text if c.isdigit()) / max(len(text), 1), 4),
        'urgency_score': urgency,
    }

CHANNEL_MAP = {'email': 1, 'sms': 3}

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Add new data source if not exists
    c.execute("SELECT source_id FROM DataSource WHERE name=?", (NEW_SOURCE_NAME,))
    row = c.fetchone()
    if row:
        source_id = row[0]
        print(f"Source '{NEW_SOURCE_NAME}' already exists (id={source_id})")
    else:
        c.execute("INSERT INTO DataSource (name) VALUES (?)", (NEW_SOURCE_NAME,))
        source_id = c.lastrowid
        print(f"Created source '{NEW_SOURCE_NAME}' (id={source_id})")

    # Get current max message_id
    max_id = c.execute("SELECT MAX(message_id) FROM Message").fetchone()[0] or 0

    inserted = 0
    for text, channel in SCAM_MESSAGES:
        text = text.strip()
        if not text:
            continue
        max_id += 1
        ch_id = CHANNEL_MAP.get(channel, 1)
        c.execute(
            "INSERT INTO Message (message_id, source_id, channel_id, raw_text, label) VALUES (?,?,?,?,?)",
            (max_id, source_id, ch_id, text, 1)
        )
        f = compute_basic_features(text)
        c.execute(
            "INSERT INTO MessageFeatures VALUES (?,?,?,?,?,?,?,?,?)",
            (max_id, f['text_length'], f['word_count'], f['has_url'], f['url_count'],
             f['exclamation_count'], f['uppercase_ratio'], f['digit_ratio'], f['urgency_score'])
        )
        inserted += 1

    for text, channel in LEGIT_MESSAGES:
        text = text.strip()
        if not text:
            continue
        max_id += 1
        ch_id = CHANNEL_MAP.get(channel, 1)
        c.execute(
            "INSERT INTO Message (message_id, source_id, channel_id, raw_text, label) VALUES (?,?,?,?,?)",
            (max_id, source_id, ch_id, text, 0)
        )
        f = compute_basic_features(text)
        c.execute(
            "INSERT INTO MessageFeatures VALUES (?,?,?,?,?,?,?,?,?)",
            (max_id, f['text_length'], f['word_count'], f['has_url'], f['url_count'],
             f['exclamation_count'], f['uppercase_ratio'], f['digit_ratio'], f['urgency_score'])
        )
        inserted += 1

    conn.commit()
    conn.close()

    scam_count = len(SCAM_MESSAGES)
    legit_count = len(LEGIT_MESSAGES)
    print(f"\nDone. Inserted {inserted} messages:")
    print(f"  Scam:  {scam_count}")
    print(f"  Legit: {legit_count}")
    print(f"\nNew total: ~{45851 + inserted} messages")
    print("\nRun `python main.py` to retrain the model.")

if __name__ == "__main__":
    main()
