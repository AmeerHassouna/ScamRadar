"""
ScamRadar+ | Gap coverage augmentation.
Adds handcrafted training examples targeting the two detected gaps:
  1. WhatsApp/Telegram crypto group recruitment — was scoring LEGIT (33%)
  2. Gift card payment scams — was only SUSPICIOUS (56%)
Plus varied examples for pig_butchering, qr_phishing, refund_scam, sim_swap.
"""

import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db 4.db')
SOURCE_NAME = 'augmented_gap_coverage'
CHANNEL_MAP = {'email': 1, 'sms': 3, 'url': 4}


# ── GAP 1: WhatsApp / Telegram crypto group recruitment ─────────────────────
# Was scoring 33% (LEGIT). Casual, friendly tone — no obvious scam language.
WHATSAPP_CRYPTO_SCAMS = [
    ("Hey, not sure if you remember me — we met at the fintech event last year. I've been running a private Telegram trading group for about 8 months now. We just closed a 280% return on ETH options. I have 3 spots open. Want in?", "sms"),
    ("Hi, I think you liked my post about crypto last week. I run a closed Telegram channel where I share my signals before I trade them. 40 members, all verified. Last month average gain was 190%. Interested? No charge to join, I just ask for 10% of profits.", "sms"),
    ("Wrong number sorry! But since I have you — I manage a private investment group on WhatsApp. We've been killing it in the crypto market. Just added 6 new members this week. If you're interested I can add you. 0 risk to join and look.", "sms"),
    ("Hey beautiful, hope you're doing well. I wanted to share something with you since we've been talking. I joined this VIP crypto group on Telegram 2 months ago and I've already made $12,000. The mentor only takes 8 people at a time. One spot just opened. I thought of you.", "sms"),
    ("Not a spam message I promise lol. I do forex and crypto signals full time. I have a private WhatsApp group where I post my trades live before I enter them. 90 day track record is up 340%. I'm opening to 5 more people this week. Reply if you want the link.", "sms"),
    ("Hi I saw your comment on the Bitcoin subreddit. I run a private group for serious investors only — no noise, no hype. We focus on altcoin gems before they pump. Last 3 calls: 4x, 7x, 2.5x. Free to join. Telegram link: t.me/alphagemsvip", "email"),
    ("Good morning. I know this is out of the blue but my mentor taught me to always share what's working. I found a trading group on Telegram that has a verified 6-month track record. All trades posted in advance. Monthly ROI averages 60-80%. Happy to add you.", "sms"),
    ("Hey, I'm the one who runs the crypto group a mutual friend mentioned. We have 15 active members and just hit our 200th consecutive profitable signal. I charge nothing to join — I make my money from my own trades. Just need to know you're serious. Telegram?", "sms"),
    ("Hi there! I wanted to personally invite you to our WhatsApp investment community. We focus on DeFi and altcoins. Entry is free but limited to 20 members for signal quality. This month the group is up 430%. Join link expires in 24 hours: wa.me/invite/scamlink123", "sms"),
    ("I know we don't know each other but I found your profile through a friend. I've been trading crypto for 4 years and recently started a closed group. No fees. I just want to help people who missed the last bull run. 4 spots left. Telegram handle: @privatecryptogroup", "email"),
    ("Quick message — I manage hedge fund strategies adapted for retail crypto traders. My private channel on Telegram posts 3-5 signals per week. This year we're at 890% cumulative return. The group is closed but I have 2 referral slots. Interested?", "sms"),
    ("Hi, a friend of mine said you might be interested in our investment group. We trade forex and crypto on Telegram. Last 90 days: 12 winning signals out of 14. Risk is managed — we never go all in. The admin is a former Goldman analyst. I can get you access.", "sms"),
    ("Hey! I've been following you for a while. I wanted to invite you personally to our VIP trading circle. We use an algorithm developed by quants. The group is on Telegram and we've had zero losing months in 2024. DM me and I'll send the private link.", "email"),
    ("This is a bit random but I saw you engage with a post about passive income. I run a crypto signals group that's been going for 18 months. Verifiable track record — 67% average monthly gains. Only 5 people allowed per month. Currently have 2 openings.", "sms"),
    ("Hi, we connected on LinkedIn a while back. I wanted to reach out because I'm quietly running a private trading group on WhatsApp and one of our members mentioned you. We trade options and crypto. Last quarter: +340%. No fees, just split profits. Interested?", "email"),
    ("Hey, I noticed you're in the crypto space. I mentor a small group of traders on Telegram — 8 people max. This isn't a signal group, it's a full mentorship. Every member this year has turned $1k into at least $15k. I have one spot. Let me know.", "sms"),
    ("Not trying to sell you anything. I run a small Telegram group where I share my actual trades, not signals. Been doing this 3 years. My group started with $10k total and now we're sitting at over $200k combined. You can verify everything. Want to join?", "sms"),
    ("Hey, I found your number in a networking group. I host a private crypto community on WhatsApp — 25 members, all serious investors. We pool research and share entries. This month we're up 180%. There's no fee to join. I just vet people first. Interested?", "sms"),
    ("Hi! My name is Grace and I invest in crypto full time. I started a small group on Telegram for people who want to learn while making money. We've had 9 straight profitable months. I'm opening to 3 more people this week. No catch — just join and see for yourself.", "sms"),
    ("Good day. I came across your profile and thought you'd be a great fit for our private investment circle. We use a proven algorithmic system for crypto futures. Minimum entry is $500 but you can see results before committing. Join our Telegram: t.me/vipfuturesgroup", "email"),
    ("Hey it's Mike from the crypto meetup. I run the trading group I mentioned. We just closed a 5x on AVAX. The group is on Telegram and I post every trade live with entry and exit. Free to join, I only ask you actually participate. Want the invite link?", "sms"),
    ("Hi, this is awkward but I'm reaching out to select people I think could benefit from what I'm sharing. I turned $2,000 into $47,000 trading crypto in 8 months. I'm teaching exactly how in a private WhatsApp group. Only 4 spots at $0. DM me if interested.", "sms"),
    ("Quick note: my trading group on Telegram just had its best week ever — 6 signals, 6 wins, average 34% per trade. I'm letting in 3 more members this week only. The group has been running for 11 months with a verified record. Message me for the link.", "sms"),
    ("Hi there. I run an exclusive crypto and forex group on Telegram. We don't sell signals — we trade together as a community and split profits. Everyone started with at least $1000 and we've 10x'd the fund in 14 months. Only accepting 2 more members. Serious inquiries only.", "email"),
    ("Hey! I matched with you on a dating app but honestly I mostly use it to meet people who are into finance. I trade crypto seriously and I'm part of a group that's been extremely profitable. No pressure but if you're interested in making money on the side, let me know.", "sms"),
    ("Not a scam, not a bot — I'm a real person who trades crypto for a living. I started a group where I teach my strategy live. 15 members so far, all profitable. Currently accepting 5 more. It's free but I do ask members to invest at least $200 to follow trades. Telegram: @realcryptomentor", "sms"),
    ("Hi, you were recommended by someone in my network. I manage a small prop trading group on WhatsApp. We focus on high-probability setups in BTC and ETH. This year we're up 1,200% collective. I'm expanding to 5 more members. Interested in joining?", "email"),
    ("Hey, random question — are you into investing? I ask because I run a small crypto group on Telegram and we're outperforming literally everything right now. The strategy is simple, not risky, and verifiable. I could add you as a guest for a week so you can see for yourself.", "sms"),
    ("Good evening. I hope this finds you well. A colleague mentioned you as someone who might appreciate what I'm building. I run a private crypto education and trading group on Telegram. We share research, trade ideas, and accountability. This month alone: +67% on our model portfolio. I'd love to have you.", "email"),
    ("Hi — this might seem random but I saw you commented on a finance post. I run a Telegram group for serious traders. We share alpha before it hits mainstream. Last 6 months: 8 of 10 calls profitable with 40%+ average gain. Free to join but limited to 20 people total. 2 spots left.", "sms"),
]

