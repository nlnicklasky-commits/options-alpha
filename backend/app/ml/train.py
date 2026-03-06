"""Model training pipeline with walk-forward validation.

Trains an ensemble of XGBoost + LightGBM + RandomForest with a
LogisticRegression meta-learner on stacked predictions.
"""

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Generator

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.features import FeatureBuilder
from app.ml.labels import LabelGenerator
from app.models.stocks import Stock

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


class ModelTrainer:
    """Orchestrates training of breakout prediction ensemble."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.feature_builder = FeatureBuilder(session)
        self.label_generator = LabelGenerator(session)

    async def prepare_data(
        self,
        start_date: date,
        end_date: date,
        label_type: str = "breakout",
        threshold_pct: float = 0.10,
        horizon_days: int = 20,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Build feature matrix + labels. Returns (X, y, dates)."""
        # Get active stock IDs
        stmt = select(Stock.id).where(Stock.is_active.is_(True))
        result = await self.session.execute(stmt)
        stock_ids = [r[0] for r in result.all()]

        if not stock_ids:
            raise ValueError("No active stocks found")

        logger.info("Building feature matrix for %d stocks...", len(stock_ids))

        # Build features
        df = await self.feature_builder.build_feature_matrix(stock_ids, start_date, end_date)
        if df.empty:
            raise ValueError("No feature data found for date range")

        df = self.feature_builder.add_lookback_features(df)
        df = self.feature_builder.remove_redundant(df, threshold=0.95)

        # Build labels
        bars_df = await self.label_generator.fetch_bars(stock_ids)

        if label_type == "breakout":
            labels = self.label_generator.label_breakout(bars_df, threshold_pct, horizon_days)
        elif label_type == "max_gain":
            labels = self.label_generator.label_max_gain(bars_df, horizon_days)
        elif label_type == "risk_reward":
            labels = self.label_generator.label_risk_reward(bars_df, horizon_days)
        elif label_type == "call_pnl":
            labels = self.label_generator.label_call_pnl(bars_df, dte=30, horizon_days=horizon_days)
        else:
            raise ValueError(f"Unknown label type: {label_type}")

        # Align labels with feature matrix via merge on (stock_id, date)
        bars_df["label"] = labels
        label_df = bars_df[["stock_id", "date", "label"]].dropna(subset=["label"])
        df = df.merge(label_df, on=["stock_id", "date"], how="inner")

        # Separate features, labels, dates
        feature_names = self.feature_builder.get_feature_names()
        available_features = [f for f in feature_names if f in df.columns]

        X = df[available_features].copy()
        y = df["label"].copy()
        dates_series = df["date"].copy()

        # Forward fill then drop remaining NaNs
        X = X.ffill().bfill()
        mask = ~X.isna().any(axis=1)
        X = X.loc[mask]
        y = y.loc[mask]
        dates_series = dates_series.loc[mask]

        logger.info(
            "Prepared data: %d samples, %d features, %.1f%% positive",
            len(X), X.shape[1], y.mean() * 100,
        )
        return X, y, dates_series

    @staticmethod
    def walk_forward_split(
        X: pd.DataFrame,
        y: pd.Series,
        dates: pd.Series,
        train_years: int = 3,
        val_months: int = 6,
    ) -> Generator[tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series], None, None]:
        """Walk-forward cross-validation splits.

        Yields (X_train, y_train, X_val, y_val) tuples, rolling forward
        by val_months each iteration.
        """
        unique_dates = sorted(dates.unique())
        if not unique_dates:
            return

        min_date = pd.Timestamp(unique_dates[0])
        max_date = pd.Timestamp(unique_dates[-1])
        dates_ts = pd.to_datetime(dates)

        train_delta = pd.DateOffset(years=train_years)
        val_delta = pd.DateOffset(months=val_months)

        # First split starts at min_date + train_years
        val_start = min_date + train_delta

        while val_start < max_date:
            val_end = val_start + val_delta

            train_mask = dates_ts < val_start
            val_mask = (dates_ts >= val_start) & (dates_ts < val_end)

            if train_mask.sum() < 100 or val_mask.sum() < 20:
                val_start = val_end
                continue

            yield (
                X.loc[train_mask],
                y.loc[train_mask],
                X.loc[val_mask],
                y.loc[val_mask],
            )

            val_start = val_end

    @staticmethod
    def train_ensemble(
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> dict[str, object]:
        """Train XGBoost + LightGBM + RandomForest base models."""
        import lightgbm as lgb
        import xgboost as xgb

        # Handle class imbalance
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        scale_pos_weight = n_neg / max(n_pos, 1)

        # XGBoost
        xgb_model = xgb.XGBClassifier(
            max_depth=6,
            n_estimators=500,
            learning_rate=0.05,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
        xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_train, y_train)],
            verbose=False,
        )

        # LightGBM
        lgb_model = lgb.LGBMClassifier(
            num_leaves=31,
            n_estimators=500,
            learning_rate=0.05,
            is_unbalance=True,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        lgb_model.fit(X_train, y_train)

        # RandomForest
        rf_model = RandomForestClassifier(
            n_estimators=300,
            max_depth=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        rf_model.fit(X_train, y_train)

        return {"xgboost": xgb_model, "lightgbm": lgb_model, "random_forest": rf_model}

    @staticmethod
    def evaluate(
        models: dict[str, object],
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> dict[str, float]:
        """Evaluate ensemble on validation set."""
        # Average probabilities from all models
        probas = []
        for name, model in models.items():
            proba = model.predict_proba(X_val)[:, 1]  # type: ignore[union-attr]
            probas.append(proba)
        avg_proba = np.mean(probas, axis=0)
        y_pred = (avg_proba >= 0.5).astype(int)

        # Profit factor: sum of gains on correct calls / sum of losses on wrong calls
        tp_mask = (y_pred == 1) & (y_val == 1)
        fp_mask = (y_pred == 1) & (y_val == 0)
        profit_factor = tp_mask.sum() / max(fp_mask.sum(), 1)

        metrics = {
            "accuracy": float(accuracy_score(y_val, y_pred)),
            "precision": float(precision_score(y_val, y_pred, zero_division=0)),
            "recall": float(recall_score(y_val, y_pred, zero_division=0)),
            "f1": float(f1_score(y_val, y_pred, zero_division=0)),
            "auc_roc": float(roc_auc_score(y_val, avg_proba)) if len(y_val.unique()) > 1 else 0.0,
            "profit_factor": float(profit_factor),
        }
        return metrics

    @staticmethod
    def train_meta_learner(
        models: dict[str, object],
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> LogisticRegression:
        """Train LogisticRegression meta-learner on stacked base model predictions."""
        stack = np.column_stack([
            model.predict_proba(X_val)[:, 1]  # type: ignore[union-attr]
            for model in models.values()
        ])
        meta = LogisticRegression(random_state=42, max_iter=1000)
        meta.fit(stack, y_val)
        return meta

    @staticmethod
    def save_model(
        models: dict[str, object],
        meta_learner: LogisticRegression,
        feature_names: list[str],
        version: str,
        metrics: dict[str, float] | None = None,
    ) -> Path:
        """Save ensemble + meta-learner to disk."""
        MODELS_DIR.mkdir(exist_ok=True)
        artifact = {
            "models": models,
            "meta_learner": meta_learner,
            "feature_names": feature_names,
            "version": version,
            "metrics": metrics or {},
        }
        path = MODELS_DIR / f"ensemble_v{version}.joblib"
        joblib.dump(artifact, path)

        # Update 'latest' symlink (or just a text file on Windows)
        latest_path = MODELS_DIR / "latest.txt"
        latest_path.write_text(f"ensemble_v{version}.joblib")

        logger.info("Model saved to %s", path)
        return path

    @staticmethod
    async def save_model_to_db(
        session: AsyncSession,
        models: dict[str, object],
        meta_learner: LogisticRegression,
        feature_names: list[str],
        version: str,
        metrics: dict[str, float] | None = None,
        sample_count: int = 0,
    ) -> None:
        """Persist model artifact as binary blob in PostgreSQL for Railway deploys."""
        import io
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from app.models.model_artifact import ModelArtifact

        artifact = {
            "models": models,
            "meta_learner": meta_learner,
            "feature_names": feature_names,
            "version": version,
            "metrics": metrics or {},
        }

        buf = io.BytesIO()
        joblib.dump(artifact, buf)
        blob = buf.getvalue()

        stmt = pg_insert(ModelArtifact).values(
            version=version,
            artifact_blob=blob,
            file_size_bytes=len(blob),
            metrics=metrics,
            feature_count=len(feature_names),
            sample_count=sample_count,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["version"],
            set_={
                "artifact_blob": blob,
                "file_size_bytes": len(blob),
                "metrics": metrics,
                "feature_count": len(feature_names),
                "sample_count": sample_count,
            },
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("Model v%s saved to database (%d bytes)", version, len(blob))

    async def full_training_run(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        label_type: str = "breakout",
    ) -> dict:
        """Orchestrate full walk-forward training pipeline."""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365 * 4)  # 4 years

        logger.info("Starting training run: %s to %s", start_date, end_date)

        X, y, dates = await self.prepare_data(start_date, end_date, label_type)

        all_metrics: list[dict[str, float]] = []
        best_models = None
        best_meta = None
        best_auc = -1.0

        for fold_idx, (X_train, y_train, X_val, y_val) in enumerate(
            self.walk_forward_split(X, y, dates)
        ):
            logger.info(
                "Fold %d: train=%d, val=%d, pos_rate=%.1f%%",
                fold_idx, len(X_train), len(X_val), y_train.mean() * 100,
            )

            models = self.train_ensemble(X_train, y_train)
            metrics = self.evaluate(models, X_val, y_val)
            logger.info("Fold %d metrics: %s", fold_idx, json.dumps(metrics, indent=2))
            all_metrics.append(metrics)

            if metrics["auc_roc"] > best_auc:
                best_auc = metrics["auc_roc"]
                best_models = models
                best_meta = self.train_meta_learner(models, X_val, y_val)

        if best_models is None:
            raise ValueError("No valid training folds produced")

        # Average metrics across folds
        avg_metrics = {}
        for key in all_metrics[0]:
            avg_metrics[key] = float(np.mean([m[key] for m in all_metrics]))

        version = end_date.strftime("%Y%m%d")
        feature_names = self.feature_builder.get_feature_names()
        model_path = self.save_model(best_models, best_meta, feature_names, version, avg_metrics)

        # Also persist to database so model survives container restarts
        try:
            await self.save_model_to_db(
                self.session, best_models, best_meta, feature_names,
                version, avg_metrics, sample_count=len(X),
            )
        except Exception:
            logger.exception("Failed to save model to DB (filesystem copy still available)")

        result = {
            "version": version,
            "model_path": str(model_path),
            "num_folds": len(all_metrics),
            "avg_metrics": avg_metrics,
            "feature_count": len(feature_names),
            "sample_count": len(X),
        }
        logger.info("Training complete: %s", json.dumps(result, indent=2))
        return result
