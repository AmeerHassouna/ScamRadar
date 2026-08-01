<div align="center">

# ScamRadar+

**AI-powered scam detection for SMS, email, and chat messages.**

Paste any suspicious text — get a calibrated verdict, confidence score, and rationale in under a second.
No account. No message storage. No tracking.

*Final Year BSc Project — Information Systems, Emek Yezreel Academic College, 2026.*
*Team: Ameer Hassouna & Moatasem Khalifeh · Supervisor: Hanan Lev*

[![Live site](https://img.shields.io/badge/live-scamradarplus.com-22c55e?style=flat-square)](https://scamradarplus.com)
[![API](https://img.shields.io/badge/API-Render-22c55e?style=flat-square)](https://scamradar-api-l2vv.onrender.com/health)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/next.js-16-000000?style=flat-square&logo=nextdotjs)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-f7931e?style=flat-square&logo=scikitlearn)](https://scikit-learn.org/)
[![Model](https://img.shields.io/badge/model-E5%20%C2%B7%20F3%20LogReg-6366f1?style=flat-square)](models/e5_metadata.json)
[![External F1](https://img.shields.io/badge/F1%20external%20(n%3D25%2C306)-0.941-brightgreen?style=flat-square)](models/e5_metadata.json)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](#license)

</div>

---

## What it does

ScamRadar+ classifies a single message — email, SMS, chat, or job posting — as **SCAM** or **LEGIT** using a text classifier trained on 253,264 real messages. It also runs optional URL reputation checks (Google Safe Browsing, VirusTotal) and produces a human-readable rationale of the signals that led to the verdict.

- Paste a message → get a verdict + confidence + rationale
- Analyse a full conversation → overall risk score plus per-message breakdown
- Stateless: no accounts, no cookies, no message retention

## Try it now

**[scamradarplus.com](https://scamradarplus.com)** — paste any suspicious message.

---

## Table of contents

- [Live production system](#live-production-system)
- [Performance](#performance)
  - [Internal test](#internal-test-n--34194)
  - [External benchmark](#external-benchmark-n--25306)
  - [Per-category recall & FP rate](#per-category-recall--false-positive-rate-external-benchmark)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Local development](#local-development)
- [Deployment](#deployment)
- [API](#api)
- [Data sources](#data-sources)
- [Limitations & responsible use](#limitations--responsible-use)
- [Historical context (v1.x → E5)](#historical-context-v1x--e5)
- [Team & acknowledgements](#team--acknowledgements)
- [License](#license)

---

## Live production system

The production model is codename **E5** (5th major experiment in the ScamRadar+ 2.0 research campaign).

| | Verified value | Source |
|---|---|---|
| **Model** | Calibrated Logistic Regression on word + character TF-IDF (500,000 features) | [`models/e5_metadata.json`](models/e5_metadata.json) |
| **Feature set** | F3 — word 1-2 grams (200k) · character 3-6 grams (300k) · sublinear TF | `e5_metadata.json` → `e4_best_params` |
| **Calibration** | none (already well-calibrated: ECE 0.012, Brier 0.012) | `e5_metadata.json` → `e5_calibration_winner` |
| **Decision threshold** | **0.59** (F1-max on validation) | [`config.py`](config.py) `E5_THRESHOLD` |
| **Training corpus** | 253,264 messages (41,905 scam / 211,359 legit) · 195,776 unique clusters after deduplication | dataset audit |
| **Real vs synthetic** | 251,766 real (99.4%) · 1,498 synthetic (0.6%) | dataset audit |
| **Data sources** | 14 documented public corpora with URLs + licenses. No Kaggle. | [Data sources](#data-sources) |
| **Model size on disk** | 22.6 MB | model artifact |
| **Inference latency** | Sub-millisecond on the classifier (batch=1 mean 0.68 ms, p95 1.86 ms) | `e5_metadata.json` → `latency_ms` |

---

## Performance

All metrics below are **verified from E5's own evaluation artifacts** ([`models/e5_metadata.json`](models/e5_metadata.json)). No historical numbers, no estimates.

### Internal test (n = 34,194)

The internal test slice is a cluster-aware, held-out portion of the training corpus (no leakage: rows are split at the cluster level, not the row level, so near-duplicates cannot cross the boundary).

| Metric | Value |
|---|---:|
| Accuracy | **0.986** |
| Precision | **0.956** |
| Recall | **0.931** |
| **F1** | **0.943** |
| ROC-AUC | 0.997 |
| PR-AUC | 0.984 |
| Expected Calibration Error (ECE) | 0.012 |
| Brier score | 0.012 |

Confusion matrix: TN = 29,595 · FP = 187 · FN = 306 · TP = 4,106.

### External benchmark (n = 25,306)

A **locked, one-shot, write-once** benchmark set. Never seen during model selection, hyperparameter search, calibration, or threshold tuning. Every scoring event is recorded in the research repository's `data/external_benchmark/LOCK.json` — by design this benchmark can only be scored once per bundle.

| Metric | Value |
|---|---:|
| Accuracy | **0.979** |
| Precision | **0.961** |
| Recall | **0.923** |
| **F1** | **0.941** |
| ROC-AUC | 0.995 |
| PR-AUC | 0.984 |

### Per-category recall & false-positive rate (external benchmark)

Real-world performance broken down by the *kind* of message, not by dataset name.

| Category | n | Metric | Value |
|---|---:|---|---:|
| Email phishing | 2,178 | Recall | **0.957** |
| Email spam | 1,719 | Recall | **0.934** |
| Smishing (SMS phishing) | 68 | Recall | **0.853** |
| Advance-fee fraud (419-style) | 489 | Recall | **0.812** |
| Recruitment scam | 81 | Recall | 0.494 |
| Legitimate chat | 13,794 | False-positive rate | **0.007%** |
| Legitimate job posting | 1,523 | False-positive rate | 0.72% |
| Legitimate SMS | 802 | False-positive rate | 1.25% |
| Legitimate email | 4,652 | False-positive rate | 3.22% |

Recruitment scams are the weakest single class — recall 0.494 reflects the genuine linguistic overlap between scam recruiter outreach and legitimate recruiter outreach at first-message register. Improving this is on the roadmap.

### Threshold sweep (external benchmark)

The production system uses threshold **0.59**. Alternative operating points if you need more precision or more recall:

| Threshold | Precision | Recall | F1 |
|---:|---:|---:|---:|
| 0.30 | 0.902 | 0.956 | 0.928 |
| 0.40 | 0.928 | 0.944 | 0.936 |
| 0.50 | 0.948 | 0.935 | 0.942 |
| **0.59** | **0.961** | **0.923** | **0.941** |
| 0.70 | 0.971 | 0.907 | 0.938 |
| 0.77 | 0.980 | 0.881 | 0.928 |
| 0.90 | 0.989 | 0.840 | 0.908 |

Full sweep in [`models/e5_threshold_sweep.json`](models/e5_threshold_sweep.json).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend — Next.js 16 static export → GitHub Pages              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Paste message · single or conversation mode               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────────────────┘
                       │  HTTPS POST /predict {text}
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  API — FastAPI on Render (Docker)                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Rate-limit · language detect (langdetect) · LRU cache     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  E5 sklearn Pipeline                                       │  │
│  │  FeatureUnion(word 1-2gram + char 3-6gram TF-IDF)          │  │
│  │            ↓                                               │  │
│  │  Logistic Regression (L2, C=5.97, class_weight=balanced)   │  │
│  │            ↓                                               │  │
│  │  P(SCAM) — threshold 0.59 → verdict SCAM / LEGIT           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Ancillary analysis (display-only — never modifies verdict)│  │
│  │  · Scam-type classifier (rule-based)                       │  │
│  │  · Tone signals (urgency · fear · reward · threat)         │  │
│  │  · URL extraction + Google Safe Browsing + VirusTotal      │  │
│  │  · Human-readable rationale ("why flagged")                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────────────────┘
                       │  JSON response
                       ▼
                    Frontend
```

The classifier is self-contained inside a single 22.6 MB joblib bundle. Ancillary analysis enriches the response with URL scans and tone signals but never influences the SCAM / LEGIT verdict.

---

## Project structure

```
ScamRadar/
├── api/                       # FastAPI backend (routes, cache, rate limits)
│   ├── main.py                # /predict · /analyze-conversation · /health
│   └── cache.py               # LRU cache for repeat requests
├── src/
│   ├── e5_inference.py        # E5 wrapper — pure inference, parity-contracted
│   ├── _02_feature_engineering.py  # tone · URL · scam-type helpers (ancillary)
│   └── _09_prediction_pipeline.py  # legacy code + E5 shim (adapter for api/)
├── models/
│   ├── e5_bundle.joblib       # ← THE PRODUCTION MODEL (loaded at API startup)
│   ├── e5_metadata.json       # Full metrics · hyperparameters · thresholds
│   └── e5_threshold_sweep.json # Precision / recall / F1 across thresholds
├── web/                       # Next.js 16 frontend → scamradarplus.com
│   ├── app/                   # App Router pages (/, /performance, /team, …)
│   └── components/ui/         # UI components
├── config.py                  # E5_BUNDLE_PATH · E5_THRESHOLD · paths
├── tests/
│   └── e5_parity_test.py      # Byte-identical parity vs standalone E5
├── docs/
│   └── USER_GUIDE.md          # End-user documentation
├── outputs/                   # Historical v1.x research reports (kept as-is)
├── scripts/                   # Historical training + evaluation scripts
│   ├── training/
│   ├── evaluation/
│   └── data_prep/
├── legacy/                    # Superseded top-level entry points
├── old_models/                # v1.x model artifacts (reference only)
├── Dockerfile                 # Production container (Render)
├── Procfile                   # Alternate start command (Heroku-style)
├── railway.toml               # Railway platform config (alternate host)
├── runtime.txt                # Python 3.11.9
└── requirements.txt           # Python dependencies
```

The E5 model was trained in a separate research repository (**ScamRadar+ 2.0**) using a strict data-first workflow with an approval-gated dataset audit. The final artifact (`E5_final_logreg_F3.joblib`) is what ships here as `models/e5_bundle.joblib`. Behavior is byte-identical to the standalone research artifact — verified in [`tests/e5_parity_test.py`](tests/e5_parity_test.py) (13 diverse messages, probability parity to within numerical rounding tolerance).

---

## Local development

### Run the API locally

```bash
# 1. Python environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Optional API keys (URL scanning is optional — the classifier works without them)
cp .env.example .env
# Edit .env → VIRUSTOTAL_API_KEY, GOOGLE_SAFEBROWSING_API_KEY if desired

# 3. Start the API (loads models/e5_bundle.joblib on startup)
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Endpoints then live at `http://127.0.0.1:8000` — see `/health`, `POST /predict`, `POST /analyze-conversation`.

### Run the frontend locally

```bash
cd web
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
```

Frontend at `http://localhost:3000` — points at the local API you started above.

### Verify E5 parity

The parity harness confirms that the API produces byte-identical probabilities and verdicts to the standalone E5 research artifact:

```bash
# Requires the local API running on port 8000
python tests/e5_parity_test.py
# → Probability parity: 13/13
# → Verdict parity:     13/13
```

---

## Deployment

- **API** — Docker container on [Render](https://render.com/), auto-deployed from `main`. The `Dockerfile` bundles the E5 artifact directly (`COPY . .`). The container fits comfortably under Render's 512 MB memory limit.
- **Frontend** — Next.js static export (`output: 'export'`), built and deployed via GitHub Actions to GitHub Pages ([`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)) at [scamradarplus.com](https://scamradarplus.com).

| File | Role |
|---|---|
| `Dockerfile` | Python 3.11 slim container for the API |
| `Procfile` | Alternate start command (Heroku-compatible) |
| `railway.toml` | Railway platform config (alternate host) |
| `runtime.txt` | Pins Python 3.11.9 |
| `.github/workflows/deploy.yml` | Builds `web/` and publishes static export to GitHub Pages |

**No secrets are required for the classifier itself.** `VIRUSTOTAL_API_KEY` and `GOOGLE_SAFEBROWSING_API_KEY` are optional — if unset, URL scanning is skipped and those response fields are neutral, but the SCAM / LEGIT verdict is unaffected.

---

## API

**Production base URL:** `https://scamradar-api-l2vv.onrender.com`

### `POST /predict`

Analyse a single message.

**Request**
```json
{ "text": "URGENT: Your account has been suspended. Verify now at http://bit.ly/verify" }
```

**Response** (25 fields — verdict + confidence + tone + URL analysis + rationale)
```json
{
  "verdict": "SCAM",
  "confidence": 99.83,
  "threshold_used": 0.59,
  "scam_type": "phishing",
  "why_flagged": "The structure and language of this message closely match a phishing pattern.|Uses urgent language to pressure quick action.|Contains a suspicious or unusual link.",
  "tone_urgency": 2, "tone_fear": 0, "tone_reward": 0, "tone_threat": 0,
  "url_suspicious_tld": 0, "url_suspicious_keyword": 0, "url_has_ip": 0,
  "scam_phrase_score": 1, "sender_impersonation": 0, "proximity_score": 0.0,
  "urls_found": ["http://bit.ly/verify"],
  "gsb_flagged": false, "gsb_threat_type": null, "gsb_attempted": true,
  "vt_malicious": 0, "vt_suspicious": 0, "vt_attempted": true,
  "normalized_text": "urgent: your account has been suspended. verify now at shorturl",
  "feature_contributions": {},
  "warnings": []
}
```

### Other endpoints

| Method | Path | Purpose | Rate limit |
|---|---|---|---|
| `POST` | `/predict` | Single-message analysis | 30/min |
| `POST` | `/analyze-conversation` | Multi-message conversation analysis (WhatsApp/iMessage/plain) | 20/min |
| `POST` | `/analyze-conversation-file` | Upload a `.txt` / `.csv` transcript | 10/min |
| `GET` | `/health` | Readiness + cache stats | 120/min |
| `GET` | `/warmup` | Keep the pipeline warm | 30/min |
| `GET` | `/stats` | Corpus + evaluation summary | 30/min |

Full request/response details: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

---

## Data sources

Every source is publicly available and documented with a URL + license. **No Kaggle data.**

| Corpus | Label | Platform | Era |
|---|---|---|---|
| UCI SMS Spam Collection (via GitHub mirror) | mixed | SMS | legacy |
| Nazario phishing (Zenodo `8339691`, legacy) | scam | email | legacy |
| Nazario phishing (Zenodo `8339691`, modern refresh) | scam | email | modern |
| Nigerian fraud emails (Zenodo `8339691`, legacy) | scam | email | legacy |
| Nigerian fraud emails (Zenodo `8339691`, modern refresh) | scam | email | modern |
| CEAS 2008 spam-challenge emails (Zenodo `8339691`) | mixed | email | legacy |
| Modern phishing validation emails (Zenodo `13474746`, Miltchev et al. 2024) | mixed | email | modern |
| Mendeley SMS phishing 2022 | scam | SMS | modern |
| EMSCAD employment scam corpus | scam | job posting | mixed |
| SpamAssassin public corpus (Apache Software Foundation) | legit | email | legacy |
| MultiWOZ 2.2 (Hugging Face) | legit | chat | modern |
| DailyDialog (Li et al., 2017) | legit | chat | modern |
| Enron ham sample | legit | email | legacy |
| Synthetic supplements (documented + audit-flagged) | scam | mixed | modern |

Every source has an entry in the ScamRadar+ 2.0 research repo's `src/scamradar/sources.py` with its download URL, license, and category tag. The dataset audit found no license issues; 0.6% of the corpus is synthetic and is flagged in the audit report.

---

## Limitations & responsible use

- **Decision aid, not oracle.** Even at F1 = 0.941 on external benchmark, the model misclassifies ~2% of messages. Don't rely on the verdict alone for financial, legal, or safety decisions.
- **English-only.** Non-English inputs are rejected (HTTP 400) by an on-request `langdetect` check.
- **Message-level, not sender-level.** The classifier reads one message at a time. It has no knowledge of the sender's identity, history, or other messages in your inbox.
- **Recruitment scams are the weakest class.** Recall 0.494 on external benchmark. If a recruiter message feels off — even if the model says LEGIT — verify through official company channels.
- **URL scanning is best-effort.** VirusTotal and Google Safe Browsing may rate-limit or time out. When they do, the classifier still returns a verdict based on message text alone.

---

## Historical context (v1.x → E5)

An earlier iteration of this project (versions v1.0 → v1.3, documented in [`outputs/intervention_log.md`](outputs/intervention_log.md), [`outputs/intervention_4_report.md`](outputs/intervention_4_report.md), and [`outputs/final_comparison_report.md`](outputs/final_comparison_report.md)) used a completely different architecture:

- **v1.x:** Random Forest over TF-IDF + character n-grams + hand-crafted numerical features + FAISS proximity scores. Trained on ~22.5k deduplicated clusters. External F1 ≈ 0.87 on a 400-message benchmark.
- **E5 (current):** Logistic Regression over word + character TF-IDF only. Trained on 195,776 clusters. External F1 = 0.941 on a 25,306-message benchmark.

E5 shares **no training data, no features, and no architecture** with v1.x. The migration replaced only the machine-learning inference stack; the frontend, API contract, deployment, and user experience are unchanged.

v1.x artifacts are preserved under [`old_models/`](old_models/) and their research reports under [`outputs/`](outputs/) as a record of the project's evolution. They are historical and should not be cited as current performance.

---

## Team & acknowledgements

| Name | Role |
|---|---|
| **Ameer Hassouna** | ML pipeline, API, frontend, evaluation methodology |
| **Moatasem Khalifeh** | Research, data curation, evaluation |
| **Hanan Lev** | Supervisor |

Final Year BSc Project — Information Systems, Emek Yezreel Academic College, 2026.

Corpora acknowledgements: Li et al. (2017, DailyDialog); Zang et al. (2020, MultiWOZ 2.2); Almeida & Gomez Hidalgo (UCI SMS Spam); Apache Software Foundation (SpamAssassin); Champa, Rabbi & Zibran (2024, Zenodo `8339691`); Miltchev, Rangelov & Genchev (2024, Zenodo `13474746`); Mendeley SMS Phishing 2022 authors; EMSCAD employment scam corpus authors; Enron corpus (CALO project public release).

---

## License

MIT © 2026 Ameer Hassouna & Moatasem Khalifeh.

See [LICENSE](LICENSE) for terms.
