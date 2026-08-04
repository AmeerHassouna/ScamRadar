"""Category A — Critical rules.

Each rule may FORCE the final verdict to SCAM because the pattern it
detects is unambiguously malicious behaviour. All rules here rely on
objective security signals (URL reputation, structured request patterns,
brand/domain mismatches) — never on generic keywords like "verify"
or "click here" alone.
"""
from __future__ import annotations

import re

from src.rule_engine.base import (
    Category,
    Rule,
    RuleAction,
    RuleContext,
    RuleResult,
    Severity,
)
from src.rule_engine.patterns import (
    CRED_REQUEST_RE,
    OTP_THEFT_RE,
    OTP_THEFT_ALT_RE,
    OTP_KEYWORD_RE,
    OTP_ASK_RE,
    GIFT_CARD_RE,
    GIFT_CARD_PAYMENT_CTX_RE,
    CRYPTO_SECRET_RE,
    CRYPTO_ACTION_RE,
    CRYPTO_WARNING_RE,
    REMOTE_TOOL_RE,
    REMOTE_ACTION_RE,
    has_credential_request,
    has_otp_theft,
    has_gift_card_payment,
    has_sensitive_account_action,
)


# ══════════════════════════════════════════════════════════════════════════
# A1 — Malicious URL (Google Safe Browsing / VirusTotal / URLhaus / PhishTank)
# ══════════════════════════════════════════════════════════════════════════

class MaliciousUrlRule(Rule):
    id = 'A1_MALICIOUS_URL'
    name = 'Malicious URL'
    description = ('One or more URLs are flagged by an external reputation '
                   'source (Google Safe Browsing, VirusTotal, URLhaus, or '
                   'PhishTank).')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    VT_MALICIOUS_THRESHOLD = 2

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if ctx.gsb_flagged:
            return self._make_result(
                explanation=(f'Google Safe Browsing flagged a URL as '
                             f'{ctx.gsb_threat_type or "malicious"}.'),
                evidence={'source': 'gsb',
                          'threat_type': ctx.gsb_threat_type,
                          'urls': ctx.urls[:3]},
            )
        if ctx.vt_malicious >= self.VT_MALICIOUS_THRESHOLD:
            return self._make_result(
                explanation=(f'VirusTotal flagged a URL as malicious '
                             f'({ctx.vt_malicious} engines).'),
                evidence={'source': 'virustotal',
                          'malicious_engines': ctx.vt_malicious,
                          'suspicious_engines': ctx.vt_suspicious,
                          'urls': ctx.urls[:3]},
            )
        if ctx.extras.get('urlhaus_flagged'):
            return self._make_result(
                explanation='URLhaus lists a URL as a known malicious host.',
                evidence={'source': 'urlhaus', 'urls': ctx.urls[:3]},
            )
        if ctx.extras.get('phishtank_flagged'):
            return self._make_result(
                explanation='PhishTank lists a URL as a confirmed phishing target.',
                evidence={'source': 'phishtank', 'urls': ctx.urls[:3]},
            )
        return None


# ══════════════════════════════════════════════════════════════════════════
# A2 — Credential request
# ══════════════════════════════════════════════════════════════════════════

