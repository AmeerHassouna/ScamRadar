# ScamRadar+

**AI-powered scam detection for SMS, email, URLs, and social media messages.**
Final Year BSc Project — Information Systems, Emek Yezreel College, 2026.
Team: Ameer Hassouna & Moatasem Khalifeh | Supervisor: Hanan Lev

[![Live Site](https://img.shields.io/badge/Live%20Site-scamradarplus.com-22c55e?style=flat-square)](https://scamradarplus.com)
[![API](https://img.shields.io/badge/API-Render-22c55e?style=flat-square)](https://scamradar-api-l2vv.onrender.com/health)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square)](https://nextjs.org)

---

## What It Does

ScamRadar+ analyses a message and returns a scam / suspicious / legit verdict with a confidence score, an explanation of the signals that fired, and (where a URL is present) a live URL reputation check.

The deployed model is designed to **assist users in identifying phishing attempts**. It is not a substitute for careful judgement.

### Detection pipeline

1. **Numerical features** — urgency, fear, reward and threat tone scores (phrase-level, negation-aware); URL structure features; readability, capitalisation and punctuation statistics
2. **TF-IDF vectorisation** — 5,000 word-level features + 3,000 character n-gram features
3. **Semantic embedding proximity** — Sentence Transformers + FAISS nearest-neighbour scoring against a training-only scam corpus (used at training time; the deployed API runs without FAISS under Render's memory limit and the pipeline degrades gracefully to 0 for this feature)
4. **URL reputation** — real-time VirusTotal and Google Safe Browsing lookups
5. **Rule-based probability floors** — hardened decisions on high-confidence patterns (romance-scam openers, pig-butchering, delivery smishing, brand impersonation, sextortion threats)

### Deployed model (v1.3)

- **Architecture**: Isotonic-calibrated Random Forest (200 trees) over the concatenated feature space above
- **Training corpus**: 22,546 unique message clusters (after SHA-1 deduplication of 47,493 raw rows) drawn from Enron, SpamAssassin, UCI-SMS, Reddit, and an external phishing corpus (`zefang-liu/phishing-email-dataset`)
- **Deployment**: FastAPI + Docker on Render; Next.js frontend on GitHub Pages

---

## Reported performance

All headline numbers below are from a **leakage-free external validation set of 400 messages** (250 phishing + 150 legitimate) drawn from sources with **SHA-1 verified zero overlap** with the training corpus.

| Metric | v1.3 (deployed) |
|---|---:|
| Accuracy | 0.850 |
| Precision | 0.924 |
| Recall | 0.828 |
| **F1** | **0.873** |
| ROC-AUC | 0.971 |
| PR-AUC | 0.984 |

**Internal held-out test (v1.3's own 15% test split on the deduplicated corpus): F1 = 0.942.**

### Methodology and evaluation integrity

Early experiments on this project reported F1 ≈ 0.97 on a random 80/20 split. A subsequent audit found that ~56% of the test rows had a near-duplicate in the training set — a data-leakage artefact caused by the highly templated nature of two of the source corpora. After introducing:

1. **SHA-1 deduplication** on normalised text (URLs and digits replaced by placeholders, whitespace collapsed) — reduced the corpus from 46,360 → 21,413 unique clusters
2. **Group-aware splitting** — train/test at the *cluster* level, not the *row* level
3. **Train-only fitting** — TF-IDF vectorisers, StandardScaler and FAISS index fit on the training slice only (previously fit on the full corpus, including test rows)
4. **An independent external validation set** — `data/external_evaluation/` — that neither model version had ever seen at training time

...the honest baseline for the original v1.0 pipeline dropped from F1 ≈ 0.97 (leaked) to F1 ≈ 0.62 (on the external set). The v1.3 model shipped today achieves F1 = 0.87 on that same set — a real +25 F1-point improvement over the honest v1.0 baseline, established through iterative interventions documented in `outputs/intervention_log.md`.

The full intervention log, per-message error analysis, and evaluation JSONs for every model version are preserved in `outputs/` for reproducibility.

---

## Architecture

```
ScamRadar+/
├── api/                  # FastAPI inference server
│   ├── main.py           #   REST endpoints (/predict, /analyze-conversation, …)
│   └── cache.py          #   In-memory result cache
├── src/                  # ML pipeline modules
│   ├── _00_dedup.py            # SHA-1 cluster deduplication
│   ├── 01_data_loading.py      # SQLite load + EDA
│   ├── _02_feature_engineering.py
│   ├── _03_tfidf_vectorization.py
│   ├── _04_vector_proximity.py # Sentence-transformer + FAISS
│   ├── _05_model_training.py
│   ├── _06_evaluation.py
│   ├── _07_hyperparameter_tuning.py
│   ├── _08_adversarial_testing.py
│   └── _09_prediction_pipeline.py
├── web/                  # Next.js 16 frontend → GitHub Pages
│   ├── app/              #   App Router pages (/, /performance, /team)
│   └── components/ui/    #   UI components
├── data/                 # SQLite database (db4.db — not committed)
├── models/               # Deployed model artefacts (v1.3 pkls + FAISS)
├── outputs/              # Evaluation reports and intervention log (not committed)
├── scripts/              # Training + evaluation scripts (not deployed)
├── app.py                # Streamlit analysis dashboard
├── main.py               # Run full training pipeline (development)
├── config.py             # Paths, thresholds, feature lists
├── requirements.txt
└── Dockerfile
```

---

## Local Setup

### Backend (FastAPI)

```bash
# 1. Install dependencies (versions pinned to v1.3 training environment)
pip install -r requirements.txt

# 2. Place the training database (not distributed)
cp path/to/db4.db data/db4.db

# 3. Start the API server (uses the shipped v1.3 model in models/)
PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Frontend (Next.js)

```bash
cd web
npm install
npm run dev          # development — http://localhost:3000
npm run build        # production static export
```

### Streamlit dashboard

```bash
streamlit run app.py
```

### Retraining the model (development only)

```bash
# Full v1.3 retrain from scratch (~5 min on a typical laptop, no GPU needed)
python scripts/train_v1_3.py
```

Retraining requires the SQLite corpus in `data/db4.db` and the external training additions in `data/external_training/external_train.csv`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/predict` | Analyse a single message |
| `POST` | `/analyze-conversation` | Analyse a full conversation (sliding-window) |
| `POST` | `/analyze-conversation-file` | Upload a `.txt` / `.csv` file |
| `GET`  | `/health` | Service health + cache stats |
| `GET`  | `/stats` | Corpus and evaluation summary |

Rate limits: 30 req/min on `/predict`, 20 req/min on conversation endpoints.

Quick example:
```bash
curl -X POST https://scamradar-api-l2vv.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "URGENT: Your account has been suspended. Click here to verify."}'
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| ML | scikit-learn 1.8.0 (pinned), FAISS, Sentence Transformers, NumPy, SciPy |
| API | FastAPI, Uvicorn, slowapi, Pydantic |
| Frontend | Next.js 16, Tailwind CSS, Framer Motion |
| Deployment | GitHub Pages (frontend) · Render (API) |
| Database | SQLite (development-only) |
| URL scanning | VirusTotal API, Google Safe Browsing API |

---

## Deployment

- **Frontend** — pushed to `main` → GitHub Actions builds Next.js static export → deploys to GitHub Pages at [scamradarplus.com](https://scamradarplus.com)
- **API** — Docker container deployed on Render at `https://scamradar-api-l2vv.onrender.com`. Under Render's 512 MB memory limit the API runs without `sentence-transformers` and `faiss-cpu`; the `proximity_scam_score` feature degrades to 0 and the Random Forest pipeline compensates via its other features (verified in the frozen v1.3 evaluation).

---

## User Guide

See [USER_GUIDE.md](USER_GUIDE.md) for detailed instructions on using the web interface and API.

---

## Team

| Name | Role |
|------|------|
| Ameer Hassouna | ML pipeline, API, frontend, evaluation methodology |
| Moatasem Khalifeh | Research, data, evaluation |
| Hanan Lev | Supervisor |
