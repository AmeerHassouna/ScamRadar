# ScamRadar+ 🛡️

AI-powered scam message detection system.
Final Year BSc Project — Information Systems, Emek Yezreel College.
Team: Ameer Hassouna & Moatasem Khalifeh | Supervisor: Hanan Lev

---

## Project Structure

```
ScamRadar+/
├── main.py                   # Run full pipeline
├── requirements.txt
├── data/
│   └── db4.db                # Place your database here
├── models/                   # Saved models (auto-created)
├── outputs/                  # Plots and results (auto-created)
└── src/
    ├── 01_data_loading.py
    ├── 02_feature_engineering.py
    ├── 03_tfidf_vectorization.py
    ├── 04_vector_proximity.py
    ├── 05_model_training.py
    ├── 06_evaluation.py
    ├── 07_hyperparameter_tuning.py
    ├── 08_adversarial_testing.py
    └── 09_prediction_pipeline.py
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Place your database
Copy your `db4.db` file into the `data/` folder.

### 3. Run the full pipeline
```bash
python main.py
```

---

## Features

- **Text Classification**: TF-IDF (5000 word features + 3000 character n-grams)
- **Tone Detection**: Urgency, Fear, Reward, Threat scoring
- **URL Verification**: VirusTotal API real-time scanning
- **Vector Proximity**: Sentence Transformers + FAISS semantic similarity
- **Adversarial Robustness**: L33t speak normalization
- **Multi-channel**: Email, SMS, URL, Reddit

---

## Results

| Version | Features | Accuracy | AUC |
|---------|----------|----------|-----|
| Baseline | 8 numerical | 81.0% | 0.887 |
| v2 | + TF-IDF | 95.32% | 0.9866 |
| v3 | + Char n-grams | 96.27% | 0.9864 |
| v4 (Final) | + Vector Proximity | **97.76%** | **0.9957** |
