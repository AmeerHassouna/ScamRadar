"""
ScamRadar+ | Step 09: Prediction Pipeline  (v5.1)
Full real-time inference with trusted-domain bonus, SUSPICIOUS tier,
non-English warning, VT error handling, and confidence capping.
"""

import re, time, pickle, os, sys
import numpy as np
import faiss
from urllib.parse import urlparse
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import (MODELS_PATH, NUMERICAL_FEATURES_V5, DEFAULT_THRESHOLD,
                    FAISS_K_SCAM, MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH,
                    VIRUSTOTAL_API_KEY, GOOGLE_SAFEBROWSING_API_KEY)
from src._02_feature_engineering import (
    preprocess_text, normalize_leet, extract_urls,
    compute_tone_features, compute_url_features, compute_new_features,
    classify_scam_type, check_url_virustotal,
)


# ── Trusted-domain check ───────────────────────────────────────────────────

_TRUSTED_DOMAINS = {
    # Banking / finance
    'bankofamerica.com', 'chase.com', 'wellsfargo.com', 'citibank.com',
    'hsbc.com', 'barclays.com', 'americanexpress.com',
    'visa.com', 'mastercard.com', 'stripe.com', 'squareup.com', 'paypal.com',
    # Big tech
    'google.com', 'apple.com', 'microsoft.com', 'amazon.com',
    'meta.com', 'yahoo.com', 'adobe.com', 'icloud.com', 'dropbox.com',
    'github.com', 'youtube.com',
    # Social / streaming
    'linkedin.com', 'twitter.com', 'instagram.com', 'facebook.com', 'tiktok.com',
    'netflix.com', 'spotify.com', 'hulu.com', 'disneyplus.com', 'playstation.com',
    # Shopping
    'ebay.com', 'etsy.com', 'shopify.com',
    # Amazon regional
    'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.co.jp',
    # Messaging / conferencing
    'whatsapp.com', 'wa.me', 't.me', 'zoom.us', 'webex.com',
    'teams.microsoft.com', 'meet.google.com',
    # SaaS / productivity tools (commonly impersonated but have real services)
    'figma.com', 'notion.so', 'canva.com', 'calendly.com',
    'wise.com', 'revolut.com', 'venmo.com',
    'booking.com', 'airbnb.com', 'coursera.org',
    'fiverr.com', 'discord.com', 'slack.com',
    'letsencrypt.org', 'openai.com', 'anthropic.com',
}


def is_all_trusted_domains(urls: list) -> bool:
    """
    Return True ONLY when every URL in the list resolves to an exact trusted domain
    (or a subdomain of one).  Empty list returns False — no URLs means no bonus.
    Uses urlparse for correct hostname extraction; never uses substring `in` matching.
    """
    if not urls:
        return False  # no URLs → no trusted-domain bonus

    for url in urls:
        parsed   = urlparse(url)
        hostname = parsed.netloc.lower()
        # strip port if present (e.g. example.com:443 → example.com)
        hostname = hostname.split(':')[0]
        # strip leading www.  (only www., not other subdomains)
        if hostname.startswith('www.'):
            hostname = hostname[4:]

        is_trusted = False
        for trusted in _TRUSTED_DOMAINS:
            # exact match (e.g. apple.com == apple.com)
            # or real subdomain (e.g. support.apple.com ends with .apple.com)
            if hostname == trusted or hostname.endswith('.' + trusted):
                is_trusted = True
                break

        if not is_trusted:
            return False  # even one untrusted URL → bonus not applied

    return True  # every URL passed


# ── Google Safe Browsing check ─────────────────────────────────────────────

