import requests
import json

API_URL = 'http://localhost:8000/analyze-conversation'

conversations = [

    # ─── SCAM CONVERSATIONS (10) ───────────────────────────────────────────

    {
        'name': 'Pig Butchering / Romance Scam',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 09:15] Sarah: Hi sorry wrong number I was trying to reach my cousin
[01/05/2026, 09:16] Sarah: I am Sarah by the way, where are you from?
[01/05/2026, 09:18] Me: Israel, you?
[01/05/2026, 09:19] Sarah: Singapore, I work as a financial analyst
[01/05/2026, 10:12] Sarah: My uncle manages a trading fund, last month I made $8000 extra just following his signals
[01/05/2026, 11:02] Sarah: I do not share this with everyone but I feel like I can trust you
[01/05/2026, 11:15] Sarah: Minimum entry is only $500, my uncle only takes people he trusts
[01/05/2026, 11:45] Sarah: The platform is tradepro-capital-invest.com/register?ref=sarah
[01/05/2026, 12:01] Sarah: Just deposit before Thursday and I will personally guide you
[01/05/2026, 12:15] Sarah: My uncle just confirmed 3 spots left, do not miss it'''
    },

    {
        'name': 'Grandparent Emergency Scam',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 14:22] Unknown: Grandma its me Jake
[01/05/2026, 14:23] Unknown: I am in serious trouble please dont hang up
[01/05/2026, 14:24] Grandma: Jake? What happened?
[01/05/2026, 14:25] Unknown: I got arrested in Mexico on vacation, I need bail money urgently
[01/05/2026, 14:26] Unknown: Please do not tell mom and dad they will be so angry
[01/05/2026, 14:27] Grandma: How much do you need?
[01/05/2026, 14:28] Unknown: $3500, please wire it immediately to this account
[01/05/2026, 14:29] Unknown: I am so scared grandma please hurry I dont have much time'''
    },

    {
        'name': 'Crypto Investment Scam',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 16:00] Mike: Hey man long time no talk
[01/05/2026, 16:05] Me: Hey Mike! How are you?
[01/05/2026, 16:06] Mike: Good good, hey I wanted to share something with you
[01/05/2026, 16:08] Mike: I have been using this crypto platform for 3 months now
[01/05/2026, 16:10] Mike: Turned $300 into $4800, completely legit
[01/05/2026, 16:12] Me: Really? How does it work?
[01/05/2026, 16:14] Mike: AI does all the trading, guaranteed 15% monthly returns
[01/05/2026, 16:16] Mike: I can get you in, minimum is $200, spots are limited
[01/05/2026, 16:18] Mike: Here is the link: crypto-ai-returns.net/register?ref=mike2026
[01/05/2026, 16:20] Mike: Just register today before spots fill up'''
    },

    {
        'name': 'Money Mule Recruitment',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 11:00] James: Hi I got your number from a mutual friend
[01/05/2026, 11:02] Me: Oh okay, who?
[01/05/2026, 11:03] James: David from the gym, anyway I run a small import business
[01/05/2026, 11:05] James: I am looking for someone trustworthy to help me receive payments
[01/05/2026, 11:07] Me: What kind of payments?
[01/05/2026, 11:08] James: Just international transfers, you receive and forward, simple
[01/05/2026, 11:10] James: Pays $300 per transaction, very easy work
[01/05/2026, 11:12] James: I need your full name and bank account details to set you up
[01/05/2026, 11:14] James: Can you start this week?'''
    },

    {
        'name': 'Fake Job Offer Scam',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 10:00] HR Team: Hello, we found your CV online and are impressed
