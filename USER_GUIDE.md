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
| **Label** | `SCAM` or `LEGIT` |
| **Confidence** | 0–100% — how certain the model is |
| **Risk Score** | Gauge from 0 (safe) to 100 (definite scam) |
| **Threat type** | Phishing · Crypto scam · OTP fraud · Fake prize · Impersonation |
| **Signals** | Which features triggered — urgency, URL risk, tone, similarity |

**Score thresholds:**

| Score | Interpretation |
|-------|----------------|
| 0–25 | Likely legitimate |
| 26–50 | Low suspicion — proceed with caution |
| 51–74 | Suspicious — treat as potentially fraudulent |
| 75–100 | High confidence scam |

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
  "label": "SCAM",
  "confidence": 0.97,
  "score": 94.2,
  "threat_type": "Phishing",
  "signals": {
    "urgency": true,
    "url_risk": true,
    "tone_fear": true,
    "vector_proximity": 0.91
  }
}
```

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
  "status": "ok",
  "model": "ScamRadar+ v5",
  "cache_hits": 142,
  "cache_size": 38
}
```

---

### GET /stats

Returns dataset statistics used to train the model.

```bash
curl https://scamradar-api-l2vv.onrender.com/stats
```

```json
{
  "total_messages": 45851,
  "scam_messages": 21955,
  "legit_messages": 23896,
  "channels": 4
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
The model has a 97.76% accuracy on its test set, which means roughly 1 in 40 predictions may be incorrect. For borderline cases (score 40–60), treat the result as a prompt to investigate further rather than a definitive verdict.
