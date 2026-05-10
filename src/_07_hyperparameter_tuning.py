"""
ScamRadar+ | Step 07: Hyperparameter Tuning
RandomizedSearchCV for Random Forest
"""

from sklearn.model_selection import RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import numpy as np


def tune_random_forest(X_train, y_train, X_test, y_test, n_iter=10):
    param_dist = {
        'n_estimators':     [100, 200, 300],
        'max_depth':        [None, 20, 30, 50],
        'min_samples_split':[2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features':     ['sqrt', 'log2']
    }

    rf_base = RandomForestClassifier(random_state=42, n_jobs=-1)

    search = RandomizedSearchCV(
        rf_base,
        param_distributions=param_dist,
        n_iter=n_iter,
        cv=3,
        scoring='f1',
        random_state=42,
        n_jobs=-1,
        verbose=1
    )

    search.fit(X_train, y_train)

    print(f"\n✅ Best parameters: {search.best_params_}")
    print(f"✅ Best CV F1 score: {search.best_score_:.4f}")

    best_rf = search.best_estimator_
    y_pred  = best_rf.predict(X_test)
    y_prob  = best_rf.predict_proba(X_test)[:, 1]

    print(f"\nTuned Random Forest on Test Set:")
    print(f"  Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"  Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"  Recall:    {recall_score(y_test, y_pred):.4f}")
    print(f"  F1 Score:  {f1_score(y_test, y_pred):.4f}")
    print(f"  AUC-ROC:   {roc_auc_score(y_test, y_prob):.4f}")

    return best_rf, search.best_params_