[01/05/2026, 10:02] HR Team: We have a remote data entry position available
[01/05/2026, 10:03] HR Team: Pays $500 per day, only 3 hours of work
[01/05/2026, 10:05] Me: That sounds interesting, tell me more
[01/05/2026, 10:06] HR Team: No experience needed, full training provided
[01/05/2026, 10:08] HR Team: Before we proceed we need to verify your identity
[01/05/2026, 10:10] HR Team: Please complete the form at amazon-remote-jobs.net/apply
[01/05/2026, 10:12] HR Team: Also send your ID, address, and bank details for payroll setup
[01/05/2026, 10:14] HR Team: We need this within 24 hours or the position goes to someone else'''
    },

    {
        'name': 'Phishing via Fake Bank Alert',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 08:30] Bank Alert: URGENT: Suspicious transaction detected on your account
[01/05/2026, 08:31] Bank Alert: Amount: $2,847 attempted at 3:14 AM
[01/05/2026, 08:32] Me: What? I did not make this transaction
[01/05/2026, 08:33] Bank Alert: We need to verify your identity immediately
[01/05/2026, 08:34] Bank Alert: Please confirm your full card number and PIN
[01/05/2026, 08:35] Bank Alert: Visit bankofamerica-secure-verify.net/confirm now
[01/05/2026, 08:36] Bank Alert: Your account will be frozen in 30 minutes if not verified
[01/05/2026, 08:37] Bank Alert: This is your final warning before account suspension'''
    },

    {
        'name': 'Advance Fee / Nigerian Prince',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 13:00] Dr Emmanuel: Good day, I am Dr Emmanuel Okafor senior banker in Lagos
[01/05/2026, 13:02] Dr Emmanuel: I have a business proposal of $15.5 million USD
[01/05/2026, 13:03] Me: What kind of proposal?
[01/05/2026, 13:05] Dr Emmanuel: I need a trusted foreign partner to help transfer funds
[01/05/2026, 13:07] Dr Emmanuel: You will receive 40% commission for your assistance
[01/05/2026, 13:09] Dr Emmanuel: All I need is your full name, address and bank details
[01/05/2026, 13:11] Dr Emmanuel: There is a small processing fee of $299 to release the funds
[01/05/2026, 13:13] Dr Emmanuel: Once paid the full $15.5 million transfers within 24 hours
[01/05/2026, 13:15] Dr Emmanuel: This is completely legal and confidential'''
    },

    {
        'name': 'Fake Delivery Customs Fee',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 15:00] DHL Express: Your international package has arrived at customs
[01/05/2026, 15:01] Me: Great, when will it be delivered?
[01/05/2026, 15:02] DHL Express: There is an unpaid customs clearance fee of $4.99
[01/05/2026, 15:03] DHL Express: Your package will be returned to sender in 24 hours if not paid
[01/05/2026, 15:04] Me: How do I pay?
[01/05/2026, 15:05] DHL Express: Please visit dhl-customs-clearance-fee.com/pay?id=9823744
[01/05/2026, 15:06] DHL Express: Enter your card details to release the package immediately
[01/05/2026, 15:07] DHL Express: Act fast, package return process begins at midnight'''
    },

    {
        'name': 'Sextortion Blackmail',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 23:00] Unknown: I have been monitoring your device for the past 3 months
[01/05/2026, 23:01] Unknown: I have footage recorded through your webcam
[01/05/2026, 23:02] Me: Who is this?
[01/05/2026, 23:03] Unknown: Someone who knows what you have been doing online
[01/05/2026, 23:04] Unknown: Send $1500 in Bitcoin to this address within 48 hours
[01/05/2026, 23:05] Unknown: Or I will send the footage to all your contacts
[01/05/2026, 23:06] Unknown: Do not contact the police, I will know immediately
[01/05/2026, 23:07] Unknown: This is your only warning'''
    },

    {
        'name': 'Fake Tech Support',
        'expected': 'SCAM',
        'text': '''[01/05/2026, 17:00] Microsoft Support: We have detected a critical virus on your computer
[01/05/2026, 17:01] Me: What? How?
[01/05/2026, 17:02] Microsoft Support: Our security system flagged your IP address
[01/05/2026, 17:03] Microsoft Support: Your personal data and bank details are at risk
[01/05/2026, 17:04] Microsoft Support: You must call us immediately at 1-888-248-3941
[01/05/2026, 17:05] Microsoft Support: Do not turn off your computer or the virus will spread
[01/05/2026, 17:06] Me: I am calling now
[01/05/2026, 17:07] Microsoft Support: We will need remote access to your computer to fix this
[01/05/2026, 17:08] Microsoft Support: Also prepare your credit card for the protection plan fee'''
    },

    # ─── LEGIT CONVERSATIONS (10) ──────────────────────────────────────────

    {
        'name': 'Friends Planning a BBQ',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 10:00] Moatasem: Hey are you coming to the BBQ on Friday?
[01/05/2026, 10:02] Me: Yes definitely! What time?
[01/05/2026, 10:03] Moatasem: Starts at 7pm, bring something to drink
[01/05/2026, 10:05] Me: Sure, should I bring anything else?
[01/05/2026, 10:06] Moatasem: Maybe some snacks would be great
[01/05/2026, 10:08] Me: No problem, see you Friday!
[01/05/2026, 10:09] Moatasem: Awesome, looking forward to it'''
    },

    {
        'name': 'University Group Project',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 14:00] Hanan: Hi everyone, reminder that the project deadline is May 15