def check_url_google_safebrowsing(url, api_key):
    import requests
    if not api_key:
        return False, None
    endpoint = f'https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}'
    payload = {
        'client': {'clientId': 'scamradar', 'clientVersion': '1.0'},
        'threatInfo': {
            'threatTypes': ['MALWARE', 'SOCIAL_ENGINEERING', 'UNWANTED_SOFTWARE',
                            'POTENTIALLY_HARMFUL_APPLICATION'],
            'platformTypes': ['ANY_PLATFORM'],
            'threatEntryTypes': ['URL'],
            'threatEntries': [{'url': url}]
        }
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'matches' in data:
                return True, data['matches'][0].get('threatType', 'THREAT')
        return False, None
    except Exception:
        return False, None


# ── Load pipeline artefacts ────────────────────────────────────────────────

def load_pipeline():
    scam_index_path = os.path.join(MODELS_PATH, 'scam_faiss.index')
    if not os.path.exists(scam_index_path):
        raise FileNotFoundError(
            "Model files not found. Please run main.py first to train the models."
        )

    print("Loading ScamRadar+ pipeline...")
    payload     = pickle.load(open(os.path.join(MODELS_PATH, 'scamradar_model.pkl'),   'rb'))
    tfidf       = pickle.load(open(os.path.join(MODELS_PATH, 'tfidf_vectorizer.pkl'),  'rb'))
    char_tfidf  = pickle.load(open(os.path.join(MODELS_PATH, 'char_vectorizer.pkl'),   'rb'))
    scaler      = pickle.load(open(os.path.join(MODELS_PATH, 'scaler.pkl'),             'rb'))
    scam_index  = faiss.read_index(scam_index_path)

    legit_index_path = os.path.join(MODELS_PATH, 'legit_faiss.index')
    legit_index = faiss.read_index(legit_index_path) if os.path.exists(legit_index_path) else None

    from sentence_transformers import SentenceTransformer
    st_model = SentenceTransformer('all-MiniLM-L6-v2')

    if isinstance(payload, dict):
        model = payload['model']
    else:
        model = payload

    print(f"✅ Pipeline loaded  (threshold={DEFAULT_THRESHOLD:.2f})")
    return model, tfidf, char_tfidf, scaler, scam_index, st_model


# ── Main predict function ──────────────────────────────────────────────────

def predict_message(text, model, tfidf, char_tfidf, scaler,
                    scam_index, st_model,
                    legit_index=None,
                    threshold=DEFAULT_THRESHOLD,
                    vt_api_key=None,
                    gsb_api_key=None):
    """
    Full prediction pipeline. Returns a result dict with all signals.
    Verdict is one of: SCAM / SUSPICIOUS / LEGIT / TOO_SHORT.
    API keys default to config constants; caller may override via vt_api_key / gsb_api_key.
    """
    # Allow callers to override keys; fall back to config constants
    _gsb_key = gsb_api_key or GOOGLE_SAFEBROWSING_API_KEY
    _vt_key  = vt_api_key  or VIRUSTOTAL_API_KEY
    warnings = []

    # ── 1. Too-short guard ────────────────────────────────────────────────
    if len(text.strip()) < MIN_MESSAGE_LENGTH:
        return {
            'verdict':              'TOO_SHORT',
            'confidence':           0.0,
            'threshold_used':       threshold,
            'scam_type':            None,
            'tone_urgency':         0, 'tone_fear':    0,
            'tone_reward':          0, 'tone_threat':  0,
            'url_suspicious_tld':   0, 'url_suspicious_keyword': 0, 'url_has_ip': 0,
            'scam_phrase_score':    0, 'sender_impersonation':   0,
            'proximity_score':      0.0,
            'urls_found':           [],
            'vt_malicious':         0, 'vt_suspicious': 0,
            'normalized_text':      '',
            'feature_contributions': {},
            'warnings': [f"Message too short to analyse ({len(text.strip())} chars). "
                         f"Minimum: {MIN_MESSAGE_LENGTH} characters."],
        }

    # ── 2. Truncate if over limit ─────────────────────────────────────────
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]
        warnings.append(f"Message truncated to {MAX_MESSAGE_LENGTH:,} characters.")

    # ── 3. Non-ASCII language warning ─────────────────────────────────────
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii / max(len(text), 1) > 0.30:
        warnings.append(
            "Message may contain non-English text — detection accuracy may be lower."
        )

    # ── 4. Preprocessing ──────────────────────────────────────────────────
    text_clean = preprocess_text(text)
    text_norm  = normalize_leet(text_clean)

    # ── 5. URL extraction ─────────────────────────────────────────────────
    urls = extract_urls(text)

    # ── 6. URL reputation: Google Safe Browsing → VirusTotal fallback ────────
    vt_malicious = vt_suspicious = 0
    gsb_flagged    = False
    gsb_threat_type = None
    gsb_attempted  = bool(urls and _gsb_key)
    vt_attempted   = False

    for url in urls[:3]:
        # GSB first
        flagged, threat = check_url_google_safebrowsing(url, _gsb_key)
        if flagged:
            gsb_flagged    = True
            gsb_threat_type = threat
            vt_malicious  += 1      # treat GSB hit as malicious for downstream rules
            continue                # skip VT for this URL — already condemned

        # VT fallback (only if GSB returned clean)
        if _vt_key:
            try:
                m, s, _ = check_url_virustotal(url, _vt_key)
                vt_malicious  += m
                vt_suspicious += s
                vt_attempted = True   # only mark attempted when call succeeds
                time.sleep(1)
            except Exception:
                pass  # VT error — falls back to "pattern analysis only"

    if urls and not gsb_attempted and not vt_attempted:
        warnings.append("URL reputation checks skipped — no API keys configured.")

    # ── 7. Feature extraction ─────────────────────────────────────────────
    # Tone on both texts: text_norm catches leet-speak, text_clean preserves
    # $ for currency-based reward patterns (normalize_leet converts $ → s).
    _tone_norm  = compute_tone_features(text_norm)
    _tone_clean = compute_tone_features(text_clean)
    tone = tuple(max(a, b) for a, b in zip(_tone_norm, _tone_clean))
    url_feat  = compute_url_features(text_norm)
    # text_clean preserves $, €, £ so currency_symbol_count is correct.
    new_feat  = compute_new_features(text_clean)
    scam_type = classify_scam_type(text_norm)

    # ── 8. TF-IDF transform ───────────────────────────────────────────────
    X_tfidf_new = tfidf.transform([text_norm])
    X_char_new  = char_tfidf.transform([text_norm])

    # ── 9. FAISS scam proximity ───────────────────────────────────────────
    emb = st_model.encode([text_norm], convert_to_numpy=True).astype('float32')
    faiss.normalize_L2(emb)
    D_scam, _ = scam_index.search(emb, k=FAISS_K_SCAM)
    prox_scam  = float(D_scam[0].mean())

    # ── 10. Numerical feature vector ──────────────────────────────────────
    #  legit_proximity_score and proximity_delta intentionally excluded —
    #  they caused false positives on legitimate corporate emails.
    raw_text = text_norm
    words    = raw_text.split()

    numerical = {
        'text_length':       len(raw_text),
        'word_count':        len(words),
        'has_url':           int(bool(urls)),
        'url_count':         len(urls),
        'exclamation_count': raw_text.count('!'),
        'uppercase_ratio':   sum(c.isupper() for c in raw_text) / max(len(raw_text), 1),
        'digit_ratio':       sum(c.isdigit() for c in raw_text) / max(len(raw_text), 1),
        'urgency_score':     tone[0],
        'tone_urgency':      tone[0],
        'tone_fear':         tone[1],
        'tone_reward':       tone[2],
        'tone_threat':       tone[3],
        'url_suspicious_tld':     url_feat[0],
        'url_suspicious_keyword': url_feat[1],
        'url_has_ip':             url_feat[2],
        **new_feat,
        'proximity_scam_score':   prox_scam * 0.5,  # ×0.5 — matches training scale
    }

    X_num_vec    = np.array([[numerical[f] for f in NUMERICAL_FEATURES_V5]])
    X_num_scaled = scaler.transform(X_num_vec)
    X_combined   = hstack([X_tfidf_new, X_char_new, csr_matrix(X_num_scaled)])

    # ── 11. Raw model probability ─────────────────────────────────────────
    prob = float(model.predict_proba(X_combined)[0][1])

    # ── 12. Trusted-domain bonus ──────────────────────────────────────────
    #  If every URL is from a known corporate domain and both APIs are clean,
    #  cap probability at 0.35 so it never crosses the threshold.
    if is_all_trusted_domains(urls) and (vt_malicious + vt_suspicious == 0) and not gsb_flagged:
        prob = min(prob, 0.35)

    # ── 12b. Legit-signal override ────────────────────────────────────────
    #  If a legit phrase is present AND every rule-based scam signal is silent
    #  (no urgency, fear, reward, threat, URL issues, scam phrases, impersonation),
    #  the message cannot be confidently SCAM — cap at 0.30 (below any threshold).
    _all_tone_zero   = tone[0] == 0 and tone[1] == 0 and tone[2] == 0 and tone[3] == 0
    _all_url_clean   = url_feat[0] == 0 and url_feat[1] == 0 and url_feat[2] == 0
    _no_scam_phrases = (new_feat.get('scam_phrase_score', 0) == 0 and
                        new_feat.get('sender_impersonation_score', 0) == 0)
    if (new_feat.get('legit_phrase_score', 0) >= 1 and
            _all_tone_zero and _all_url_clean and _no_scam_phrases and
            vt_malicious == 0):
        prob = min(prob, 0.30)

    # ── 12c. Investment-scam floor ────────────────────────────────────────
    #  ≥2 reward-pattern hits AND ≥2 currency symbols is an unambiguous
    #  investment / crypto scam signal.  Only applies when URLs are NOT all
    #  trusted (to avoid overcounting legitimate financial emails).
    if (tone[2] >= 2 and
            new_feat.get('currency_symbol_count', 0) >= 2 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)

    # ── 12d. Phrase-backed scam-type floor ───────────────────────────────
    #  Standard floor (threshold ≥ 2): type fires + scam_phrase_score ≥ 2.
    #  Low-threshold floor (threshold ≥ 1): highly-specific types whose
    #  phrases almost never appear in legitimate messages.
    _PHRASE_FLOOR_TYPES = frozenset({
        'romance_scam', 'advance_fee_scam', 'delivery_scam',
        'credential_phishing', 'emergency_scam',
        'bank_impersonation', 'threat_scam',
    })
    _PHRASE_FLOOR_TYPES_LOW = frozenset({
        'social_media_scam', 'investment_scam',
    })

    _phrase_score = new_feat.get('scam_phrase_score', 0)
    if (scam_type in _PHRASE_FLOOR_TYPES and
            _phrase_score >= 2 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)
    elif (scam_type in _PHRASE_FLOOR_TYPES_LOW and
            _phrase_score >= 1 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)

    # ── 12d2. General phrase floor ────────────────────────────────────────
    #  Any 2+ highly-specific scam phrases match regardless of classified type.
    if (_phrase_score >= 2 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)

    # ── 12d6. Investment scam tone floor ──────────────────────────────────
    #  investment_scam type + confirmed reward tone signal (even without a
    #  phrase match) is a reliable combined indicator.
    if (scam_type == 'investment_scam' and
            tone[2] >= 1 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)

    # ── 12d5. Suspicious URL + scam phrase combo floor ────────────────────
    #  A suspicious URL keyword + at least one matching scam phrase is a
    #  strong combined signal, even when the type classifier returns general_spam.
    if (url_feat[1] == 1 and
            _phrase_score >= 1 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)

    # ── 12d3. Lookalike-domain floor ─────────────────────────────────────
    #  detect_lookalike_domain() adds 2 to sender_impersonation_score when
    #  the hostname impersonates a brand or embeds a credential-harvesting
    #  action word.  Score ≥ 2 means at least one lookalike URL was found —
    #  that alone is enough to floor at 0.72 without needing phrase matches.
    #  The `not is_all_trusted_domains` guard prevents this from firing on
    #  legitimate subdomains like myaccount.google.com or appleid.apple.com.
    if (new_feat.get('sender_impersonation_score', 0) >= 2 and
            prob < 0.72 and
            not is_all_trusted_domains(urls)):
        prob = max(prob, 0.72)

    # ── 12e. OTP / verification-code guard ───────────────────────────────
    #  A 6-digit code (NNN-NNN or NNNNNN) combined with "do not share" is an
    #  unambiguous one-time-password message — cap well below any threshold.
    _has_6digit_code = bool(re.search(r'\b\d{3}[-\s]\d{3}\b|\b\d{6}\b', text_clean))
    _has_no_share    = 'do not share' in text_clean.lower()
    if _has_6digit_code and _has_no_share and vt_malicious == 0 and not gsb_flagged:
        prob = min(prob, 0.25)

    # ── 13. Confidence capping (never show 0 % or 100 %) ─────────────────
    conf_pct = round(max(2.0, min(98.0, prob * 100)), 2)

    # ── 14. Three-tier verdict ────────────────────────────────────────────
    if prob >= 0.60:
        verdict = "SCAM"
    elif prob >= threshold:
        verdict = "SUSPICIOUS"
    else:
        verdict = "LEGIT"

    # ── 15. Feature contributions ─────────────────────────────────────────
    contributions = {}
    if hasattr(model, 'coef_'):
        coef = np.array(model.coef_[0])
        n_tfidf = X_tfidf_new.shape[1]
        n_char  = X_char_new.shape[1]
        num_coef = coef[n_tfidf + n_char:]
        for i, feat in enumerate(NUMERICAL_FEATURES_V5):
            contributions[feat] = round(float(num_coef[i] * X_num_scaled[0][i]), 4)
    elif hasattr(model, 'feature_importances_'):
        n_tfidf = X_tfidf_new.shape[1]
        n_char  = X_char_new.shape[1]
        imp = model.feature_importances_[n_tfidf + n_char:]
        for i, feat in enumerate(NUMERICAL_FEATURES_V5):
            contributions[feat] = round(float(imp[i]), 4)

    return {
        'verdict':                verdict,
        'confidence':             conf_pct,
        'threshold_used':         threshold,
        'scam_type':              scam_type,
        'tone_urgency':           tone[0],
        'tone_fear':              tone[1],
        'tone_reward':            tone[2],
        'tone_threat':            tone[3],
        'url_suspicious_tld':     url_feat[0],
        'url_suspicious_keyword': url_feat[1],
        'url_has_ip':             url_feat[2],
        'scam_phrase_score':      new_feat['scam_phrase_score'],
        'sender_impersonation':   new_feat['sender_impersonation_score'],
        'proximity_score':        round(prox_scam, 4),
        'urls_found':             urls,
        'gsb_flagged':            gsb_flagged,
        'gsb_threat_type':        gsb_threat_type,
        'gsb_attempted':          gsb_attempted,
        'vt_malicious':           vt_malicious,
        'vt_suspicious':          vt_suspicious,
        'vt_attempted':           vt_attempted,
        'normalized_text':        text_norm,
        'feature_contributions':  contributions,
        'warnings':               warnings,
    }


# ── Standalone test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    VT_API_KEY = os.environ.get('VT_API_KEY') or None
    model, tfidf, char_tfidf, scaler, scam_idx, st_model = load_pipeline()
    threshold = DEFAULT_THRESHOLD

    tests = [
        "Hi Sarah, just a heads up that your annual membership auto-renews on May 1st. "
        "Since you've been with us for 3 years, we are locking in your current rate of $89/year. "
        "Nothing you need to do. Thanks for being a loyal member!",
        "URGENT: Your PayPal account has been suspended! Verify now at http://paypal-secure-verify.tk/login",
        "This email has been delivered from a send-only address. For more information visit "
        "https://www.playstation.com/support and https://www.playstation.com/network/legal/terms-of-service/",
    ]
    for msg in tests:
        r = predict_message(msg, model, tfidf, char_tfidf, scaler,
                            scam_idx, st_model, VT_API_KEY, legit_idx, threshold)
        print(f"\n{'─'*60}")
        print(f"Message : {msg[:80]}")
        print(f"Verdict : {r['verdict']} ({r['confidence']:.1f}%)  |  Type: {r['scam_type']}")
        print(f"Prox    : {r['proximity_score']:.3f}")
