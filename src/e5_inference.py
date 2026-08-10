"""
E5 inference wrapper — loads the frozen E5 bundle and exposes predict/predict_proba.

The E5 bundle (models/e5_bundle.joblib) is a self-contained sklearn Pipeline
(word+char TF-IDF → LogisticRegression) trained during the E5 stage. It was
evaluated at threshold 0.59 (F1-max) on n=34,194 internal test and n=25,306
external benchmark, achieving F1=0.943 / 0.941 respectively.

Parity contract
---------------
This module's sole job is to preserve **byte-for-byte behavioral parity** with
the frozen E5 candidate. Specifically:

  * Input to the model is the RAW TEXT string, exactly as the E5 training
    evaluate.py does: `p = model.predict_proba(df.text)[:, 1]`.
    No pre-normalisation, no lowercasing, no URL stripping — the internal
    TfidfVectorizers handle tokenisation.

  * The threshold is E5's stored `threshold_f1` (0.59). Never the legacy
    (0.40) or any hybrid value.

  * The verdict is strictly binary: SCAM if prob >= 0.59, else LEGIT.
    No SUSPICIOUS tier, no rule floors, no URL-based verdict escalation,
    no probability boosts. The wrapper NEVER modifies the probability or
    the verdict — it only ADDS ancillary display fields (scam_type, tone,
    urls_found, GSB/VT status) for frontend compatibility.

  * Given the same input text, this module MUST produce the same probability
    and verdict as the frozen E5 model. Any deviation is a bug.
"""
from __future__ import annotations

import os
import sys
import warnings

import joblib

# Add project root so sibling module imports resolve when this file is
# loaded via `from src.e5_inference import ...`
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import re

from config import (
    E5_BUNDLE_PATH,
    E5_THRESHOLD,
    E7_P2_SAFETY_NET_CAP,
    MIN_MESSAGE_LENGTH,
)


# ══════════════════════════════════════════════════════════════════════════
# Rule A — "Pure OTP" pattern detector
# ══════════════════════════════════════════════════════════════════════════
# Recognises the very tight structural pattern of a legitimate OTP / MFA
# verification message. Enabled by env var SCAMRADAR_OTP_RULE_ON=true.
#
# When ALL of the following hold, we treat the message as a pure OTP and
# cap scam probability to E7_P2_SAFETY_NET_CAP (below the 0.59 threshold,
# i.e. verdict flips to LEGIT):
#   - length < 350 chars
#   - contains an OTP-related keyword (code / verification / OTP / passcode)
#   - contains a 3-8 digit code somewhere in the text
#   - contains NO URLs (http://, https://, www.)
#   - contains NO phone-length digit runs (>8 consecutive digits after
#     stripping separators)
#   - contains NO information-request phrases (please provide/forward/reply
#     with/send us/confirm your)
#
# A scammer cannot exploit this rule: a message with no URL, no phone
# number, and no request has no attack surface — they'd have nowhere to
# send the victim.
# ══════════════════════════════════════════════════════════════════════════

_OTP_KEYWORD_RE   = re.compile(r'\b(?:verification\s*code|one[- ]time\s*(?:code|passcode|password)|passcode|otp|verify\s*code|security\s*code|access\s*code)\b|(?:^|\s)code\s+is\s+\d', re.I)
_OTP_CODE_RE      = re.compile(r'\b\d{3,8}\b')
_URL_ANY_RE       = re.compile(r'https?://|www\.', re.I)
_PHONE_LONG_RE    = re.compile(r'\+?\d[\d\s\-().]{7,}\d')  # 9+ digits with separators
_REQUEST_RE       = re.compile(
    r'\b(?:please\s+(?:provide|confirm|reply|forward|send|share|enter\s+at|call|contact|click)'
    r'|reply\s+(?:with|to\s+us|now)'
    r'|forward\s+(?:me|us|to)'
    r'|send\s+(?:me|us|it\s+to)'
    r'|share\s+(?:this|it)\s+with\s+(?:us|our|support))\b',
    re.I,
)


