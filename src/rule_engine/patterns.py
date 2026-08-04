"""Shared regex-based pattern detectors used by multiple rules.

All A-category rules that inspect textual behaviour (credential request,
OTP theft, gift-card payment, remote-access request, crypto seed request,
sensitive account action) expose their detectors here so B and C rules
can reuse them for guard checks — e.g. A8-compound requires
brand-impersonation AND one of these action patterns; C1 refuses to
fire if any of these action patterns is present.
"""
from __future__ import annotations

import re


# ── Credential request (password / PIN / CVV / SSN / private key / ...) ──
_CRED_TARGETS = (
    r'password|passcode|pin|cvv|cvc|security\s+code|recovery\s+code|'
    r'seed\s+phrase|mnemonic|private\s+key|wallet\s+key|social\s+security\s+number|'
    r'ssn|full\s+ssn|routing\s+number|account\s+number|card\s+number'
)
CRED_REQUEST_RE = re.compile(
    r'\b(?:enter|type|send|reply\s+with|provide|share|confirm|verify|'
    r'give\s+us|tell\s+us|forward|dm\s+me\s+with)\s+'
    r'(?:your\s+|the\s+)?(?:full\s+|complete\s+)?'
    r'(?:' + _CRED_TARGETS + r')\b',
    re.IGNORECASE,
)


def has_credential_request(text: str) -> bool:
    return bool(text and CRED_REQUEST_RE.search(text))


# ── OTP theft (asks user to send/reply/forward a code) ───────────────────
# Loosened 2026-08-04 — the old strict regex required an OTP keyword to
# appear IMMEDIATELY after the request verb (e.g. "reply with verification
# code"). Modern OTP-theft messages routinely say "reply to this message
# with the code" (with intervening words) or "read the code back" (using
# bare "the code" rather than "verification code"). New design:
#   * OTP_KEYWORD_RE  — indicates the message is ABOUT a one-time code
#                       (verification/one-time/security/access/2fa/OTP/
#                        passcode, or "a code was sent to your phone" pattern)
#   * OTP_ASK_RE      — indicates a request TO SEND the code back
#                       (reply with, forward it, read it back, etc.)
# has_otp_theft() fires only when BOTH match — so we don't false-fire on
# code-review or discount-code messages that mention "the code" without
# any OTP context.
OTP_KEYWORD_RE = re.compile(
    r'\b(?:verification\s+code|one[- ]time\s+(?:code|password|passcode|pin)|'
    r'security\s+code|access\s+code|2fa\s+code|auth(?:entication)?\s+code|'
    r'confirmation\s+code|sms\s+code|text\s+code|'
    r'otp|passcode|'
    r'\d\s*-?\s*digit\s+(?:verification\s+|security\s+)?code|'
    r'(?:a|the)\s+code\s+(?:was|has\s+been)\s+(?:sent|messaged|texted))\b',
    re.IGNORECASE,
)
OTP_ASK_RE = re.compile(
    r'\b(?:'
    # Direct verb + directional pattern
    r'reply\s+(?:with|to|us|me|now|back)|'
    r'send\s+(?:it|us|me|back|the\s+code)|'
    r'forward\s+(?:it|us|me|the\s+code)|'
    r'share\s+(?:it|us|me|the\s+code)\b|'
    r'text\s+(?:us|me|back|it)|'
    r'read\s+(?:it|the\s+code|back)|'
    r'give\s+(?:us|me)\s+the\b|'
    r'tell\s+(?:us|me)\s+the\b|'
    r'dm\s+(?:us|me)|'
    # Explicit please-provide patterns
    r'please\s+(?:provide|share|forward|reply\s+with)|'
    # Direct question forms
    r'what\'?s\s+(?:the|your)\s+(?:code|pin|otp)|'
    r'confirm\s+the\s+(?:code|pin|otp)\b'
    r')\b',
    re.IGNORECASE,
)

# Kept for backward compat — the strict originals are now unused
OTP_THEFT_RE = OTP_KEYWORD_RE
OTP_THEFT_ALT_RE = OTP_ASK_RE


_OTP_NEGATION_RE = re.compile(
    r'\b(?:never|do\s+not|don\'?t|will\s+never|are\s+not\s+to|please\s+do\s+not)\s+'
    r'(?:reply|send|forward|share|text|read|give|tell|dm)\b',
    re.IGNORECASE,
)


def has_otp_theft(text: str) -> bool:
    """Fires when the text both (a) contains an OTP-context keyword AND
    (b) contains a request-to-send-the-code verb pattern AND (c) is NOT
    a negated warning like 'Never share it' / 'Do not forward the code'."""
    if not text:
        return False
    if not (OTP_KEYWORD_RE.search(text) and OTP_ASK_RE.search(text)):
        return False
    # Negation guard — legit OTP messages routinely say "Never share it"
    # or "Do not forward the code". Those must not force-scam.
    if _OTP_NEGATION_RE.search(text):
        return False
    return True


