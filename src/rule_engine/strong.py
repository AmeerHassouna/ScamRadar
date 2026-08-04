"""Category B — Strong scam signals.

These rules INCREASE scam probability but never force the verdict. They
raise confidence when objective structural signals correlate with scam
patterns (URL shorteners, homoglyphs, punycode, QR-code payments, etc.).
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
from src.rule_engine.critical import detect_brand_impersonation


# NOTE: Adjustment magnitudes are configured in `src/rule_engine/weights.py`.
# The `default_adjustment` on each class is the shipped fallback used only
# if the weights table has no entry for that rule.
INCREASE_HIGH   = 0.25
INCREASE_MEDIUM = 0.15
INCREASE_LOW    = 0.08


# ══════════════════════════════════════════════════════════════════════════
# B1 — URL shortener + login/payment request
# ══════════════════════════════════════════════════════════════════════════
URL_SHORTENERS = {
    'bit.ly', 'tinyurl.com', 'ow.ly', 't.co', 'goo.gl', 'is.gd', 'buff.ly',
    'tiny.cc', 'cutt.ly', 'rebrand.ly', 'shorturl.at', 'rb.gy', 'lnkd.in',
    's.id', 'v.gd', 'shorte.st', 'adf.ly', 'bl.ink', 'clck.ru', 'trib.al',
    'x.co', 'urlz.fr', 'soo.gd', 'chilp.it', 'linktr.ee',
}
_ACTION_REQUEST_RE = re.compile(
    r'\b(?:login|log\s+in|sign\s+in|verify|confirm|update|reactivate|'
    r'pay(?:ment)?|complete\s+payment|make\s+a\s+payment|invoice|'
    r'claim|redeem|activate|unlock)\b',
    re.IGNORECASE,
)


class UrlShortenerActionRule(Rule):
    id = 'B1_URL_SHORTENER_ACTION'
    name = 'URL shortener + action request'
    description = ('A URL from a link-shortener service is combined with '
                   'a login / payment / claim request. Shorteners hide '
                   'the destination — legitimate senders rarely need to.')
    category = Category.STRONG
    severity = Severity.HIGH
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_HIGH

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        hits = [h for h in ctx.hostnames if h in URL_SHORTENERS]
        if not hits:
            return None
        if not _ACTION_REQUEST_RE.search(ctx.text):
            return None
        return self._make_result(
            explanation=(f'Shortened URL ({hits[0]}) combined with a '
                         f'login/payment request.'),
            evidence={'shorteners': hits, 'urls': ctx.urls[:3]},
        )


# ══════════════════════════════════════════════════════════════════════════
# B2 — Homoglyph domains
# ══════════════════════════════════════════════════════════════════════════
# Domain hostname contains characters from mixed scripts, or Cyrillic /
# Greek characters that visually mimic Latin letters.
_LATIN_RE     = re.compile(r'[a-zA-Z]')
_NON_LATIN_RE = re.compile(r'[^\x00-\x7f]')


def _has_homoglyph(hostname: str) -> bool:
    if not hostname:
        return False
    has_latin     = bool(_LATIN_RE.search(hostname))
    has_non_latin = bool(_NON_LATIN_RE.search(hostname))
    return has_latin and has_non_latin


class HomoglyphDomainRule(Rule):
    id = 'B2_HOMOGLYPH_DOMAIN'
    name = 'Homoglyph domain'
    description = ('A URL hostname mixes Latin with non-Latin (Cyrillic, '
                   'Greek) look-alike characters. Signature of domain-'
                   'spoofing attacks.')
    category = Category.STRONG
    severity = Severity.HIGH
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_HIGH

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        bad = [h for h in ctx.hostnames if _has_homoglyph(h)]
        if not bad:
            return None
        return self._make_result(
            explanation=f'Hostname "{bad[0]}" mixes Latin with non-Latin script.',
            evidence={'hosts': bad},
        )


# ══════════════════════════════════════════════════════════════════════════
# B3 — Punycode domains
# ══════════════════════════════════════════════════════════════════════════

class PunycodeDomainRule(Rule):
    id = 'B3_PUNYCODE_DOMAIN'
    name = 'Punycode domain'
    description = ('A URL hostname uses punycode (xn--...) — commonly used '
                   'to encode internationalised domain names, but a red '
                   'flag when combined with brand names.')
    category = Category.STRONG
    severity = Severity.MEDIUM
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_MEDIUM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        bad = [h for h in ctx.hostnames if h.startswith('xn--')
               or '.xn--' in h]
        if not bad:
            return None
        return self._make_result(
            explanation=f'Hostname "{bad[0]}" uses punycode encoding.',
            evidence={'hosts': bad},
        )


# ══════════════════════════════════════════════════════════════════════════
# B4 — QR code requesting payment / login
# ══════════════════════════════════════════════════════════════════════════
_QR_MENTION_RE = re.compile(r'\bqr\s*code\b', re.IGNORECASE)
_QR_ACTION_RE  = re.compile(
    r'\b(?:scan\s+(?:this|the|below|to)|to\s+pay|for\s+payment|'
    r'to\s+login|to\s+sign\s+in|to\s+verify|to\s+claim)\b',
    re.IGNORECASE,
)


class QrPaymentLoginRule(Rule):
    id = 'B4_QR_PAYMENT_LOGIN'
    name = 'QR code payment / login'
    description = ('The message references a QR code together with a scan-'
                   'to-pay / scan-to-login instruction. Quishing (QR-code '
                   'phishing) bypasses URL scanners entirely.')
    category = Category.STRONG
    severity = Severity.HIGH
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_HIGH

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        if not _QR_MENTION_RE.search(ctx.text):
            return None
        if not _QR_ACTION_RE.search(ctx.text):
            return None
        return self._make_result(
            explanation='Instructs the user to scan a QR code to pay or log in.',
            evidence={},
        )


# ══════════════════════════════════════════════════════════════════════════
# B5 — Threat + immediate payment
# ══════════════════════════════════════════════════════════════════════════
_THREAT_RE = re.compile(
    r'\b(?:arrest(?:ed)?|arrest\s+warrant|warrant|lawsuit|prosecute[d]?|'
    r'suspended|terminated|blocked|deport(?:ed|ation)?|criminal\s+charges|'
    r'legal\s+action|penalty|fine|jail|prison|court\s+summons|'
    r'account\s+closure|account\s+locked)\b',
    re.IGNORECASE,
)
_PAYMENT_DEMAND_RE = re.compile(
    r'\b(?:pay\s+now|pay\s+immediately|make\s+payment|wire\s+transfer|'
    r'send\s+(?:money|funds|payment)|deposit|settle|clear\s+the\s+balance|'
    r'transfer\s+(?:the\s+)?funds|pay\s+within|pay\s+by\s+today)\b',
    re.IGNORECASE,
)
_URGENCY_RE = re.compile(
    r'\b(?:within\s+\d+\s*(?:hours?|minutes?|days?)|'
    r'immediately|urgent(?:ly)?|right\s+now|today|before\s+\d+\s*(?:am|pm)|'
    r'last\s+chance|final\s+notice)\b',
    re.IGNORECASE,
)


class ThreatImmediatePaymentRule(Rule):
    id = 'B5_THREAT_IMMEDIATE_PAYMENT'
    name = 'Threat + immediate payment'
    description = ('The message combines a legal/personal threat (arrest, '
                   'lawsuit, deportation) with a demand for immediate '
                   'payment. Classic coercion pattern.')
    category = Category.STRONG
    severity = Severity.HIGH
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_HIGH

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        m_t = _THREAT_RE.search(ctx.text)
        if not m_t:
            return None
        m_p = _PAYMENT_DEMAND_RE.search(ctx.text)
        if not m_p:
            return None
        urgency = bool(_URGENCY_RE.search(ctx.text))
        return self._make_result(
            explanation=(f'Threat ({m_t.group(0)}) + payment demand '
                         f'({m_p.group(0)}){" + urgency" if urgency else ""}.'),
            evidence={'threat': m_t.group(0),
                      'payment': m_p.group(0),
                      'urgency': urgency},
        )


# ══════════════════════════════════════════════════════════════════════════
# B6 — Impossible brand / domain combinations
# ══════════════════════════════════════════════════════════════════════════
# The hostname contains a brand name as a subdomain OR non-official TLD
# (e.g. "amazon-support.xyz", "paypal-secure.top", "apple.verify-id.com").
_BRAND_TOKENS = (
    'amazon', 'paypal', 'apple', 'microsoft', 'google', 'netflix',
    'facebook', 'instagram', 'linkedin', 'fedex', 'ups', 'dhl', 'usps',
    'chase', 'wellsfargo', 'bankofamerica', 'hsbc', 'stripe', 'venmo',
    'zelle', 'coinbase', 'binance', 'irs',
)
_SUSPICIOUS_TLDS = {
    'xyz', 'top', 'tk', 'ml', 'ga', 'cf', 'gq', 'click', 'link', 'work',
    'buzz', 'zip', 'rest', 'monster', 'cyou', 'quest', 'cam', 'shop',
    'icu', 'live', 'online',
}


class ImpossibleBrandDomainRule(Rule):
    id = 'B6_IMPOSSIBLE_BRAND_DOMAIN'
    name = 'Impossible brand / domain combination'
    description = ('A URL hostname embeds a well-known brand name as a '
                   'sub-label or uses a suspicious TLD (.xyz, .top, .tk, '
                   'etc.) — brand-lookalike phishing infrastructure.')
    category = Category.STRONG
    severity = Severity.HIGH
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_HIGH

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        for host in ctx.hostnames:
            parts = host.split('.')
            if not parts:
                continue
            tld = parts[-1]
            root = parts[-2] if len(parts) >= 2 else ''
            # Case 1: brand token appears as a sub-label (not the root)
            for brand in _BRAND_TOKENS:
                if brand in host and root != brand and not host.endswith(
                        f'.{brand}.com') and root != brand:
                    # Ensure it appears as a genuine token, not by coincidence
                    if re.search(rf'(^|[.\-]){re.escape(brand)}([.\-]|$)', host):
                        return self._make_result(
                            explanation=(f'Hostname "{host}" embeds brand '
                                         f'"{brand}" outside its root.'),
                            evidence={'host': host, 'brand': brand},
                        )
            # Case 2: any brand root + suspicious TLD
            if root in _BRAND_TOKENS and tld in _SUSPICIOUS_TLDS:
                return self._make_result(
                    explanation=(f'Brand root "{root}" on suspicious TLD ".{tld}".'),
                    evidence={'host': host, 'brand': root, 'tld': tld},
                )
        return None


# ══════════════════════════════════════════════════════════════════════════
# B7 — High-risk financial request
# ══════════════════════════════════════════════════════════════════════════
_HIGH_RISK_PAYMENT_RE = re.compile(
    r'\b(?:wire\s+transfer|bank\s+wire|swift\s+transfer|'
    r'western\s+union|moneygram|money\s+gram|'
    r'zelle|via\s+zelle|through\s+zelle|'
    r'cash\s+app|cashapp|'
    r'crypto(?:currency)?|bitcoin|btc|ethereum|eth|usdt|usdc|'
    r'stablecoin|wallet\s+address)\b',
    re.IGNORECASE,
)
_UNKNOWN_RECIPIENT_RE = re.compile(
    r'\b(?:send\s+(?:it\s+)?to|transfer\s+to|deposit\s+to|pay\s+to)\s+'
    r'(?:this|the\s+following|below|address|account|number)\b',
    re.IGNORECASE,
)


class HighRiskFinancialRule(Rule):
    id = 'B7_HIGH_RISK_FINANCIAL'
    name = 'High-risk financial payment method'
    description = ('The message directs payment via an irreversible / hard-'
                   'to-recall channel (wire, Western Union, MoneyGram, '
                   'Zelle, Cash App, crypto) to an unspecified or '
                   'unfamiliar recipient.')
    category = Category.STRONG
    severity = Severity.HIGH
    default_action = RuleAction.INCREASE
    default_adjustment = INCREASE_MEDIUM

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        m_pay = _HIGH_RISK_PAYMENT_RE.search(ctx.text)
        if not m_pay:
            return None
        adjustment = INCREASE_MEDIUM
        # Bump to HIGH if the message also directs the funds to an
        # unspecified account/wallet.
        if _UNKNOWN_RECIPIENT_RE.search(ctx.text):
            adjustment = INCREASE_HIGH
        return self._make_result(
            explanation=(f'Directs payment via {m_pay.group(0)} '
                         f'(irreversible channel).'),
            adjustment=adjustment,
            evidence={'method': m_pay.group(0)},
        )


# B8 (Brand impersonation standalone) removed 2026-08-02 — fired 216× on
# the 25k external benchmark and added FPs on legit emails that mention
# brand names alongside unrelated legitimate URLs. The compound version
# (brand + sensitive action) remains as A8 in critical.py.


STRONG_RULES = [
    UrlShortenerActionRule(),
    HomoglyphDomainRule(),
    PunycodeDomainRule(),
    QrPaymentLoginRule(),
    ThreatImmediatePaymentRule(),
    ImpossibleBrandDomainRule(),
    HighRiskFinancialRule(),
]