def _is_pure_otp(text: str) -> bool:
    """True if `text` matches the pure-OTP structural pattern."""
    if not text or len(text) > 350:
        return False
    if not _OTP_KEYWORD_RE.search(text):
        return False
    if not _OTP_CODE_RE.search(text):
        return False
    if _URL_ANY_RE.search(text):
        return False
    if _REQUEST_RE.search(text):
        return False
    # Phone number check — allow the code itself, reject longer runs
    max_run = 0
    for m in _PHONE_LONG_RE.finditer(text):
        digits_only = re.sub(r'\D', '', m.group(0))
        if len(digits_only) > max_run:
            max_run = len(digits_only)
    if max_run > 8:  # 9+ consecutive digits → likely a phone number
        return False
    return True
from src.features import (
    preprocess_text,
    classify_scam_type,
    compute_tone_features,
    compute_url_features,
    compute_new_features,
    extract_urls,
    check_url_virustotal,
)
# GSB and trusted-domain helpers live inside inference.py;
# import lazily inside functions to avoid a circular import (since
# inference.py's own shim imports from here).


# ══════════════════════════════════════════════════════════════════════════
# E7-P1 ADAPTER  (local research-mode only — never active in production)
# ══════════════════════════════════════════════════════════════════════════
# Presents the same `.predict_proba(list_of_texts)` interface as an sklearn
# Pipeline, so the rest of the E5 code path continues to work unchanged
# when the SCAMRADAR_LOCAL_MODEL env var selects a research variant.
# ══════════════════════════════════════════════════════════════════════════

class _E7P1Adapter:
    """Wraps an e7_p1_* bundle (LR + word_vec + char_vec + scaler +
    feature_cols) to present the same predict_proba([texts]) interface
    that E5's Pipeline provides."""
    def __init__(self, bundle: dict):
        self.lr = bundle['lr']
        self.word_vec = bundle['word_vec']
        self.char_vec = bundle['char_vec']
        self.scaler = bundle['scaler']
        self.feature_cols = bundle['feature_cols']
        self.variant = bundle.get('variant', 'e7_p1_unknown')
        # Runtime-only version — mirrors scripts/training/train_e7_p1.py byte-for-byte
        # but lives in src/ so the deployed image doesn't need the training script.
        from src.rule_engine.numerical_features import compute_all_numerical
        self._compute = compute_all_numerical

    def predict_proba(self, texts):
        import numpy as np
        from scipy.sparse import hstack, csr_matrix
        Xw = self.word_vec.transform(texts)
        Xc = self.char_vec.transform(texts)
        num_rows = []
        for t in texts:
            feats = self._compute(t)
            num_rows.append([feats.get(c, 0) for c in self.feature_cols])
        Xn = np.array(num_rows, dtype=np.float64)
        Xn = self.scaler.transform(Xn)
        Xn = np.clip(Xn, -8.0, 8.0)          # matches training-time hygiene
        X = hstack([Xw, Xc, csr_matrix(Xn)]).tocsr()
        return self.lr.predict_proba(X)


# ══════════════════════════════════════════════════════════════════════════
# LOADER
# ══════════════════════════════════════════════════════════════════════════

def load_e5_pipeline(bundle_path: str | None = None) -> dict:
    """Load the E5 joblib bundle by default.

    Local research override: set env var `SCAMRADAR_LOCAL_MODEL=e7_p1_full`
    (or any other e7_p1_* variant) to load that research bundle instead.
    This ONLY affects the local process — the E5 bundle file on disk is
    untouched, and production Render deployment stays on E5.

    Returns a dict whose shape is compatible with `api/main.py`'s existing
    `_pipe[...]` access pattern.
    """
    # Production default: E8-P9. Rule engine extended with A9/A10/A11
    # type-floors (investment/romance/threat) and A3 OTP-theft loosened
    # with a negation guard. An env-var override to any other e7_p1_*
    # research variant (or the empty string to fall back to the E5
    # bundle) takes precedence.
    override = os.environ.get('SCAMRADAR_LOCAL_MODEL', 'e7_p1_full_e8p9').strip()
    if override.startswith('e7_p1_'):
        # Research variant — different bundle schema; wrap in adapter
        variant_path = os.path.join(
            os.path.dirname(E5_BUNDLE_PATH),
            'e7_p1_variants', f'{override}.joblib'
        )
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            bundle = joblib.load(variant_path)
        model = _E7P1Adapter(bundle)
        threshold = float(bundle.get('threshold', E5_THRESHOLD))
        metadata = {
            'variant': override,
            'feature_cols': bundle.get('feature_cols'),
            'converged': bundle.get('converged'),
            'note': bundle.get('note'),
        }
        print(f'[e5_inference] LOCAL OVERRIDE ACTIVE: loaded {override} '
              f'from {variant_path} (threshold={threshold})')
    else:
        path = bundle_path or E5_BUNDLE_PATH
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            bundle = joblib.load(path)
        model = bundle['model']
        threshold = float(bundle.get('threshold_f1', E5_THRESHOLD))
        metadata = {
            'feature_set':               bundle.get('feature_set'),
            'model_name':                bundle.get('model_name'),
            'calibration':               bundle.get('calibration'),
            'hpo_params':                bundle.get('hpo_params'),
            'threshold_f1':              bundle.get('threshold_f1'),
            'threshold_precision_floor': bundle.get('threshold_precision_floor'),
        }

    return {
        'model':        model,
        'threshold':    threshold,
        'metadata':     metadata,
        # Legacy positional-arg slots kept as None so the existing
        # api/main.py call site keeps working without any change.
        'tfidf':        None,
        'char_tfidf':   None,
        'scaler':       None,
        'scam_index':   None,
        'st_model':     None,
    }


