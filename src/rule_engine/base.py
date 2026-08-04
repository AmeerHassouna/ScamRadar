"""Rule engine core: enums, dataclasses, Rule ABC, RuleEngine orchestrator.

Design contract
---------------
* Rules are stateless and side-effect free. They receive a RuleContext and
  return a RuleResult or None.
* Category A (Critical) can FORCE_SCAM → final_probability = 1.0.
* Category B (Strong) can INCREASE probability but never force any verdict.
* Category C (Legit) can DECREASE probability but never force LEGIT
  (they do not hard-set the verdict; they only subtract from probability
  with a floor to prevent literal zero).
* Rule adjustments are cumulative within each category. Multiple B rules
  add their INCREASE deltas; multiple C rules subtract their DECREASE
  deltas. Clamped to [PROB_FLOOR, PROB_CEILING].
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable

# Cumulative-adjustment clamps. FORCE_SCAM sets prob to 1.0 explicitly and
# bypasses the ceiling. PROB_FLOOR prevents C rules from driving prob to
# literal zero (defence in depth against total classifier suppression).
PROB_FLOOR   = 0.01
PROB_CEILING = 0.99


class Category(str, enum.Enum):
    CRITICAL = 'A'   # can FORCE_SCAM
    STRONG   = 'B'   # INCREASE only
    LEGIT    = 'C'   # DECREASE only, never force LEGIT


class Severity(str, enum.Enum):
    CRITICAL = 'critical'   # A-rules
    HIGH     = 'high'
    MEDIUM   = 'medium'
    LOW      = 'low'
    INFO     = 'info'       # C-rules (informational; only reduces confidence)


class RuleAction(str, enum.Enum):
    FORCE_SCAM = 'force_scam'    # A-only: overrides prob to 1.0
    INCREASE   = 'increase'      # B: prob += adjustment
    DECREASE   = 'decrease'      # C: prob -= adjustment (subject to floor)
    HARD_CAP   = 'hard_cap'      # C-only: prob = min(prob, adjustment). Enforces
                                 # an upper bound (e.g. all-trusted URLs → cap 0.35).
                                 # Mirrors v1.x's aggressive URL-trust override.
                                 # Applied AFTER all INCREASE/DECREASE totals.
    NO_CHANGE  = 'no_change'     # rule fired but chose not to adjust


@dataclass
class RuleContext:
    """All pre-computed signals a rule may inspect.

    Built once per prediction by `context.build_context()`.  Rules must
    NOT recompute expensive signals — they read from context only.
    """
    text: str                       # raw user input
    text_norm: str                  # preprocessed / lowercased
    text_lower: str                 # simple .lower() for cheap matching
    urls: list                      # extracted URLs (strings)
    hostnames: list                 # eTLD+1-ish hostnames parsed from urls
    trusted_domains: set            # from config.TRUSTED_DOMAINS
    gsb_flagged: bool               # Google Safe Browsing hit
    gsb_threat_type: str | None
    vt_malicious: int               # VirusTotal engines flagging malicious
    vt_suspicious: int
    tone_urgency: int
    tone_fear: int
    tone_reward: int
    tone_threat: int
    scam_phrase_score: int
    sender_impersonation_score: int
    scam_type: str                  # from classify_scam_type() — e.g. 'romance_scam'
    ml_probability: float           # untouched classifier output
    ml_threshold: float             # verdict threshold (e.g. 0.59)
    # Optional payload for rules that want raw feature dicts:
    extras: dict = field(default_factory=dict)


@dataclass
class RuleResult:
    """One rule's decision."""
    rule_id: str
    name: str
    category: Category
    severity: Severity
    action: RuleAction
    adjustment: float                  # signed delta applied (+ for INCREASE, - for DECREASE, 0 for FORCE/NO_CHANGE)
    explanation: str                   # short human-readable rationale
    evidence: dict = field(default_factory=dict)   # matched patterns, urls, etc. — for auditability

    def to_dict(self) -> dict:
        return {
            'rule_id':     self.rule_id,
            'name':        self.name,
            'category':    self.category.value,
            'severity':    self.severity.value,
            'action':      self.action.value,
            'adjustment':  round(float(self.adjustment), 4),
            'explanation': self.explanation,
            'evidence':    self.evidence,
        }


