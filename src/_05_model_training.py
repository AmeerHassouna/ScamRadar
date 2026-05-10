"""
ScamRadar+ | Step 05: Model Training  (v5)
LR / DT / RF + confidence calibration + threshold optimisation.
"""

import time, pickle, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import f1_score
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MODELS_PATH

os.makedirs(MODELS_PATH, exist_ok=True)


class _IsotonicCalibratedModel:
    """Thin wrapper: applies isotonic calibration on top of a fitted classifier."""

    def __init__(self, base_model, calibrator):
        self.base_model  = base_model
        self.calibrator  = calibrator

    def predict_proba(self, X):
        raw = self.base_model.predict_proba(X)[:, 1]
        cal = self.calibrator.predict(raw)
        return np.column_stack([1 - cal, cal])

    def predict(self, X, threshold=0.5):
        return (self.predict_proba(X)[:, 1] >= threshold).astype(int)

    # Forward unknown attributes to base model (e.g. coef_, feature_importances_)
    # Guard against recursion during unpickling before __init__ runs.
    def __getattr__(self, name):
        if name in ('base_model', 'calibrator'):
            raise AttributeError(name)
        return getattr(self.base_model, name)


def train_all_models(X_train, y_train):
    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
        "Decision Tree":       DecisionTreeClassifier(random_state=42),
        "Random Forest":       RandomForestClassifier(n_estimators=100,
                                                       random_state=42, n_jobs=-1),
    }
    trained = {}
    for name, m in models.items():
        print(f"Training {name}...")
        t0 = time.time()
        m.fit(X_train, y_train)
        trained[name] = m
        print(f"✅ {name} trained in {time.time() - t0:.1f}s\n")
    print("✅ All models trained!")
    return trained


def calibrate_model(model, X_val, y_val):
    """
    Fit an isotonic calibrator on held-out validation probabilities
    and return a wrapped model with corrected predict_proba.
    (cv='prefit' removed in sklearn 1.4+; this approach is equivalent.)
    """
    print("Calibrating model probabilities (isotonic regression)...")
    raw_probs  = model.predict_proba(X_val)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds='clip')
    calibrator.fit(raw_probs, y_val)
    print("✅ Calibration complete!")
    return _IsotonicCalibratedModel(model, calibrator)


def find_optimal_threshold(model, X_val, y_val, step=0.01):
    """
    Sweep thresholds from 0.1 to 0.9 and return the one that maximises
    F1 on the validation set.
    """
    print("Finding optimal decision threshold...")
    probs = model.predict_proba(X_val)[:, 1]
    thresholds = np.arange(0.40, 0.91, step)   # floor at 0.40 to prevent false positives
    best_t, best_f1 = 0.40, 0.0
    for t in thresholds:
        preds = (probs >= t).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    print(f"✅ Optimal threshold: {best_t:.2f}  (F1={best_f1:.4f})")
    return round(float(best_t), 2), round(float(best_f1), 4)


def save_best_model(model, threshold: float = 0.5):
    """Save model + threshold together so the pipeline stays consistent."""
    payload = {'model': model, 'threshold': threshold}
    pickle.dump(payload, open(os.path.join(MODELS_PATH, 'scamradar_model.pkl'), 'wb'))
    print(f"✅ Model saved  (threshold={threshold:.2f})  →  models/scamradar_model.pkl")


def load_model():
    payload = pickle.load(open(os.path.join(MODELS_PATH, 'scamradar_model.pkl'), 'rb'))
    # Support both old format (bare model) and new format (dict)
    if isinstance(payload, dict):
        return payload['model'], payload.get('threshold', 0.5)
    return payload, 0.5