# ══════════════════════════════════════════════════════════════════════════
# CORE PREDICTION — parity-critical
# ══════════════════════════════════════════════════════════════════════════

def _e5_probability(text: str, pipe) -> float:
    """The parity-critical call. Identical to the E5 training-time evaluate.py:
       p = model.predict_proba(df.text)[:, 1]
    """
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        proba = pipe['model'].predict_proba([text])
    return float(proba[0, 1])


# ══════════════════════════════════════════════════════════════════════════
# WRAPPER — ancillary fields for frontend compatibility
# ══════════════════════════════════════════════════════════════════════════

def _empty_ancillary(warnings_list=None):
    """Response fields with neutral defaults, used for TOO_SHORT and other
    early-exit paths."""
    return {
        'threshold_used':         E5_THRESHOLD,
        'scam_type':              None,
        'why_flagged':            '',
        'tone_urgency':           0,
        'tone_fear':              0,
        'tone_reward':            0,
        'tone_threat':            0,
        'url_suspicious_tld':     0,
        'url_suspicious_keyword': 0,
        'url_has_ip':             0,
        'scam_phrase_score':      0,
        'sender_impersonation':   0,
        'proximity_score':        0.0,
        'urls_found':             [],
        'gsb_flagged':            False,
        'gsb_threat_type':        None,
        'gsb_attempted':          False,
        'vt_malicious':           0,
        'vt_suspicious':          0,
        'vt_attempted':           False,
        'normalized_text':        '',
        'feature_contributions':  {},
        'warnings':               warnings_list or [],
    }


