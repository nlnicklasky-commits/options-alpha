"""Model scoring service.

Loads trained ensemble, scores stocks, and stores signals in the database.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import delete, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.features import FeatureBuilder
from app.models.daily_bars import DailyBar
from app.models.options import OptionsSnapshot
from app.models.signals import Signal
from app.models.stocks import Stock
from app.models.technicals import TechnicalSnapshot

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "ml" / "models"


class ModelScorer:
    """Scores stocks using the trained ensemble model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._artifact: dict | None = None

    def load_model(self, version: str = "latest") -> bool:
        """Load ensemble from joblib. Returns True if loaded, False if no model found."""
        # Try filesystem first
        if version == "latest":
            latest_file = MODELS_DIR / "latest.txt"
            if not latest_file.exists():
                # Try loading from DB
                if self._load_from_db():
                    return True
                logger.warning("No trained model found. Run training first.")
                return False
            model_name = latest_file.read_text().strip()
            path = MODELS_DIR / model_name
        else:
            path = MODELS_DIR / f"ensemble_v{version}.joblib"

        if not path.exists():
            # Try loading from DB
            if self._load_from_db(version):
                return True
            logger.warning("Model not found: %s", path)
            return False

        self._artifact = joblib.load(path)
        logger.info("Loaded model version: %s", self._artifact.get("version", "unknown"))
        return True

    def _load_from_db(self, version: str = "latest") -> bool:
        """Try to load model artifact from PostgreSQL (sync query via run_sync)."""
        try:
            import io
            from sqlalchemy import select as sync_select
            from app.models.model_artifact import ModelArtifact

            # Use a sync approach: we'll do this in score methods that are async
            # For now, just mark as not available — async load handled separately
            return False
        except Exception:
            logger.exception("Failed to load model from DB")
            return False

    async def _try_load_from_db(self) -> bool:
        """Async: load latest model artifact from PostgreSQL."""
        try:
            from app.models.model_artifact import ModelArtifact

            stmt = (
                select(ModelArtifact)
                .order_by(ModelArtifact.created_at.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return False

            import io
            artifact = joblib.load(io.BytesIO(row.artifact_blob))
            self._artifact = artifact
            logger.info("Loaded model version %s from database", artifact.get("version", "unknown"))

            # Cache to filesystem for faster next load
            try:
                MODELS_DIR.mkdir(parents=True, exist_ok=True)
                version = artifact.get("version", "unknown")
                path = MODELS_DIR / f"ensemble_v{version}.joblib"
                joblib.dump(artifact, path)
                latest_path = MODELS_DIR / "latest.txt"
                latest_path.write_text(f"ensemble_v{version}.joblib")
                logger.info("Cached model to filesystem: %s", path)
            except Exception:
                logger.warning("Could not cache model to filesystem (OK on ephemeral deploys)")

            return True
        except Exception:
            logger.exception("Failed to load model from database")
            return False

    def _ensure_loaded(self) -> dict | None:
        if self._artifact is None:
            loaded = self.load_model()
            if not loaded:
                return None
        return self._artifact

    def _predict(self, X: pd.DataFrame) -> np.ndarray | None:
        """Run ensemble prediction, return probabilities 0-1."""
        artifact = self._ensure_loaded()
        if artifact is None:
            return None
        models = artifact["models"]
        meta = artifact["meta_learner"]
        feature_names = artifact["feature_names"]

        X_aligned = X.reindex(columns=feature_names, fill_value=0.0)
        stack = np.column_stack([
            model.predict_proba(X_aligned)[:, 1]
            for model in models.values()
        ])
        return meta.predict_proba(stack)[:, 1]

    async def score_single(self, symbol: str) -> dict:
        """Compute features for today and score a single stock."""
        # Try DB load if filesystem load failed
        artifact = self._ensure_loaded()
        if artifact is None:
            loaded = await self._try_load_from_db()
            if not loaded:
                return {
                    "symbol": symbol.upper(),
                    "error": "No trained model available. Run training first.",
                    "composite_score": 0,
                    "breakout_probability": 0,
                    "component_scores": {},
                    "top_features": [],
                }
            artifact = self._artifact

        stmt = select(Stock).where(Stock.symbol == symbol.upper())
        result = await self.session.execute(stmt)
        stock = result.scalar_one_or_none()
        if not stock:
            raise ValueError(f"Stock {symbol} not found")

        today = date.today()
        lookback = today - timedelta(days=30)  # need lookback for delta features

        builder = FeatureBuilder(self.session)
        df = await builder.build_feature_matrix([stock.id], lookback, today)
        if df.empty:
            raise ValueError(f"No feature data for {symbol}")

        df = builder.add_lookback_features(df)

        # Use the most recent row
        latest = df[df["date"] == df["date"].max()]
        if latest.empty:
            raise ValueError(f"No recent features for {symbol}")

        probas = self._predict(latest)
        composite_score = float(probas[0]) * 100  # 0-100 scale

        # Component scores from individual models
        models = artifact["models"]
        feature_names = artifact["feature_names"]
        X_aligned = latest.reindex(columns=feature_names, fill_value=0.0)

        component_scores = {}
        for name, model in models.items():
            p = model.predict_proba(X_aligned)[:, 1]
            component_scores[name] = float(p[0]) * 100

        # Feature importance for this prediction
        top_features = self._get_prediction_drivers(X_aligned.iloc[0], artifact)

        return {
            "symbol": symbol.upper(),
            "date": today.isoformat(),
            "composite_score": round(composite_score, 2),
            "breakout_probability": round(float(probas[0]), 4),
            "component_scores": {k: round(v, 2) for k, v in component_scores.items()},
            "top_features": top_features,
        }

    async def score_universe(self, min_score: float = 0.0) -> list[dict]:
        """Score all active stocks, store in signals table, return results."""
        artifact = self._ensure_loaded()
        if artifact is None:
            loaded = await self._try_load_from_db()
            if not loaded:
                logger.warning("No model available for scoring universe")
                return []
            artifact = self._artifact

        stmt = select(Stock).where(Stock.is_active.is_(True))
        result = await self.session.execute(stmt)
        stocks = result.scalars().all()
        stock_ids = [s.id for s in stocks]
        stock_map = {s.id: s.symbol for s in stocks}

        if not stock_ids:
            return []

        today = date.today()
        lookback = today - timedelta(days=30)

        builder = FeatureBuilder(self.session)
        df = await builder.build_feature_matrix(stock_ids, lookback, today)
        if df.empty:
            return []

        df = builder.add_lookback_features(df)

        # Get latest date per stock
        latest_dates = df.groupby("stock_id")["date"].max().reset_index()
        latest_df = df.merge(latest_dates, on=["stock_id", "date"])

        if latest_df.empty:
            return []

        probas = self._predict(latest_df)
        scores = probas * 100

        # Build results and store signals
        results = []
        for i, (_, row) in enumerate(latest_df.iterrows()):
            sid = int(row["stock_id"])
            score = float(scores[i])
            if score < min_score:
                continue

            # Get options data for suggestions
            opts = await self._get_latest_options(sid, today)

            signal = Signal(
                stock_id=sid,
                date=today,
                breakout_probability=Decimal(str(round(float(probas[i]), 4))),
                composite_score=Decimal(str(round(score, 2))),
                model_version=artifact.get("version", "unknown"),
            )

            # Upsert: delete existing signal for same stock+date
            await self.session.execute(
                delete(Signal).where(Signal.stock_id == sid, Signal.date == today)
            )
            self.session.add(signal)

            results.append({
                "symbol": stock_map.get(sid, "???"),
                "stock_id": sid,
                "composite_score": round(score, 2),
                "breakout_probability": round(float(probas[i]), 4),
            })

        await self.session.commit()

        # Sort by score descending
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        logger.info("Scored %d stocks, %d above threshold", len(stock_ids), len(results))
        return results

    async def get_top_signals(self, n: int = 20, min_score: float = 60.0) -> list[dict]:
        """Query signals table for today's best opportunities, enriched with market data.

        Uses the most recent DailyBar/TechnicalSnapshot/OptionsSnapshot for each stock
        (not just exact signal-date matches), so enrichment data shows even when the
        signal date is ahead of the latest available market data.
        """
        today = date.today()

        # Subqueries: get the most recent row for each stock (within 7 days of signal)
        latest_bar = (
            select(DailyBar.stock_id, DailyBar.close)
            .where(DailyBar.stock_id == Signal.stock_id, DailyBar.date <= today)
            .order_by(DailyBar.date.desc())
            .limit(1)
            .correlate(Signal)
            .lateral("latest_bar")
        )

        latest_tech = (
            select(
                TechnicalSnapshot.stock_id,
                TechnicalSnapshot.volume_ratio,
                TechnicalSnapshot.sma_50,
                TechnicalSnapshot.sma_200,
                TechnicalSnapshot.rsi_14,
                TechnicalSnapshot.adx_14,
                TechnicalSnapshot.bb_pctb,
                TechnicalSnapshot.pattern_wedge_falling,
                TechnicalSnapshot.pattern_wedge_rising,
                TechnicalSnapshot.pattern_triangle_ascending,
                TechnicalSnapshot.pattern_triangle_descending,
                TechnicalSnapshot.pattern_triangle_symmetric,
                TechnicalSnapshot.pattern_flag_bull,
                TechnicalSnapshot.pattern_flag_bear,
                TechnicalSnapshot.pattern_pennant,
                TechnicalSnapshot.pattern_cup_handle,
                TechnicalSnapshot.pattern_double_bottom,
                TechnicalSnapshot.pattern_head_shoulders_inv,
                TechnicalSnapshot.pattern_channel_up,
                TechnicalSnapshot.pattern_consolidation_score,
            )
            .where(TechnicalSnapshot.stock_id == Signal.stock_id, TechnicalSnapshot.date <= today)
            .order_by(TechnicalSnapshot.date.desc())
            .limit(1)
            .correlate(Signal)
            .lateral("latest_tech")
        )

        latest_opts = (
            select(OptionsSnapshot.stock_id, OptionsSnapshot.iv_rank)
            .where(OptionsSnapshot.stock_id == Signal.stock_id, OptionsSnapshot.date <= today)
            .order_by(OptionsSnapshot.date.desc())
            .limit(1)
            .correlate(Signal)
            .lateral("latest_opts")
        )

        stmt = (
            select(
                Signal,
                Stock.symbol,
                Stock.name,
                Stock.sector,
                latest_bar.c.close,
                latest_tech.c.volume_ratio,
                latest_tech.c.sma_50,
                latest_tech.c.sma_200,
                latest_tech.c.rsi_14,
                latest_tech.c.adx_14,
                latest_tech.c.bb_pctb,
                latest_tech.c.pattern_cup_handle,
                latest_tech.c.pattern_triangle_ascending,
                latest_tech.c.pattern_flag_bull,
                latest_tech.c.pattern_wedge_falling,
                latest_tech.c.pattern_double_bottom,
                latest_tech.c.pattern_head_shoulders_inv,
                latest_tech.c.pattern_channel_up,
                latest_tech.c.pattern_consolidation_score,
                latest_opts.c.iv_rank,
            )
            .join(Stock, Signal.stock_id == Stock.id)
            .outerjoin(latest_bar, true())
            .outerjoin(latest_tech, true())
            .outerjoin(latest_opts, true())
            .where(Signal.date == today, Signal.composite_score >= Decimal(str(min_score)))
            .order_by(Signal.composite_score.desc())
            .limit(n)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        signals = []
        for row in rows:
            sig = row[0]
            symbol = row[1]
            name = row[2]
            sector = row[3]
            close = row[4]
            vol_ratio = row[5]
            sma_50 = row[6]
            sma_200 = row[7]
            rsi_14 = row[8]
            adx_14 = row[9]
            bb_pctb = row[10]
            # Pattern columns (11-18)
            pattern_scores = {
                "cup & handle": row[11],
                "ascending triangle": row[12],
                "bull flag": row[13],
                "falling wedge": row[14],
                "double bottom": row[15],
                "inv head & shoulders": row[16],
                "channel up": row[17],
                "consolidation": row[18],
            }
            iv_rank = row[19]

            # Determine dominant pattern from TechnicalSnapshot pattern columns
            pattern = self._detect_pattern_from_technicals(pattern_scores)

            # SMA bullish: sma_50 > sma_200
            sma_bullish: bool | None = None
            if sma_50 is not None and sma_200 is not None:
                sma_bullish = float(sma_50) > float(sma_200)

            def _f(v: object) -> float | None:
                """Convert Decimal/numeric to float or None."""
                return float(v) if v is not None else None

            signals.append({
                "symbol": symbol,
                "name": name,
                "composite_score": _f(sig.composite_score) or 0,
                "breakout_probability": _f(sig.breakout_probability) or 0,
                "model_version": sig.model_version,
                "date": sig.date.isoformat(),
                "pattern": pattern,
                "iv_rank": _f(iv_rank),
                "price": _f(close),
                "volume_ratio": _f(vol_ratio),
                "sector": sector,
                "sma_bullish": sma_bullish,
                # Sub-scores from Signal model
                "technical_score": _f(sig.technical_score),
                "momentum_score": _f(sig.momentum_score),
                "volume_score": _f(sig.volume_score),
                "pattern_score": _f(sig.pattern_score),
                "regime_score": _f(sig.regime_score),
                "options_score": _f(sig.options_score),
                # Key technicals
                "rsi_14": _f(rsi_14),
                "adx_14": _f(adx_14),
                "bb_pctb": _f(bb_pctb),
                # Trade suggestion
                "expected_move_pct": _f(sig.expected_move_pct),
                "confidence": _f(sig.confidence),
                "risk_reward_ratio": _f(sig.risk_reward_ratio),
            })
        return signals

    @staticmethod
    def _detect_pattern_from_technicals(pattern_scores: dict[str, object]) -> str | None:
        """Find the dominant chart pattern from TechnicalSnapshot pattern columns.

        Returns the pattern with the highest score above 50, or None.
        """
        best_name: str | None = None
        best_score: float = 50.0  # minimum threshold
        for name, val in pattern_scores.items():
            if val is not None:
                score = float(val)
                if score > best_score:
                    best_score = score
                    best_name = name
        return best_name

    async def _get_latest_options(self, stock_id: int, ref_date: date) -> dict | None:
        """Get latest options snapshot for a stock."""
        stmt = (
            select(OptionsSnapshot)
            .where(
                OptionsSnapshot.stock_id == stock_id,
                OptionsSnapshot.date <= ref_date,
            )
            .order_by(OptionsSnapshot.date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "iv_rank": float(row.iv_rank) if row.iv_rank else None,
            "iv_30d": float(row.iv_30d) if row.iv_30d else None,
            "front_atm_call_bid": float(row.front_atm_call_bid) if row.front_atm_call_bid else None,
            "front_atm_call_ask": float(row.front_atm_call_ask) if row.front_atm_call_ask else None,
        }

    @staticmethod
    def _get_prediction_drivers(
        x_row: pd.Series,
        artifact: dict,
        top_n: int = 10,
    ) -> list[dict]:
        """Get top features driving a single prediction."""
        models = artifact["models"]
        feature_names = artifact["feature_names"]

        all_imp: list[np.ndarray] = []
        for model in models.values():
            if hasattr(model, "feature_importances_"):
                imp = np.array(model.feature_importances_)
                total = imp.sum()
                if total > 0:
                    imp = imp / total
                all_imp.append(imp)

        if not all_imp:
            return []

        avg_imp = np.mean(all_imp, axis=0)
        sorted_idx = np.argsort(avg_imp)[::-1][:top_n]

        return [
            {
                "feature": feature_names[i],
                "importance": round(float(avg_imp[i]), 4),
                "value": round(float(x_row.iloc[i]), 4) if not pd.isna(x_row.iloc[i]) else None,
            }
            for i in sorted_idx
            if i < len(feature_names)
        ]