# ── GAP 2: Gift card payment scams ──────────────────────────────────────────
# Was scoring 56% (SUSPICIOUS). Should be SCAM.
GIFT_CARD_SCAMS = [
    ("This is the IRS. Your Social Security number has been suspended due to suspicious activity. To avoid arrest, you must pay $2,000 in Google Play gift cards immediately. Call 1-888-221-4399 with the card numbers.", "sms"),
    ("URGENT: This is a final notice from the Social Security Administration. Your benefits have been suspended due to illegal activity linked to your account. Call 1-877-399-0291 now. Purchase $500 in iTunes gift cards to resolve this matter and avoid criminal charges.", "sms"),
    ("Hi, this is your boss. I'm in a meeting and can't talk but I need a favor urgently. Please go to CVS and buy 4x $100 Amazon gift cards and send me the redemption codes. I'll explain later and reimburse you. Don't tell anyone in the office yet.", "sms"),
    ("This is a federal agent with the FBI Cyber Division. Your bank account has been flagged for money laundering. To freeze the investigation and avoid arrest today, purchase $1,500 in eBay gift cards and call us back immediately. Ask for badge number 447.", "sms"),
    ("You have an outstanding balance with Microsoft Support. To prevent your computer from being permanently disabled, please purchase a $300 Google Play card from any store, scratch off the back, and call 1-800-447-2910 with the 16-digit code.", "email"),
    ("Your Amazon account has been compromised and your security deposit of $999 must be processed via gift cards due to a banking hold. Please purchase Amazon gift cards for this amount and reply with the code. Our fraud team will cancel the hold immediately.", "sms"),
    ("This is the local sheriff department. There is an active warrant for your arrest for unpaid taxes. To clear the warrant before officers are dispatched to your address, you must pay $800 in iTunes gift cards. Call 1-844-220-0882 immediately.", "sms"),
    ("Hello, this is Microsoft Technical Support. We've detected a virus on your Windows computer that is accessing your bank accounts. To protect your funds, purchase $200 in Steam gift cards and call us at 1-800-642-7676 with the card numbers.", "sms"),
    ("CEO MESSAGE — Please treat this as urgent and confidential. I need you to purchase 5x $200 Google Play gift cards for a client gift. Send me the codes as soon as you have them. I'm in a board meeting all day. Will explain fully when I'm out.", "email"),
    ("Norton Antivirus: Your annual subscription has expired and we detected 3 critical threats on your device. To remove them now and reactivate your protection, purchase a $150 iTunes gift card and call our tech team at 1-877-400-0034 with the code.", "sms"),
    ("This is Medicare Fraud Prevention. Your Medicare card has been used fraudulently. To protect your benefits and avoid suspension, you must pay a $400 security deposit using Google Play gift cards. Keep this call confidential. Call 1-800-229-4399.", "sms"),
    ("Hi honey, it's grandma. I'm in trouble and I need you to help me. I can't explain everything right now but please buy $500 in Amazon gift cards and send me the codes. Don't tell your mom or dad. I'll explain everything soon. I love you.", "sms"),
    ("Your Apple ID has been used to purchase $1,299 of apps in China. If you did not make this purchase, call our fraud line at 1-855-412-9004. To stop the charge, you will need to purchase Apple gift cards equal to the amount and verify with our agent.", "sms"),
    ("FINAL WARNING from the IRS Collections Division: You have a tax lien filed against your property. To stop the lien and avoid wage garnishment today, you must resolve your $3,200 balance using iTunes gift cards. Call agent Harris at 1-888-301-5583.", "email"),
    ("Hi, this is PayPal Fraud Prevention. Someone in Nigeria attempted to transfer $2,400 from your account. To block the transfer and secure your funds, we need you to verify ownership using Google Play gift cards totaling $200. Call us immediately.", "sms"),
    ("This is an automated alert from the US Treasury Department. A warrant has been issued in your name. To temporarily suspend this warrant and speak with a resolution officer, call 1-877-209-4433 and have $600 in Walmart gift cards ready.", "sms"),
    ("Your grandson called from a hospital in Mexico City. He was in an accident and needs surgery immediately. He asked us to call you. The hospital requires a deposit of $1,200. He said you could send Amazon gift card codes. Please act fast.", "sms"),
    ("HP Support: Our diagnostics show your computer has a critical error exposing your banking credentials to hackers right now. Call 1-800-349-8830. Our technician will guide you through the fix. Have a $100 Google Play gift card ready for the security patch fee.", "sms"),
    ("NOTICE: Your electric service will be disconnected in 45 minutes due to an unpaid balance. To stop disconnection immediately, purchase a $250 MoneyPak card or Google Play card from any Walgreens and call 1-877-340-9941 with the number.", "sms"),
    ("This is bank fraud prevention. We detected a suspicious wire transfer of $4,800 from your account. Your funds are frozen pending verification. To restore access, you must confirm your identity via a $500 iTunes gift card. Do not visit the branch.", "sms"),
]

