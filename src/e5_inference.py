"""
E5 inference wrapper — behaviorally identical to standalone ScamRadar+ 2.0.

The E5 bundle (models/e5_bundle.joblib) is a self-contained sklearn Pipeline
(word+char TF-IDF → LogisticRegression) trained by ScamRadar+ 2.0. It was
evaluated at threshold 0.59 (F1-max) on n=34,194 internal test and n=25,306
external benchmark, achieving F1=0.943 / 0.941 respectively.

Parity contract
---------------
This module's sole job is to preserve **byte-for-byte behavioral parity** with
the standalone E5 candidate. Specifically:

  * Input to the model is the RAW TEXT string, exactly as ScamRadar+ 2.0's
    evaluate.py does: `p = model.predict_proba(df.text)[:, 1]`.
    No pre-normalisation, no lowercasing, no URL stripping — the internal
    TfidfVectorizers handle tokenisation.

  * The threshold is E5's stored `threshold_f1` (0.59). Never the legacy
    DEFAULT_THRESHOLD (0.40). Never a hybrid value.

  * The verdict is strictly binary: SCAM if prob >= 0.59, else LEGIT.
    No SUSPICIOUS tier, no rule floors, no URL-based verdict escalation,
    no probability boosts. The wrapper NEVER modifies the probability or
    the verdict — it only ADDS ancillary display fields (scam_type, tone,
    urls_found, GSB/VT status) for frontend compatibility.

  * Given the same input text, this module MUST produce the same probability
    and verdict as the standalone E5 model. Any deviation is a bug.
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

from config import (
    E5_BUNDLE_PATH,
    E5_THRESHOLD,
    MIN_MESSAGE_LENGTH,
)
from src._02_feature_engineering import (
    preprocess_text,
    classify_scam_type,
    compute_tone_features,
    compute_url_features,
    compute_new_features,
    extract_urls,
    check_url_virustotal,
)
# GSB and trusted-domain helpers live inside _09_prediction_pipeline.py;
# import lazily inside functions to avoid a circular import (since
# _09_prediction_pipeline.py's own shim imports from here).


# ══════════════════════════════════════════════════════════════════════════
# LOADER
# ══════════════════════════════════════════════════════════════════════════

def load_e5_pipeline(bundle_path: str | None = None) -> dict:
    """Load the E5 joblib bundle.

    Returns a dict whose shape is compatible with `api/main.py`'s existing
    `_pipe[...]` access pattern. Legacy keys (`tfidf`, `char_tfidf`,
    `scaler`, `scam_index`, `st_model`) are populated with `None` because
    the E5 bundle is entirely self-contained.
    """
    path = bundle_path or E5_BUNDLE_PATH
    # Silence sklearn 1.5→1.8 version-mismatch warnings; we verified
    # loading works and predictions are correct in the parity harness.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        bundle = joblib.load(path)
    return {
        # Core E5 artifact — sklearn Pipeline(FeatureUnion(word,char) → LogReg)
        'model':        bundle['model'],
        'threshold':    float(bundle.get('threshold_f1', E5_THRESHOLD)),
        'metadata': {
            'feature_set':               bundle.get('feature_set'),
            'model_name':                bundle.get('model_name'),
            'calibration':               bundle.get('calibration'),
            'hpo_params':                bundle.get('hpo_params'),
            'threshold_f1':              bundle.get('threshold_f1'),
            'threshold_precision_floor': bundle.get('threshold_precision_floor'),
        },
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
    """The parity-critical call. Identical to ScamRadar+ 2.0 evaluate.py:
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
    # DEFAULT_THRESHOLD (0.40).
    if threshold is None:
        threshold = float(pipe.get('threshold', E5_THRESHOLD))

    # === E5 CORE — parity-critical, do not modify ===
    prob = _e5_probability(text, pipe)
    verdict = 'SCAM' if prob >= threshold else 'LEGIT'
    confidence_pct = round(prob * 100, 2)
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
        from src._09_prediction_pipeline import check_url_google_safebrowsing
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
    }
