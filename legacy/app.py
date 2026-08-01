"""ScamRadar+ | Streamlit Dashboard"""

import os
import re
import sys
import pickle
import sqlite3

import faiss
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from scipy.sparse import csr_matrix, hstack
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score,
                             roc_curve)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

# ── Must be first Streamlit call ───────────────────────────────────────────
st.set_page_config(
    page_title="ScamRadar+",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (DB_PATH, MODELS_PATH, NUMERICAL_FEATURES_V5,
                    MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH, DEFAULT_THRESHOLD,
                    FAISS_K_SCAM)

NUMERICAL_FEATURES = NUMERICAL_FEATURES_V5   # alias used throughout app

# ── Global CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Base ──────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main { font-family: 'Inter', sans-serif !important; }

[data-testid="stAppViewContainer"] { background: #0F0F0F !important; }
[data-testid="stMain"] .block-container { padding-top: 2rem !important; }
[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #111111 !important;
    border-right: 1px solid #1F1F1F !important;
}
[data-testid="stSidebar"] .block-container { padding: 0 !important; }

/* ── Typography ────────────────────────────────────────────────────────── */
h1, h2, h3, h4 { color: #F9FAFB !important; font-family: 'Inter', sans-serif !important; }
p, li, span     { color: #9CA3AF; font-family: 'Inter', sans-serif !important; }

/* ── Logo / Brand ──────────────────────────────────────────────────────── */
.brand-wrap {
    padding: 28px 20px 20px 20px;
    border-bottom: 1px solid #1F1F1F;
    margin-bottom: 8px;
}
.brand-gradient {
    font-size: 1.5rem; font-weight: 900; letter-spacing: 2px;
    background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A78BFA 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.brand-sub {
    font-size: 0.7rem; color: #4B5563; margin-top: 3px;
    letter-spacing: 0.5px; text-transform: uppercase;
}

/* ── Nav items ─────────────────────────────────────────────────────────── */
div[data-testid="stRadio"] > label { display: none !important; }
div[data-testid="stRadio"] > div   { gap: 2px !important; }
div[data-testid="stRadio"] > div > label {
    width: 100%; padding: 10px 16px !important;
    border-radius: 8px !important; font-size: 0.88rem !important;
    font-weight: 500 !important; color: #6B7280 !important;
    cursor: pointer; transition: all 0.15s ease;
    border: 1px solid transparent !important;
}
div[data-testid="stRadio"] > div > label:hover {
    background: #1A1A1A !important; color: #F9FAFB !important;
}
div[data-testid="stRadio"] > div > label[data-testid="stMarkdownContainer"] { display: none; }

/* ── Metric pill (sidebar stats) ───────────────────────────────────────── */
.stat-pill {
    display: flex; align-items: center; justify-content: space-between;
    background: #1A1A1A; border: 1px solid #2A2A2A;
    border-radius: 8px; padding: 8px 14px; margin: 4px 0;
    font-size: 0.82rem;
}
.stat-label { color: #6B7280; }
.stat-val   { color: #F9FAFB; font-weight: 600; }

/* ── Section headers ───────────────────────────────────────────────────── */
.sec-head {
    font-size: 0.82rem; font-weight: 700; color: #6B7280;
    text-transform: uppercase; letter-spacing: 1px;
    margin: 1.6rem 0 0.8rem 0;
}

/* ── Verdict banners ───────────────────────────────────────────────────── */
.scam-banner {
    background: linear-gradient(135deg, #1C0A0A 0%, #2D0F0F 100%);
    border: 1px solid #EF4444; border-radius: 16px;
    padding: 32px 24px; text-align: center; margin-bottom: 12px;
    box-shadow: 0 0 40px rgba(239, 68, 68, 0.15);
}
.suspicious-banner {
    background: linear-gradient(135deg, #1C1200 0%, #2D1F00 100%);
    border: 1px solid #F59E0B; border-radius: 16px;
    padding: 32px 24px; text-align: center; margin-bottom: 12px;
    box-shadow: 0 0 40px rgba(245, 158, 11, 0.15);
}
.legit-banner {
    background: linear-gradient(135deg, #071A12 0%, #0A2818 100%);
    border: 1px solid #10B981; border-radius: 16px;
    padding: 32px 24px; text-align: center; margin-bottom: 12px;
    box-shadow: 0 0 40px rgba(16, 185, 129, 0.15);
}
.verdict-label {
    font-size: 3rem; font-weight: 900; letter-spacing: 8px;
    font-family: 'Inter', sans-serif;
}
.verdict-meta { font-size: 0.95rem; color: #6B7280; margin-top: 8px; }

/* ── Metric cards ──────────────────────────────────────────────────────── */
.metric-card {
    background: #1A1A1A; border: 1px solid #2A2A2A;
    border-radius: 12px; padding: 20px 16px; text-align: center;
    transition: border-color 0.2s ease;
}
.metric-card:hover { border-color: #6366F1; }
.metric-val { font-size: 1.7rem; font-weight: 800; color: #6366F1; }
.metric-lbl { font-size: 0.75rem; color: #6B7280; margin-top: 4px;
              text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Analyse button ────────────────────────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #6366F1, #8B5CF6) !important;
    border: none !important; border-radius: 10px !important;
    font-weight: 700 !important; font-size: 0.95rem !important;
    letter-spacing: 0.5px; height: 3.2rem !important;
    box-shadow: 0 4px 24px rgba(99, 102, 241, 0.4) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 6px 32px rgba(99, 102, 241, 0.6) !important;
    transform: translateY(-1px) !important;
}

/* ── Text area / inputs ────────────────────────────────────────────────── */
[data-testid="stTextArea"] textarea {
    background: #1A1A1A !important; border: 1px solid #2A2A2A !important;
    border-radius: 10px !important; color: #F9FAFB !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.9rem !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}
[data-testid="stTextInput"] input {
    background: #1A1A1A !important; border: 1px solid #2A2A2A !important;
    border-radius: 8px !important; color: #F9FAFB !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* ── Similarity cards ──────────────────────────────────────────────────── */
.sim-card {
    background: #1A1A1A; border: 1px solid #2A2A2A;
    border-left: 3px solid #EF4444;
    border-radius: 10px; padding: 12px 16px; margin: 6px 0;
}
.sim-score { color: #F87171; font-size: 0.72rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 0.5px; }
.sim-text  { color: #9CA3AF; font-size: 0.83rem; margin-top: 5px; line-height: 1.5; }

/* ── Badge ─────────────────────────────────────────────────────────────── */
.badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.3px;
}
.badge-red    { background: rgba(239,68,68,0.15);  color: #F87171; }
.badge-amber  { background: rgba(245,158,11,0.15); color: #FCD34D; }
.badge-green  { background: rgba(16,185,129,0.15); color: #34D399; }
.badge-indigo { background: rgba(99,102,241,0.15); color: #A5B4FC; }

/* ── Info card (model info) ────────────────────────────────────────────── */
.info-card {
    background: #1A1A1A; border: 1px solid #2A2A2A;
    border-radius: 10px; padding: 14px 16px;
    font-size: 0.8rem; color: #6B7280; margin-top: 16px;
    line-height: 1.7;
}
.info-card b { color: #9CA3AF; }

/* ── Divider ───────────────────────────────────────────────────────────── */
hr { border-color: #1F1F1F !important; }

/* ── Dataframes ────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #2A2A2A !important; border-radius: 10px !important;
    background: #1A1A1A !important;
}

/* ── Expander ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #1A1A1A !important; border: 1px solid #2A2A2A !important;
    border-radius: 10px !important;
}

/* ── Scrollbar ─────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #111111; }
::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #6366F1; }

/* ── Tech stack pill ───────────────────────────────────────────────────── */
.tech-pill {
    display: inline-block; background: #1A1A1A; border: 1px solid #2A2A2A;
    border-radius: 20px; padding: 5px 14px; margin: 4px 3px;
    font-size: 0.78rem; color: #9CA3AF;
}
.tech-pill span { color: #6366F1; font-weight: 600; margin-right: 5px; }

/* ── Team card ─────────────────────────────────────────────────────────── */
.team-card {
    background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px;
    padding: 20px; text-align: center; margin-bottom: 12px;
}
.team-avatar {
    width: 56px; height: 56px; border-radius: 50%;
    background: linear-gradient(135deg, #6366F1, #8B5CF6);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; margin: 0 auto 10px auto;
}
.team-name { color: #F9FAFB; font-weight: 700; font-size: 1rem; }
.team-role { color: #6B7280; font-size: 0.78rem; margin-top: 4px; }

/* ── Character counter ─────────────────────────────────────────────────── */
.char-counter {
    font-size: 0.75rem; color: #4B5563; text-align: right;
    margin-top: -6px; padding-right: 4px;
}
.char-counter.warn { color: #F59E0B; }
.char-counter.over { color: #EF4444; }
</style>
""", unsafe_allow_html=True)

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#9CA3AF", family="Inter, sans-serif"),
    margin=dict(t=30, b=10, l=10, r=10),
)


# ══════════════════════════════════════════════════════════════════════════
#  CACHED LOADERS
# ══════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_raw_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT m.message_id, m.raw_text, m.label,
               c.type  AS channel,  ds.name AS source,
               mf.text_length,   mf.word_count,     mf.has_url,
               mf.url_count,     mf.exclamation_count,
               mf.uppercase_ratio, mf.digit_ratio,  mf.urgency_score
        FROM Message m
        JOIN Channel    c  ON m.channel_id = c.channel_id
        JOIN DataSource ds ON m.source_id  = ds.source_id
        JOIN MessageFeatures mf ON m.message_id = mf.message_id
        ORDER BY m.message_id
    """, conn)
    conn.close()
    return df


@st.cache_resource(show_spinner=False)
def load_saved_models():
    required = ["scamradar_model.pkl", "tfidf_vectorizer.pkl",
                "char_vectorizer.pkl", "scaler.pkl", "scam_faiss.index"]
    missing  = [f for f in required if not os.path.exists(os.path.join(MODELS_PATH, f))]
    if missing:
        st.error("Model files not found. Please run `main.py` first to train the models.")
        return None
    try:
        payload    = pickle.load(open(os.path.join(MODELS_PATH, "scamradar_model.pkl"),   "rb"))
        tfidf      = pickle.load(open(os.path.join(MODELS_PATH, "tfidf_vectorizer.pkl"),  "rb"))
        char_tfidf = pickle.load(open(os.path.join(MODELS_PATH, "char_vectorizer.pkl"),   "rb"))
        scaler     = pickle.load(open(os.path.join(MODELS_PATH, "scaler.pkl"),             "rb"))
        faiss_idx  = faiss.read_index(os.path.join(MODELS_PATH, "scam_faiss.index"))
        legit_path = os.path.join(MODELS_PATH, "legit_faiss.index")
        legit_idx  = faiss.read_index(legit_path) if os.path.exists(legit_path) else None
        if isinstance(payload, dict):
            model, threshold = payload["model"], payload.get("threshold", DEFAULT_THRESHOLD)
        else:
            model, threshold = payload, DEFAULT_THRESHOLD
        return model, tfidf, char_tfidf, scaler, faiss_idx, legit_idx, threshold
    except Exception as e:
        st.error(f"Failed to load model files: {e}")
        return None


@st.cache_resource(show_spinner=False)
def load_sentence_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


@st.cache_data(show_spinner=False)
def load_embeddings() -> np.ndarray:
    return np.load(os.path.join(MODELS_PATH, "embeddings.npy"))


# ── Feature helpers (self-contained so no circular import) ─────────────────
def _compute_tone(text: str):
    t = text.lower() if isinstance(text, str) else ""
    urgency = sum(1 for w in ["urgent","immediately","expires","limited time",
                               "act now","hurry","deadline","last chance","asap"] if w in t)
    fear    = sum(1 for w in ["suspended","blocked","unauthorized",
                               "suspicious activity","verify your account",
                               "locked","compromised"] if w in t)
    reward  = sum(1 for w in ["winner","won","prize","reward","gift card",
                               "free","congratulations","selected",
                               "claim your","bonus"] if w in t)
    threat  = sum(1 for w in ["legal action","arrested","police","lawsuit",
                               "penalty","fined","criminal","court"] if w in t)
    return urgency, fear, reward, threat


def _compute_url_feats(text: str):
    txt = text if isinstance(text, str) else ""
    urls = re.findall(r'https?://(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})',
                      txt.lower())
    bad_tlds = [".xyz",".top",".club",".online",".site",
                ".info",".biz",".tk",".ml",".ga",".cf"]
    bad_kws  = ["login","verify","secure","account","update",
                "confirm","banking","paypal","amazon","apple"]
    has_tld  = int(any(any(u.endswith(t) for t in bad_tlds) for u in urls))
    has_kw   = int(any(any(k in u for k in bad_kws) for u in urls))
    has_ip   = int(bool(re.search(r'https?://\d{1,3}(?:\.\d{1,3}){3}', txt)))
    return has_tld, has_kw, has_ip


def _add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    from src._02_feature_engineering import (
        preprocess_text, compute_tone_features, compute_url_features, compute_new_features
    )
    df["raw_text"] = df["raw_text"].fillna("").apply(preprocess_text)
    tone = df["raw_text"].apply(compute_tone_features)
    df["tone_urgency"] = tone.apply(lambda x: x[0])
    df["tone_fear"]    = tone.apply(lambda x: x[1])
    df["tone_reward"]  = tone.apply(lambda x: x[2])
    df["tone_threat"]  = tone.apply(lambda x: x[3])
    url_f = df["raw_text"].apply(compute_url_features)
    df["url_suspicious_tld"]     = url_f.apply(lambda x: x[0])
    df["url_suspicious_keyword"] = url_f.apply(lambda x: x[1])
    df["url_has_ip"]             = url_f.apply(lambda x: x[2])
    new_f = df["raw_text"].apply(compute_new_features)
    for col in ["avg_word_length", "capitalized_word_count", "scam_phrase_score",
                "sender_impersonation_score", "punctuation_density",
                "question_mark_count", "currency_symbol_count",
                "readability_score", "unique_word_ratio", "legit_phrase_score"]:
        df[col] = new_f.apply(lambda x: x[col])
    return df


@st.cache_resource(show_spinner=False)
def get_full_df() -> pd.DataFrame:
    """Raw data + all V5 engineered features + scam proximity (scaled ×0.5)."""
    df = load_raw_data().copy()
    df = _add_engineered_features(df)

    models = load_saved_models()
    if models is None:
        return df
    _, _, _, _, faiss_idx, _, _ = models
    embeddings = load_embeddings()
    norm = embeddings.astype("float32").copy()
    faiss.normalize_L2(norm)
    D_scam, _ = faiss_idx.search(norm, k=FAISS_K_SCAM)
    # Scale ×0.5 to match training — legit/delta excluded (caused false positives)
    df["proximity_scam_score"] = D_scam.mean(axis=1).astype(float) * 0.5
    return df


@st.cache_resource(show_spinner=False)
def get_evaluation_results():
    """Train LR / DT / RF on the full V5 feature matrix; return all eval artefacts."""
    df = get_full_df()
    models = load_saved_models()
    if models is None:
        return None
    _, tfidf, char_tfidf, scaler, _, _, _ = models

    X_tfidf = tfidf.transform(df["raw_text"].fillna(""))
    X_char  = char_tfidf.transform(df["raw_text"].fillna(""))
    X_num   = scaler.transform(df[NUMERICAL_FEATURES].fillna(0).values)
    X       = hstack([X_tfidf, X_char, csr_matrix(X_num)])
    y       = df["label"].values

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    classifiers = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
        "Decision Tree":       DecisionTreeClassifier(random_state=42),
        "Random Forest":       RandomForestClassifier(n_estimators=100,
                                                       random_state=42, n_jobs=-1),
    }

    metrics, roc_data, cm_data, trained = {}, {}, {}, {}
    for name, clf in classifiers.items():
        clf.fit(X_tr, y_tr)
        yp   = clf.predict(X_te)
        prob = clf.predict_proba(X_te)[:, 1]
        metrics[name] = {
            "Accuracy":  round(accuracy_score(y_te, yp), 4),
            "Precision": round(precision_score(y_te, yp), 4),
            "Recall":    round(recall_score(y_te, yp), 4),
            "F1":        round(f1_score(y_te, yp), 4),
            "AUC-ROC":   round(roc_auc_score(y_te, prob), 4),
        }
        fpr, tpr, _ = roc_curve(y_te, prob)
        roc_data[name] = (fpr.tolist(), tpr.tolist())
        cm_data[name]  = confusion_matrix(y_te, yp).tolist()
        trained[name]  = clf

    # Per-channel (RF on full dataset)
    rf     = trained["Random Forest"]
    y_all  = rf.predict(X)
    df2    = df.copy()
    df2["prediction"] = y_all
    ch_rows = []
    for ch in ["email", "url", "sms", "reddit"]:
        mask = df2["channel"] == ch
        if not mask.any():
            continue
        yt = df2.loc[mask, "label"]
        yp = df2.loc[mask, "prediction"]
        ch_rows.append({
            "Channel":   ch.upper(),
            "Messages":  int(mask.sum()),
            "Accuracy":  round(accuracy_score(yt, yp), 4),
            "Precision": round(precision_score(yt, yp, zero_division=0), 4),
            "Recall":    round(recall_score(yt, yp, zero_division=0), 4),
            "F1":        round(f1_score(yt, yp, zero_division=0), 4),
        })

    # Feature importance (RF)
    tfidf_names = tfidf.get_feature_names_out().tolist()
    char_names  = [f"char_{f}" for f in char_tfidf.get_feature_names_out()]
    all_names   = tfidf_names + char_names + NUMERICAL_FEATURES
    imp         = rf.feature_importances_
    top_idx     = np.argsort(imp)[::-1][:20]
    fi_df = pd.DataFrame({
        "Feature":    [all_names[i] for i in top_idx],
        "Importance": imp[top_idx],
    }).sort_values("Importance")

    return metrics, roc_data, cm_data, trained, pd.DataFrame(ch_rows), fi_df


# ══════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div class="brand-wrap">
        <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.8rem;">🛡️</span>
            <div>
                <div class="brand-gradient">ScamRadar+</div>
                <div class="brand-sub">AI Scam Detection · v2.0</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "nav",
        ["🔍  Scam Detector",
         "📊  Model Performance",
         "📈  Data Exploration",
         "ℹ️   About"],
        label_visibility="collapsed",
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.7rem;color:#374151;text-transform:uppercase;'
        'letter-spacing:1px;padding:0 16px;margin-bottom:8px;">Dataset</div>',
        unsafe_allow_html=True,
    )

    df_raw = load_raw_data()
    total  = len(df_raw)
    scams  = int(df_raw["label"].sum())
    legits = total - scams

    st.markdown(f"""
    <div style="padding: 0 12px;">
        <div class="stat-pill">
            <span class="stat-label">Total messages</span>
            <span class="stat-val">{total:,}</span>
        </div>
        <div class="stat-pill">
            <span class="stat-label">Scam</span>
            <span class="stat-val" style="color:#F87171;">{scams:,}</span>
        </div>
        <div class="stat-pill">
            <span class="stat-label">Legit</span>
            <span class="stat-val" style="color:#34D399;">{legits:,}</span>
        </div>
        <div class="stat-pill">
            <span class="stat-label">Channels</span>
            <span class="stat-val" style="color:#A5B4FC;">4</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div style="font-size:0.68rem;color:#1F2937;text-align:center;'
        'padding:20px 16px 10px 16px;">BSc Data Science Project · ScamRadar+ © 2025</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 1 — SCAM DETECTOR
# ══════════════════════════════════════════════════════════════════════════

if page == "🔍  Scam Detector":
    st.markdown(
        '<h2 style="font-size:1.7rem;font-weight:800;margin-bottom:4px;">'
        '🛡️ Scam Detector</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#6B7280;margin-bottom:20px;">'
        'Paste any email, SMS, URL, or social-media post — the AI pipeline analyses it instantly.</p>',
        unsafe_allow_html=True,
    )

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        message = st.text_area(
            "Message",
            height=190,
            placeholder="Paste your message here…",
            label_visibility="collapsed",
            max_chars=MAX_MESSAGE_LENGTH,
        )
        char_count = len(message) if message else 0
        pct = char_count / MAX_MESSAGE_LENGTH
        counter_cls = "over" if pct > 1 else "warn" if pct > 0.85 else ""
        st.markdown(
            f'<div class="char-counter {counter_cls}">{char_count:,} / {MAX_MESSAGE_LENGTH:,}</div>',
            unsafe_allow_html=True,
        )

    with col_btn:
        st.markdown("<div style='height:52px'></div>", unsafe_allow_html=True)
        analyse_btn = st.button(
            "🔍  Analyse", type="primary", use_container_width=True
        )

    if analyse_btn and message.strip():
        models = load_saved_models()
        if models is None:
            st.stop()
        model, tfidf, char_tfidf, scaler, faiss_idx, legit_idx, threshold = models

        if len(message.strip()) < MIN_MESSAGE_LENGTH:
            st.warning(
                f"Message too short to analyse ({len(message.strip())} chars). "
                f"Please enter at least {MIN_MESSAGE_LENGTH} characters."
            )
            st.stop()

        with st.spinner("Running prediction pipeline…"):
            st_model = load_sentence_model()
            from src._09_prediction_pipeline import predict_message
            result = predict_message(
                message, model, tfidf, char_tfidf, scaler,
                faiss_idx, st_model,
                legit_index=legit_idx,
                threshold=threshold,
            )

        verdict   = result["verdict"]
        conf      = result["confidence"]
        scam_type = result.get("scam_type", "general_spam")
        is_scam       = verdict == "SCAM"
        is_suspicious = verdict == "SUSPICIOUS"

        TYPE_ICONS = {
            "phishing":             "🎣",
            "credential_phishing":  "🔑",
            "prize_fraud":          "🎰",
            "bank_impersonation":   "🏦",
            "job_scam":             "💼",
            "investment_scam":      "📈",
            "romance_scam":         "💔",
            "advance_fee_scam":     "💸",
            "delivery_scam":        "📦",
            "social_media_scam":    "📱",
            "emergency_scam":       "🚑",
            "threat_scam":          "⚖️",
            "general_spam":         "📧",
        }

        # ── Verdict banner ─────────────────────────────────────────────
        if is_scam:
            banner_cls, colour, icon = "scam-banner", "#EF4444", "🚨"
        elif is_suspicious:
            banner_cls, colour, icon = "suspicious-banner", "#F59E0B", "⚠️"
        else:
            banner_cls, colour, icon = "legit-banner", "#10B981", "✅"

        type_icon  = TYPE_ICONS.get(scam_type, "📧")
        type_label = scam_type.replace("_", " ").title() if scam_type else ""

        type_line = ""
        if is_scam or is_suspicious:
            badge_cls = "badge-red" if is_scam else "badge-amber"
            type_line = (f'<div style="margin-top:10px;">'
                         f'<span class="badge {badge_cls}">{type_icon} {type_label}</span>'
                         f'</div>')

        suspicious_note = ""
        if is_suspicious:
            suspicious_note = ('<div style="margin-top:8px;font-size:0.85rem;color:#FCD34D;">'
                               'Borderline confidence — treat with caution.</div>')

        st.markdown(f"""
        <div class="{banner_cls}">
            <div class="verdict-label" style="color:{colour};">{icon} {verdict}</div>
            <div class="verdict-meta">Confidence: <b style="color:{colour};">{conf:.1f}%</b>
                &nbsp;·&nbsp; Threshold: {threshold:.2f}
            </div>
            {type_line}{suspicious_note}
        </div>
        """, unsafe_allow_html=True)

        # ── Warnings from pipeline ─────────────────────────────────────
        for w in result.get("warnings", []):
            st.warning(w)

        # ── Confidence gauge ───────────────────────────────────────────
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=conf,
            number={"suffix": "%", "font": {"size": 28, "color": colour, "family": "Inter"}},
            gauge={
                "axis":  {"range": [0, 100], "tickcolor": "#374151"},
                "bar":   {"color": colour},
                "bgcolor": "#1A1A1A",
                "steps": [
                    {"range": [0,  40], "color": "#0A1F14"},
                    {"range": [40, 60], "color": "#1C1200"},
                    {"range": [60, 100], "color": "#1C0A0A"},
                ],
                "threshold": {
                    "line": {"color": colour, "width": 3},
                    "thickness": 0.8, "value": conf,
                },
            },
        ))
        fig_gauge.update_layout(
            height=200, margin=dict(t=20, b=0, l=30, r=30),
            paper_bgcolor="rgba(0,0,0,0)", font_color="#9CA3AF",
            font_family="Inter, sans-serif",
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

        st.divider()

        # ── Row 1: Tone + URL/Proximity + Similar scams ────────────────
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown('<div class="sec-head">Tone Analysis</div>', unsafe_allow_html=True)
            tone_df = pd.DataFrame({
                "Signal": ["Urgency", "Fear", "Reward", "Threat"],
                "Score":  [result["tone_urgency"], result["tone_fear"],
                           result["tone_reward"],  result["tone_threat"]],
            })
            fig_tone = px.bar(
                tone_df, x="Signal", y="Score",
                color="Score",
                color_continuous_scale=["#10B981", "#F59E0B", "#EF4444"],
                text="Score",
            )
            fig_tone.update_traces(textposition="outside")
            fig_tone.update_layout(
                **PLOTLY_LAYOUT, height=260,
                coloraxis_showscale=False,
                yaxis=dict(range=[0, max(tone_df["Score"].max() + 1, 4)]),
            )
            st.plotly_chart(fig_tone, use_container_width=True)

        with c2:
            st.markdown('<div class="sec-head">URL & Proximity</div>', unsafe_allow_html=True)

            prox_s = result["proximity_score"]
            if prox_s > 0.65:
                p_col = "#EF4444"
            elif prox_s > 0.45:
                p_col = "#F59E0B"
            else:
                p_col = "#10B981"

            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:10px;">
                <div class="metric-val" style="color:{p_col};">{prox_s:.3f}</div>
                <div class="metric-lbl">Semantic similarity to known scams</div>
            </div>
            """, unsafe_allow_html=True)

            urls = result.get("urls_found", [])
            if urls:
                st.markdown(
                    f'<p style="color:#6B7280;font-size:0.82rem;margin-bottom:6px;">'
                    f'{len(urls)} URL(s) detected</p>',
                    unsafe_allow_html=True,
                )
                for u in urls[:3]:
                    st.code(u[:55] + ("…" if len(u) > 55 else ""), language=None)

                gsb_flagged  = result.get("gsb_flagged", False)
                gsb_threat   = result.get("gsb_threat_type") or "THREAT"
                gsb_attempted = result.get("gsb_attempted", False)
                vt_m  = result.get("vt_malicious", 0)
                vt_s  = result.get("vt_suspicious", 0)
                vt_at = result.get("vt_attempted", False)

                # Google Safe Browsing row
                if gsb_flagged:
                    st.markdown(
                        f'<div style="background:rgba(239,68,68,0.1);border:1px solid #EF4444;'
                        f'border-radius:8px;padding:8px 12px;margin:4px 0;font-size:0.83rem;">'
                        f'🚨 <b style="color:#F87171;">Google Safe Browsing</b>: '
                        f'Flagged as <code style="color:#FCA5A5;">{gsb_threat}</code></div>',
                        unsafe_allow_html=True,
                    )
                elif gsb_attempted:
                    st.markdown(
                        '<div style="background:rgba(16,185,129,0.08);border:1px solid #10B981;'
                        'border-radius:8px;padding:8px 12px;margin:4px 0;font-size:0.83rem;">'
                        '✅ <b style="color:#34D399;">Google Safe Browsing</b>: Clean</div>',
                        unsafe_allow_html=True,
                    )

                # VirusTotal row
                if gsb_flagged:
                    pass  # GSB already condemned — VT skipped for flagged URLs
                elif vt_m > 0:
                    st.markdown(
                        f'<div style="background:rgba(239,68,68,0.1);border:1px solid #EF4444;'
                        f'border-radius:8px;padding:8px 12px;margin:4px 0;font-size:0.83rem;">'
                        f'🚨 <b style="color:#F87171;">VirusTotal</b>: '
                        f'{vt_m} malicious flag(s)</div>',
                        unsafe_allow_html=True,
                    )
                elif vt_s > 0:
                    st.markdown(
                        f'<div style="background:rgba(245,158,11,0.08);border:1px solid #F59E0B;'
                        f'border-radius:8px;padding:8px 12px;margin:4px 0;font-size:0.83rem;">'
                        f'⚠️ <b style="color:#FCD34D;">VirusTotal</b>: '
                        f'{vt_s} suspicious flag(s)</div>',
                        unsafe_allow_html=True,
                    )
                elif vt_at:
                    st.markdown(
                        '<div style="background:rgba(16,185,129,0.08);border:1px solid #10B981;'
                        'border-radius:8px;padding:8px 12px;margin:4px 0;font-size:0.83rem;">'
                        '✅ <b style="color:#34D399;">VirusTotal</b>: Clean</div>',
                        unsafe_allow_html=True,
                    )

                if not gsb_attempted and not vt_at:
                    st.markdown(
                        '<div style="background:#1A1A1A;border:1px solid #2A2A2A;'
                        'border-radius:8px;padding:8px 12px;margin:4px 0;font-size:0.83rem;'
                        'color:#6B7280;">🔍 URL pattern analysis only</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<p style="color:#4B5563;font-size:0.85rem;">No URLs detected.</p>',
                    unsafe_allow_html=True,
                )

        with c3:
            st.markdown('<div class="sec-head">Top 3 Similar Scams</div>', unsafe_allow_html=True)
            df_full    = get_full_df()
            scam_texts = df_full[df_full["label"] == 1]["raw_text"].fillna("").tolist()
            from src._04_vector_proximity import get_similar_scams
            similar = get_similar_scams(message, st_model, faiss_idx, scam_texts, k=3)
            for i, item in enumerate(similar, 1):
                pct     = item["similarity"] * 100
                snippet = item["message"][:130] + ("…" if len(item["message"]) > 130 else "")
                st.markdown(f"""
                <div class="sim-card">
                    <div class="sim-score">#{i} &nbsp;·&nbsp; {pct:.1f}% similarity</div>
                    <div class="sim-text">{snippet}</div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # ── Row 2: Feature contributions + Why explanation ─────────────
        ca, cb = st.columns([3, 2])

        with ca:
            st.markdown(
                '<div class="sec-head">Feature Contributions (numerical signals)</div>',
                unsafe_allow_html=True,
            )
            contribs = result.get("feature_contributions", {})
            if contribs:
                contrib_df = (
                    pd.DataFrame({"Feature": list(contribs.keys()),
                                  "Contribution": list(contribs.values())})
                    .reindex(columns=["Feature", "Contribution"])
                    .assign(abs_val=lambda d: d["Contribution"].abs())
                    .sort_values("abs_val", ascending=False)
                    .head(12)
                    .sort_values("Contribution")
                )
                contrib_df["Colour"] = contrib_df["Contribution"].apply(
                    lambda v: "#EF4444" if v > 0 else "#10B981"
                )
                fig_contrib = go.Figure(go.Bar(
                    x=contrib_df["Contribution"],
                    y=contrib_df["Feature"],
                    orientation="h",
                    marker_color=contrib_df["Colour"].tolist(),
                    text=contrib_df["Contribution"].round(3).astype(str),
                    textposition="outside",
                ))
                fig_contrib.update_layout(
                    **PLOTLY_LAYOUT, height=360,
                    xaxis_title="Contribution to scam score (red = towards scam)",
                    xaxis=dict(zeroline=True, zerolinecolor="#2A2A2A"),
                )
                st.plotly_chart(fig_contrib, use_container_width=True)
            else:
                st.info("Feature contributions not available for this model type.")

        with cb:
            st.markdown('<div class="sec-head">Why is this flagged?</div>', unsafe_allow_html=True)
            reasons = []

            if result["tone_urgency"] > 0:
                reasons.append(f"🔴 **Urgency language** detected ({result['tone_urgency']} signal(s))")
            if result["tone_fear"] > 0:
                reasons.append(f"🔴 **Fear / account-threat language** detected ({result['tone_fear']} signal(s))")
            if result["tone_reward"] > 0:
                reasons.append(f"🔴 **Reward / prize language** detected ({result['tone_reward']} signal(s))")
            if result["tone_threat"] > 0:
                reasons.append(f"🔴 **Legal-threat language** detected ({result['tone_threat']} signal(s))")
            if result.get("scam_phrase_score", 0) > 0:
                reasons.append(f"🔴 **{result['scam_phrase_score']} known scam phrase(s)** matched")
            if result.get("sender_impersonation", 0):
                reasons.append("🔴 **Brand impersonation** — known brand name + action verb co-occur")
            if result.get("url_has_ip"):
                reasons.append("🔴 **IP-based URL** — a hallmark of phishing links")
            if result.get("url_suspicious_tld"):
                reasons.append("🔴 **Suspicious domain extension** (.tk / .xyz / .ml etc.)")
            if result.get("url_suspicious_keyword"):
                reasons.append("🔴 **Phishing keyword** in URL path (verify, login, secure…)")
            if result.get("gsb_flagged"):
                reasons.append(
                    f"🔴 **Google Safe Browsing**: URL flagged as "
                    f"{result.get('gsb_threat_type', 'THREAT')}"
                )
            if result.get("vt_malicious", 0) > 0 and not result.get("gsb_flagged"):
                reasons.append(f"🔴 **VirusTotal**: {result['vt_malicious']} engine(s) flagged URL")
            if result.get("proximity_score", 0) > 0.65:
                reasons.append(
                    f"🔴 **Semantically similar to known scams** "
                    f"(proximity={result['proximity_score']:.3f})"
                )

            if not reasons:
                if is_scam or is_suspicious:
                    prox = result.get("proximity_score", 0)
                    if prox > 0.50:
                        reasons.append(
                            "⚠️ **Message is semantically similar to known scams** — "
                            "FAISS proximity score is elevated."
                        )
                    else:
                        reasons.append(
                            "⚠️ **Subtle linguistic patterns detected** — "
                            "the ML model found statistical signals across word and character "
                            "n-grams that correlate with scam messages."
                        )
                else:
                    reasons = ["✅ No significant scam signals detected. Message appears legitimate."]

            for r_line in reasons:
                st.markdown(r_line)

            st.markdown(f"""
            <div class="info-card">
                <b>Model info</b><br>
                Probabilities calibrated with isotonic regression.<br>
                Decision threshold: {threshold:.2f}
                &nbsp;(≥0.60 = SCAM, {threshold:.2f}–0.60 = SUSPICIOUS).
            </div>
            """, unsafe_allow_html=True)

    elif analyse_btn:
        st.warning("Please enter a message to analyse.")

    else:
        st.markdown("""
        <div style="text-align:center; padding:80px 0; color:#1F2937;">
            <div style="font-size:4.5rem; filter:drop-shadow(0 0 32px rgba(99,102,241,0.4));">🛡️</div>
            <div style="font-size:1.15rem; margin-top:16px; color:#4B5563;">
                Paste a message above and click <b style="color:#6366F1;">Analyse</b> to get started.
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 2 — MODEL PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════

elif page == "📊  Model Performance":
    st.markdown(
        '<h2 style="font-size:1.7rem;font-weight:800;margin-bottom:4px;">'
        '📊 Model Performance</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#6B7280;margin-bottom:20px;">20% hold-out test set · '
        'three classifiers evaluated on the V5 feature matrix.</p>',
        unsafe_allow_html=True,
    )

    models_exist = all(
        os.path.exists(os.path.join(MODELS_PATH, f))
        for f in ["scamradar_model.pkl", "tfidf_vectorizer.pkl",
                  "char_vectorizer.pkl", "scaler.pkl", "scam_faiss.index"]
    )
    if not models_exist:
        st.error("Model files not found in `models/`. Please run `main.py` first.")
        st.stop()

    with st.spinner("Loading evaluation data — this takes ~60 s on first visit…"):
        eval_result = get_evaluation_results()
    if eval_result is None:
        st.error("Model files not found. Please run `main.py` first.")
        st.stop()
    metrics, roc_data, cm_data, trained, ch_df, fi_df = eval_result

    # ── Summary metric cards ────────────────────────────────────────────
    st.markdown('<div class="sec-head">Model Comparison</div>', unsafe_allow_html=True)

    model_names  = list(metrics.keys())
    metric_keys  = ["Accuracy", "Precision", "Recall", "F1", "AUC-ROC"]
    best_vals    = {k: max(metrics[n][k] for n in model_names) for k in metric_keys}

    for name in model_names:
        m = metrics[name]
        cols = st.columns(6)
        cols[0].markdown(
            f'<div style="font-weight:700;color:#F9FAFB;font-size:0.9rem;'
            f'padding-top:18px;padding-left:4px;">{name}</div>',
            unsafe_allow_html=True,
        )
        for col, key in zip(cols[1:], metric_keys):
            val     = m[key]
            is_best = val == best_vals[key]
            colour  = "#6366F1" if is_best else "#6B7280"
            star    = " ★" if is_best else ""
            col.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-val" style="color:{colour};font-size:1.4rem;">{val:.4f}</div>'
                f'<div class="metric-lbl">{key}{star}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown("")

    with st.expander("View full metrics table"):
        tbl = pd.DataFrame(metrics).T.reset_index()
        tbl.columns = ["Model"] + metric_keys
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    st.divider()

    # ── ROC + Confusion matrices ────────────────────────────────────────
    col_roc, col_cm = st.columns(2)

    with col_roc:
        st.markdown('<div class="sec-head">ROC Curves</div>', unsafe_allow_html=True)
        colors = ["#6366F1", "#8B5CF6", "#10B981"]
        fig_roc = go.Figure()
        for (name, (fpr, tpr)), color in zip(roc_data.items(), colors):
            auc = metrics[name]["AUC-ROC"]
            fig_roc.add_trace(go.Scatter(
                x=fpr, y=tpr, mode="lines",
                name=f"{name} (AUC={auc:.4f})",
                line=dict(color=color, width=2.5),
            ))
        fig_roc.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], mode="lines",
            name="Random Guess",
            line=dict(color="#374151", width=1.5, dash="dash"),
        ))
        fig_roc.update_layout(
            **PLOTLY_LAYOUT,
            height=370,
            xaxis_title="False Positive Rate",
            yaxis_title="True Positive Rate",
            legend=dict(x=0.35, y=0.08, bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_roc, use_container_width=True)

    with col_cm:
        st.markdown('<div class="sec-head">Confusion Matrices</div>', unsafe_allow_html=True)
        fig_cm = make_subplots(rows=1, cols=3, subplot_titles=model_names)
        for i, (name, cm) in enumerate(cm_data.items(), 1):
            arr = np.array(cm)
            fig_cm.add_trace(go.Heatmap(
                z=arr,
                x=["Legit", "Scam"], y=["Legit", "Scam"],
                colorscale=[[0, "#1A1A1A"], [1, "#6366F1"]],
                showscale=(i == 3),
                text=arr, texttemplate="%{text}",
                textfont=dict(size=15, color="white"),
                zmin=0,
            ), row=1, col=i)
        fig_cm.update_layout(
            **PLOTLY_LAYOUT,
            height=370,
            margin=dict(t=50, b=10, l=10, r=10),
        )
        fig_cm.update_xaxes(title_text="Predicted")
        fig_cm.update_yaxes(title_text="Actual", col=1)
        st.plotly_chart(fig_cm, use_container_width=True)

    st.divider()

    # ── Feature importance ──────────────────────────────────────────────
    st.markdown(
        '<div class="sec-head">Top 20 Feature Importances — Random Forest</div>',
        unsafe_allow_html=True,
    )
    fig_fi = px.bar(
        fi_df, x="Importance", y="Feature", orientation="h",
        color="Importance",
        color_continuous_scale=[[0, "#2A2A3A"], [1, "#6366F1"]],
    )
    fig_fi.update_layout(
        **PLOTLY_LAYOUT,
        height=480,
        coloraxis_showscale=False,
        yaxis=dict(tickfont=dict(size=11)),
    )
    st.plotly_chart(fig_fi, use_container_width=True)

    st.divider()

    # ── Per-channel ─────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-head">Per-Channel Performance — Random Forest (full dataset)</div>',
        unsafe_allow_html=True,
    )
    col_cht, col_chb = st.columns([2, 3])
    with col_cht:
        st.dataframe(ch_df, use_container_width=True, hide_index=True)
    with col_chb:
        fig_ch = px.bar(
            ch_df.melt(id_vars="Channel",
                       value_vars=["Accuracy", "Precision", "Recall", "F1"]),
            x="Channel", y="value", color="variable",
            barmode="group",
            color_discrete_sequence=["#6366F1", "#8B5CF6", "#10B981", "#F59E0B"],
            labels={"value": "Score", "variable": "Metric"},
        )
        fig_ch.update_layout(
            **PLOTLY_LAYOUT,
            height=300,
            yaxis=dict(range=[0.97, 1.002]),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig_ch, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 3 — DATA EXPLORATION
# ══════════════════════════════════════════════════════════════════════════

elif page == "📈  Data Exploration":
    st.markdown(
        '<h2 style="font-size:1.7rem;font-weight:800;margin-bottom:4px;">'
        '📈 Data Exploration</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#6B7280;margin-bottom:20px;">Distribution and correlation analysis '
        'across all 45 k messages.</p>',
        unsafe_allow_html=True,
    )

    with st.spinner("Loading data…"):
        df = get_full_df()

    # ── Summary metric cards ────────────────────────────────────────────
    summary_cols = st.columns(5)
    summary_data = [
        ("Total Messages",  f"{len(df):,}",                    "#6366F1"),
        ("Scam",            f"{int(df['label'].sum()):,}",      "#EF4444"),
        ("Legit",           f"{int((df['label']==0).sum()):,}", "#10B981"),
        ("Channels",        "4",                                "#8B5CF6"),
        ("Avg Length",      f"{df['text_length'].mean():.0f} ch", "#F59E0B"),
    ]
    for col, (lbl, val, clr) in zip(summary_cols, summary_data):
        col.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-val" style="color:{clr};">{val}</div>'
            f'<div class="metric-lbl">{lbl}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Row 1 ───────────────────────────────────────────────────────────
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        st.markdown('<div class="sec-head">Class Distribution</div>', unsafe_allow_html=True)
        cd = (df["label"]
              .map({0: "Legit", 1: "Scam"})
              .value_counts()
              .reset_index())
        cd.columns = ["Label", "Count"]
        fig1 = px.pie(
            cd, values="Count", names="Label", hole=0.52,
            color="Label",
            color_discrete_map={"Legit": "#10B981", "Scam": "#EF4444"},
        )
        fig1.update_traces(textinfo="percent+label", textfont_size=13)
        fig1.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    with r1c2:
        st.markdown('<div class="sec-head">Label Distribution by Channel</div>', unsafe_allow_html=True)
        ch_grp = (df.groupby(["channel", "label"])
                    .size()
                    .reset_index(name="count"))
        ch_grp["Label"] = ch_grp["label"].map({0: "Legit", 1: "Scam"})
        fig2 = px.bar(
            ch_grp, x="channel", y="count", color="Label",
            barmode="group",
            color_discrete_map={"Legit": "#10B981", "Scam": "#EF4444"},
            labels={"channel": "Channel", "count": "Messages"},
        )
        fig2.update_layout(**PLOTLY_LAYOUT, height=320,
                           legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig2, use_container_width=True)

    # ── Row 2 ───────────────────────────────────────────────────────────
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        st.markdown('<div class="sec-head">Text Length Distribution</div>', unsafe_allow_html=True)
        fig3 = go.Figure()
        for lab, name, color in [(0, "Legit", "#10B981"), (1, "Scam", "#EF4444")]:
            vals = df[df["label"] == lab]["text_length"].clip(upper=3000)
            fig3.add_trace(go.Histogram(
                x=vals, name=name, opacity=0.75,
                marker_color=color, nbinsx=60,
            ))
        fig3.update_layout(
            **PLOTLY_LAYOUT, barmode="overlay", height=320,
            xaxis_title="Character count (capped at 3,000)",
            yaxis_title="Messages",
            legend=dict(orientation="h", y=1.08),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with r2c2:
        st.markdown('<div class="sec-head">Proximity Score Distribution</div>', unsafe_allow_html=True)
        fig4 = go.Figure()
        for lab, name, color in [(0, "Legit", "#10B981"), (1, "Scam", "#EF4444")]:
            vals = df[df["label"] == lab]["proximity_scam_score"]
            fig4.add_trace(go.Histogram(
                x=vals, name=name, opacity=0.75,
                marker_color=color, nbinsx=60,
            ))
        fig4.update_layout(
            **PLOTLY_LAYOUT, barmode="overlay", height=320,
            xaxis_title="Cosine similarity to nearest scam embedding",
            yaxis_title="Messages",
            legend=dict(orientation="h", y=1.08),
        )
        st.plotly_chart(fig4, use_container_width=True)

    # ── Correlation heatmap ─────────────────────────────────────────────
    st.markdown('<div class="sec-head">Feature Correlation Heatmap</div>', unsafe_allow_html=True)
    corr_cols = [
        "text_length", "word_count", "has_url", "url_count",
        "exclamation_count", "uppercase_ratio", "digit_ratio", "urgency_score",
        "tone_urgency", "tone_fear", "tone_reward", "tone_threat",
        "url_suspicious_tld", "url_suspicious_keyword", "url_has_ip",
        "scam_phrase_score", "sender_impersonation_score",
        "proximity_scam_score", "label",
    ]
    corr = df[corr_cols].corr().round(2)
    fig5 = px.imshow(
        corr,
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        text_auto=".2f",
    )
    fig5.update_traces(textfont_size=9)
    fig5.update_layout(
        **PLOTLY_LAYOUT,
        height=560,
        margin=dict(t=10, b=10, l=10, r=10),
        coloraxis_colorbar=dict(thickness=14),
    )
    st.plotly_chart(fig5, use_container_width=True)

    # ── Word count by source ────────────────────────────────────────────
    st.markdown('<div class="sec-head">Word Count Distribution by Source</div>', unsafe_allow_html=True)
    fig6 = px.box(
        df.assign(Label=df["label"].map({0: "Legit", 1: "Scam"})),
        x="source", y="word_count",
        color="Label",
        color_discrete_map={"Legit": "#10B981", "Scam": "#EF4444"},
        labels={"source": "Data Source", "word_count": "Word Count"},
        points=False,
    )
    fig6.update_layout(
        **PLOTLY_LAYOUT, height=360,
        yaxis=dict(range=[0, 600]),
        legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig6, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 4 — ABOUT
# ══════════════════════════════════════════════════════════════════════════

elif page == "ℹ️   About":
    st.markdown(
        '<h2 style="font-size:1.7rem;font-weight:800;margin-bottom:4px;">'
        'ℹ️ About ScamRadar+</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#6B7280;margin-bottom:24px;">BSc Data Science final-year project · '
        'multi-layer AI scam detection across four real-world channels.</p>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown("""
<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:8px;">Project Description</div>
<p style="color:#9CA3AF;line-height:1.8;">
<b style="color:#F9FAFB;">ScamRadar+</b> is an AI-powered scam-message detection system. It uses a
multi-layer approach combining classical NLP, semantic embeddings, and supervised machine learning
to detect scam messages across four real-world communication channels:
<b style="color:#A5B4FC;">Email, SMS, URL phishing pages</b>, and <b style="color:#A5B4FC;">Reddit</b>.
</p>
        """, unsafe_allow_html=True)

        st.divider()

        # Team
        st.markdown(
            '<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:12px;">Team</div>',
            unsafe_allow_html=True,
        )
        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown("""
            <div class="team-card">
                <div class="team-avatar">👨‍💻</div>
                <div class="team-name">Ameer Hassouna</div>
                <div class="team-role">Lead Developer & Data Scientist</div>
            </div>
            """, unsafe_allow_html=True)
        with tc2:
            st.markdown("""
            <div class="team-card">
                <div class="team-avatar">🎓</div>
                <div class="team-name">Supervisor</div>
                <div class="team-role">TBC</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Dataset
        st.markdown(
            '<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:12px;">Dataset</div>',
            unsafe_allow_html=True,
        )
        ds_cols = st.columns(3)
        ds_stats = [
            ("Total", "45,851", "#6366F1"),
            ("Scam",  "21,955 (47.9%)", "#EF4444"),
            ("Legit", "23,896 (52.1%)", "#10B981"),
        ]
        for col, (lbl, val, clr) in zip(ds_cols, ds_stats):
            col.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-val" style="color:{clr};font-size:1.2rem;">{val}</div>'
                f'<div class="metric-lbl">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<p style="color:#6B7280;font-size:0.82rem;margin-top:10px;">'
            'Sources: Enron · SpamAssassin · SMS Spam Corpus · PhishTank · Reddit<br>'
            'Storage: SQLite normalised schema (Message, Channel, DataSource, MessageFeatures)</p>',
            unsafe_allow_html=True,
        )

        st.divider()

        # Methodology
        st.markdown(
            '<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:12px;">Methodology</div>',
            unsafe_allow_html=True,
        )
        steps = [
            ("Data Pipeline", "All datasets unified into SQLite. Pre-computed features stored in MessageFeatures for fast retrieval."),
            ("Feature Engineering", "Tone detection (urgency/fear/reward/threat), URL analysis, L33t-speak normalisation, TF-IDF word + character n-grams."),
            ("Semantic Similarity", "45,851 messages encoded with Sentence Transformers (all-MiniLM-L6-v2, 384-dim). FAISS flat index for proximity scoring."),
            ("Classifiers", "Logistic Regression · Random Forest · Decision Tree trained on 8,016-feature combined matrix."),
            ("Adversarial Robustness", "Tested against L33t speak, emoji substitution, mixed case, extra whitespace — all variants correctly classified."),
            ("VirusTotal Integration", "Optional real-time URL reputation check via VirusTotal API v3."),
        ]
        for i, (title, desc) in enumerate(steps, 1):
            st.markdown(f"""
            <div style="display:flex;gap:14px;margin-bottom:14px;align-items:flex-start;">
                <div style="min-width:28px;height:28px;background:linear-gradient(135deg,#6366F1,#8B5CF6);
                    border-radius:50%;display:flex;align-items:center;justify-content:center;
                    font-size:0.75rem;font-weight:700;color:white;margin-top:2px;">{i}</div>
                <div>
                    <div style="color:#F9FAFB;font-weight:600;font-size:0.9rem;">{title}</div>
                    <div style="color:#6B7280;font-size:0.82rem;margin-top:3px;line-height:1.6;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_b:
        # Tech stack
        st.markdown(
            '<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:12px;">Tech Stack</div>',
            unsafe_allow_html=True,
        )
        tech_items = [
            ("Language",      "Python 3.12"),
            ("ML",            "scikit-learn"),
            ("Embeddings",    "Sentence Transformers"),
            ("Vector Search", "FAISS"),
            ("Database",      "SQLite"),
            ("Dashboard",     "Streamlit + Plotly"),
            ("URL Scanning",  "VirusTotal API v3"),
        ]
        pills_html = ""
        for comp, tech_name in tech_items:
            pills_html += f'<div class="tech-pill"><span>{comp}</span>{tech_name}</div>'
        st.markdown(f'<div style="line-height:2.4;">{pills_html}</div>', unsafe_allow_html=True)

        st.divider()

        # Pipeline files
        st.markdown(
            '<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:12px;">Pipeline Files</div>',
            unsafe_allow_html=True,
        )
        pipeline_files = [
            "Data Loading & EDA",
            "Feature Engineering",
            "TF-IDF Vectorisation",
            "FAISS Vector Proximity",
            "Model Training",
            "Evaluation & Metrics",
            "Hyperparameter Tuning",
            "Adversarial Testing",
            "Prediction Pipeline",
        ]
        for i, desc in enumerate(pipeline_files, 1):
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
                f'border-bottom:1px solid #1F1F1F;">'
                f'<code style="color:#6366F1;font-size:0.78rem;background:#1A1A1A;'
                f'padding:2px 8px;border-radius:4px;">0{i:01d}_</code>'
                f'<span style="color:#9CA3AF;font-size:0.83rem;">{desc}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # Model perf table
        st.markdown(
            '<div style="color:#F9FAFB;font-size:1.05rem;font-weight:700;margin-bottom:12px;">'
            'Classifier Results</div>',
            unsafe_allow_html=True,
        )
        perf_data = [
            ("Logistic Regression", "0.9811", "0.9983"),
            ("Random Forest",       "0.9761", "0.9956"),
            ("Decision Tree",       "0.9735", "0.9745"),
        ]
        for model_name, f1, auc in perf_data:
            st.markdown(f"""
            <div style="background:#1A1A1A;border:1px solid #2A2A2A;border-radius:8px;
                padding:10px 14px;margin-bottom:6px;display:flex;
                justify-content:space-between;align-items:center;">
                <span style="color:#9CA3AF;font-size:0.82rem;">{model_name}</span>
                <div style="display:flex;gap:10px;">
                    <span class="badge badge-indigo">F1 {f1}</span>
                    <span class="badge badge-green">AUC {auc}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