# ── Pig butchering — early stage (subtle, casual, no urgency yet) ─────────────
PIG_BUTCHERING_SUBTLE = [
    ("Hi! I think I have the wrong number — I was trying to reach my colleague Jennifer. Sorry to bother you! By the way, I'm Rachel, a financial consultant in New York. Hope you have a wonderful day!", "sms"),
    ("Oops wrong number! I meant to text my friend David. I'm Kevin by the way — just moved here for work. Since we're talking anyway, what do you do for work? Always nice to meet new people!", "sms"),
    ("Hi there! Sorry — wrong number. I was messaging my cousin. I'm Linda, I work in tech. Have a good day! 😊", "sms"),
    ("Hello! Is this Mark? I think I have the wrong contact. Anyway I'm Christina — financial advisor from Hong Kong. Hope your week is going well!", "sms"),
    ("Hi, I came across your profile and thought you looked interesting. I'm currently based in Singapore doing investment consulting. I don't usually message strangers but something about your profile made me curious. How are you?", "sms"),
    ("Hey! We matched a while back and I never messaged, sorry! I've been super busy — I work in finance and it's been a crazy year. The markets have been wild! Do you invest at all?", "sms"),
    ("Hi there, hope you're having a good week. I was just thinking — we've been chatting for a while and I realized I never told you what I do. I work in crypto trading. It's been very good to me lately. What about you?", "sms"),
    ("I've been meaning to tell you — I use this app called TradePro that my uncle in Singapore showed me. I put in $300 last month and made back $1,100. I was skeptical at first too but the returns have been consistent. Happy to share more if you're curious.", "sms"),
    ("Not sure if I mentioned it but I've been doing really well with crypto this year. I have a mentor who runs a platform where we can see his trades in real time. He's been trading for 15 years. I've made more in 3 months than in my whole last year at work.", "sms"),
    ("I wanted to ask — have you ever tried investing in crypto? I ask because I found something that's been changing my life financially and I don't want to keep it to myself. No pressure at all, just genuinely want to share with someone I trust.", "sms"),
    ("I know this might sound weird but my financial situation completely changed this year. I started using a trading platform my cousin showed me — it's invite-only. I've been able to withdraw profits every week. I thought of you because you seem smart about money.", "sms"),
    ("Hey, random question — are you interested in passive income at all? I've been doing really well with a strategy a friend taught me. I was a total skeptic 6 months ago. Now I'm making more from trading than from my job. I can show you my account if you want proof.", "sms"),
    ("I just made my 4th withdrawal from the platform this month. $3,200 total this month alone. I wish I had found this 2 years ago. Honestly I feel bad not sharing it with people I care about. Would you be open to just looking at it? Zero obligation.", "sms"),
    ("My portfolio on the platform is up 340% since I started in March. I started with just $500. My account manager Linda has been incredible — she contacts me every day. I know it sounds too good to be true but I have the screenshots. Want to see?", "sms"),
    ("You can start with as little as $100 on the platform to try it. Most people start small and see the returns before adding more. My friend Jessica started with $200 and now trades $10k. The minimum deposit is low because they want you to see results first before committing more.", "sms"),
]