class CredentialRequestRule(Rule):
    id = 'A2_CREDENTIAL_REQUEST'
    name = 'Credential request'
    description = ('The message asks the user to disclose a named secret '
                   '(password, PIN, CVV, recovery code, SSN, private key, '
                   'seed phrase, etc.). No legitimate service asks for '
                   'these over unstructured text.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        m = CRED_REQUEST_RE.search(ctx.text)
        if not m:
            return None
        return self._make_result(
            explanation=(f'Requests a named credential: "{m.group(0)[:60]}"'),
            evidence={'match': m.group(0)},
        )


# ══════════════════════════════════════════════════════════════════════════
# A3 — OTP theft
# ══════════════════════════════════════════════════════════════════════════

class OtpTheftRule(Rule):
    id = 'A3_OTP_THEFT'
    name = 'OTP theft request'
    description = ('The message asks the user to send / reply with / '
                   'forward a verification code. Legitimate one-time '
                   'codes are never requested back — only entered on the '
                   'sender\'s own site.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        # Use the has_otp_theft() helper — requires BOTH an OTP-context
        # keyword AND a request-to-send verb pattern. Prevents FPs on
        # legit OTP notifications ("do not share this code") and on
        # non-OTP messages that mention codes ("share the code review").
        if not has_otp_theft(ctx.text):
            return None
        kw = OTP_KEYWORD_RE.search(ctx.text)
        ask = OTP_ASK_RE.search(ctx.text)
        return self._make_result(
            explanation=('Requests the user to hand over a verification / '
                         'one-time code.'),
            evidence={
                'keyword_match': kw.group(0) if kw else None,
                'request_match': ask.group(0) if ask else None,
            },
        )


# ══════════════════════════════════════════════════════════════════════════
# A4 — Gift card payment
# ══════════════════════════════════════════════════════════════════════════

class GiftCardPaymentRule(Rule):
    id = 'A4_GIFT_CARD_PAYMENT'
    name = 'Gift card payment demanded'
    description = ('The message requests payment via gift cards (Apple, '
                   'Google Play, Amazon, Steam, iTunes, etc.). This is '
                   'the classic irreversible-payment scam channel.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        m_card = GIFT_CARD_RE.search(ctx.text)
        if not m_card:
            return None
        if not GIFT_CARD_PAYMENT_CTX_RE.search(ctx.text):
            return None
        return self._make_result(
            explanation=f'Demands payment via {m_card.group(0).strip()}.',
            evidence={'match': m_card.group(0)},
        )


# ══════════════════════════════════════════════════════════════════════════
# A5 — Crypto wallet recovery phrase
# ══════════════════════════════════════════════════════════════════════════

class CryptoSeedPhraseRule(Rule):
    id = 'A5_CRYPTO_SEED_PHRASE'
    name = 'Crypto seed phrase request'
    description = ('The message asks the user to enter / share / restore a '
                   'crypto wallet\'s seed phrase, recovery phrase, or '
                   'private key. No legitimate wallet or exchange asks '
                   'for these.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        m_secret = CRYPTO_SECRET_RE.search(ctx.text)
        if not m_secret:
            return None
        if not CRYPTO_ACTION_RE.search(ctx.text):
            return None
        if CRYPTO_WARNING_RE.search(ctx.text):
            return None
        return self._make_result(
            explanation=f'Requests interaction with "{m_secret.group(0)}".',
            evidence={'match': m_secret.group(0)},
        )


# ══════════════════════════════════════════════════════════════════════════
# A6 — Remote access software
# ══════════════════════════════════════════════════════════════════════════

class RemoteAccessRule(Rule):
    id = 'A6_REMOTE_ACCESS_SOFTWARE'
    name = 'Remote-access software request'
    description = ('The message references a remote-access tool '
                   '(TeamViewer, AnyDesk, UltraViewer, etc.) combined with '
                   'an install / connect action. Signature pattern of '
                   'tech-support scams.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        m_tool = REMOTE_TOOL_RE.search(ctx.text)
        if not m_tool:
            return None
        if not REMOTE_ACTION_RE.search(ctx.text):
            return None
        return self._make_result(
            explanation=(f'Requests remote-access tool "{m_tool.group(0)}" '
                         f'be installed / connected.'),
            evidence={'match': m_tool.group(0)},
        )


# A7 (Display URL mismatch) removed 2026-08-02 — fired 443× on the 25k
# external benchmark, most on legit ham_email that references domain names
# in prose alongside legitimate URLs. Precision hit was too large.


# ══════════════════════════════════════════════════════════════════════════
# Brand-impersonation core detector (shared by A8-compound and B8)
# ══════════════════════════════════════════════════════════════════════════
BRAND_TO_DOMAIN: dict = {
    'amazon':      {'amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr',
                    'amazon.co.jp', 'amazon.it', 'amazon.es', 'amazon.ca'},
    'paypal':      {'paypal.com'},
    'apple':       {'apple.com', 'icloud.com', 'me.com'},
    'microsoft':   {'microsoft.com', 'outlook.com', 'live.com', 'hotmail.com',
                    'onedrive.com', 'office.com', 'office365.com'},
    'google':      {'google.com', 'gmail.com', 'googlemail.com', 'youtube.com'},
    'netflix':     {'netflix.com'},
    'facebook':    {'facebook.com', 'meta.com', 'fb.com'},
    'instagram':   {'instagram.com'},
    'linkedin':    {'linkedin.com'},
    'twitter':     {'twitter.com', 'x.com'},
    'fedex':       {'fedex.com'},
    'ups':         {'ups.com'},
    'dhl':         {'dhl.com'},
    'usps':        {'usps.com'},
    'chase':       {'chase.com'},
    'wells fargo': {'wellsfargo.com'},
    'bank of america': {'bankofamerica.com'},
    'hsbc':        {'hsbc.com', 'hsbc.co.uk'},
    'barclays':    {'barclays.com', 'barclays.co.uk'},
    'stripe':      {'stripe.com'},
    'venmo':       {'venmo.com'},
    'zelle':       {'zellepay.com'},
    'coinbase':    {'coinbase.com'},
    'binance':     {'binance.com', 'binance.us'},
    'irs':         {'irs.gov'},
}


def _matches_any(host: str, domains) -> bool:
    return any(host == d or host.endswith('.' + d) for d in domains)


def detect_brand_impersonation(ctx: RuleContext) -> dict | None:
    """Shared core: returns evidence dict if any URL contradicts a
    brand named in the text, else None.

    Fires when:
        (1) The text names a known brand, AND
        (2) No URL points to that brand's official domain, AND
        (3) At least one URL is *not* a trusted domain (i.e. actually foreign
            infrastructure — not just a different trusted service).
    """
    if not ctx.hostnames:
        return None
    brand_hit = None
    for brand in BRAND_TO_DOMAIN:
        if re.search(rf'\b{re.escape(brand)}\b', ctx.text_lower):
            brand_hit = brand
            break
    if not brand_hit:
        return None
    official = BRAND_TO_DOMAIN[brand_hit]
    # (2) any URL matches the official brand domain → not impersonation
    if any(_matches_any(h, official) for h in ctx.hostnames):
        return None
    # (3) every URL is on a trusted domain → too weak to flag (may be a
    # newsletter linking Amazon via a YouTube video, for example)
    if all(_matches_any(h, ctx.trusted_domains) for h in ctx.hostnames):
        return None
    return {
        'brand': brand_hit,
        'official_domains': sorted(official),
        'actual_hosts': list(ctx.hostnames[:5]),
    }


# ══════════════════════════════════════════════════════════════════════════
# A8 — Brand impersonation + sensitive action (COMPOUND CRITICAL RULE)
# ══════════════════════════════════════════════════════════════════════════
# Fires only when brand impersonation is combined with one of:
#   • credential request  (matches A2 pattern)
#   • OTP theft           (matches A3 pattern)
#   • gift-card payment   (matches A4 pattern)
#   • sensitive account action (login / reset password / verify identity /
#     unlock account / reactivate / complete payment / action required)
#
# Brand impersonation alone is deferred to B8 (INCREASE only) — matches
# messages that mention Amazon but link to youtube.com aren't
# necessarily phishing and shouldn't be force-scam'd on that signal alone.
# ══════════════════════════════════════════════════════════════════════════

class BrandImpersonationWithActionRule(Rule):
    id = 'A8_BRAND_IMPERSONATION_WITH_ACTION'
    name = 'Brand impersonation + sensitive action'
    description = ('The message names a well-known brand, links to a '
                   'foreign / non-brand domain, AND asks the user to '
                   'perform a sensitive action (login, credential entry, '
                   'OTP hand-over, payment, or account verification).')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        det = detect_brand_impersonation(ctx)
        if det is None:
            return None
        # Require a concurrent sensitive-action / credential-theft pattern
        action_kind: str | None = None
        if has_credential_request(ctx.text):
            action_kind = 'credential_request'
        elif has_otp_theft(ctx.text):
            action_kind = 'otp_theft'
        elif has_gift_card_payment(ctx.text):
            action_kind = 'gift_card_payment'
        elif has_sensitive_account_action(ctx.text):
            action_kind = 'sensitive_account_action'
        if action_kind is None:
            return None
        return self._make_result(
            explanation=(f'Message names "{det["brand"]}" and links to '
                         f'{", ".join(det["actual_hosts"][:2])} while '
                         f'requesting a sensitive action ({action_kind}).'),
            evidence={**det, 'action_kind': action_kind},
        )


# ══════════════════════════════════════════════════════════════════════════
# A9 / A10 / A11 — Type-specific FORCE_SCAM floors (ported from v1.x)
# ══════════════════════════════════════════════════════════════════════════
# v1.x had ~100% recall on romance / investment / threat scams because it
# force-lifted probability to 0.72 whenever classify_scam_type() identified
# a matching type AND a supporting signal was present. FP-safe because
# classify_scam_type() only returns these specific labels when its regex
# patterns match — legitimate transactional messages (Netflix receipts,
# Amazon orders, etc.) always classify as 'general_spam' and never trigger.

class InvestmentScamTypeFloorRule(Rule):
    id = 'A9_INVESTMENT_TYPE_FLOOR'
    name = 'Investment scam type + reward tone'
    description = ('classify_scam_type() identified investment/crypto '
                   'scam patterns AND the message has reward-tone or '
                   'scam-phrase signals. Ported from v1.x.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if ctx.scam_type != 'investment_scam':
            return None
        if ctx.tone_reward < 1 and ctx.scam_phrase_score < 1:
            return None
        return self._make_result(
            explanation=('Message pattern classified as investment scam '
                         'with supporting reward-tone / scam-phrase signal.'),
            evidence={'scam_type': ctx.scam_type,
                      'tone_reward': ctx.tone_reward,
                      'phrase_score': ctx.scam_phrase_score},
        )


class RomanceScamTypeFloorRule(Rule):
    id = 'A10_ROMANCE_TYPE_FLOOR'
    name = 'Romance scam type + phrase signal'
    description = ('classify_scam_type() identified romance-scam patterns '
                   'AND phrase-score >= 1. Ported from v1.x.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if ctx.scam_type != 'romance_scam':
            return None
        if ctx.scam_phrase_score < 1:
            return None
        return self._make_result(
            explanation=('Message pattern classified as romance scam with '
                         'supporting scam-phrase signal.'),
            evidence={'scam_type': ctx.scam_type,
                      'phrase_score': ctx.scam_phrase_score},
        )


class ThreatScamTypeFloorRule(Rule):
    id = 'A11_THREAT_TYPE_FLOOR'
    name = 'Threat/authority scam type + phrase signal'
    description = ('classify_scam_type() identified threat/authority scam '
                   'patterns (police, court, IRS, arrest) AND phrase-'
                   'score >= 1 OR tone_threat >= 1. Ported from v1.x.')
    category = Category.CRITICAL
    severity = Severity.CRITICAL
    default_action = RuleAction.FORCE_SCAM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if ctx.scam_type != 'threat_scam':
            return None
        if ctx.scam_phrase_score < 1 and ctx.tone_threat < 1:
            return None
        return self._make_result(
            explanation=('Message pattern classified as threat/authority '
                         'scam with supporting phrase or threat-tone signal.'),
            evidence={'scam_type': ctx.scam_type,
                      'phrase_score': ctx.scam_phrase_score,
                      'tone_threat': ctx.tone_threat},
        )


# ── Public rule list (order-in-list irrelevant; engine sorts by priority) ─
# A8 (BrandImpersonationWithActionRule) removed 2026-08-03 — misfired on
# 43 legit ham_email items in the external benchmark (43/237 = 18% of
# all FPs). Newsletter/marketing emails routinely combine brand-mention +
# "Register today / Manage newsletters / View online" action verbs +
# tracking URLs on non-brand domains, all three triggering A8's force-scam.
CRITICAL_RULES = [
    MaliciousUrlRule(),
    CredentialRequestRule(),
    OtpTheftRule(),
    GiftCardPaymentRule(),
    CryptoSeedPhraseRule(),
    RemoteAccessRule(),
    InvestmentScamTypeFloorRule(),
    RomanceScamTypeFloorRule(),
    ThreatScamTypeFloorRule(),
]