[01/05/2026, 14:02] Ameer: Got it, I am finishing the ML model this week
[01/05/2026, 14:03] Moatasem: I will have the data preparation done by Thursday
[01/05/2026, 14:05] Hanan: Great progress team, remember to push everything to GitHub
[01/05/2026, 14:07] Ameer: Yes the repo is up to date, latest commit was yesterday
[01/05/2026, 14:08] Hanan: Perfect, see you both at the presentation on May 20'''
    },

    {
        'name': 'Customer Support Chat',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 11:00] Amazon Support: Hello, how can I help you today?
[01/05/2026, 11:01] Me: My order has not arrived yet, it was due yesterday
[01/05/2026, 11:02] Amazon Support: I am sorry to hear that, let me check your order
[01/05/2026, 11:03] Amazon Support: I can see order #84729, it is delayed due to weather
[01/05/2026, 11:04] Amazon Support: Expected delivery is now tomorrow by 6pm
[01/05/2026, 11:05] Me: Okay thank you for letting me know
[01/05/2026, 11:06] Amazon Support: You can track it at amazon.com/orders anytime
[01/05/2026, 11:07] Amazon Support: Is there anything else I can help you with?'''
    },

    {
        'name': 'Doctor Appointment',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 09:00] Clinic: Good morning, this is Clalit clinic calling
[01/05/2026, 09:01] Me: Good morning
[01/05/2026, 09:02] Clinic: We wanted to remind you of your appointment tomorrow at 10am
[01/05/2026, 09:03] Me: Yes I remember, thank you
[01/05/2026, 09:04] Clinic: Please bring your health insurance card and arrive 10 minutes early
[01/05/2026, 09:05] Me: Will do, see you tomorrow
[01/05/2026, 09:06] Clinic: If you need to reschedule please call 04-860-7777'''
    },

    {
        'name': 'Legitimate Bank Transaction Alert',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 20:15] Chase Bank: Transaction alert on your account ending 4521
[01/05/2026, 20:16] Chase Bank: Amount: $89.99 at Apple Store, April 28 at 3:42 PM
[01/05/2026, 20:16] Me: Yes that was me, I bought an app
[01/05/2026, 20:17] Chase Bank: Thank you for confirming. No further action needed
[01/05/2026, 20:18] Chase Bank: If you ever see an unrecognized charge visit chase.com/fraud
[01/05/2026, 20:19] Me: Got it, thank you'''
    },

    {
        'name': 'Family WhatsApp Group',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 18:00] Mom: Is everyone coming for dinner Sunday?
[01/05/2026, 18:02] Dad: Yes of course, what time?
[01/05/2026, 18:03] Mom: Around 6pm, I am making your favourite
[01/05/2026, 18:05] Me: I will be there, should I bring anything?
[01/05/2026, 18:06] Mom: Just bring yourself, and remind your brother
[01/05/2026, 18:08] Me: Will do, see you Sunday!
[01/05/2026, 18:09] Dad: Looking forward to it'''
    },

    {
        'name': 'Work Slack Conversation',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 09:30] Manager: Good morning team, standup in 30 minutes
[01/05/2026, 09:31] Me: Good morning, I will be there
[01/05/2026, 09:32] Colleague: Same, just finishing the PR review
[01/05/2026, 09:45] Manager: Quick reminder to update your tasks in Jira before EOD
[01/05/2026, 09:47] Me: Already done, pushed the latest changes this morning
[01/05/2026, 09:48] Manager: Great work everyone, see you at standup'''
    },

    {
        'name': 'Legitimate LinkedIn Recruiter',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 13:00] Rachel Cohen: Hi Ameer, I came across your profile on LinkedIn