# ── QR phishing variants ─────────────────────────────────────────────────────
QR_PHISHING = [
    ("Your Chase Bank account requires immediate verification. Open your phone camera and scan the QR code in this message to confirm your identity and restore access.", "sms"),
    ("NHS appointment confirmation required. Scan the QR code below to verify your attendance or cancel your appointment. Failure to respond in 24 hours will result in removal from the waiting list.", "sms"),
    ("Parking violation #PV-4421 issued at Main St. Pay your $45 fine online or scan the QR code on this notice within 7 days to avoid a $200 late penalty.", "sms"),
    ("Your toll account has a negative balance of -$12.40. Scan the QR code to add funds and avoid vehicle registration suspension.", "sms"),
    ("DVLA: Your vehicle tax is overdue. Scan the QR code below to pay immediately and avoid a court summons and £1,000 fine.", "sms"),
    ("Your Netflix account has been placed on hold due to a billing issue. Scan the QR code to update your payment information and resume your subscription.", "sms"),
    ("Centrelink: You have an unread message about your payment. Scan the QR code to log in securely and view the update regarding your account.", "sms"),
    ("Your MetroPCS account has a balance of $0. Service will be suspended in 2 hours. Scan the QR code to add a payment method and keep your number active.", "sms"),
    ("Important: Your Google account was accessed from an unknown device in Russia. Scan this QR code immediately to secure your account and review activity.", "sms"),
    ("ATO: You have a tax refund of $847.20 pending. Scan the QR code to verify your bank details and receive your refund within 3 business days.", "sms"),
    ("Your electric utility payment failed. To avoid service disconnection scan the QR code and update your payment method before 5pm today.", "sms"),
    ("Your Apple ID has been locked following multiple failed sign-in attempts. Scan this QR code to unlock your account and verify your identity.", "sms"),
    ("COVID-19 exposure notification: You may have been in contact with a confirmed case. Scan the QR code to report your status and receive further instructions.", "sms"),
    ("Your LinkedIn account password was reset from a new device. If this wasn't you, scan the QR code to immediately revoke access and secure your account.", "sms"),
    ("Coinbase: Withdraw request of $4,200 submitted from a new device. Scan QR code within 10 minutes to cancel this transaction or it will be processed.", "sms"),
]