class Rule:
    """Base class for all rules.

    Subclasses declare:
        id (str), name (str), description (str),
        category (Category), severity (Severity), default_action (RuleAction),
        default_adjustment (float, ships-with default; overridden by weights table)

    And implement:
        evaluate(ctx: RuleContext) -> RuleResult | None

    Adjustment magnitude and priority are read at runtime from
    `src.rule_engine.weights` — the class-level `default_adjustment` is the
    fallback used only when the weights table has no entry for `self.id`.
    """
    id: str
    name: str
    description: str
    category: Category
    severity: Severity
    default_action: RuleAction
    default_adjustment: float = 0.0
    default_priority: int = 50

    # ── Runtime-configurable weights (read from weights table each call) ──
    @property
    def adjustment(self) -> float:
        """Adjustment magnitude for this rule (from weights table, or fallback)."""
        from src.rule_engine.weights import get_weight
        return get_weight(self.id, self.default_adjustment)

    @property
    def priority(self) -> int:
        """Evaluation priority (higher = earlier). From weights table, or fallback."""
        from src.rule_engine.weights import get_priority
        return get_priority(self.id, self.default_priority)

    @property
    def action(self) -> RuleAction:
        """Effective action (weights-table override wins over class default)."""
        from src.rule_engine.weights import get_action
        return get_action(self.id, self.default_action) or self.default_action

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:      # pragma: no cover — abstract
        raise NotImplementedError

    # Small helper so subclasses stay terse
    def _make_result(
        self,
        explanation: str,
        evidence: dict | None = None,
        action: RuleAction | None = None,
        adjustment: float | None = None,
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.id,
            name=self.name,
            category=self.category,
            severity=self.severity,
            action=action or self.action,
            adjustment=(self.adjustment if adjustment is None else adjustment),
            explanation=explanation,
            evidence=evidence or {},
        )


