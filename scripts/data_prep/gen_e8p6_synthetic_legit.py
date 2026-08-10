"""
E8-P6 — Large-scale synthetic legitimate data generation.

Goal
----
Scale up E8-P2's approach to ~15-20k rows so the LR's coefficient on
generic English function words (`your`, `to`, `here`, `re`, `hi`, `link`,
`free`, `email`) meaningfully shrinks toward neutrality. E8-P2's 1,978
rows were too small vs. the 130k+ legit training corpus to move those
coefficients. E8-P6 targets 10-15× that scale with broader category /
brand coverage.

Approach
--------
* Reuse all E8-P2 infrastructure: placeholder pools, region-pairing,
  category-specific amount ranges, paraphrase pools, safety validators.
* Add ~130 NEW templates covering the failure modes we saw:
    - Long-form newsletters (LinkedIn/Substack style — the LinkedIn FP)
    - Terms of Use / Privacy Policy updates (the Higgsfield FP)
    - Referral / guest-pass promos (the Claude guest pass FP)
    - Short receipts (the Anthropic receipt FP)
    - Account maintenance requests (the Temu FP — but with SAFE wording only)
    - SaaS product update announcements
    - Cloud / infra notifications (AWS/GCP/GitHub Actions)
    - Support ticket updates (Zendesk/Intercom)
    - Domain / SSL certificate notifications
    - Event / meeting invitations
    - Travel confirmations
* Increase variations per template to 80-120 (was 25-40 in E8-P2).
* Same 100% safety guarantee — no credential/OTP/gift-card/crypto-seed/
  remote-access patterns can appear in a legit message.
* Same URL discipline — every URL uses an allowlisted official domain.

Output
------
data/synthetic_legit/e8p6/dataset.parquet    — validated dataset
data/synthetic_legit/e8p6/samples.txt        — human-readable preview
data/synthetic_legit/e8p6/rejection_report.json
data/synthetic_legit/e8p6/generation_stats.json
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Reuse ALL infrastructure from E8-P2
from scripts.data_prep.gen_e8p2_synthetic_legit import (
    RNG, TEMPLATES as E8P2_TEMPLATES,
    render_template, validate,
    _fill_slots,
    AMOUNT_KINDS, CURRENCY_KINDS,
)

OUT_DIR = os.path.join(_ROOT, 'data', 'synthetic_legit', 'e8p6')
os.makedirs(OUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════
# NEW E8-P6 templates — categories targeting observed FP failure modes
# ══════════════════════════════════════════════════════════════════════════
# Reuses ALL placeholder tokens registered in _fill_slots (via P2 generator).
# ══════════════════════════════════════════════════════════════════════════

E8P6_NEW_TEMPLATES = [

    # ── LONG NEWSLETTER / MARKETING (Substack / LinkedIn / Medium style) ─
    # The LinkedIn FP was in this shape.
    {'id': 'nl_substack_weekly',       'category': 'newsletter_marketing', 'brand': 'substack',
     'body': ('This week on our newsletter: 5 essays worth your time. '
              '{full_name} on why product taste matters more than metrics. '
              'A deep dive into how {full_name} built a $10M business from '
              'their kitchen table. Plus: reader questions on remote work, '
              'and our monthly roundup of the best long-form writing. '
              'Read it all at substack.com — takes about 20 minutes.'), 'n': 60},

    {'id': 'nl_linkedin_article',      'category': 'newsletter_marketing', 'brand': 'linkedin',
     'body': ('New from your network on LinkedIn: {full_name} just published '
              '"{article_title}". {mins}-minute read. Their piece has already '
              'gathered {viewers} views and dozens of thoughtful comments. '
              'Read on LinkedIn to join the conversation.'), 'n': 60},

    {'id': 'nl_medium_daily',          'category': 'newsletter_marketing', 'brand': 'medium',
     'body': ('Your Daily Digest from Medium. Based on your reading history, '
              'here are 5 stories we think you\'ll like today. '
              '"{article_title}" by {full_name} — {mins} min read. '
              '"{article_title}" — {mins2} min read. Read at medium.com.'), 'n': 50},

    {'id': 'nl_ycombinator_weekly',    'category': 'newsletter_marketing', 'brand': 'yc',
     'body': ('This week in YC: 8 companies from the current batch launched. '
              'Highlights include a new AI code review tool, a payments '
              'startup for creators, and an open-source database. Plus, '
              'notes from Demo Day and how founders are thinking about '
              'growth in 2026. Read the full recap on the YC blog.'), 'n': 40},

    {'id': 'nl_ai_prompt_pack',        'category': 'newsletter_marketing', 'brand': 'substack',
     'body': ('{count} AI Prompts That Actually Work. Most people use AI '
              'for content the wrong way — they throw in a vague prompt, '
              'get robotic output, then spend {mins} minutes trying to make '
              'it sound human. We spent months testing and refining. Kept '
              'only the ones that produced usable output on the first try. '
              '{count} prompts, {count2} categories: posts, emails, '
              'landing pages, and research. Each comes with the exact '
              'prompt, the reasoning behind it, and a real output example. '
              'Over {readers} people already grabbed this. Grab it here '
              'for free.'), 'n': 50},

    {'id': 'nl_stratechery_note',      'category': 'newsletter_marketing', 'brand': 'substack',
     'body': ('The interesting question about the {topic} announcement isn\'t '
              'what was announced, but why now. In this week\'s note, I walk '
              'through the strategic logic, the competitive dynamics, and '
              'what it means for the broader industry. Free readers get '
              'the first half; the rest is for paying subscribers.'), 'n': 40},

    {'id': 'nl_axios_am',              'category': 'newsletter_marketing', 'brand': 'axios',
     'body': ('Good morning. Today\'s Axios AM in {city} — {word_count} words '
              'in {mins} minutes. Top of the news: {topic}. Also inside: a '
              'chart on inflation, one big thing on the housing market, '
              'and a smart brevity briefing on the week ahead. Was this '
              'email forwarded to you? Sign up for free at axios.com.'), 'n': 40},

    # ── TERMS / PRIVACY / POLICY UPDATES (Higgsfield style) ──────────────
    {'id': 'tos_higgsfield_style',     'category': 'tos_privacy_update', 'brand': 'anthropic',
     'body': ('{greeting}, We\'re updating our Terms of Use and Privacy '
              'Policy to reflect new features and how the platform works. '
              'These updates take effect on {date}. Here\'s what matters '
              'most: Transparent pricing. Any subscription price increase '
              'will apply only to your next renewal term, and you\'ll '
              'receive at least 30 days\' notice by email. A grace period '
              'on payments. If a payment fails, you\'ll typically have up '
              'to 14 days to resolve it before it affects your subscription. '
              'Refund protections. If we ever discontinue something you\'ve '
              'paid for, you\'ll receive a refund for the unused portion. '
              'See what changed and why. We\'ve explained everything in '
              'plain language.'), 'n': 40},

    {'id': 'tos_google_update',        'category': 'tos_privacy_update', 'brand': 'google',
     'body': ('We\'re updating the Google Terms of Service and Privacy '
              'Policy. The changes take effect on {date}. What\'s changing: '
              'clearer language on how we protect your data, updated '
              'information about our AI features, and improvements to our '
              'account controls. Your existing controls and settings remain '
              'the same. Review the full updates at policies.google.com.'), 'n': 40},

    {'id': 'tos_apple_update',         'category': 'tos_privacy_update', 'brand': 'apple',
     'body': ('The Apple Media Services Terms and Conditions have been '
              'updated. These new terms apply beginning {date}. Changes '
              'include: updated language on subscription auto-renewal, '
              'clarified refund policies for App Store purchases, and '
              'expanded information about parental controls. You can '
              'review the complete terms in Settings > Apple ID > Terms '
              'and Conditions on any of your devices.'), 'n': 35},

    {'id': 'tos_stripe_update',        'category': 'tos_privacy_update', 'brand': 'stripe',
     'body': ('An update to your Stripe agreement. Effective {date}, we\'re '
              'making a few changes to our Services Agreement and Connected '
              'Account Agreement. The updates clarify our data protection '
              'practices, add information about new payment methods we now '
              'support, and update our processing fees for a small subset '
              'of card types. Full details at stripe.com/legal.'), 'n': 35},

    {'id': 'tos_notion_update',        'category': 'tos_privacy_update', 'brand': 'notion',
     'body': ('Notion is updating our Terms of Service and Privacy Policy, '
              'effective {date}. What\'s new: clearer guidance on AI '
              'features and how we handle content used with them, and '
              'refined language on team workspace ownership. Your data '
              'ownership and privacy controls are unchanged. Read the '
              'update at notion.so/legal.'), 'n': 30},

    {'id': 'tos_discord_update',       'category': 'tos_privacy_update', 'brand': 'discord',
     'body': ('Discord: We\'re updating our Terms of Service and Privacy '
              'Policy. These changes take effect {date}. The updates '
              'clarify how we handle user-generated content, expand our '
              'safety and moderation policies, and align our documentation '
              'with recent EU regulations. Read the full changes at '
              'discord.com/terms.'), 'n': 30},

    {'id': 'tos_dropbox_update',       'category': 'tos_privacy_update', 'brand': 'dropbox',
     'body': ('Dropbox is updating our Terms of Service, Privacy Policy, '
              'and Acceptable Use Policy, effective {date}. The most '
              'significant changes are around AI-assisted features, '
              'updated data-retention practices for team accounts, and '
              'refined language on billing. No action is needed on your '
              'part — the updates apply automatically.'), 'n': 30},

    # ── REFERRAL / GUEST PASS / INVITE PROMOS (Claude guest pass style) ──
    {'id': 'promo_claude_guest',       'category': 'referral_promo', 'brand': 'anthropic',
     'body': ('It\'s a win-win. Gift a friend one free week of Claude Code '
              'on the Pro plan by sending them a guest pass. If they love '
              'it and subscribe, you\'ll get {currency}{amount} of usage '
              'credits per referral. How to send a guest pass: Type '
              '/passes in your CLI or visit your Claude Code settings. '
              'Copy the referral link and send it to a friend. Receive '
              '{currency}{amount} of usage credits if your friend '
              'subscribes to a paid plan. Terms apply.'), 'n': 40},

    {'id': 'promo_dropbox_refer',      'category': 'referral_promo', 'brand': 'dropbox',
     'body': ('Refer a friend, earn free space. When your friend signs up '
              'for Dropbox using your referral link and installs the '
              'desktop app, you\'ll each get {gb} GB of extra space free. '
              'You can earn up to 32 GB. Share your link at dropbox.com/'
              'referrals.'), 'n': 35},

    {'id': 'promo_uber_refer',         'category': 'referral_promo', 'brand': 'uber',
     'body': ('Invite friends, earn free rides. Share your Uber referral '
              'code with friends who haven\'t tried Uber yet. When they '
              'take their first trip, you get {currency}{amount} in Uber '
              'Cash. Your code: {code_6}. Share it in the Uber app or '
              'at uber.com/refer.'), 'n': 30},

    {'id': 'promo_notion_team',        'category': 'referral_promo', 'brand': 'notion',
     'body': ('Invite your team to Notion and earn credits. For every '
              'teammate who joins your workspace and stays for 30 days, '
              'you\'ll receive {currency}{amount} in Notion credits. '
              'Send invites from your workspace settings. There\'s no '
              'cap on referrals.'), 'n': 25},

    {'id': 'promo_spotify_family',     'category': 'referral_promo', 'brand': 'spotify',
     'body': ('Add family and save. Your Spotify Premium Family plan can '
              'include up to 6 people at one address for just '
              '{currency}{amount}/month total. Invite them from your '
              'account page. Each person gets their own login, playlists, '
              'and Downloads.'), 'n': 25},

    # ── SHORT RECEIPTS (Anthropic-style — under 60 words) ────────────────
    {'id': 'receipt_short_anthropic',  'category': 'short_receipt', 'brand': 'anthropic',
     'body': ('Receipt from Anthropic, PBC. {currency}{amount} paid {date}. '
              'Receipt number {stripe_id}. Payment method Visa - {last4}. '
              'Prepaid extra usage, Individual plan. Total {currency}{amount}. '
              'Download invoice at console.anthropic.com.'), 'n': 40},

    {'id': 'receipt_short_openai',     'category': 'short_receipt', 'brand': 'openai',
     'body': ('Receipt from OpenAI. {currency}{amount} paid {date}. '
              'Receipt number {stripe_id}. Payment method Mastercard '
              'ending in {last4}. ChatGPT Plus monthly subscription. '
              'View at platform.openai.com/account/billing.'), 'n': 40},

    {'id': 'receipt_short_stripe',     'category': 'short_receipt', 'brand': 'stripe',
     'body': ('Receipt from {merchant}. {currency}{amount} paid {date}. '
              'Payment method Amex ending in {last4}. Receipt number '
              '{stripe_id}. Questions? Contact {merchant} directly.'), 'n': 40},

    {'id': 'receipt_short_paddle',     'category': 'short_receipt', 'brand': 'paddle',
     'body': ('Your Paddle receipt. {currency}{amount} for {merchant}. '
              'Invoice #{invoice_id}. Payment received on {date}. Download '
              'invoice at paddle.com/customer-portal.'), 'n': 30},

    {'id': 'receipt_short_lemonsqueezy', 'category': 'short_receipt', 'brand': 'lemonsqueezy',
     'body': ('Order confirmation from Lemon Squeezy. {currency}{amount} '
              'for {merchant}. Receipt #{invoice_id}. Payment method '
              'card ending {last4}. Thank you for your purchase.'), 'n': 25},

    # ── ACCOUNT MAINTENANCE / INFO UPDATE (Temu style — SAFE wording) ────
    # IMPORTANT: These MUST NOT phrase things like "click below to enter your
    # password" or "verify your credentials". Only benign "review your info"
    # style with an anti-fraud reminder. Never asks for anything sensitive.
    {'id': 'acct_temu_info_review',    'category': 'account_maintenance', 'brand': 'temu',
     'body': ('{greeting}, it\'s been more than 6 months since you last '
              'reviewed your personal info on your account. Keeping your '
              'personal info up to date can help better protect your '
              'account. If you\'d like to review it, sign in to your '
              'Temu account and go to Settings > Personal Info. If you '
              'recently updated your info, please ignore this reminder. '
              'Anti-Fraud Reminder: Temu does not ask customers for '
              'additional fees, passwords, or verification codes via '
              'SMS or email. Never share such information.'), 'n': 35},

    {'id': 'acct_facebook_info_review','category': 'account_maintenance', 'brand': 'facebook',
     'body': ('It\'s been a while since you reviewed your Facebook account '
              'settings. Take a moment to review who can see your posts, '
              'update your contact info, and check your security settings. '
              'Sign in to Facebook and visit Settings & Privacy.'), 'n': 30},

    {'id': 'acct_linkedin_profile',    'category': 'account_maintenance', 'brand': 'linkedin',
     'body': ('Keep your LinkedIn profile current. Your profile hasn\'t '
              'been updated in {mins} months. Adding your latest work, '
              'a fresh photo, or a short summary can significantly boost '
              'how often your profile is viewed. Update at linkedin.com.'), 'n': 30},

    {'id': 'acct_google_review',       'category': 'account_maintenance', 'brand': 'google',
     'body': ('Time for a Google Security Checkup. It\'s been over 6 '
              'months since your last checkup. Take 2 minutes to review '
              'devices signed into your account, third-party access, and '
              'saved passwords. Start your checkup at myaccount.google.com/'
              'security-checkup.'), 'n': 30},

    {'id': 'acct_amazon_review',       'category': 'account_maintenance', 'brand': 'amazon',
     'body': ('Your Amazon Account: annual review. It\'s a good time to '
              'review your saved addresses, payment methods, and default '
              'settings. This helps ensure smooth checkout and delivery. '
              'Go to Your Account > Login & Security.'), 'n': 25},

    # ── SAAS PRODUCT UPDATE ANNOUNCEMENTS ────────────────────────────────
    {'id': 'prod_notion_ai',           'category': 'product_update', 'brand': 'notion',
     'body': ('New in Notion: AI-powered databases. You can now generate '
              'entire databases from a description. Just type / and choose '
              '"AI generate database" — Notion will build the structure, '
              'suggest properties, and populate example rows. Available to '
              'all Notion AI subscribers today.'), 'n': 30},

    {'id': 'prod_figma_dev_mode',      'category': 'product_update', 'brand': 'figma',
     'body': ('Figma product update: Dev Mode is now generally available. '
              'Inspect any frame, export code snippets in React or SwiftUI, '
              'and see design changes in your Git diff. Available for all '
              'Professional and Organization plans starting {date}.'), 'n': 25},

    {'id': 'prod_slack_huddles',       'category': 'product_update', 'brand': 'slack',
     'body': ('What\'s new in Slack this week: Huddles now support screen '
              'sharing on mobile, threads have a cleaner navigation, and '
              'we\'ve added new keyboard shortcuts for switching between '
              'workspaces. Read the full release notes at slack.com/'
              'release-notes.'), 'n': 25},

    {'id': 'prod_github_copilot',      'category': 'product_update', 'brand': 'github',
     'body': ('GitHub Copilot: what\'s new this month. Faster inline '
              'suggestions, expanded support for Ruby and PHP, and a new '
              '"explain this code" command in your editor. Free for '
              'verified students and maintainers of popular open-source '
              'projects. See details at github.com/features/copilot.'), 'n': 25},

    {'id': 'prod_vercel_features',     'category': 'product_update', 'brand': 'vercel',
     'body': ('Ship faster with Vercel: this month we released a new '
              'preview deployment dashboard, added support for Turbopack '
              'builds, and cut cold start times by 30%. All updates are '
              'live for every project — no config changes needed.'), 'n': 25},

    {'id': 'prod_openai_gpt_update',   'category': 'product_update', 'brand': 'openai',
     'body': ('OpenAI: What\'s new this week. Improved response quality '
              'for long-form tasks, faster streaming, and expanded rate '
              'limits for Plus and Pro subscribers. Also new: an "explain '
              'my code" mode in ChatGPT. Read the release notes at '
              'openai.com/blog.'), 'n': 25},

    {'id': 'prod_linear_release',      'category': 'product_update', 'brand': 'linear',
     'body': ('Linear release notes. This cycle: a rewritten filter '
              'engine (10× faster on large datasets), new triage inbox '
              'for support teams, and improved GitHub integration. All '
              'changes ship gradually over the next 7 days. Full notes '
              'at linear.app/changelog.'), 'n': 25},

    # ── CLOUD / INFRA NOTIFICATIONS ──────────────────────────────────────
    {'id': 'cloud_aws_billing',        'category': 'cloud_alert', 'brand': 'aws',
     'body': ('AWS Billing alert. Your account estimated total for '
              '{month} is currently {currency}{amount}. This is above '
              'your configured alert threshold. Review usage details in '
              'the AWS Billing Console. Alert configured by you at '
              'account creation.'), 'n': 30},

    {'id': 'cloud_gcp_quota',          'category': 'cloud_alert', 'brand': 'google',
     'body': ('Google Cloud: You\'re approaching a quota limit. Your '
              'project "{workspace}" is at {mins}% of its monthly Compute '
              'Engine CPU quota. Consider requesting a quota increase or '
              'reviewing your usage. Review at console.cloud.google.com.'), 'n': 25},

    {'id': 'cloud_github_actions',     'category': 'cloud_alert', 'brand': 'github',
     'body': ('GitHub Actions: your organisation has used {mins}% of its '
              'included Actions minutes for {month}. At the current pace, '
              'you\'ll hit the included limit around {date}. Review usage '
              'at github.com/organisations/{workspace}/billing.'), 'n': 25},

    {'id': 'cloud_cloudflare_alert',   'category': 'cloud_alert', 'brand': 'cloudflare',
     'body': ('Cloudflare notification: your zone {gh_user}.io is showing '
              'unusually high request volume over the past {mins} minutes. '
              'This could indicate a traffic spike or an attack. Review '
              'analytics at dash.cloudflare.com.'), 'n': 20},

    {'id': 'cloud_vercel_deploy',      'category': 'cloud_alert', 'brand': 'vercel',
     'body': ('Vercel deployment complete. Project: {gh_user}/{repo}. '
              'Deployment {stripe_id} succeeded in {mins} seconds and is '
              'now live at production URL. Preview available at '
              'vercel.com/{gh_user}/{repo}.'), 'n': 25},

    # ── SUPPORT TICKET / AUTO-REPLY (Zendesk/Intercom style) ─────────────
    {'id': 'supp_ticket_received',     'category': 'support_ticket', 'brand': 'stripe',
     'body': ('Thanks for reaching out, {name}. We\'ve received your '
              'message and created ticket #{invoice_id}. Our team will '
              'respond within 2 business days. You can reply to this '
              'email to add more details to the ticket.'), 'n': 30},

    {'id': 'supp_ticket_updated',      'category': 'support_ticket', 'brand': 'notion',
     'body': ('Ticket #{invoice_id} update. Our support team has '
              'responded to your ticket about "{article_title}". Read '
              'the response and reply at notion.so/help.'), 'n': 25},

    {'id': 'supp_ticket_resolved',     'category': 'support_ticket', 'brand': 'linear',
     'body': ('Your ticket #{invoice_id} has been marked resolved. If '
              'the issue persists, reply to this email and we\'ll reopen '
              'the ticket. Otherwise, no further action is needed. Thanks '
              'for the report!'), 'n': 25},

    {'id': 'supp_survey_request',      'category': 'support_ticket', 'brand': 'intercom',
     'body': ('How did we do? You recently interacted with our support '
              'team on ticket #{invoice_id}. If you have a moment, we\'d '
              'love your feedback — a 1-minute survey helps us improve. '
              'Take the survey via the link in your support portal.'), 'n': 20},

    # ── DOMAIN / SSL / DEV INFRA ─────────────────────────────────────────
    {'id': 'domain_renewal',           'category': 'domain_ssl', 'brand': 'namecheap',
     'body': ('Your domain {gh_user}.com expires in 30 days on {date}. '
              'Auto-renew is enabled — your payment method Visa ending '
              '{last4} will be charged {currency}{amount} on renewal. '
              'Manage at ap.www.namecheap.com.'), 'n': 25},

    {'id': 'ssl_renewal',              'category': 'domain_ssl', 'brand': 'letsencrypt',
     'body': ('Let\'s Encrypt: your certificate for {gh_user}.io has been '
              'renewed. New expiry: {date}. Certificate ID: {stripe_id}. '
              'This is an automated notification — no action needed.'), 'n': 20},

    {'id': 'github_pr_review',         'category': 'domain_ssl', 'brand': 'github',
     'body': ('A pull request needs your review. {full_name} opened '
              'PR #{shopify_id} in {gh_user}/{repo}: "{article_title}". '
              '{mins} files changed, +{count} −{count2}. Review at '
              'github.com/{gh_user}/{repo}/pull/{shopify_id}.'), 'n': 30},

    {'id': 'github_issue_assigned',    'category': 'domain_ssl', 'brand': 'github',
     'body': ('You\'ve been assigned an issue on {gh_user}/{repo}: '
              '"{article_title}" (#{shopify_id}). {full_name} mentioned '
              'you in the discussion. View at github.com/{gh_user}/{repo}/'
              'issues/{shopify_id}.'), 'n': 30},

    # ── EVENT / MEETING INVITES ──────────────────────────────────────────
    {'id': 'event_zoom_invite',        'category': 'event_invite', 'brand': 'zoom',
     'body': ('You\'re invited to a Zoom meeting. "{meeting_name}" on '
              '{date} at {time_gmt}. Meeting ID: {meeting_id}. Join with '
              'one tap from your calendar or at zoom.us/j/{meeting_id}.'),
     'n': 30},

    {'id': 'event_calendar_reminder',  'category': 'event_invite', 'brand': 'google',
     'body': ('Reminder: "{meeting_name}" starting in {mins} minutes. '
              'Location: Google Meet. Attendees: {full_name}, {full_name}, '
              'and 2 others. View in Calendar.'), 'n': 25},

    {'id': 'event_eventbrite',         'category': 'event_invite', 'brand': 'eventbrite',
     'body': ('Your ticket for "{meeting_name}" on {date}. Doors open at '
              '{time_gmt}. Location: {city}, {country}. Order number '
              '{invoice_id}. Bring this email or open the Eventbrite app '
              'for entry.'), 'n': 25},

    {'id': 'event_meetup_new',         'category': 'event_invite', 'brand': 'meetup',
     'body': ('New event from your Meetup group: "{meeting_name}". '
              '{date} at {time_gmt} in {city}. {count} people have RSVP\'d '
              'so far. Reserve your spot at meetup.com.'), 'n': 20},

    # ── TRAVEL CONFIRMATIONS ─────────────────────────────────────────────
    {'id': 'travel_airbnb_confirmed',  'category': 'travel_confirm', 'brand': 'airbnb',
     'body': ('Your Airbnb reservation is confirmed. Stay: {mins} nights '
              'in {city}, {country}. Check-in: {date}. Reservation code: '
              '{stripe_id}. Total: {currency}{amount}. Manage at '
              'airbnb.com/reservations.'), 'n': 30},

    {'id': 'travel_booking_hotel',     'category': 'travel_confirm', 'brand': 'booking',
     'body': ('Booking.com: your reservation at {merchant} Hotel in '
              '{city} is confirmed. Check-in {date}, check-out '
              '{date2}. Confirmation number: {invoice_id}. Total: '
              '{currency}{amount}.'), 'n': 30},

    {'id': 'travel_flight_ticket',     'category': 'travel_confirm', 'brand': 'delta',
     'body': ('Delta Air Lines: your booking is confirmed. Flight DL '
              '{count2} from {city} to {city2} on {date}. '
              'Confirmation code: {reference}. Total: {currency}{amount}. '
              'Check in at delta.com 24 hours before departure.'), 'n': 30},

    {'id': 'travel_uber_receipt',      'category': 'travel_confirm', 'brand': 'uber',
     'body': ('Thanks for riding with Uber, {name}. Your trip on {date} '
              'from {city} — {currency}{amount}. Payment method: Visa '
              'ending {last4}. View receipt at riders.uber.com.'), 'n': 30},

    {'id': 'travel_expedia_itinerary', 'category': 'travel_confirm', 'brand': 'expedia',
     'body': ('Your Expedia itinerary is ready. Flight + hotel package '
              'to {city} on {date}. Confirmation: {reference}. Total: '
              '{currency}{amount}. Manage your booking at expedia.com/'
              'itinerary.'), 'n': 25},

    # ── SUBSCRIPTION LIFECYCLE (renewal / trial ending / plan changes) ───
    {'id': 'sub_trial_ending',         'category': 'subscription_lifecycle', 'brand': 'notion',
     'body': ('Your Notion Plus trial ends in 7 days on {date}. To keep '
              'access to unlimited file uploads, longer version history, '
              'and other Plus features, add a payment method. If you\'d '
              'prefer to stay on the Free plan, no action is needed — '
              'you\'ll automatically be moved when the trial ends.'), 'n': 30},

    {'id': 'sub_plan_upgraded',        'category': 'subscription_lifecycle', 'brand': 'figma',
     'body': ('Your Figma plan was upgraded. You\'re now on the Professional '
              'plan at {currency}{amount}/month, billed monthly. Your new '
              'plan includes unlimited files, version history, and team '
              'libraries. First charge: {date}.'), 'n': 25},

    {'id': 'sub_plan_downgraded',      'category': 'subscription_lifecycle', 'brand': 'linear',
     'body': ('Your Linear plan will change on {date}. Based on your '
              'request, you\'ll move from Standard ({currency}{amount}/'
              'seat) to the Basic plan. Any pro-rated credit will appear '
              'on your next invoice.'), 'n': 20},

    {'id': 'sub_paused',               'category': 'subscription_lifecycle', 'brand': 'spotify',
     'body': ('Your Spotify Premium is paused as requested. You\'ll '
              'automatically be resumed on {date} — or you can resume '
              'anytime from spotify.com/account. During pause, you\'ll '
              'have Free access with ads.'), 'n': 25},

    # ── TWO-FACTOR / DEVICE MANAGEMENT (security-adjacent, notify-only) ──
    {'id': 'sec_2fa_enabled',          'category': 'security_notification', 'brand': 'github',
     'body': ('Two-factor authentication was enabled on your GitHub '
              'account. From now on, sign-ins will require a code from '
              'your authenticator app. {if_not_you}, review your account '
              'at github.com/settings/security immediately.'), 'n': 25},

    {'id': 'sec_new_recovery_email',   'category': 'security_notification', 'brand': 'google',
     'body': ('A new recovery email was added to your Google Account. '
              '{if_this_was_you}, {no_action}. {if_not_you}, review '
              'your account at myaccount.google.com/security.'), 'n': 25},

    {'id': 'sec_device_removed',       'category': 'security_notification', 'brand': 'apple',
     'body': ('A trusted device was removed from your Apple ID: {device}. '
              '{if_this_was_you}, {ignore_safely}. {if_not_you}, sign '
              'in at appleid.apple.com and review your trusted devices.'), 'n': 25},

    {'id': 'sec_backup_codes',         'category': 'security_notification', 'brand': 'microsoft',
     'body': ('New two-factor authentication backup codes were generated '
              'for your Microsoft account. Store them somewhere safe — '
              'you\'ll need them if you lose access to your phone. '
              '{if_not_you}, review at account.microsoft.com/security.'), 'n': 20},

    # ── SHIPPING EXPANSION ───────────────────────────────────────────────
    {'id': 'ship_amazon_returned',     'category': 'shipping', 'brand': 'amazon',
     'body': ('Your return was received. Order #{amazon_id} — {product}. '
              'Refund of {currency}{amount} will appear on your original '
              'payment method within 3–5 business days.'), 'n': 25},

    {'id': 'ship_delivery_delayed',    'category': 'shipping', 'brand': 'fedex',
     'body': ('FedEx: your shipment is delayed. Tracking number: '
              '{fedex_tracking}. Original estimated delivery: {date}. '
              'New estimated delivery: {date2}. Reason: weather. Track '
              'at fedex.com.'), 'n': 25},

    {'id': 'ship_pickup_ready',        'category': 'shipping', 'brand': 'ups',
     'body': ('UPS: your package is ready for pickup at UPS Access Point '
              '{merchant} in {city}. Tracking: {ups_tracking}. Bring '
              'photo ID. Package will be held for 7 days.'), 'n': 25},

    {'id': 'ship_out_for_delivery',    'category': 'shipping', 'brand': 'dhl',
     'body': ('DHL: your shipment {dhl_tracking} is out for delivery '
              'today in {city}. Expected arrival window: {time_range}. '
              'A signature may be required.'), 'n': 25},

    # ── ORDER STATUS EXPANSION ───────────────────────────────────────────
    {'id': 'order_amazon_refund',      'category': 'order_confirmation', 'brand': 'amazon',
     'amount_kind': 'amazon_order',
     'body': ('Refund processed. Order #{amazon_id} — {product}. Your '
              'refund of {currency}{amount} has been issued and should '
              'appear on your payment method within 3–5 business days.'),
     'n': 25},

    {'id': 'order_doordash_delivered', 'category': 'order_confirmation', 'brand': 'doordash',
     'body': ('DoorDash: your order from {food_place} has been delivered. '
              'How was it? Rate your Dasher and food in the app.'), 'n': 25},

    {'id': 'order_ubereats_arriving',  'category': 'order_confirmation', 'brand': 'uber_eats',
     'body': ('Uber Eats: your order from {food_place} is arriving in '
              '{mins} minutes. Your Dasher: {name}. Track in the app.'), 'n': 25},

    # ── PAYMENT EXPANSION ────────────────────────────────────────────────
    {'id': 'pay_stripe_payout',        'category': 'payment_activity', 'brand': 'stripe',
     'amount_kind': 'stripe_payout',
     'body': ('Your Stripe payout of {currency}{amount} is on the way. '
              'Estimated arrival: {date} in your bank account ending '
              '{last4}. View at dashboard.stripe.com/payouts.'), 'n': 25},

    {'id': 'pay_wise_sent',            'category': 'payment_activity', 'brand': 'wise',
     'amount_kind': 'wise_transfer',
     'body': ('Wise: you sent {currency}{amount} to {full_name}. '
              'Reference: {reference}. Expected arrival: {date}. '
              'Track at wise.com.'), 'n': 25},

    {'id': 'pay_paypal_refund',        'category': 'payment_activity', 'brand': 'paypal',
     'amount_kind': 'paypal_transfer',
     'body': ('PayPal: a refund of {currency}{amount} from {merchant} '
              'was received. Available in your PayPal balance. '
              'Transaction ID: {txn_id}.'), 'n': 25},

    {'id': 'pay_venmo_request',        'category': 'payment_activity', 'brand': 'venmo',
     'amount_kind': 'venmo_transfer', 'currency_kind': 'usd_only',
     'body': ('Venmo: {full_name} requested {currency}{amount} from you. '
              'Note: "{venmo_note}". Pay or decline in the Venmo app.'), 'n': 25},

    # ── OTP EXPANSION ────────────────────────────────────────────────────
    {'id': 'otp_apple',                'category': 'otp_notification', 'brand': 'apple',
     'body': ('Your Apple ID verification code: {code_6}. Use this to '
              'sign in to your Apple ID. {dont_share_code}.'), 'n': 25},

    {'id': 'otp_dropbox',              'category': 'otp_notification', 'brand': 'dropbox',
     'body': ('Dropbox: your sign-in code is {code_6}. Enter this in the '
              'Dropbox app to complete sign-in. This code expires in '
              '10 minutes.'), 'n': 25},

    {'id': 'otp_github',               'category': 'otp_notification', 'brand': 'github',
     'body': ('GitHub: your authentication code is {code_6}. Use this '
              'to complete sign-in. If you didn\'t request it, someone '
              'may have your password — reset it immediately.'), 'n': 25},

    {'id': 'otp_slack',                'category': 'otp_notification', 'brand': 'slack',
     'body': ('Slack: your confirmation code is {code_6}. Enter this in '
              'the Slack app or website to complete your sign-in.'), 'n': 25},

    {'id': 'otp_notion',               'category': 'otp_notification', 'brand': 'notion',
     'body': ('Notion: your login code is {code_6}. Use this to sign in '
              'from your browser. Expires in 15 minutes.'), 'n': 25},

    {'id': 'otp_linkedin',             'category': 'otp_notification', 'brand': 'linkedin',
     'body': ('LinkedIn: your verification PIN is {code_6}. Enter this on '
              'the LinkedIn site to verify. {dont_share_code}.'), 'n': 25},
]


# Combined pool
ALL_TEMPLATES = E8P2_TEMPLATES + E8P6_NEW_TEMPLATES


# ══════════════════════════════════════════════════════════════════════════
# Bump variations per existing E8-P2 template so their contribution scales
# with the new templates. E8-P2 targets 25-40 per template; scale to 70-90.
# ══════════════════════════════════════════════════════════════════════════

for t in ALL_TEMPLATES:
    if t.get('id', '').startswith(('ship_amazon_', 'order_amazon_', 'sec_google_',
                                     'sec_microsoft_', 'sec_apple_', 'receipt_apple_',
                                     'receipt_netflix_', 'receipt_spotify_')):
        # High-priority templates for the failure modes → bump higher
        t['n'] = max(t.get('n', 30), 150)
    elif t in E8P2_TEMPLATES:
        t['n'] = max(t.get('n', 25), 100)
    else:
        # NEW templates — bump so total reaches ~15k
        t['n'] = max(t.get('n', 30), 120)


# ══════════════════════════════════════════════════════════════════════════
# Extend _fill_slots's value dict with a few new placeholder tokens the
# new templates reference. Monkey-patch by wrapping _fill_slots.
# ══════════════════════════════════════════════════════════════════════════

import string
from scripts.data_prep import gen_e8p2_synthetic_legit as _p2


_original_fill_slots = _p2._fill_slots


def _extended_fill_slots(body: str, amount_kind='generic',
                          balance_kind='checking', currency_kind='multi') -> str:
    """Wraps E8-P2's _fill_slots to inject additional placeholders used
    by the new E8-P6 templates."""
    # First, resolve any NEW-template placeholders using string.Formatter
    # with a defaultdict-like fallback. Simpler: pre-substitute new keys.
    from scripts.data_prep.gen_e8p2_synthetic_legit import (
        rand_name, rand_full_name,
    )
    extra = {
        'article_title':  RNG.choice([
            'The AI Playbook Nobody Talks About',
            'Building for the Long Term in a Short-Term Industry',
            '5 Lessons from Scaling a Design Team to 40 People',
            'Why Your Best Ideas Come From Constraints',
            'The Case for Slow Software',
            'How We Ship Faster With Fewer Meetings',
            'Rethinking Onboarding in the Remote Era',
            'Small Bets, Big Learnings',
            'What I Wish I Knew Before Launching',
            'Notes From a Year of Building in Public',
        ]),
        'viewers':       str(RNG.randint(1200, 45000)),
        'readers':       f'{RNG.randint(1000, 25000):,}',
        'count':         str(RNG.randint(15, 60)),
        'count2':        str(RNG.randint(3, 12)),
        'word_count':    str(RNG.randint(800, 1400)),
        'topic':         RNG.choice(['OpenAI', 'Anthropic', 'the Fed',
                                     'the AI Act', 'the housing market',
                                     'the credit market', 'Q3 earnings',
                                     'quantum computing', 'DePIN',
                                     'the crypto rally']),
        'month':         RNG.choice(['January', 'February', 'March', 'April',
                                     'May', 'June', 'July', 'August',
                                     'September', 'October', 'November',
                                     'December']),
        'gb':            str(RNG.choice([500, 1024, 2048, 5120])),
        'city2':         RNG.choice(['New York', 'San Francisco', 'London',
                                     'Berlin', 'Amsterdam', 'Barcelona',
                                     'Tokyo', 'Singapore', 'Dublin', 'Lisbon']),
        'date2':         _p2.rand_date(),
    }
    # Do a pre-pass replacement for NEW keys, then hand off to P2 for the rest
    for k, v in extra.items():
        body = body.replace('{' + k + '}', v)
    return _original_fill_slots(body, amount_kind, balance_kind, currency_kind)


# Monkey-patch — render_template imported from p2 uses p2's _fill_slots
_p2._fill_slots = _extended_fill_slots


# ══════════════════════════════════════════════════════════════════════════
# Main generation
# ══════════════════════════════════════════════════════════════════════════

def main():
    print('=== E8-P6 large-scale synthetic legit dataset ===')
    print(f'  templates: {len(ALL_TEMPLATES)}  '
          f'(E8-P2: {len(E8P2_TEMPLATES)}, new: {len(E8P6_NEW_TEMPLATES)})')
    total_target = sum(t['n'] for t in ALL_TEMPLATES)
    print(f'  target variations: {total_target:,}')
    n_brands = len({t["brand"] for t in ALL_TEMPLATES})
    n_cats = len({t["category"] for t in ALL_TEMPLATES})
    print(f'  brand diversity: {n_brands}')
    print(f'  categories: {n_cats}')
    print()

    kept: list = []
    rejections: Counter = Counter()
    seen_texts: set = set()
    for t in ALL_TEMPLATES:
        target = t['n']
        attempts = 0
        wins = 0
        while wins < target and attempts < target * 4:
            attempts += 1
            try:
                text = render_template(t)
            except KeyError as e:
                rejections[f'template_missing_slot:{e}'] += 1
                break
            # Hash the ENTIRE text (looser dedup than E8-P2's first-120-chars).
            # Retains variations that differ only in mid/late tokens.
            key = text
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
                'label':       0,
                'category':    t['category'],
                'brand':       t['brand'],
                'template_id': t['id'],
                'has_url':     bool(t.get('url')),
            })
            wins += 1

    df = pd.DataFrame(kept)
    print(f'  kept: {len(df):,}')
    print(f'  by category:')
    for cat, n in df.category.value_counts().items():
        print(f'    {cat:26s} {n:>5}')
    print(f'  by brand (top 20):')
    for brand, n in df.brand.value_counts().head(20).items():
        print(f'    {brand:26s} {n:>5}')
    print(f'  URLs present: {int(df.has_url.sum())} ({df.has_url.mean()*100:.0f}%)')
    print(f'  rejections:')
    for r, n in rejections.most_common():
        print(f'    {r:26s} {n:>5}')

    out = os.path.join(OUT_DIR, 'dataset.parquet')
    df.to_parquet(out, index=False)
    print(f'\nWrote {out}   ({len(df):,} rows)')

    # Stratified samples for review
    parts = []
    for tid, g in df.groupby('template_id'):
        parts.append(g.sample(min(len(g), 3), random_state=42))
    sample = pd.concat(parts, ignore_index=True)
    lines = []
    for _, r in sample.iterrows():
        lines.append(f'[{r["category"]}]  [{r["brand"]}]  [{r["template_id"]}]')
        lines.append(r['text'])
        lines.append('')
    with open(os.path.join(OUT_DIR, 'samples.txt'), 'w') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {OUT_DIR}/samples.txt   ({len(sample)} preview messages)')

    with open(os.path.join(OUT_DIR, 'rejection_report.json'), 'w') as f:
        json.dump(dict(rejections), f, indent=2)
    stats = {
        'n_kept':             int(len(df)),
        'n_templates':        len(ALL_TEMPLATES),
        'n_new_templates':    len(E8P6_NEW_TEMPLATES),
        'n_brands':           n_brands,
        'n_categories':       n_cats,
        'urls_present_ratio': round(float(df.has_url.mean()), 4),
        'per_category':       {k: int(v) for k, v in df.category.value_counts().items()},
        'per_brand':          {k: int(v) for k, v in df.brand.value_counts().items()},
        'per_template':       {k: int(v) for k, v in df.template_id.value_counts().items()},
        'rejections':         dict(rejections),
    }
    with open(os.path.join(OUT_DIR, 'generation_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    print(f'Wrote {OUT_DIR}/generation_stats.json')


if __name__ == '__main__':
    main()
