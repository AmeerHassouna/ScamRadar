"""Configurable rule weights, priorities, and action overrides.

Single source of truth for tuning the rule engine without touching rule
code. Each rule reads its adjustment magnitude and priority from the
tables below at evaluation time.

Sign convention
---------------
Weights are magnitudes (always positive). The sign is applied by the
engine based on the rule's category:
    Category A (Critical)  → FORCE_SCAM (magnitude ignored, prob → 1.0)
    Category B (Strong)    → +magnitude (INCREASE)
    Category C (Legit)     → -magnitude (DECREASE)
"""
from __future__ import annotations

from src.rule_engine.base import RuleAction


# ── Confidence adjustment magnitudes ──────────────────────────────────────
# For Category A rules, the value is symbolic (1.0 = "full force") and the
# engine sets probability to 1.0 regardless. For B/C the value is applied
# directly with the appropriate sign.
RULE_WEIGHTS: dict = {
    # ── A — Critical (FORCE_SCAM) ─────────────────────────────────────────
    'A1_MALICIOUS_URL':                    1.0,
    'A2_CREDENTIAL_REQUEST':               1.0,
    'A3_OTP_THEFT':                        1.0,
    'A4_GIFT_CARD_PAYMENT':                1.0,
    'A5_CRYPTO_SEED_PHRASE':               1.0,
    'A6_REMOTE_ACCESS_SOFTWARE':           1.0,
    # A7 removed (see critical.py)
    # A8 removed (see critical.py)

    # ── B — Strong (INCREASE) ─────────────────────────────────────────────
    'B1_URL_SHORTENER_ACTION':             0.25,
    'B2_HOMOGLYPH_DOMAIN':                 0.25,
    'B3_PUNYCODE_DOMAIN':                  0.15,
    'B4_QR_PAYMENT_LOGIN':                 0.25,
    'B5_THREAT_IMMEDIATE_PAYMENT':         0.25,
    'B6_IMPOSSIBLE_BRAND_DOMAIN':          0.25,
    'B7_HIGH_RISK_FINANCIAL':              0.15,
    # B8 removed (see strong.py)

    # ── C — Legit (DECREASE) ──────────────────────────────────────────────
    'C1_BRAND_OFFICIAL_DOMAIN':            0.30,
    'C2_OFFICIAL_DOMAIN_CONSISTENCY':      0.30,
    'C3_OTP_NOTIFICATION':                 0.30,
    # C4 removed (see legit.py)
}


# ── Priority (evaluated highest first within each category) ───────────────
# Priority determines evaluation ORDER within a category. It does NOT
# determine adjustment size or override cross-category precedence
# (Critical always outranks Strong which always outranks Legit — the
# engine enforces that separately).
RULE_PRIORITIES: dict = {
    # ── A — Critical (100 → 70) ───────────────────────────────────────────
    'A1_MALICIOUS_URL':                    100,
    'A2_CREDENTIAL_REQUEST':                95,
    'A3_OTP_THEFT':                         90,
    'A4_GIFT_CARD_PAYMENT':                 85,
    'A5_CRYPTO_SEED_PHRASE':                82,
    'A6_REMOTE_ACCESS_SOFTWARE':            80,
    # A7 removed
    # A8 removed

    # ── B — Strong (70 → 50) ──────────────────────────────────────────────
    'B1_URL_SHORTENER_ACTION':              70,
    'B5_THREAT_IMMEDIATE_PAYMENT':          67,
    'B4_QR_PAYMENT_LOGIN':                  65,
    'B6_IMPOSSIBLE_BRAND_DOMAIN':           63,
    'B7_HIGH_RISK_FINANCIAL':               62,
    # B8 removed
    'B2_HOMOGLYPH_DOMAIN':                  58,
    'B3_PUNYCODE_DOMAIN':                   55,

    # ── C — Legit (50 → 30) ───────────────────────────────────────────────
    'C1_BRAND_OFFICIAL_DOMAIN':             40,
    'C2_OFFICIAL_DOMAIN_CONSISTENCY':       35,
    'C3_OTP_NOTIFICATION':                  30,
    # C4 removed
}


# ── Optional per-rule action overrides ────────────────────────────────────
# Populate to override a rule's declared default_action without editing
# its class. Leave empty by default.
RULE_ACTIONS: dict = {}


# ── Cumulative adjustment caps ────────────────────────────────────────────
# The rule engine always evaluates every rule and reports every result,
# but the CUMULATIVE probability delta contributed by non-critical rules
# is clamped to these bounds before being applied to the ML probability.
# This prevents "rule explosion" where many medium-strength rules
# stacking would dominate the ML classifier's judgment.
#
# FORCE_SCAM (Category A) bypasses the cap entirely — a single confirmed
# malicious signal (e.g. GSB-flagged URL) still sets probability to 1.0.
MAX_POSITIVE_ADJUSTMENT = +0.40   # Category B stacked increases cap here
MAX_NEGATIVE_ADJUSTMENT = -0.40   # Category C stacked decreases cap here


# ── Lookup helpers ────────────────────────────────────────────────────────

def get_weight(rule_id: str, default: float = 0.0) -> float:
    return float(RULE_WEIGHTS.get(rule_id, default))


def get_priority(rule_id: str, default: int = 50) -> int:
    return int(RULE_PRIORITIES.get(rule_id, default))


def get_action(rule_id: str, default: RuleAction | None = None) -> RuleAction | None:
    return RULE_ACTIONS.get(rule_id, default)


def get_max_positive_adjustment() -> float:
    return float(MAX_POSITIVE_ADJUSTMENT)


def get_max_negative_adjustment() -> float:
    return float(MAX_NEGATIVE_ADJUSTMENT)
