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
[![Model](https://img.shields.io/badge/model-E8--P9%20%C2%B7%20LogReg%20%2B%20Rule%20Engine-6366f1?style=flat-square)](models/e7_p1_variants)
[![Baseline F1](https://img.shields.io/badge/F1%20baseline%20(E5%2C%20n%3D25%2C306)-0.941-brightgreen?style=flat-square)](outputs/eval/e7_p1_results.json)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](#license)

</div>

---

## What it does

ScamRadar+ classifies a single message — email, SMS, chat, or job posting — as **SCAM**, **SUSPICIOUS**, or **LEGIT** using a Logistic Regression text classifier over ~500k word- and character-TF-IDF features plus 25 hand-engineered numerical features (tone, URL, phrase, and text-statistics signals). A modular Rule Engine runs after the classifier to catch modern scam patterns the ML alone misses (credential requests, OTP theft, gift-card demands, romance/investment/threat archetypes). Optional URL reputation checks (Google Safe Browsing, VirusTotal) enrich the response.

- Paste a message → get a verdict + confidence + human-readable rationale
- Analyse a full conversation → overall risk score plus per-message breakdown
- Stateless: no accounts, no cookies, no message retention
- Training corpus: 283,501 real + adversarial-synthetic messages (E8-P9 build)

## Try it now

**[scamradarplus.com](https://scamradarplus.com)** — paste any suspicious message.

---

## Table of contents

- [Live production system](#live-production-system)
- [Performance](#performance)
  - [Baseline — pure E5 classifier](#baseline--pure-e5-classifier-n--25306)
  - [Production — E8-P9 build](#production--e8-p9-build-n--25306-same-benchmark)
  - [Per-category recall & FP rate](#per-category-recall--false-positive-rate-e8-p9-external-benchmark)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Local development](#local-development)
- [Deployment](#deployment)
- [API](#api)
- [Data sources](#data-sources)
- [Limitations & responsible use](#limitations--responsible-use)
- [Historical context (v1.x → E5 → E7 → E8-P9)](#historical-context-v1x--e5--e7--e8-p9)
- [Team & acknowledgements](#team--acknowledgements)
- [License](#license)

---

## Live production system

The production build is codename **E8-P9** — the E7-P1 Full classifier (E5 recipe extended with 25 numerical features) retrained on an expanded corpus of 283,501 messages, then wrapped in a modular Rule Engine. Bundle selection is env-driven (`SCAMRADAR_LOCAL_MODEL`, defaults to `e7_p1_full_e8p9`), so rolling back to any prior E7/E8 variant is a single env-var change.

| | Verified value | Source |
|---|---|---|
| **Classifier** | Logistic Regression (C = 5.968, L2, `class_weight=balanced`, `solver=liblinear`) | [`models/e7_p1_variants/e7_p1_full_e8p9.joblib`](models/e7_p1_variants) |
| **Text features** | word 1–2 grams (200,000) · character 3–6 grams (300,000) · sublinear TF · L2 normalisation | bundle `word_vec` / `char_vec` |
| **Numerical features** | 25 hand-engineered signals: tone (urgency · fear · reward · threat), URL structure, phrase scores (scam / legit / brand-impersonation), 13 text statistics | bundle `feature_cols` · [`src/_02_feature_engineering.py`](src/_02_feature_engineering.py) |
| **Post-processing** | Modular **Rule Engine** — Critical (force-scam) · Strong (evidence boost) · Legit (evidence dampen) categories. Type-floor rules (A9 investment · A10 romance · A11 threat) keep recall high on modern conversational scams the classifier alone misses. | [`src/rule_engine/`](src/rule_engine) |
| **URL safety net (E7-P2)** | Caps scam probability at 0.50 when a message contains URLs and every URL resolves to a trusted domain. Prevents legit brand emails being force-flagged by aggressive rules. | [`config.py`](config.py) `E7_P2_SAFETY_NET_*` |
| **Decision threshold** | **0.59** (F1-max on validation — inherited from E5, unchanged) | bundle `threshold` · [`config.py`](config.py) `E5_THRESHOLD` |
| **Training corpus** | 283,501 messages · E8-P6 base (267,723) + 14,669 modern synthetic scams (conversational / investment / romance / threat) + 1,109 paired-legit adversarial twins | [`scripts/data_prep/merge_e8p8_into_training.py`](scripts/data_prep/merge_e8p8_into_training.py) |
| **Data sources** | 14 documented public corpora with URLs + licenses. No Kaggle. Synthetic augmentation is generated in-house and flagged in the audit. | [Data sources](#data-sources) |
| **Bundle size** | 22.6 MB (single joblib, same as E5) | model artifact |
| **Inference latency** | Sub-millisecond on the classifier itself; ~1–3 ms including rule-engine evaluation | measured |

**Bundle selection.** The API loads `models/e7_p1_variants/${SCAMRADAR_LOCAL_MODEL}.joblib` at startup. Setting `SCAMRADAR_LOCAL_MODEL=e7_p1_full_e8p6` rolls back to the pre-E8-P9 build; unsetting it or setting an unknown value falls back to `models/e5_bundle.joblib` (the original text-only E5).

---

## Performance

Two figures matter and are reported separately below:

1. **Pure ML classifier (E5 baseline)** — measures the Logistic Regression head on its own, on a locked one-shot external benchmark. This is the "how good is the model?" number.
2. **Full production pipeline (E8-P9)** — classifier + 25 numerical features + Rule Engine, evaluated on the same external benchmark. This is the "what does a user actually see?" number.

Both are computed from real artifacts checked into this repository — no historical or estimated numbers.

### Baseline — pure E5 classifier (n = 25,306)

A **locked, one-shot, write-once** benchmark. Never seen during model selection, hyperparameter search, calibration, or threshold tuning. Every scoring event is recorded in the project's [`data_pipeline/data/external_benchmark/LOCK.json`](data_pipeline/) — by design this benchmark can only be scored once per bundle.

| Metric | Value |
|---|---:|
| Accuracy | **0.979** |
| Precision | **0.961** |
| Recall | **0.923** |
| **F1** | **0.941** |
| ROC-AUC | 0.995 |
| PR-AUC | 0.984 |
| ECE / Brier | 0.008 / 0.017 |

Source: [`outputs/eval/e7_p1_results.json`](outputs/eval/e7_p1_results.json) → `results.e5.external.primary_threshold_0.59`.

### Production — E8-P9 build (n = 25,306, same benchmark)

Same locked benchmark scored end-to-end (classifier → rule engine → final verdict).

| Metric | Value | vs. E5 baseline |
|---|---:|---:|
| Accuracy | **0.969** | −0.010 |
| Precision | **0.910** | −0.051 |
| Recall | **0.916** | −0.007 |
| **F1** | **0.913** | −0.028 |

Confusion matrix: TN = 20,361 · FP = 410 · FN = 381 · TP = 4,154. Source: [`outputs/eval/e8p9_per_item.parquet`](outputs/eval/e8p9_per_item.parquet).

**Why is F1 lower than the pure classifier?** Deliberate tradeoff. The external benchmark is dominated by 2008-era transactional and marketing emails (Nazario, CEAS 2008, Nigerian fraud). E8-P9 was retrained on ~15,000 modern synthetic scams (conversational SMS, investment DMs, romance, threats) that don't appear in this benchmark, and the Rule Engine's type-floor rules (A9 investment / A10 romance / A11 threat) fire on some benchmark items that superficially resemble those modern archetypes. The net effect: **slightly more FPs on legacy legit email in exchange for meaningfully better coverage of modern conversational scams** — the categories users actually get today.

### Per-category recall & false-positive rate (E8-P9, external benchmark)

| Category | n | Metric | E5 baseline | E8-P9 production |
|---|---:|---|---:|---:|
| Email phishing | 2,178 | Recall | 0.957 | **0.950** |
| Email spam | 1,719 | Recall | 0.934 | **0.929** |
| Smishing (SMS phishing) | 68 | Recall | 0.853 | **0.853** |
| Advance-fee fraud (419-style) | 489 | Recall | 0.812 | **0.800** |
| Recruitment scam | 81 | Recall | 0.494 | **0.482** |
| Legitimate chat | 13,794 | False-positive rate | 0.007% | **0.00%** |
| Legitimate job posting | 1,523 | False-positive rate | 0.72% | **1.05%** |
| Legitimate SMS | 802 | False-positive rate | 1.25% | **1.00%** |
| Legitimate email | 4,652 | False-positive rate | 3.22% | **8.30%** |

Recruitment scams remain the weakest single class — real linguistic overlap between scam recruiter outreach and legit recruiter outreach at first-message register. The `ham_email` FP jump (3.22% → 8.30%) is where the modern rule engine trades legacy precision for modern recall; work to shrink that back is on the roadmap.

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
│  │  Rate-limit · langdetect · LRU cache · in-flight dedup     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  E7-P1 Full sklearn Pipeline (bundle: e7_p1_full_e8p9)     │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  word 1–2 gram TF-IDF     (200 000 features)         │  │  │
│  │  │  char 3–6 gram TF-IDF     (300 000 features)         │  │  │
│  │  │  25 numerical features    (tone · URL · phrase ·     │  │  │
│  │  │                            text stats, StandardScaler)│  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │            ↓ concatenated feature matrix (500 025)         │  │
│  │  Logistic Regression (C=5.97, L2, class_weight=balanced)   │  │
│  │            ↓                                               │  │
│  │  ml_probability ∈ [0, 1]                                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Rule Engine  (src/rule_engine/)                           │  │
│  │  A — Critical (force-scam) : credential req · OTP theft ·  │  │
│  │       gift-card · remote-access · crypto seed · brand-     │  │
│  │       impersonation compound · investment / romance /      │  │
│  │       threat type-floors (A9 / A10 / A11)                  │  │
│  │  B — Strong (evidence boost) : URL shorteners · threat +   │  │
│  │       immediate payment · impossible brand domain, …       │  │
│  │  C — Legit (evidence dampen) : official transactional      │  │
│  │       domain consistency, …                                │  │
│  │            ↓                                               │  │
│  │  final_probability + triggered_rules[]                     │  │
│  │            ↓                                               │  │
│  │  E7-P2 URL safety net (cap at 0.50 if all URLs trusted)    │  │
│  │            ↓                                               │  │
│  │  threshold 0.59 → verdict SCAM / SUSPICIOUS / LEGIT        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Ancillary enrichment (display-only)                       │  │
│  │  · Scam-type classifier (phishing · investment · romance…) │  │
│  │  · URL extraction + Google Safe Browsing + VirusTotal      │  │
│  │  · Human-readable rationale ("why_flagged")                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────────────────┘
                       │  JSON response (25 fields)
                       ▼
                    Frontend
```

The classifier bundle (22.6 MB joblib) contains the LR, both TF-IDF vectorizers, the `StandardScaler` for the numerical features, and the training-time feature-column ordering — everything needed for byte-identical inference. The Rule Engine sits *outside* the bundle in `src/rule_engine/` so rules can be added or tuned without retraining.

---

## Project structure

```
ScamRadar/
├── api/                       # FastAPI backend (routes, cache, rate limits)
│   ├── main.py                # /predict · /analyze-conversation · /health
│   └── cache.py               # LRU + in-flight-dedup cache
├── src/
│   ├── e5_inference.py        # Bundle loader — resolves SCAMRADAR_LOCAL_MODEL
│   │                          # (default: e7_p1_full_e8p9), returns predict fn
│   ├── _02_feature_engineering.py  # 25 numerical features (tone · URL · phrase · text stats)
│   ├── _09_prediction_pipeline.py  # Full inference pipeline (feature build + predict + rules)
│   └── rule_engine/           # Modular post-classifier rule system
│       ├── base.py            # Rule / RuleEngine / RuleContext / Severity primitives
│       ├── context.py         # build_context() — assembles the state each rule reads
│       ├── critical.py        # A-category rules (force-scam) incl. A9/A10/A11 type floors
│       ├── strong.py          # B-category rules (evidence boost)
│       ├── legit.py           # C-category rules (evidence dampen)
│       ├── patterns.py        # Shared regex-based detectors (credential / OTP / gift-card / …)
│       ├── numerical_features.py  # Rule inputs derived from the 25 numerical features
│       └── weights.py         # Per-rule adjustment magnitudes + priorities
├── models/
│   ├── e5_bundle.joblib       # Legacy E5 (text-only) — kept as env-selectable fallback
│   ├── e5_metadata.json       # Full metrics · hyperparameters · thresholds for E5
│   ├── e5_threshold_sweep.json # Precision / recall / F1 across thresholds (E5)
│   └── e7_p1_variants/
│       ├── e7_p1_full_e8p9.joblib   # ← THE PRODUCTION BUNDLE
│       ├── e7_p1_full_e8p6.joblib   # Rollback target (pre-synthetic-scam corpus)
│       └── e7_p1_{tone,url,phrase,textstats,full}.joblib  # Ablation variants
├── web/                       # Next.js 16 frontend → scamradarplus.com
│   ├── app/                   # App Router pages (/, /performance, /team, …)
│   └── components/ui/         # UI components
├── extension/                 # Chrome MV3 extension (highlight → right-click → analyse)
│   ├── manifest.json
│   ├── background.js          # Context menu + API client
│   ├── content.js             # On-demand Shadow-DOM overlay
│   └── popup.{html,js,css}    # Toolbar popup + API-health indicator
├── config.py                  # E5_BUNDLE_PATH · E5_THRESHOLD · E7_P2 safety-net params
├── tests/
│   ├── e5_parity_test.py      # Byte-identical parity vs the frozen E5 bundle (13 messages)
│   ├── holdout_eval.py        # E7/E8 external-benchmark evaluator
│   ├── stress_test.py         # Concurrent request stress harness
│   └── tier2_external.py      # Tier-2 acceptance runner
├── docs/
│   └── USER_GUIDE.md          # End-user documentation
├── outputs/
│   ├── eval/                  # E5 / E7 / E8-P{1..9} evaluation artifacts
│   ├── coefs/                 # Per-variant coefficient snapshots
│   └── e7_p1_report.md        # E7-P1 research report
├── scripts/
│   ├── training/              # train_e7_p1.py · train_e8p9.py · …
│   ├── evaluation/            # eval_e7_p1.py · analyze_e8p9_errors.py · …
│   └── data_prep/             # gen_e8p8_synthetic_scam.py · merge_e8p8_into_training.py
├── data_pipeline/             # Stage 0 — data collection (acquire → clean → split → audit)
│   └── src/scamradar/         # sources.py (13 corpora registry) + acquire.py + …
├── legacy/                    # Superseded top-level entry points
├── old_models/                # v1.x model artifacts (reference only)
├── Dockerfile                 # Production container (Render)
├── Procfile                   # Alternate start command (Heroku-style)
├── railway.toml               # Railway platform config (alternate host)
├── runtime.txt                # Python 3.11.9
└── requirements.txt           # Python dependencies
```

**Model provenance.** The E5 classifier was trained by the data collection pipeline at [`data_pipeline/`](data_pipeline/) — a strict data-first workflow with an approval-gated dataset audit (`python -m scamradar acquire → clean → audit → approve-dataset → split`). E7 (numerical-feature fusion) and E8 (corpus expansion + rule engine) were built on top, in `scripts/training/`. Every training + evaluation step has a corresponding script under `scripts/training/` or `scripts/evaluation/`; every evaluation artifact is under `outputs/eval/`. E5 → E8-P9 shares the LR head recipe, TF-IDF vocab sizes, and decision threshold (0.59) — the additions are numerical features, an expanded corpus, and the post-classifier Rule Engine. Byte-identical parity of the LR head vs the frozen E5 bundle is checked in [`tests/e5_parity_test.py`](tests/e5_parity_test.py).

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

# 3. Start the API (loads models/e7_p1_variants/e7_p1_full_e8p9.joblib on
#    startup — override with SCAMRADAR_LOCAL_MODEL to load a different variant)
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

### Verify E5-fallback parity

The parity harness confirms that when the API is pointed at the E5 fallback bundle (`SCAMRADAR_LOCAL_MODEL=` unset or unknown), it produces byte-identical probabilities and verdicts to the frozen E5 bundle. This guards the safe-rollback path; the default E8-P9 build is validated separately via the eval scripts under `scripts/evaluation/`.

```bash
# Requires the local API running on port 8000 with the E5 bundle loaded
SCAMRADAR_LOCAL_MODEL= python tests/e5_parity_test.py
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

Every source has an entry in [`data_pipeline/src/scamradar/sources.py`](data_pipeline/src/scamradar/sources.py) with its download URL, license, and category tag. The dataset audit found no license issues; 0.6% of the corpus is synthetic and is flagged in the audit report.

---

## Limitations & responsible use

- **Decision aid, not oracle.** Even at F1 = 0.941 on external benchmark, the model misclassifies ~2% of messages. Don't rely on the verdict alone for financial, legal, or safety decisions.
- **English-only.** Non-English inputs are rejected (HTTP 400) by an on-request `langdetect` check.
- **Message-level, not sender-level.** The classifier reads one message at a time. It has no knowledge of the sender's identity, history, or other messages in your inbox.
- **Recruitment scams are the weakest class.** Recall 0.494 on external benchmark. If a recruiter message feels off — even if the model says LEGIT — verify through official company channels.
- **URL scanning is best-effort.** VirusTotal and Google Safe Browsing may rate-limit or time out. When they do, the classifier still returns a verdict based on message text alone.

---

## Historical context (v1.x → E5 → E7 → E8-P9)

Four generations of ML architecture ship with this repository — each superseded but retained for provenance.

| Generation | Architecture | Training | External F1 (n = 25,306) | Location |
|---|---|---|---:|---|
| **v1.x** (2025) | Random Forest + TF-IDF + char-grams + hand-crafted numerics + FAISS proximity | ~22.5k deduplicated clusters | ≈ 0.87 (400-message benchmark, not the locked 25,306 set) | [`old_models/`](old_models) |
| **E5** (Aug 2026) | Logistic Regression + word 1–2 gram TF-IDF + char 3–6 gram TF-IDF (500k features) | 195,776 clusters | **0.941** | [`models/e5_bundle.joblib`](models/e5_bundle.joblib) |
| **E7-P1 Full** (Aug 2026) | E5 recipe + 25 numerical features (tone · URL · phrase · text stats) | Same corpus as E5 | 0.941 (unchanged; adds explainability, not accuracy) | [`models/e7_p1_variants/e7_p1_full.joblib`](models/e7_p1_variants) |
| **E8-P9** (Aug 2026, current) | E7-P1 Full + modular Rule Engine (Critical/Strong/Legit categories, A9–A11 type floors) | E5 corpus + 14,669 modern synthetic scams + 1,109 legit-pair adversarial twins → **283,501 messages total** | 0.913 on legacy benchmark (see [Performance](#performance) for the tradeoff explanation) | [`models/e7_p1_variants/e7_p1_full_e8p9.joblib`](models/e7_p1_variants/e7_p1_full_e8p9.joblib) |

**What changed between generations, in one sentence each:**

- **v1.x → E5:** Full ML rewrite. New training corpus (195k clusters vs 22.5k), new architecture (LogReg over word+char TF-IDF vs RF over mixed features), new external benchmark (locked 25,306 vs ad-hoc 400). No shared code, features, or data.
- **E5 → E7-P1:** Same head and text features; added 25 numerical features (already computed elsewhere in the codebase but previously ignored by the classifier) via feature-concatenation. Small F1 movements (±0.001) but the numerical block enables the Rule Engine to reason over consistent inputs.
- **E7-P1 → E8-P9:** Same architecture; added a modular Rule Engine and expanded the training corpus with 15,778 modern messages targeting conversational / investment / romance / threat scams that the 2008-era external benchmark doesn't measure. Deliberate tradeoff — some legacy-email precision for meaningful modern-scam recall.

v1.x artifacts remain under [`old_models/`](old_models/) and E5 under [`models/e5_bundle.joblib`](models/e5_bundle.joblib); either can be swapped back in via the `SCAMRADAR_LOCAL_MODEL` env var without a redeploy.

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