class RuleEngine:
    """Applies a list of rules in category order and returns the aggregated
    decision.

    Priority: Critical (A) → Strong (B) → Legit (C).
    A FORCE_SCAM result short-circuits: probability is set to 1.0 and no
    further B/C rules can adjust it downward (any B rules that fired
    before the FORCE still contribute to `triggered_rules` for auditability
    but their adjustments are ignored in the final probability).
    """

    def __init__(self, rules: list):
        # Sort by priority DESC within each category so higher-priority rules
        # evaluate first. Cross-category order (A → B → C) is enforced by
        # `run()` regardless of priority numbers.
        self.rules_by_cat: dict = {
            Category.CRITICAL: sorted([r for r in rules if r.category == Category.CRITICAL],
                                      key=lambda r: -r.priority),
            Category.STRONG:   sorted([r for r in rules if r.category == Category.STRONG],
                                      key=lambda r: -r.priority),
            Category.LEGIT:    sorted([r for r in rules if r.category == Category.LEGIT],
                                      key=lambda r: -r.priority),
        }

    @property
    def all_rules(self) -> list:
        return (self.rules_by_cat[Category.CRITICAL]
              + self.rules_by_cat[Category.STRONG]
              + self.rules_by_cat[Category.LEGIT])

    def run(self, ctx: RuleContext) -> dict:
        """Evaluate every rule and return the aggregated decision.

        Returns dict with keys:
            ml_probability     — ctx.ml_probability (unchanged pass-through)
            final_probability  — after adjustments
            triggered_rules    — list[RuleResult.to_dict()]
            adjustments        — dict {category → summed_delta}
            forced_scam        — bool
            explanation        — short human-readable rationale
        """
        triggered: list = []
        forced_scam = False

        # A — Critical
        for rule in self.rules_by_cat[Category.CRITICAL]:
            try:
                result = rule.evaluate(ctx)
            except Exception as e:
                result = None                     # rule failure never blocks pipeline
            if result is None:
                continue
            triggered.append(result)
            if result.action == RuleAction.FORCE_SCAM:
                forced_scam = True

        # B — Strong (only aggregated if not forced)
        strong_delta = 0.0
        for rule in self.rules_by_cat[Category.STRONG]:
            try:
                result = rule.evaluate(ctx)
            except Exception:
                result = None
            if result is None:
                continue
            triggered.append(result)
            if result.action == RuleAction.INCREASE:
                strong_delta += float(result.adjustment)

        # C — Legit (only if not forced)
        legit_delta = 0.0
        hard_caps: list = []
        if not forced_scam:
            for rule in self.rules_by_cat[Category.LEGIT]:
                try:
                    result = rule.evaluate(ctx)
                except Exception:
                    result = None
                if result is None:
                    continue
                triggered.append(result)
                if result.action == RuleAction.DECREASE:
                    legit_delta -= abs(float(result.adjustment))
                elif result.action == RuleAction.HARD_CAP:
                    hard_caps.append(float(result.adjustment))

        # ── Clamp cumulative adjustments before applying to ML prob ──────
        # Every rule still fires and is reported, but the aggregate cannot
        # exceed the configured caps. Prevents "rule explosion" from
        # letting many medium-strength rules dominate the classifier.
        from src.rule_engine.weights import (
            get_max_positive_adjustment,
            get_max_negative_adjustment,
        )
        max_pos = get_max_positive_adjustment()
        max_neg = get_max_negative_adjustment()

        raw_strong_delta = strong_delta
        raw_legit_delta  = legit_delta
        applied_strong_delta = min(strong_delta, max_pos)   # cap upward pressure
        applied_legit_delta  = max(legit_delta,  max_neg)   # cap downward pressure (neg → floor)
        strong_capped = applied_strong_delta < raw_strong_delta - 1e-9
        legit_capped  = applied_legit_delta  > raw_legit_delta  + 1e-9

        # Compose final probability
        if forced_scam:
            final = 1.0
        else:
            final = ctx.ml_probability + applied_strong_delta + applied_legit_delta
            # Apply any HARD_CAP from C-rules AFTER the additive block.
            # Multiple caps → take the lowest (most restrictive).
            if hard_caps:
                final = min(final, min(hard_caps))
            final = max(PROB_FLOOR, min(PROB_CEILING, final))

        explanation = self._compose_explanation(triggered, forced_scam,
                                                ctx.ml_probability, final)

        return {
            'ml_probability':    round(float(ctx.ml_probability), 4),
            'final_probability': round(float(final), 4),
            'triggered_rules':   [r.to_dict() for r in triggered],
            'adjustments': {
                # Values actually applied to the ML probability (post-clamp)
                Category.CRITICAL.value: 1.0 if forced_scam else 0.0,
                Category.STRONG.value:   round(applied_strong_delta, 4),
                Category.LEGIT.value:    round(applied_legit_delta,  4),
            },
            'raw_adjustments': {
                # Sum of individual rule adjustments BEFORE clamping
                Category.STRONG.value:   round(raw_strong_delta, 4),
                Category.LEGIT.value:    round(raw_legit_delta,  4),
            },
            'caps': {
                'max_positive':  round(max_pos, 4),
                'max_negative':  round(max_neg, 4),
                'strong_capped': bool(strong_capped),
                'legit_capped':  bool(legit_capped),
                'hard_cap_hit':  bool(hard_caps),
                'hard_cap_value': round(min(hard_caps), 4) if hard_caps else None,
            },
            'forced_scam':       forced_scam,
            'explanation':       explanation,
        }

    @staticmethod
    def _compose_explanation(triggered: list, forced_scam: bool,
                             ml_prob: float, final_prob: float) -> str:
        if forced_scam:
            crit_names = [r.name for r in triggered
                          if r.category == Category.CRITICAL
                          and r.action == RuleAction.FORCE_SCAM]
            return ('Forced SCAM by critical rule(s): '
                    + ', '.join(crit_names) if crit_names else 'Forced SCAM.')
        if not triggered:
            return f'No rules triggered — classifier probability {ml_prob:.2f} used as-is.'
        parts = []
        for r in triggered:
            sign = '+' if r.adjustment > 0 else ''
            parts.append(f'{r.name} ({sign}{r.adjustment:+.2f})' if r.adjustment
                         else r.name)
        return (f'{ml_prob:.2f} → {final_prob:.2f}  (' + '; '.join(parts) + ')')