# ── SIM swap / OTP theft variants ────────────────────────────────────────────
SIM_SWAP = [
    ("Hi this is Sarah from Vodafone customer care. I'm processing your account update but I need to verify it's really you. I've sent a 6-digit code to your phone. Can you read that out to me?", "sms"),
    ("This is your bank's fraud team. We've blocked a suspicious payment but need to confirm your identity before we can release the hold. What is the one-time code that just appeared on your phone?", "sms"),
    ("Hey it's me, I'm having trouble logging in from abroad and locked myself out. I'm using a friend's phone. Can you quickly check if you got a verification code from Instagram and tell me what it says?", "sms"),
    ("IT department here. We're rolling out a security update to your account and need to verify your identity. A confirmation code was sent to your registered mobile. Please provide the code when you receive it.", "email"),
    ("Hi, this is the Google security team. We detected an attempted sign-in to your account from an unknown location. To block it we sent a verification code. Please tell us the code so we can lock out the attacker.", "email"),
    ("Hi mom. My phone broke and I'm using a classmate's phone. I'm trying to log into my account but need the code they sent to my number. Can you check my old phone and tell me the 6-digit code? It expires in 5 minutes.", "sms"),
    ("PayPal security notice: To complete your identity verification, we sent a 4-digit code to your mobile number ending in 7832. Please reply with the code to confirm your account.", "sms"),
    ("This is AT&T technical support. There's a SIM conflict on your account that could cause you to lose service. I've sent a verification code to your device. Please provide it now to prevent service interruption.", "sms"),
    ("Hey, I'm trying to add you as a co-admin on our shared account but the system sent the verification code to your number by mistake. Can you forward the 6-digit code you just received? Just reply with the numbers.", "sms"),
    ("Amazon security alert: A new device is attempting to purchase $394 using your saved card. To block this transaction, reply with the one-time code we just sent to your registered phone number.", "sms"),
    ("Hi this is Experian credit monitoring. Fraudulent activity was detected on your credit file. A verification code was sent to the number on file. Please provide this code to freeze your credit immediately.", "sms"),
    ("This is the WhatsApp support team. To restore your account after our recent security audit, please provide the 6-digit registration code we sent to your phone number right now.", "sms"),
    ("Hey, quick question — did you get a text from Apple just now? I'm trying to set up Family Sharing and it accidentally sent the code to you instead of me. Can you read it to me? It's just 6 digits.", "sms"),
    ("Your Uber account is temporarily locked due to a payment issue. To unlock it, please verify ownership by providing the SMS code just sent to your mobile number ending in 4491.", "sms"),
    ("HMRC security check: To process your tax refund, we need to verify your identity. Enter the 6-digit code sent to your mobile. If you cannot access it, please call 0800-161-1950 and provide the code to our agent.", "sms"),
]

