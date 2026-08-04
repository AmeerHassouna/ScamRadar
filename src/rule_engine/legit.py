"""Category C — Legitimate confidence rules.

These rules DECREASE scam probability when objective legit signals are
present (brand mentioned + matching official domain, all URLs on trusted
domains, structural OTP-notification pattern). They can lower the
probability below the verdict threshold — but they NEVER hard-force
LEGIT. The engine still uses a floor to guarantee probability > 0.
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
from src.rule_engine.critical import BRAND_TO_DOMAIN
from src.rule_engine.patterns import has_any_critical_action_pattern


# NOTE: Adjustment magnitudes are configured in `src/rule_engine/weights.py`.
# The `default_adjustment` on each class is the shipped fallback used only
# if the weights table has no entry for that rule.
DECREASE_STRONG   = 0.30
DECREASE_MODERATE = 0.15
DECREASE_LOW      = 0.08


# ══════════════════════════════════════════════════════════════════════════
# C1 — Brand mentioned + official matching domain
# ══════════════════════════════════════════════════════════════════════════

class BrandOfficialDomainRule(Rule):
    id = 'C1_BRAND_OFFICIAL_DOMAIN'
    name = 'Brand + official matching domain'
    description = ('The message names a well-known brand and every URL '
                   'points to that brand\'s official domain — provided '
                   'no critical action pattern (credential request, OTP '
                   'theft, gift-card payment, remote-access request, '
                   'crypto seed request) is present in the text.')
    category = Category.LEGIT
    severity = Severity.INFO
    default_action = RuleAction.DECREASE
    default_adjustment = DECREASE_STRONG

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        # SAFETY GUARD (per spec item 2): even if the URLs are official,
        # a concurrent critical-action pattern means we MUST NOT reduce
        # the probability. Critical rules always dominate legit rules.
        if has_any_critical_action_pattern(ctx.text):
            return None

        if not ctx.hostnames:
            return None
        low = ctx.text_lower
        brand_hit = None
        for brand in BRAND_TO_DOMAIN:
            if re.search(rf'\b{re.escape(brand)}\b', low):
                brand_hit = brand
                break
        if not brand_hit:
            return None
        official = BRAND_TO_DOMAIN[brand_hit]

        def matches(host: str) -> bool:
            return any(host == d or host.endswith('.' + d) for d in official)

        if not all(matches(h) for h in ctx.hostnames):
            return None
        return self._make_result(
            explanation=(f'Message names "{brand_hit}" and every URL points '
                         f'to its official domain.'),
            evidence={'brand': brand_hit,
                      'official_domains': sorted(official),
                      'hosts': ctx.hostnames},
        )


# ══════════════════════════════════════════════════════════════════════════
# C2 — Official domain consistency
# ══════════════════════════════════════════════════════════════════════════
# Every URL resolves to a domain (or subdomain) in TRUSTED_DOMAINS AND
# no critical/strong URL-safety rule fired. Uses the same trusted set as
# the E7-P2 safety net.

class OfficialDomainConsistencyRule(Rule):
    id = 'C2_OFFICIAL_DOMAIN_CONSISTENCY'
    name = 'Official domain consistency'
    description = ('Every URL in the message resolves to a trusted domain, '
                   'and no external URL reputation source (GSB / VT) flagged '
                   'any of them.')
    category = Category.LEGIT
    severity = Severity.INFO
    default_action = RuleAction.DECREASE
    default_adjustment = DECREASE_STRONG

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if not ctx.hostnames:
            return None
        if ctx.gsb_flagged:
            return None
        if ctx.vt_malicious >= 2:
            return None

        def is_trusted(host: str) -> bool:
            return any(host == d or host.endswith('.' + d)
                       for d in ctx.trusted_domains)

        if not all(is_trusted(h) for h in ctx.hostnames):
            return None
        return self._make_result(
            explanation=('All URLs point to trusted domains and no external '
                         'reputation source flagged them.'),
            evidence={'hosts': ctx.hostnames},
        )


# ══════════════════════════════════════════════════════════════════════════
# C3 — OTP notification (pure notify-only pattern)
# ══════════════════════════════════════════════════════════════════════════
# Structural pattern of a legitimate OTP / MFA verification message.
# All of the following must hold:
#   - contains an OTP-related keyword (code, verification, OTP, passcode)
#   - contains a 3-8 digit code somewhere in the text
#   - contains NO URLs
#   - contains NO phone-length digit run (>8 consecutive digits)
#   - contains NO request-for-code phrase (please provide/forward/reply
#     with/send us/confirm your)
# A message with no URL, no phone number, and no send-back request has no
# attack surface — scammer has nowhere to receive the victim's data.

_OTP_KEYWORD_RE = re.compile(
    r'\b(?:verification\s*code|one[- ]time\s*(?:code|passcode|password)|'
    r'passcode|otp|verify\s*code|security\s*code|access\s*code)\b'
    r'|(?:^|\s)code\s+is\s+\d',
    re.IGNORECASE,
)
_OTP_CODE_RE       = re.compile(r'\b\d{3,8}\b')
_URL_ANY_RE        = re.compile(r'https?://|www\.', re.IGNORECASE)
_PHONE_LONG_RE     = re.compile(r'\+?\d[\d\s\-().]{7,}\d')
_SEND_REQUEST_RE   = re.compile(
    r'\b(?:please\s+(?:provide|confirm|reply|forward|send|share|enter\s+at|'
    r'call|click)'
    r'|reply\s+(?:with|to\s+us|now)'
    r'|forward\s+(?:me|us|to)'
    r'|send\s+(?:me|us|it\s+to)'
    r'|share\s+(?:this|it)\s+with\s+(?:us|our|support))\b',
    re.IGNORECASE,
)


def _is_pure_otp_notification(text: str) -> bool:
    # Length cap bumped 350 → 700 chars (2026-08-04) so real corporate OTP
    # emails with a full footer ("© YEAR Corp. About | Privacy | Legal ...
    # EA logo / footer icon") still qualify. The real safety guards are
    # the no-URL / no-phone / no-request-for-code checks below — those
    # are what actually prevent OTP-theft phishing from slipping through.
    if not text or len(text) > 700:
        return False
    if not _OTP_KEYWORD_RE.search(text):
        return False
    if not _OTP_CODE_RE.search(text):
        return False
    if _URL_ANY_RE.search(text):
        return False
    if _SEND_REQUEST_RE.search(text):
        return False
    # Phone-number check — 9+ consecutive digits ≠ an OTP code
    max_run = 0
    for m in _PHONE_LONG_RE.finditer(text):
        digits_only = re.sub(r'\D', '', m.group(0))
        if len(digits_only) > max_run:
            max_run = len(digits_only)
    if max_run > 8:
        return False
    return True


class OtpNotificationRule(Rule):
    id = 'C3_OTP_NOTIFICATION'
    name = 'OTP notification (notify-only)'
    description = ('The message contains a verification code and matches '
                   'the notify-only structural pattern: no URL, no phone '
                   'number, and no request to send the code back.')
    category = Category.LEGIT
    severity = Severity.INFO
    default_action = RuleAction.DECREASE
    default_adjustment = DECREASE_STRONG

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if not _is_pure_otp_notification(ctx.text):
            return None
        return self._make_result(
            explanation=('Structural pure-OTP pattern: verification code '
                         'present with no URL, no phone number, and no '
                         'send-back request.'),
            evidence={},
        )


# C4 (TrustedUrlHardCapRule) removed 2026-08-04 — tested and reverted:
# fired 85× on external benchmark, saved only 4 FPs but hard-capped 36 real
# scams to LEGIT (footer URLs to trusted domains fooled it). Net −0.38 pp F1.
# HARD_CAP infrastructure in base.py is kept dormant for any future rule.


LEGIT_RULES = [
    BrandOfficialDomainRule(),
    OfficialDomainConsistencyRule(),
    OtpNotificationRule(),
]