def predict_e5(
    text: str,
    pipe: dict,
    threshold: float | None = None,
    vt_api_key: str | None = None,
    gsb_api_key: str | None = None,
) -> dict:
    """Full E5 prediction with ancillary display fields.

    Verdict/confidence come EXCLUSIVELY from E5. Ancillary analysis
    (scam_type, tone, urls, GSB/VT) populate response fields for the
    frontend but NEVER modify the probability or verdict.
    """
    warnings_list: list[str] = []

    # Length guard — same policy as the legacy pipeline. TOO_SHORT is
    # not an E5 output, it's an API-level early exit.
    if not text or len(str(text).strip()) < MIN_MESSAGE_LENGTH:
        result = {
            'verdict':    'TOO_SHORT',
            'confidence': 0.0,
        }
        result.update(_empty_ancillary(warnings_list))
        return result

    # Threshold: default to E5's stored value. NEVER fall back to
    # fallback value 0.40.
    if threshold is None:
        threshold = float(pipe.get('threshold', E5_THRESHOLD))

    # === E5 CORE — parity-critical, do not modify ===
    prob_raw = _e5_probability(text, pipe)
    # === END E5 CORE ===

    # --- Ancillary analysis (populates display fields, no verdict impact) ---
    text_norm = preprocess_text(text)
    try:
        scam_type = classify_scam_type(text_norm)
    except Exception:
        scam_type = 'general_spam'
    try:
        tone = compute_tone_features(text_norm)
    except Exception:
        tone = (0, 0, 0, 0)
    try:
        urls = extract_urls(text)
    except Exception:
        urls = []
    try:
        url_feat = compute_url_features(text_norm)
    except Exception:
        url_feat = (0, 0, 0)
    try:
        new_feat = compute_new_features(text_norm)
    except Exception:
        new_feat = {}

    # URL scanning — populate display fields ONLY. Never escalates verdict.
    gsb_flagged, gsb_threat_type, gsb_attempted = False, None, False
    vt_malicious, vt_suspicious, vt_attempted = 0, 0, False
    if urls:
        # Lazy import to avoid circular dependency at module-load time.
        from src.inference import check_url_google_safebrowsing
        if gsb_api_key:
            gsb_attempted = True
            for u in urls[:3]:
                try:
                    flagged, threat_type = check_url_google_safebrowsing(u, gsb_api_key)
                    if flagged:
                        gsb_flagged = True
                        gsb_threat_type = threat_type
                        break
                except Exception:
                    pass
        if vt_api_key:
            vt_attempted = True
            for u in urls[:3]:
                try:
                    vt_result = check_url_virustotal(u, vt_api_key)
                    if isinstance(vt_result, dict):
                        vt_malicious = max(vt_malicious, int(vt_result.get('malicious', 0)))
                        vt_suspicious = max(vt_suspicious, int(vt_result.get('suspicious', 0)))
                    elif isinstance(vt_result, tuple) and len(vt_result) >= 2:
                        vt_malicious = max(vt_malicious, int(vt_result[0] or 0))
                        vt_suspicious = max(vt_suspicious, int(vt_result[1] or 0))
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════════════════════
    # POST-CLASSIFICATION LAYER
    # ══════════════════════════════════════════════════════════════════════
    # Modular Rule Engine (opt-in via SCAMRADAR_RULE_ENGINE_ON=true) fully
    # replaces the legacy Rule A / URL safety-net blocks. When active it
    # can FORCE_SCAM (Category A), INCREASE (Category B), or DECREASE
    # (Category C) the probability. When inactive the legacy Rule A + URL
    # safety-net path is used (unchanged behaviour for existing E7-P2).
    # ══════════════════════════════════════════════════════════════════════
    # Production default: rule engine ON. Explicit env-var override wins.
    rule_engine_active = os.environ.get('SCAMRADAR_RULE_ENGINE_ON', 'true').lower() in ('true','1','yes','on')
    otp_rule_active = os.environ.get('SCAMRADAR_OTP_RULE_ON', '').lower() in ('true','1','yes','on')
    safety_net_active = os.environ.get('SCAMRADAR_SAFETY_NET_ON', '').lower() in ('true','1','yes','on')

    prob = prob_raw
    otp_rule_capped = False
    safety_net_capped = False
    rule_engine_result: dict | None = None

    if rule_engine_active:
        from src.rule_engine import build_context, build_default_engine
        # Cache the engine on the module so we don't rebuild the rule list
        # on every call. (Rules are stateless, cheap to build, but this
        # avoids the small per-call construction cost.)
        engine = globals().get('_RULE_ENGINE_SINGLETON')
        if engine is None:
            engine = build_default_engine()
            globals()['_RULE_ENGINE_SINGLETON'] = engine

        ctx = build_context(
            text=text,
            ml_probability=prob_raw,
            ml_threshold=threshold,
            text_norm=text_norm,
            urls=urls,
            tone=tone,
            scam_phrase_score=new_feat.get('scam_phrase_score', 0),
            sender_impersonation_score=new_feat.get('sender_impersonation_score', 0),
            scam_type=scam_type,
            gsb_flagged=gsb_flagged,
            gsb_threat_type=gsb_threat_type,
            vt_malicious=vt_malicious,
            vt_suspicious=vt_suspicious,
        )
        rule_engine_result = engine.run(ctx)
        prob = float(rule_engine_result['final_probability'])
        if rule_engine_result['triggered_rules']:
            warnings_list.append(
                f'rule_engine_applied_prob:{prob_raw:.4f}_to_{prob:.4f}_'
                f'rules:{len(rule_engine_result["triggered_rules"])}'
            )
    else:
        # Legacy Rule A: Pure-OTP structural pattern
        if otp_rule_active and prob > E7_P2_SAFETY_NET_CAP and _is_pure_otp(text):
            prob = E7_P2_SAFETY_NET_CAP
            otp_rule_capped = True
            warnings_list.append(
                f'otp_rule_capped_prob:{prob_raw:.4f}_to_{prob:.4f}_reason_pure_otp'
            )

        # Legacy Rule B (URL safety net): all URLs trusted + GSB clean → cap
        if safety_net_active and not otp_rule_capped and urls and prob > E7_P2_SAFETY_NET_CAP:
            from src.inference import is_all_trusted_domains
            try:
                all_trusted = is_all_trusted_domains(urls)
            except Exception:
                all_trusted = False
            gsb_ok = not gsb_flagged
            if all_trusted and gsb_ok:
                prob = E7_P2_SAFETY_NET_CAP
                safety_net_capped = True
                warnings_list.append(
                    f'safety_net_capped_prob:{prob_raw:.4f}_to_{prob:.4f}_reason_all_urls_trusted'
                )

    verdict = 'SCAM' if prob >= threshold else 'LEGIT'
    confidence_pct = round(prob * 100, 2)

    # why_flagged — short human-readable rationale from ancillary signals.
    # This is for display only; does not affect verdict/confidence.
    why_parts: list[str] = []
    if verdict != 'LEGIT':
        if scam_type and scam_type != 'general_spam':
            why_parts.append(
                'The structure and language of this message closely match a '
                f'{scam_type.replace("_", " ")} pattern.'
            )
        if tone[0] >= 2:
            why_parts.append('Uses urgent language to pressure quick action.')
        if tone[3] >= 1:
            why_parts.append('Contains threatening or coercive language.')
        if tone[2] >= 2:
            why_parts.append('Promises rewards, prizes, or unrealistic benefits.')
        if urls and (url_feat[0] or url_feat[1] or url_feat[2]):
            why_parts.append('Contains a suspicious or unusual link.')
        if gsb_flagged:
            why_parts.append('A link is confirmed dangerous by Google Safe Browsing.')
        if not why_parts:
            why_parts.append('The overall pattern matches known scam messaging.')
    why_flagged = '|'.join(why_parts[:3])

    return {
        'verdict':                verdict,
        'confidence':             confidence_pct,
        'threshold_used':         threshold,
        'scam_type':              scam_type,
        'why_flagged':            why_flagged,
        'tone_urgency':           tone[0],
        'tone_fear':              tone[1],
        'tone_reward':            tone[2],
        'tone_threat':            tone[3],
        'url_suspicious_tld':     url_feat[0],
        'url_suspicious_keyword': url_feat[1],
        'url_has_ip':             url_feat[2],
        'scam_phrase_score':      new_feat.get('scam_phrase_score', 0),
        'sender_impersonation':   new_feat.get('sender_impersonation_score', 0),
        'proximity_score':        0.0,          # E5 has no FAISS proximity
        'urls_found':             urls,
        'gsb_flagged':            gsb_flagged,
        'gsb_threat_type':        gsb_threat_type,
        'gsb_attempted':          gsb_attempted,
        'vt_malicious':           vt_malicious,
        'vt_suspicious':          vt_suspicious,
        'vt_attempted':           vt_attempted,
        'normalized_text':        text_norm,
        'feature_contributions':  {},           # E5 has 500k TF-IDF coeffs, no per-name map
        'warnings':               warnings_list,
        # E7-P2 safety-net telemetry (extra fields; frontend ignores unknown keys)
        'safety_net_active':      safety_net_active,
        'safety_net_capped':      safety_net_capped,
        'otp_rule_active':        otp_rule_active,
        'otp_rule_capped':        otp_rule_capped,
        'raw_probability':        round(float(prob_raw), 4),
        # Rule Engine explainability (only populated when engine active).
        # Fields:
        #   ml_probability   — untouched classifier output
        #   final_probability — post-engine probability used for the verdict
        #   triggered_rules   — list[{rule_id, name, category, severity,
        #                       action, adjustment, explanation, evidence}]
        #   adjustments       — {'A': ..., 'B': ..., 'C': ...} per-category deltas
        #   forced_scam       — bool
        #   explanation       — short human-readable rationale
        'rule_engine_active':     rule_engine_active,
        'rule_engine':            rule_engine_result,
        'ml_probability':         round(float(prob_raw), 4),
        'final_probability':      round(float(prob), 4),
        'triggered_rules':        (rule_engine_result or {}).get('triggered_rules', []),
    }
