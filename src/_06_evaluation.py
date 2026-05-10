"""
ScamRadar+ | Step 06: Model Evaluation
Metrics, confusion matrix, ROC curve, per-channel evaluation, cross-validation
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, confusion_matrix, roc_auc_score,
                             roc_curve, classification_report)
from sklearn.model_selection import StratifiedKFold, cross_val_score

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'outputs')
os.makedirs(OUTPUT_PATH, exist_ok=True)


def evaluate_all_models(trained_models, X_test, y_test):
    results = {}
    for name, model in trained_models.items():
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        acc  = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred)
        rec  = recall_score(y_test, y_pred)
        f1   = f1_score(y_test, y_pred)
        auc  = roc_auc_score(y_test, y_prob)

        results[name] = {'Accuracy': acc, 'Precision': prec, 'Recall': rec, 'F1': f1, 'AUC': auc}

        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")
        print(f"  Accuracy:  {acc:.4f}")
        print(f"  Precision: {prec:.4f}")
        print(f"  Recall:    {rec:.4f}")
        print(f"  F1 Score:  {f1:.4f}")
        print(f"  AUC-ROC:   {auc:.4f}")
        print(f"\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=['Legit (0)', 'Scam (1)']))

    return results


def plot_confusion_matrices(trained_models, X_test, y_test):
    fig, axes = plt.subplots(1, len(trained_models), figsize=(6*len(trained_models), 5))
    if len(trained_models) == 1:
        axes = [axes]

    for ax, (name, model) in zip(axes, trained_models.items()):
        y_pred = model.predict(X_test)
        cm = confusion_matrix(y_test, y_pred)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax,
                    xticklabels=['Legit', 'Scam'],
                    yticklabels=['Legit', 'Scam'])
        ax.set_title(f'{name}')
        ax.set_xlabel('Predicted')
        ax.set_ylabel('Actual')

    plt.suptitle('Confusion Matrices - All Models', fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_PATH, 'confusion_matrices.png'), dpi=200)
    plt.close()
    print("✅ Confusion matrices saved!")


def plot_roc_curves(trained_models, X_test, y_test):
    plt.figure(figsize=(10, 6))
    for name, model in trained_models.items():
        y_prob = model.predict_proba(X_test)[:, 1]
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        auc = roc_auc_score(y_test, y_prob)
        plt.plot(fpr, tpr, label=f'{name} (AUC = {auc:.4f})')

    plt.plot([0, 1], [0, 1], 'k--', label='Random Guess')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve - All Models')
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_PATH, 'roc_curve.png'), dpi=200)
    plt.close()
    print("✅ ROC curve saved!")


def plot_feature_importance(rf_model, tfidf, char_tfidf, numerical_features):
    import numpy as np
    tfidf_names = tfidf.get_feature_names_out().tolist()
    char_names  = [f'char_{f}' for f in char_tfidf.get_feature_names_out()]
    all_names   = tfidf_names + char_names + numerical_features

    importances = rf_model.feature_importances_
    indices = np.argsort(importances)[::-1][:20]
    top_features = [all_names[i] for i in indices]
    top_importances = importances[indices]

    plt.figure(figsize=(12, 6))
    plt.barh(top_features[::-1], top_importances[::-1])
    plt.xlabel('Feature Importance')
    plt.title('Top 20 Most Important Features - Random Forest')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_PATH, 'feature_importance.png'), dpi=200)
    plt.close()
    print("✅ Feature importance saved!")


def cross_validate_models(trained_models, X_combined, y):
    print("Running 5-Fold Cross Validation...\n")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for name, model in trained_models.items():
        scores = cross_val_score(model, X_combined, y, cv=skf, scoring='f1', n_jobs=-1)
        print(f"{name}:")
        print(f"  F1 per fold: {[round(s, 4) for s in scores]}")
        print(f"  Mean F1:     {scores.mean():.4f}")
        print(f"  Std F1:      {scores.std():.4f}\n")

    print("✅ Cross validation complete!")


def evaluate_per_channel(df, rf_model, X_combined, y):
    y_pred_all = rf_model.predict(X_combined)
    df = df.copy()
    df['prediction'] = y_pred_all

    print("Random Forest Performance Per Channel:")
    print("="*60)
    for channel in df['channel'].unique():
        mask = df['channel'] == channel
        y_true_ch = df[mask]['label']
        y_pred_ch = df[mask]['prediction']

        acc  = accuracy_score(y_true_ch, y_pred_ch)
        prec = precision_score(y_true_ch, y_pred_ch, zero_division=0)
        rec  = recall_score(y_true_ch, y_pred_ch, zero_division=0)
        f1   = f1_score(y_true_ch, y_pred_ch, zero_division=0)

        print(f"\nChannel: {channel.upper()} ({mask.sum()} messages)")
        print(f"  Accuracy:  {acc:.4f}")
        print(f"  Precision: {prec:.4f}")
        print(f"  Recall:    {rec:.4f}")
        print(f"  F1 Score:  {f1:.4f}")

    print("\n✅ Per-channel evaluation complete!")
