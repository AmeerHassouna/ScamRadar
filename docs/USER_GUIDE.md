# ScamRadar+ User Guide

ScamRadar+ detects scam messages using AI — paste any suspicious text and get an instant verdict with a confidence score, threat label, and explanation.

Live site: **https://scamradarplus.com**

---

## Table of Contents

1. [Using the Web Interface](#1-using-the-web-interface)
   - [Single Message Analysis](#single-message-analysis)
   - [Conversation Analysis](#conversation-analysis)
   - [File Upload](#file-upload)
   - [Understanding the Results](#understanding-the-results)
2. [Using the API](#2-using-the-api)
   - [POST /predict](#post-predict)
   - [POST /analyze-conversation](#post-analyze-conversation)
   - [POST /analyze-conversation-file](#post-analyze-conversation-file)
   - [GET /health](#get-health)
   - [GET /stats](#get-stats)
3. [Tips for Best Results](#3-tips-for-best-results)
4. [Supported Channel Types](#4-supported-channel-types)
5. [Rate Limits](#5-rate-limits)
6. [FAQ](#6-faq)

---

## 1. Using the Web Interface

Open **https://scamradarplus.com** in any browser.

### Single Message Analysis

1. Type or paste a message into the text box in the hero section.
2. Press the **Send** button (or hit `Enter`).
3. Results appear below the input within a second or two.

**Example inputs:**

```
URGENT: Your bank account has been suspended. Click here to verify your details immediately or lose access.
```

```
Congratulations! You've been selected for a $1,000 Amazon gift card. Claim now: bit.ly/claim99
```

### Conversation Analysis

To analyse a multi-message conversation, switch to **Conversation** mode using the toggle above the text box. Paste a full conversation thread — the model uses a sliding-window approach to scan every segment of the conversation and highlights the most suspicious parts.

Format your conversation like this (one message per line, optionally prefixed with a speaker label):

```
Alice: Hey, I saw your listing on Facebook
Bob: Can I pay you via Zelle? I'll send extra for your trouble
Alice: Sure, how much extra?
Bob: Just $200 — send the item to my cousin's address first
```

### File Upload

Click the **Upload** icon below the text box to submit a `.txt`, `.log`, or `.csv` file (max 1 MB). The file is scanned as a plain-text conversation.

### Understanding the Results

| Field | Description |
|-------|-------------|
| **Label** | `SCAM` or `LEGIT` (binary — the production model does not emit a middle `SUSPICIOUS` tier) |
| **Confidence** | 0–100% — the model's scam probability, expressed as a percentage |
| **Threat type** | Phishing · Advance-fee fraud · Smishing · Recruitment scam · Investment scam · Romance scam · Marketplace scam · Delivery scam · Impersonation · General spam |
| **Signals** | Ancillary display fields — urgency, fear, reward, threat tone scores; URL structure; live URL reputation |

**Confidence bands:**

| Confidence | Interpretation |
|---|---|
| 0–40 | Highly unlikely to be a scam (well below the 0.59 decision threshold) |
| 40–59 | Borderline legit — treat with normal caution |
| 59–75 | Above the decision threshold — model classifies as SCAM |
| 75–100 | High-confidence scam |

The decision boundary is fixed at **confidence = 59** (the F1-optimal threshold on validation data — inherited from E5, unchanged through E7 and E8-P9).

**Dark / Light mode** — use the sun/moon toggle in the navigation bar.

---

## 2. Using the API

Base URL: `https://scamradar-api-l2vv.onrender.com`

All endpoints accept and return JSON. No authentication is required for the public endpoints.

> **Note:** The API is hosted on Render's free tier. The first request after a period of inactivity may take 30–60 seconds while the container wakes up. Subsequent requests are fast.

---

### POST /predict

Analyse a single message.

**Request**

```http
POST /predict
Content-Type: application/json
```

```json
{
  "text": "Your PayPal account has been limited. Log in at paypa1-support.com to restore access."
}
```

**Constraints:** `text` must be between 10 and 5 000 characters.

**Response**

```json
{
  "verdict": "SCAM",
  "confidence": 87.4,
  "threshold_used": 0.59,
  "scam_type": "phishing",
  "why_flagged": "The structure and language of this message closely match a phishing pattern.|Uses urgent language to pressure quick action.|Contains a suspicious or unusual link.",
  "tone_urgency": 2, "tone_fear": 1, "tone_reward": 0, "tone_threat": 0,
  "url_suspicious_tld": 1, "url_suspicious_keyword": 1, "url_has_ip": 0,
  "scam_phrase_score": 1, "sender_impersonation": 0, "proximity_score": 0.0,
  "urls_found": ["http://paypa1-support.com"],
  "gsb_flagged": false, "gsb_threat_type": null, "gsb_attempted": true,
  "vt_malicious": 0, "vt_suspicious": 0, "vt_attempted": true,
  "normalized_text": "your paypal account has been limited. log in at paypa1-support.com to restore access.",
  "feature_contributions": {},
  "warnings": []
}
```

Note: `confidence` is the final scam probability as a percentage (0–100), after both the ML classifier and the Rule Engine. `threshold_used` is the fixed decision threshold (0.59). `verdict` is one of `SCAM`, `SUSPICIOUS`, `LEGIT`, or `TOO_SHORT` — `SUSPICIOUS` is a borderline band between roughly 0.40 and 0.59 that is surfaced when a message trips ancillary signals (dangerous URL, untrusted domain, VirusTotal hit) without the ML crossing the SCAM threshold on its own.

**cURL example**

```bash
curl -X POST https://scamradar-api-l2vv.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "URGENT: Your account has been suspended. Click here to verify."}'
```

**Python example**

```python
import httpx

response = httpx.post(
    "https://scamradar-api-l2vv.onrender.com/predict",
    json={"text": "URGENT: Your account has been suspended. Click here to verify."}
)
print(response.json())
```

---

### POST /analyze-conversation

Analyse a full conversation thread. The API applies three methods in parallel:
- Full-conversation analysis
- Sliding-window segment scanning (window of 5 messages, 50% overlap)
- Final 30% of the conversation (scammers often escalate at the end)

Results are aggregated into a single verdict.

**Request**

```http
POST /analyze-conversation
Content-Type: application/json
```

```json
{
  "text": "Alice: I saw your ad on Craigslist\nBob: Yes still available\nAlice: Can I pay by cashier cheque?\nBob: Sure, send $300 extra for shipping"
}
```

**Constraints:** `text` must not exceed 100 000 characters.

**cURL example**

```bash
curl -X POST https://scamradar-api-l2vv.onrender.com/analyze-conversation \
  -H "Content-Type: application/json" \
  -d '{"text": "Alice: Hi\nBob: Send me your banking details to receive payment"}'
```

---

### POST /analyze-conversation-file

Upload a plain-text file for analysis.

**Accepted formats:** `.txt`, `.log`, `.csv`
**Max file size:** 1 MB
**Content-Type:** must be `text/plain` or `text/csv`

**cURL example**

```bash
curl -X POST https://scamradar-api-l2vv.onrender.com/analyze-conversation-file \
  -H "Content-Type: multipart/form-data" \
  -F "file=@conversation.txt;type=text/plain"
```

---

### GET /health

Check if the API is running and get cache statistics.

```bash
curl https://scamradar-api-l2vv.onrender.com/health
```

```json
{
  "status": "ready",
  "model": "ScamRadar+ (E8-P9)",
  "predict_cached": 142,
  "predict_maxsize": 10000,
  "predict_ttl_s": 3600,
  "url_cached": 22,
  "url_maxsize": 50000,
  "url_ttl_s": 86400
}
```

---

### GET /stats

Returns training corpus statistics and the deployed model's external-validation metrics.

```bash
curl https://scamradar-api-l2vv.onrender.com/stats
```

```json
{
  "deployed_model":              "ScamRadar+ (E8-P9)",
  "model_architecture":          "Logistic Regression + word/char TF-IDF (500,000 text features) + 25 numerical features + modular Rule Engine",
  "training_corpus_raw":         283501,
  "training_corpus_dedup":       195776,
  "channels":                    4,
  "scam_types":                  12,
  "features":                    500025,
  "external_eval_size":          25306,
  "external_accuracy":           0.9687,
  "external_precision":          0.9102,
  "external_recall":             0.9160,
  "external_f1":                 0.9131,
  "external_baseline_f1":        0.9414,
  "external_baseline_precision": 0.9605,
  "external_baseline_recall":    0.9230,
  "external_baseline_roc_auc":   0.9950,
  "external_baseline_pr_auc":    0.9839,
  "threshold":                   0.59,
  "evaluation_note":             "External metrics measured on a locked one-shot benchmark of 25,306 messages held out from all model selection, tuning, and threshold optimisation. Production numbers include the Rule Engine; baseline numbers are the pure classifier for reference."
}
```

---

## 3. Tips for Best Results

- **Include full context.** A complete message gives the model more signals than a fragment. `"Click here"` alone won't trigger detection; `"Your bank account is suspended — click here to verify: bit.ly/bankfix"` will.
- **Paste URLs as-is.** Don't strip links from messages — URL risk is one of the strongest signals.
- **Use Conversation mode for chat threads.** Single-message mode analyses text in isolation; conversation mode catches escalation patterns that only appear across multiple turns.
- **Don't paraphrase.** Run the original text, not a summary. The model reads tone, character patterns, and specific phrasing.
- **Short messages are harder.** Messages under ~20 characters have less signal. Add surrounding context when possible.

---

## 4. Supported Channel Types

| Channel | Examples |
|---------|---------|
| **SMS** | Bank alerts, OTP requests, prize notifications, delivery phishing |
| **Email** | PayPal/Amazon/HMRC phishing, job scams, advance-fee fraud |
| **URL** | Suspicious links, typosquatting domains, shortened URLs |
| **Social media / Reddit** | Crypto giveaways, romance scams, fake investment groups |

---

## 5. Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/predict` | 30 requests / minute |
| `/analyze-conversation` | 20 requests / minute |
| `/analyze-conversation-file` | 20 requests / minute |
| `/stats` | 30 requests / minute |

Exceeding the limit returns HTTP `429 Too Many Requests`. Wait 60 seconds and retry.

---

## 6. FAQ

**Q: Why does the first request take so long?**
The API runs on Render's free tier, which spins down containers after inactivity. The first request after a cold start can take up to 60 seconds. Subsequent requests are instant.

**Q: Is my message stored or logged?**
Messages are cached in memory for performance (so repeated identical inputs return instantly). The cache is cleared when the server restarts. No messages are written to disk or sent to third parties beyond URL scanning (VirusTotal / Google Safe Browsing) when a URL is detected.

**Q: What languages are supported?**
The model was trained primarily on English text and performs best on English. Detection quality may be lower for other languages.

**Q: Can I use the API in my own project?**
Yes — the API is public and unauthenticated. Please respect the rate limits. For high-volume use, consider self-hosting using the provided Dockerfile.

**Q: How do I run it locally?**
See [README.md](README.md) for full local setup instructions.

**Q: The result seems wrong — what should I do?**
On the locked one-shot external benchmark (n = 25,306), the pure ML classifier scores F1 = 0.941; the full production pipeline (E8-P9, classifier + rule engine) scores F1 = 0.913. Either way, roughly 3–9% of messages will be misclassified. For borderline cases (confidence 40–75), treat the result as a prompt to investigate further rather than a definitive verdict. This tool is designed to *assist* your judgement, not replace it.

**Q: What are the model's honest performance limits?**
On the 25,306-item external benchmark, the production E8-P9 build gets recall = 0.916 (misses ~8% of scams) and precision = 0.910 (~9% of items flagged as scam are actually legitimate). The weakest single scam class remains recruitment scams (recall 0.48) — if a message reads like a recruiter and the offer feels off, verify through official company channels regardless of the verdict. E8-P9 also trades a small amount of legacy-legit-email precision (ham_email FP rate 3.22% → 8.30%) for meaningfully better coverage of modern conversational / investment / romance / threat scams that the 2008-era external benchmark doesn't measure. Full per-category numbers are in [README.md](../README.md) → Performance.
