# ScamRadar+ User Guide

ScamRadar+ detects scam messages using AI — paste any suspicious text and get an instant verdict with a confidence score, threat label, and explanation.

**Live site:** [https://scamradarplus.com](https://scamradarplus.com)
**Hosted API:** [https://scamradar-api-l2vv.onrender.com](https://scamradar-api-l2vv.onrender.com)

This guide covers everything a user or developer needs: installing the system, running each component locally, using the hosted product, and reproducing the model and evaluation.

---

## Table of Contents

**Setup and local run**

1. [Installation & Configuration](#1-installation--configuration)
2. [Running the API Locally](#2-running-the-api-locally)
3. [Running the Web Application Locally](#3-running-the-web-application-locally)
4. [Using the Browser Extension](#4-using-the-browser-extension)
5. [Reproducing the Model and Evaluation Artifacts](#5-reproducing-the-model-and-evaluation-artifacts)

**Using the deployed system**

6. [Using the Web Interface](#6-using-the-web-interface)
7. [Using the API](#7-using-the-api)
8. [Tips for Best Results](#8-tips-for-best-results)
9. [Supported Channel Types](#9-supported-channel-types)
10. [Rate Limits](#10-rate-limits)
11. [FAQ](#11-faq)

---

# Setup and local run

## 1. Installation & Configuration

### 1.1 Prerequisites

- **Python 3.11** or newer.
- **Node.js 20** or newer (for the web frontend).
- **Google Chrome 116+** (for the browser extension — optional).
- **git** to clone the repository.

### 1.2 Clone the repository

```bash
git clone https://github.com/AmeerHassouna/ScamRadar.git
cd ScamRadar
```

### 1.3 Python environment

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1.4 Environment variables

Copy the template and fill in optional API keys:

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Required? | Purpose |
|---|---|---|
| `VIRUSTOTAL_API_KEY` | optional | Enables VirusTotal URL reputation checks on URLs found in messages. |
| `GOOGLE_SAFEBROWSING_API_KEY` | optional | Enables Google Safe Browsing checks on those URLs. |
| `ALLOWED_ORIGINS` | optional | Comma-separated list of frontends allowed to call the API (defaults to `http://localhost:3000`). |

Neither URL-scanning key is required — the classifier works without them and simply reports "GSB / VT not attempted" in the response.

### 1.5 Verify the installation

```bash
make help
```

You should see a categorised list of developer commands (`setup`, `api`, `web`, `train`, `bakeoff`, `eval`, `summary`, `notebooks`, `test`, `deploy`, `clean`). All subsequent sections use these Makefile targets as shorthand.

---

## 2. Running the API Locally

### 2.1 Start the server

```bash
make api
# — or equivalently —
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

On startup, the API loads the deployed E8-P9 model bundle from `models/e7_p1_variants/e7_p1_full_e8p9.joblib`.

To load a different model variant, set the `SCAMRADAR_LOCAL_MODEL` environment variable to any bundle name under `models/e7_p1_variants/` (for example, `e7_p1_full` for the pre-E8 baseline). Setting it to an unknown value falls back to the E5 bundle at `models/e5_bundle.joblib`.

### 2.2 Confirm the API is running

Once the server prints `Pipeline loaded`, verify:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status":          "ready",
  "model":           "ScamRadar+ (E8-P9)",
  "predict_cached":  0,
  "predict_maxsize": 10000,
  "predict_ttl_s":   3600
}
```

### 2.3 Score a message end-to-end

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "URGENT: Your account has been suspended. Click here to verify."}'
```

The full endpoint reference is in Section 7.

---

## 3. Running the Web Application Locally

The frontend is a Next.js 16 application (App Router, TypeScript, Tailwind, Recharts).

### 3.1 Install dependencies

```bash
cd web
npm install
```

### 3.2 Point the frontend at your local API

```bash
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
```

If you leave `NEXT_PUBLIC_API_URL` unset, the frontend defaults to `http://localhost:8000` when running in development mode.

### 3.3 Start the dev server

```bash
npm run dev
# — or from the repo root —
make web
```

The frontend is now available at [http://localhost:3000](http://localhost:3000). It calls the API you started in Section 2. Both must be running.

### 3.4 Available pages

- `/` — landing page with the interactive prediction input.
- `/performance` — model performance dashboard (accuracy, precision, recall, F1, ROC-AUC, PR-AUC, ECE, confusion matrix, per-category charts, ROC curve, dataset composition).
- `/team` — team page.
- `/privacy`, `/terms` — legal.

---

## 4. Using the Browser Extension

An optional Chrome extension lets you analyse any highlighted text on any web page without leaving that page.

> The extension is a **local prototype** — it only talks to a locally-running API at `http://127.0.0.1:8000`. It does not send data to the hosted production API. Complete the API setup in Section 2 before loading the extension.

### 4.1 Load the extension into Chrome

1. Open `chrome://extensions/`.
2. Toggle **Developer mode** on (top-right).
3. Click **Load unpacked**.
4. Select the `extension/` folder in this repo.
5. Optionally pin the ScamRadar+ icon to the toolbar.

### 4.2 Analyse text on any page

1. Go to any webpage (email, forum, article, DM…).
2. Highlight the suspicious text (between 20 and 5,000 characters).
3. Right-click on the highlight.
4. Choose **Analyze with ScamRadar+** from the context menu.
5. A floating card appears in the top-right of the page showing:
   - A colour-coded verdict (LEGIT / SUSPICIOUS / SCAM)
   - Confidence percentage and scam type
   - The reasons the model flagged the text
   - Signal intensities (urgency / fear / reward / threat)
   - Any URLs found and whether they are flagged

Click the toolbar icon at any time to see whether the local API is reachable.

### 4.3 Privacy guarantees

- The extension only reads the exact text you highlight and pass through the context menu. It never reads the DOM, form fields, cookies, tabs, history, or URLs.
- Nothing is injected into any page unless you explicitly invoke the context menu item.
- The only network destination is `http://127.0.0.1:8000` (or `http://localhost:8000`) — no analytics, no telemetry, no third-party calls.

Full architecture and permission details are in `extension/README.md`.

---

## 5. Reproducing the Model and Evaluation Artifacts

The deployed E8-P9 model is fully reproducible from the scripts in this repository. The following Makefile targets cover the common developer workflows:

```bash
make train        # Train the deployed E8-P9 classifier bundle
make bakeoff      # Run the final classifier bake-off (LR vs LinearSVC vs SGD)
make eval         # Re-score the external benchmark end-to-end
make summary      # Rebuild consolidated evaluation summary (fast, aggregation only)
make notebooks    # Execute all four CRISP-DM notebooks end-to-end
```

### 5.1 Notebook layer

The `notebooks/` directory contains the four CRISP-DM notebooks (Data Understanding, Data Preparation, Modeling, Evaluation). Each notebook is a presentation layer over the production scripts — it invokes a `cached_step` helper that runs the underlying script only if the required artifacts are missing on disk.

Execute all four notebooks end-to-end:

```bash
make notebooks
```

Or open a single notebook in Jupyter:

```bash
jupyter notebook notebooks/evaluation.ipynb
```

Every table, plot, and metric in the notebooks is generated from persisted artifacts in `outputs/eval/` or `models/`. Nothing is retrained inside the notebooks.

### 5.2 Evaluation artifacts

After `make summary` and `make bakeoff` complete, the following consolidated artifacts are written to `outputs/eval/`:

| Artifact | Contents |
|---|---|
| `master_summary.json`/`.csv` | One row per stage of the modelling programme (E2 through E8-P9), with winner, primary-metric value, and evidence artifact. |
| `e8p9_findings.md` | Formal Evaluation-phase document: deployed-model card, external headline (both raw classifier and full deployed pipeline), alternative-classifier comparison, conclusions, discovered issues, known limitations. |
| `e8p9_bakeoff_results.json`/`.csv` | Full metric matrix for the three-classifier bake-off (Logistic Regression vs LinearSVC vs SGD) on identical features. |
| `e8p9_per_item.parquet` | Per-item predictions of the deployed pipeline on all 25,306 external-benchmark records. |

---

# Using the deployed system

## 6. Using the Web Interface

Open **[https://scamradarplus.com](https://scamradarplus.com)** in any browser.

### 6.1 Single message analysis

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

### 6.2 Conversation analysis

To analyse a multi-message conversation, switch to **Conversation** mode using the toggle above the text box. Paste a full conversation thread — the model uses a sliding-window approach to scan every segment of the conversation and highlights the most suspicious parts.

Format your conversation like this (one message per line, optionally prefixed with a speaker label):

```
Alice: Hey, I saw your listing on Facebook
Bob: Can I pay you via Zelle? I'll send extra for your trouble
Alice: Sure, how much extra?
Bob: Just $200 — send the item to my cousin's address first
```

### 6.3 File upload

Click the **Upload** icon below the text box to submit a `.txt`, `.log`, or `.csv` file (max 1 MB). The file is scanned as a plain-text conversation.

### 6.4 Understanding the results

| Field | Description |
|-------|-------------|
| **Label** | `SCAM` / `SUSPICIOUS` / `LEGIT` — `SUSPICIOUS` is a borderline band between roughly 0.40 and 0.59 confidence that trips when ancillary signals fire (dangerous URL, untrusted domain, VirusTotal hit) without the classifier crossing the SCAM threshold alone. |
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

### 6.5 Performance dashboard

Visit **[/performance](https://scamradarplus.com/performance)** for the full model-performance dashboard: stat cards for Accuracy / Precision / Recall / F1 / ROC-AUC / PR-AUC / ECE, an interactive ROC curve, confusion matrix, per-scam-category recall bars, dataset composition, and a timeline of the E-series iterations that led to the deployed model.

### 6.6 Dark / Light mode

Use the sun/moon toggle in the navigation bar.

---

## 7. Using the API

**Hosted base URL:** `https://scamradar-api-l2vv.onrender.com`
**Local base URL:** `http://127.0.0.1:8000` (after Section 2)

All endpoints accept and return JSON. No authentication is required for the public endpoints.

> **Note:** The hosted API runs on Render's free tier. The first request after a period of inactivity may take 30–60 seconds while the container wakes up. Subsequent requests are fast.

### 7.1 `POST /predict`

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

**Constraints:** `text` must be between 20 and 5,000 characters.

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

`confidence` is the final scam probability as a percentage (0–100), after both the ML classifier and the Rule Engine. `threshold_used` is the fixed decision threshold (0.59). `verdict` is one of `SCAM`, `SUSPICIOUS`, `LEGIT`, or `TOO_SHORT`.

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

### 7.2 `POST /analyze-conversation`

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

**Constraints:** `text` must not exceed 100,000 characters.

**cURL example**

```bash
curl -X POST https://scamradar-api-l2vv.onrender.com/analyze-conversation \
  -H "Content-Type: application/json" \
  -d '{"text": "Alice: Hi\nBob: Send me your banking details to receive payment"}'
```

### 7.3 `POST /analyze-conversation-file`

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

### 7.4 `GET /health`

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

### 7.5 `GET /stats`

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

## 8. Tips for Best Results

- **Include full context.** A complete message gives the model more signals than a fragment. `"Click here"` alone won't trigger detection; `"Your bank account is suspended — click here to verify: bit.ly/bankfix"` will.
- **Paste URLs as-is.** Don't strip links from messages — URL risk is one of the strongest signals.
- **Use Conversation mode for chat threads.** Single-message mode analyses text in isolation; conversation mode catches escalation patterns that only appear across multiple turns.
- **Don't paraphrase.** Run the original text, not a summary. The model reads tone, character patterns, and specific phrasing.
- **Short messages are harder.** Messages under ~20 characters have less signal. Add surrounding context when possible.

---

## 9. Supported Channel Types

| Channel | Examples |
|---------|---------|
| **SMS** | Bank alerts, OTP requests, prize notifications, delivery phishing |
| **Email** | PayPal/Amazon/HMRC phishing, job scams, advance-fee fraud |
| **URL** | Suspicious links, typosquatting domains, shortened URLs |
| **Social media / Reddit** | Crypto giveaways, romance scams, fake investment groups |

---

## 10. Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/predict` | 30 requests / minute |
| `/analyze-conversation` | 20 requests / minute |
| `/analyze-conversation-file` | 20 requests / minute |
| `/stats` | 30 requests / minute |

Exceeding the limit returns HTTP `429 Too Many Requests`. Wait 60 seconds and retry.

---

## 11. FAQ

**Q: Why does the first request take so long?**
The hosted API runs on Render's free tier, which spins down containers after inactivity. The first request after a cold start can take up to 60 seconds. Subsequent requests are instant. Local runs are unaffected.

**Q: Is my message stored or logged?**
Messages are cached in memory for performance (so repeated identical inputs return instantly). The cache is cleared when the server restarts. No messages are written to disk or sent to third parties beyond URL scanning (VirusTotal / Google Safe Browsing) when a URL is detected.

**Q: What languages are supported?**
The model was trained on English text; non-English input is rejected at the API boundary with HTTP `400`.

**Q: Can I use the API in my own project?**
Yes — the hosted API is public and unauthenticated. Please respect the rate limits (Section 10). For high-volume use, self-host using the provided Dockerfile.

**Q: How do I run it locally?**
See Sections 1–3 above for local setup, and Section 4 for the browser extension.

**Q: How do I reproduce the model?**
See Section 5. `make train` produces the deployed bundle; `make bakeoff` runs the classifier comparison; `make summary` rebuilds the consolidated evaluation artifacts. All four CRISP-DM notebooks execute against the produced artifacts.

**Q: The result seems wrong — what should I do?**
On the locked one-shot external benchmark (n = 25,306), the pure ML classifier scores F1 = 0.941; the full production pipeline (E8-P9, classifier + rule engine) scores F1 = 0.913. Either way, roughly 3–9% of messages will be misclassified. For borderline cases (confidence 40–75), treat the result as a prompt to investigate further rather than a definitive verdict. This tool is designed to *assist* your judgement, not replace it.

**Q: What are the model's honest performance limits?**
On the 25,306-item external benchmark, the production E8-P9 build gets recall = 0.916 (misses ~8% of scams) and precision = 0.910 (~9% of items flagged as scam are actually legitimate). The weakest single scam class remains recruitment scams (recall 0.48) — if a message reads like a recruiter and the offer feels off, verify through official company channels regardless of the verdict. E8-P9 also trades a small amount of legacy-legit-email precision (ham_email FP rate 3.22% → 8.30%) for meaningfully better coverage of modern conversational / investment / romance / threat scams that the 2008-era external benchmark doesn't measure. Full per-category numbers are in [README.md](../README.md) → Performance.