# ── Refund / overpayment scam variants ───────────────────────────────────────
REFUND_SCAMS = [
    ("Hi, I sent you $620 through Zelle by mistake — I meant to pay my landlord. I know this is awkward but could you send it back? My landlord is threatening to evict me. I can also send you $50 for the trouble.", "sms"),
    ("Hello, I'm reaching out because I purchased your item on Facebook Marketplace and I accidentally sent $750 instead of $75. It was a typo. Can you please refund the extra $675 via CashApp? My username is @johnd22.", "sms"),
    ("This is a notice from your payroll department. Due to a system error, your last paycheck included an overpayment of $1,840. You are required to return the excess amount via money order or Zelle within 5 business days to avoid deductions.", "email"),
    ("Hi there. I'm a mystery shopper coordinator. We mailed you a cashier's check for $2,800 for your first assignment. Keep $200 for yourself and send the remaining $2,600 via MoneyGram to our vendor in Texas. The assignment details are attached.", "email"),
    ("We've detected an error in our refund system that sent you $4,300 instead of $43. To avoid legal action for keeping government funds, please return $4,257 via wire transfer or gift card to our resolution department within 24 hours.", "email"),
    ("Hey, I know this is random but I bought concert tickets from you on StubHub and accidentally sent double payment — $380 instead of $190. Could you send back $190 via Venmo? My account is @ticketbuyer2024.", "sms"),
    ("I'm the buyer for the car you listed. I sent a cashier's check for $3,500 but it came out to $5,200 by mistake — my accountant made an error. Please cash the check and wire me back the difference of $1,700 via Western Union. Keep $50 for your trouble.", "email"),
    ("This is Amazon customer service. Our system shows a duplicate charge of $289 was applied to your account. To process your refund, we need to access your account. Please provide your online banking username and we will credit you within minutes.", "sms"),
    ("Hi, I'm a publisher and I overpaid for your freelance article by $450. I can't cancel the PayPal payment — it's already sent. Could you please refund $450 back to me? If PayPal gives you any issues, try sending via Zelle instead.", "email"),
    ("Your insurance claim resulted in a payout of $6,200 — however our system shows you were only owed $1,800. The excess $4,400 was transferred to you in error. To avoid legal recovery proceedings, please return the funds via wire transfer within 48 hours.", "email"),
]

# ── Legit messages — balance the new scam additions ──────────────────────────
LEGIT_MESSAGES = [
    ("Hi, are you free for coffee this weekend? Let me know what works for you and we can pick a spot!", "sms"),
    ("Your Spotify playlist has been shared with 3 of your friends. They can now listen along with you.", "sms"),
    ("Hey, just wanted to say thank you for covering my shift on Tuesday. I really appreciate it — I owe you one.", "sms"),
    ("Your Google account: New sign-in on iPhone in New York. If this was you, no action needed. If not, review your account at myaccount.google.com.", "email"),
    ("Your two-step verification code for Dropbox is 294817. This code expires in 10 minutes. Do not share it with anyone, including Dropbox support.", "sms"),
    ("Hi, your appointment with Dr. Sarah Johnson is confirmed for Thursday at 2:15pm. Please arrive 10 minutes early. To cancel: call 555-0134.", "sms"),
    ("Your Airbnb reservation is confirmed. Check-in: Dec 20. Check-out: Dec 23. Host: James M. Check-in details sent to your email.", "sms"),
    ("We noticed a new sign-in to your Apple ID from a MacBook in Chicago, IL on May 5 at 11:23am. If this was you, you can ignore this message.", "email"),
    ("Hi, I reviewed the contract you sent over. Looks good overall — I just have two small edits on page 4. I'll send you a marked-up version tomorrow morning.", "email"),
    ("Your Chase Freedom card ending in 4821 was used for $62.40 at Trader Joe's on May 5. If you did not make this purchase, call the number on the back of your card.", "sms"),
    ("Duolingo: You have a 30-day streak! Keep it going — practice Spanish today to maintain your streak.", "sms"),
    ("Your Venmo payment of $40 to Alex for 'dinner split' has been sent. The money will appear in their account shortly.", "sms"),
    ("Hi, the team meeting tomorrow has been moved to 3pm instead of 2pm. Same Zoom link. Let me know if that works!", "sms"),
    ("Your Amazon delivery is scheduled for today by 8pm. You don't need to be home — it will be left at the front door.", "sms"),
    ("This is an automated alert from your bank: A transfer of $1,200 was completed to savings account ending in 6490 on May 5. No action required.", "sms"),
    ("Your verification code for WhatsApp is 947-281. Don't share this code with others. Our employees will never ask for the code.", "sms"),
    ("Hi! I saw your GitHub PR and left some comments. Overall it looks great — just one suggestion on the auth middleware. Nice work!", "email"),
    ("Your Coinbase account: We detected a sign-in from a new browser in Los Angeles. If this was you, no action is needed. If not, secure your account at coinbase.com/security.", "email"),
    ("Hey, are you coming to the dinner on Saturday? We're meeting at 7pm at Carmine's. Let me know so we can reserve the right size table.", "sms"),
    ("Your monthly bank statement for April is now available. Log in at yourbank.com to view your full statement and transaction history.", "email"),
]


