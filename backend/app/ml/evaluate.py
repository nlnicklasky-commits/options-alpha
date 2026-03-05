"""Model evaluation utilities.

Provides classification metrics, feature importance analysis,
calibration curves, and regime-based breakdowns.
"""

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve as sk_calibration_curve
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class ModelEvaluator:
    """Evaluates trained models with detailed metrics and breakdowns."""

    @staticmethod
    def classification_report(
        y_true: np.ndarray | pd.Series,
        y_pred: np.ndarray | pd.Series,
        y_proba: np.ndarray | pd.Series,
    ) -> dict[str, float]:
        """Compute precision, recall, f1, AUC-ROC."""
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        y_proba = np.asarray(y_proba)

        has_both_classes = len(np.unique(y_true)) > 1

        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "auc_roc": float(roc_auc_score(y_true, y_proba)) if has_both_classes else 0.0,
            "support_positive": int(y_true.sum()),
            "support_negative": int(len(y_true) - y_true.sum()),
        }

    @staticmethod
    def feature_importance(
        models: dict[str, object],
        feature_names: list[str] | None = None,
        top_n: int = 30,
    ) -> list[dict[str, object]]:
        """Aggregate feature importance across ensemble, return top N features."""
        all_importances: list[np.ndarray] = []

        for name, model in models.items():
            if hasattr(model, "feature_importances_"):
                imp = np.array(model.feature_importances_)
                # Normalize to sum to 1
                total = imp.sum()
                if total > 0:
                    imp = imp / total
                all_importances.append(imp)

        if not all_importances:
            return []

        # Average across models
        avg_imp = np.mean(all_importances, axis=0)

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(len(avg_imp))]

        # Sort by importance
        sorted_idx = np.argsort(avg_imp)[::-1][:top_n]
        return [
            {"feature": feature_names[i], "importance": float(avg_imp[i])}
            for i in sorted_idx
        ]

    @staticmethod
    def score_distribution(
        y_proba: np.ndarray | pd.Series,
        n_bins: int = 20,
    ) -> list[dict[str, object]]:
        """Histogram of predicted probabilities."""
        y_proba = np.asarray(y_proba)
        counts, bin_edges = np.histogram(y_proba, bins=n_bins, range=(0, 1))
        return [
            {
                "bin_start": float(bin_edges[i]),
                "bin_end": float(bin_edges[i + 1]),
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]

    @staticmethod
    def calibration_curve(
        y_true: np.ndarray | pd.Series,
        y_proba: np.ndarray | pd.Series,
        n_bins: int = 10,
    ) -> list[dict[str, float]]:
        """Calibration: are 80% confidence predictions right 80% of the time?"""
        y_true = np.asarray(y_true)
        y_proba = np.asarray(y_proba)

        if len(np.unique(y_true)) < 2:
            return []

        fraction_pos, mean_predicted = sk_calibration_curve(
            y_true, y_proba, n_bins=n_bins, strategy="uniform"
        )
        return [
            {"predicted": float(mean_predicted[i]), "actual": float(fraction_pos[i])}
            for i in range(len(fraction_pos))
        ]

    @staticmethod
    def regime_breakdown(
        y_true: np.ndarray | pd.Series,
        y_pred: np.ndarray | pd.Series,
        regime_labels: np.ndarray | pd.Series,
    ) -> dict[str, dict[str, float]]:
        """Performance breakdown by market regime (BULL/BEAR/CHOPPY etc.)."""
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        regime_labels = np.asarray(regime_labels)

        results: dict[str, dict[str, float]] = {}
        for regime in np.unique(regime_labels):
            if regime is None or (isinstance(regime, float) and np.isnan(regime)):
                continue
            mask = regime_labels == regime
            if mask.sum() < 5:
                continue

            yt = y_true[mask]
            yp = y_pred[mask]
            results[str(regime)] = {
                "accuracy": float(accuracy_score(yt, yp)),
                "precision": float(precision_score(yt, yp, zero_division=0)),
                "recall": float(recall_score(yt, yp, zero_division=0)),
                "f1": float(f1_score(yt, yp, zero_division=0)),
                "count": int(mask.sum()),
                "positive_rate": float(yt.mean()),
            }

        return results
