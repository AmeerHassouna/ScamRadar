# ScamRadar+

**AI-powered scam detection for SMS, email, URLs, and social media.**
Final Year BSc Project — Information Systems, Emek Yezreel College, 2026.
Team: Ameer Hassouna & Moatasem Khalifeh | Supervisor: Hanan Lev

[![Live Site](https://img.shields.io/badge/Live%20Site-scamradarplus.com-22c55e?style=flat-square)](https://scamradarplus.com)
[![API](https://img.shields.io/badge/API-Render-22c55e?style=flat-square)](https://scamradar-api-l2vv.onrender.com/health)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square)](https://nextjs.org)

---

## What It Does

ScamRadar+ detects scam messages using a four-layer ML pipeline:

1. **Numerical features** — urgency, fear, reward, and threat tone scoring
2. **TF-IDF** — 5 000 word-level + 3 000 character n-gram features
3. **Semantic embedding** — Sentence Transformers + FAISS vector proximity search
4. **URL scanning** — VirusTotal & Google Safe Browsing real-time checks

Final accuracy: **97.76%** — AUC **0.9957** on a 45 851-message dataset across SMS, email, URL, and Reddit channels.

---

## Architecture

```
ScamRadar+/
├── api/                  # FastAPI inference server
│   ├── main.py           #   REST endpoints (/predict, /analyze-conversation, …)
│   └── cache.py          #   In-memory result cache
├── src/                  # ML pipeline modules
│   ├── 01_data_loading.py
│   ├── _02_feature_engineering.py
│   ├── _03_tfidf_vectorization.py
│   ├── _04_vector_proximity.py
│   ├── _05_model_training.py
│   ├── _06_evaluation.py
│   ├── _07_hyperparameter_tuning.py
│   ├── _08_adversarial_testing.py
│   └── _09_prediction_pipeline.py
├── web/                  # Next.js 16 frontend → GitHub Pages
│   ├── app/              #   App Router pages (/, /performance, /team)
│   └── components/ui/    #   UI components
├── data/                 # SQLite database (db4.db — not committed)
├── models/               # Saved model artefacts (auto-created by pipeline)
├── outputs/              # Evaluation plots and reports (auto-created)
├── app.py                # Streamlit analysis dashboard
├── main.py               # Run full training pipeline
├── config.py             # Paths, thresholds, feature lists
├── requirements.txt
└── Dockerfile
```

---

## Local Setup

### Backend (FastAPI)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Place your database
cp path/to/db4.db data/db4.db

# 3. Train the full pipeline (creates models/ and outputs/)
python main.py

# 4. Start the API server
PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### Frontend (Next.js)

```bash
cd web
npm install
npm run dev          # development — http://localhost:3000
npm run build        # production static export
```

### Streamlit Dashboard

```bash
streamlit run app.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/predict` | Analyse a single message |
| `POST` | `/analyze-conversation` | Analyse a full conversation (sliding-window) |
| `POST` | `/analyze-conversation-file` | Upload a `.txt` / `.csv` file |
| `GET`  | `/health` | Service health + cache stats |
| `GET`  | `/stats` | Dataset statistics |

Rate limits: 30 req/min on `/predict`, 20 req/min on conversation endpoints.

Quick example:
```bash
curl -X POST https://scamradar-api-l2vv.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "URGENT: Your account has been suspended. Click here to verify."}'
```

---

## Model Results

| Version | Features | Accuracy | AUC |
|---------|----------|----------|-----|
| Baseline | 8 numerical | 81.0% | 0.887 |
| v2 | + TF-IDF (word) | 95.32% | 0.9866 |
| v3 | + Char n-grams | 96.27% | 0.9864 |
| v4 | + Vector Proximity | **97.76%** | **0.9957** |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| ML | scikit-learn, FAISS, Sentence Transformers, NumPy, SciPy |
| API | FastAPI, Uvicorn, slowapi, Pydantic |
| Frontend | Next.js 16, Tailwind CSS, Framer Motion |
| Deployment | GitHub Pages (frontend) · Render (API) |
| Database | SQLite (db4.db — 45 851 labelled messages) |
| URL scanning | VirusTotal API, Google Safe Browsing API |

---

## Deployment

- **Frontend** — pushed to `main` → GitHub Actions builds Next.js static export → deploys to GitHub Pages at [scamradarplus.com](https://scamradarplus.com)
- **API** — Docker container deployed on Render free tier at `https://scamradar-api-l2vv.onrender.com`

---

## User Guide

See [USER_GUIDE.md](USER_GUIDE.md) for detailed instructions on using the web interface and API.

---

## Team

| Name | Role |
|------|------|
| Ameer Hassouna | ML pipeline, API, frontend |
| Moatasem Khalifeh | Research, data, evaluation |
| Hanan Lev | Supervisor |