def compute_basic_features(text):
    words = text.split()
    urls = re.findall(r'https?://\S+', text)
    urgency_words = ['urgent', 'immediately', 'asap', 'expire', 'suspended',
                     'verify', 'confirm', 'act now', 'arrest', 'warrant']
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


def insert_messages(conn, messages, label, source_id):
    c = conn.cursor()
    max_id = c.execute('SELECT MAX(message_id) FROM Message').fetchone()[0] or 0
    inserted = 0
    for text, channel in messages:
        text = text.strip()
        if not text:
            continue
        exists = c.execute('SELECT 1 FROM Message WHERE raw_text=?', (text,)).fetchone()
        if exists:
            continue
        max_id += 1
        ch_id = CHANNEL_MAP.get(channel, 3)
        c.execute(
            'INSERT INTO Message (message_id, source_id, channel_id, raw_text, label) VALUES (?,?,?,?,?)',
            (max_id, source_id, ch_id, text, label),
        )
        f = compute_basic_features(text)
        c.execute(
            'INSERT INTO MessageFeatures VALUES (?,?,?,?,?,?,?,?,?)',
            (max_id, f['text_length'], f['word_count'], f['has_url'], f['url_count'],
             f['exclamation_count'], f['uppercase_ratio'], f['digit_ratio'], f['urgency_score']),
        )
        inserted += 1
    conn.commit()
    return inserted


def main():
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
    print(f"Source: '{SOURCE_NAME}' (id={source_id})")

    before = c.execute('SELECT COUNT(*) FROM Message').fetchone()[0]

    groups = [
        ('WhatsApp/Telegram crypto group scams', WHATSAPP_CRYPTO_SCAMS, 1),
        ('Gift card payment scams', GIFT_CARD_SCAMS, 1),
        ('Pig butchering — early stage', PIG_BUTCHERING_SUBTLE, 1),
        ('QR phishing variants', QR_PHISHING, 1),
        ('SIM swap / OTP theft', SIM_SWAP, 1),
        ('Refund / overpayment scams', REFUND_SCAMS, 1),
        ('Legit balancing messages', LEGIT_MESSAGES, 0),
    ]

    total = 0
    for name, msgs, label in groups:
        n = insert_messages(conn, msgs, label, source_id)
        print(f"  {name}: {n} inserted")
        total += n

    after = c.execute('SELECT COUNT(*) FROM Message').fetchone()[0]
    scam = c.execute('SELECT COUNT(*) FROM Message WHERE label=1').fetchone()[0]
    legit = c.execute('SELECT COUNT(*) FROM Message WHERE label=0').fetchone()[0]
    conn.close()

    print(f"\nTotal inserted: {total}")
    print(f"DB: {before} → {after} messages  (scam={scam}, legit={legit})")
    print("\nNext step: python main.py")


if __name__ == '__main__':
    main()