# ── Gift card payment demand ─────────────────────────────────────────────
GIFT_CARD_RE = re.compile(
    r'\b(?:apple|google|amazon|steam|itunes|target|walmart|ebay|visa|'
    r'sephora|xbox|playstation|paypal|razer|nintendo)?\s*'
    r'gift\s+cards?\b',
    re.IGNORECASE,
)
GIFT_CARD_PAYMENT_CTX_RE = re.compile(
    r'\b(?:pay(?:ment)?|paying|send|purchase|buy|use|owe|owed|settle|clear|'
    r'wire|transfer|deposit)\b',
    re.IGNORECASE,
)


def has_gift_card_payment(text: str) -> bool:
    if not text:
        return False
    return bool(GIFT_CARD_RE.search(text)) and bool(GIFT_CARD_PAYMENT_CTX_RE.search(text))


# ── Crypto wallet seed / recovery phrase request ─────────────────────────
CRYPTO_SECRET_RE = re.compile(
    r'\b(?:seed\s+phrase|recovery\s+phrase|mnemonic\s+phrase|mnemonic|'
    r'12[-\s]?word\s+(?:phrase|seed)|24[-\s]?word\s+(?:phrase|seed)|'
    r'private\s+key|wallet\s+key|secret\s+recovery\s+phrase)\b',
    re.IGNORECASE,
)
CRYPTO_ACTION_RE = re.compile(
    r'\b(?:enter|verify|confirm|recover|restore|sync|validate|import|'
    r'connect|link|send|share|paste|type|provide|reveal|show)\b',
    re.IGNORECASE,
)
CRYPTO_WARNING_RE = re.compile(
    r'\bnever\s+(?:enter|share|give|reveal|type|paste)\b',
    re.IGNORECASE,
)


def has_crypto_seed_request(text: str) -> bool:
    if not text:
        return False
    if not CRYPTO_SECRET_RE.search(text):
        return False
    if not CRYPTO_ACTION_RE.search(text):
        return False
    if CRYPTO_WARNING_RE.search(text):        # e.g. "never share your seed"
        return False
    return True


# ── Remote-access software install / connect request ────────────────────
REMOTE_TOOL_RE = re.compile(
    r'\b(?:teamviewer|anydesk|ultraviewer|logmein|log\s?me\s?in|'
    r'quickassist|quick\s+assist|screenconnect|screen\s?connect|'
    r'supremo|zoho\s+assist|isl\s+light|remote\s+utilities|ammyy|'
    r'vnc|realvnc|tightvnc|splashtop|gotoassist|go\s?to\s?assist|'
    r'connectwise\s+control|beyondtrust|dwservice)\b',
    re.IGNORECASE,
)
REMOTE_ACTION_RE = re.compile(
    r'\b(?:install|download|run|open|launch|start|enter|type|share|give|'
    r'provide|read|allow|grant|connect|join)\b',
    re.IGNORECASE,
)


def has_remote_access_request(text: str) -> bool:
    if not text:
        return False
    return bool(REMOTE_TOOL_RE.search(text)) and bool(REMOTE_ACTION_RE.search(text))


# ── Sensitive account action (login / reset password / verify identity / ...)
# Used by A8-compound to combine with brand impersonation. This is a
# STRUCTURED action pattern — not a bare keyword — matching specific
# high-risk request forms.
SENSITIVE_ACTION_RE = re.compile(
    r'\b(?:log(?:in|\s+in)|sign[\s-]?in|sign[\s-]?up|'
    r'reset\s+(?:your\s+)?password|'
    r'verify\s+(?:your\s+)?(?:account|identity|payment|billing|address|email|phone)|'
    r'confirm\s+(?:your\s+)?(?:account|identity|payment|billing|order|address)|'
    r'update\s+(?:your\s+)?(?:payment|billing|account)\s+(?:info|details|information|method|address)|'
    r'reactivate\s+(?:your\s+)?account|'
    r'unlock\s+(?:your\s+)?account|'
    r'complete\s+(?:your\s+)?(?:payment|verification|order|purchase|profile)|'
    r'pay(?:ment)?\s+(?:now|required|overdue|is\s+due|failed|is\s+overdue)|'
    r'action\s+required|'
    r'authenticate\s+(?:your\s+)?(?:account|identity)|'
    r'submit\s+(?:your\s+)?(?:payment|documents|verification|identity))\b',
    re.IGNORECASE,
)


def has_sensitive_account_action(text: str) -> bool:
    return bool(text and SENSITIVE_ACTION_RE.search(text))


# ── Aggregate: any "critical action pattern" (used by C1 guard) ─────────
def has_any_critical_action_pattern(text: str) -> bool:
    """True if the text contains any critical-severity behavioural pattern:
    credential request, OTP theft, gift-card payment demand, remote-access
    install request, or crypto seed-phrase request. Used by Category C
    rules to refuse to lower probability when a dangerous pattern is
    concurrently present.
    """
    return (has_credential_request(text)
            or has_otp_theft(text)
            or has_gift_card_payment(text)
            or has_remote_access_request(text)
            or has_crypto_seed_request(text))