[01/05/2026, 13:01] Rachel Cohen: I am a recruiter at Microsoft Israel
[01/05/2026, 13:02] Me: Hi Rachel, nice to meet you
[01/05/2026, 13:03] Rachel Cohen: We have a Senior Data Scientist opening that matches your background
[01/05/2026, 13:05] Me: That sounds interesting, can you share more details?
[01/05/2026, 13:06] Rachel Cohen: Of course, I will send the job description to your LinkedIn inbox
[01/05/2026, 13:07] Rachel Cohen: Would you be open to a 15 minute call this week?
[01/05/2026, 13:08] Me: Yes Thursday afternoon works for me
[01/05/2026, 13:09] Rachel Cohen: Perfect, I will send a calendar invite to your email'''
    },

    {
        'name': 'Food Delivery Order',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 19:00] Wolt: Your order from Dominos Pizza has been confirmed
[01/05/2026, 19:01] Wolt: Estimated delivery time: 30 minutes
[01/05/2026, 19:15] Wolt: Your driver Avi has picked up your order
[01/05/2026, 19:20] Me: Great, how far away is he?
[01/05/2026, 19:21] Wolt: Avi is 10 minutes away, track at wolt.com/orders/928374
[01/05/2026, 19:30] Wolt: Your order has been delivered, enjoy your meal!
[01/05/2026, 19:31] Me: Thank you, received it!'''
    },

    {
        'name': 'Legitimate OTP Verification',
        'expected': 'LEGIT',
        'text': '''[01/05/2026, 22:00] WhatsApp: Your WhatsApp code is 847-291
[01/05/2026, 22:00] WhatsApp: Do not share this code with anyone
[01/05/2026, 22:01] WhatsApp: WhatsApp will never call you to verify your code
[01/05/2026, 22:02] Me: Got the code, logging in now
[01/05/2026, 22:03] System: Login successful from new device Tel Aviv Israel
[01/05/2026, 22:04] Me: Yes that was me, all good'''
    },
]


def test_conversation(conv):
    try:
        response = requests.post(
            API_URL,
            json={'text': conv['text']},
            timeout=60,
        )
        result = response.json()
        verdict = result.get('overall_verdict', 'ERROR')
        risk_score = result.get('risk_score', 0)
        full_score = result.get('full_conversation_score', 0)
        window_score = result.get('window_analysis_score', 0)
        final_score = result.get('final_messages_score', 0)
        passed = verdict == conv['expected']
        return {
            'passed': passed,
            'verdict': verdict,
            'expected': conv['expected'],
            'risk_score': risk_score,
            'full_score': full_score,
            'window_score': window_score,
            'final_score': final_score,
        }
    except Exception as e:
        return {
            'passed': False,
            'verdict': 'ERROR',
            'expected': conv['expected'],
            'risk_score': 0,
            'full_score': 0,
            'window_score': 0,
            'final_score': 0,
            'error': str(e),
        }


print('\n' + '=' * 80)
print('SCAMRADAR+ CONVERSATION STRESS TEST')
print('=' * 80)

results_cache = []
passed = 0
failed = 0
failures = []

for i, conv in enumerate(conversations):
    result = test_conversation(conv)
    results_cache.append(result)
    status = '✅ PASS' if result['passed'] else '❌ FAIL'
    if result['passed']:
        passed += 1
    else:
        failed += 1
        failures.append({'name': conv['name'], **result})

    print(f'\n[{i+1:02d}] {conv["name"]}')
    print(f'     {status} | Expected: {result["expected"]} | Got: {result["verdict"]} | Risk: {result["risk_score"]}%')
    if not result['passed']:
        print(f'     Scores → Full: {result.get("full_score")}% | Window: {result.get("window_score")}% | Final: {result.get("final_score")}%')

scam_passed  = sum(1 for r in results_cache[:10] if r['passed'])
legit_passed = sum(1 for r in results_cache[10:] if r['passed'])

print('\n' + '=' * 80)
print(f'RESULTS: {passed}/20 passed ({round(passed / 20 * 100)}%)')
print(f'Scam detection : {scam_passed}/10')
print(f'Legit detection: {legit_passed}/10')

if failures:
    print(f'\nFAILURES:')
    for f in failures:
        print(f'  - {f["name"]}: expected {f["expected"]}, got {f["verdict"]} ({f["risk_score"]}%)')

print('=' * 80)
