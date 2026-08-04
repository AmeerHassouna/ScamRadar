"""ScamRadar+ modular post-classification Rule Engine.

Runs after the ML classifier (E5/E7-P1/P2) and adjusts the final
probability using objective security signals. Every prediction returns:
    ml_probability   — untouched classifier output
    final_probability — after rule adjustments
    triggered_rules   — list of rule results (id, name, adjustment, ...)
    explanation       — short human-readable rationale

Adding a new rule requires only writing a `Rule` subclass and appending it
to the rule list in the relevant category module — no changes to the
engine, wiring code, or existing rules.
"""
from src.rule_engine.base import (
    Category,
    Rule,
    RuleAction,
    RuleContext,
    RuleEngine,
    RuleResult,
    Severity,
)
from src.rule_engine.context import build_context
from src.rule_engine.critical import CRITICAL_RULES
from src.rule_engine.legit import LEGIT_RULES
from src.rule_engine.strong import STRONG_RULES

DEFAULT_RULES = CRITICAL_RULES + STRONG_RULES + LEGIT_RULES


def build_default_engine() -> RuleEngine:
    """Return a RuleEngine loaded with all shipped rules."""
    return RuleEngine(DEFAULT_RULES)


__all__ = [
    'Category',
    'Rule',
    'RuleAction',
    'RuleContext',
    'RuleEngine',
    'RuleResult',
    'Severity',
    'build_context',
    'build_default_engine',
    'CRITICAL_RULES',
    'STRONG_RULES',
    'LEGIT_RULES',
    'DEFAULT_RULES',
]
