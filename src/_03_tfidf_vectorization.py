"""
ScamRadar+ | Step 03: TF-IDF Vectorization  (v5)
Word-level TF-IDF + Character n-gram features.
NUMERICAL_FEATURES_V5 now includes dual proximity + 9 new engineered features.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from scipy.sparse import hstack, csr_matrix
import pickle, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MODELS_PATH, NUMERICAL_FEATURES_V4, NUMERICAL_FEATURES_V5

os.makedirs(MODELS_PATH, exist_ok=True)

# Re-export for backward compatibility
NUMERICAL_FEATURES    = NUMERICAL_FEATURES_V4   # original 16-feature set
NUMERICAL_FEATURES_V5 = NUMERICAL_FEATURES_V5   # new 27-feature set (imported from config)


def build_tfidf(df):
    print("Building TF-IDF features...")
    df['raw_text'] = df['raw_text'].fillna('')

    tfidf = TfidfVectorizer(
        max_features=5000, ngram_range=(1, 2),
        stop_words='english', sublinear_tf=True,
    )
    X_tfidf = tfidf.fit_transform(df['raw_text'])
    print(f"✅ TF-IDF shape: {X_tfidf.shape}")

    char_tfidf = TfidfVectorizer(
        analyzer='char_wb', ngram_range=(3, 5),
        max_features=3000, sublinear_tf=True,
    )
    X_char = char_tfidf.fit_transform(df['raw_text'])
    print(f"✅ Char n-gram shape: {X_char.shape}")

    return tfidf, char_tfidf, X_tfidf, X_char


def build_combined_features(df, X_tfidf, X_char, numerical_features):
    print("Combining all features...")
    X_num  = df[numerical_features].fillna(0).values
    scaler = StandardScaler()
    X_num_scaled = scaler.fit_transform(X_num)
    X_combined = hstack([X_tfidf, X_char, csr_matrix(X_num_scaled)])
    print(f"✅ Combined feature matrix shape: {X_combined.shape}")
    return X_combined, scaler


def split_data(X_combined, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X_combined, y, test_size=0.2, random_state=42, stratify=y,
    )
    print(f"✅ Train: {X_train.shape[0]} | Test: {X_test.shape[0]}")
    return X_train, X_test, y_train, y_test


def save_vectorizers(tfidf, char_tfidf, scaler):
    pickle.dump(tfidf,      open(os.path.join(MODELS_PATH, 'tfidf_vectorizer.pkl'), 'wb'))
    pickle.dump(char_tfidf, open(os.path.join(MODELS_PATH, 'char_vectorizer.pkl'),  'wb'))
    pickle.dump(scaler,     open(os.path.join(MODELS_PATH, 'scaler.pkl'),            'wb'))
    print("✅ Vectorizers and scaler saved to models/")
