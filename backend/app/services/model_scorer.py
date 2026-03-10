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
from sqlalchemy import delete, select
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

        Uses simple separate queries to fetch the most recent DailyBar/TechnicalSnapshot
        for each stock, ensuring data is fetched reliably.
        """
        today = date.today()

        # Get top signals for today
        stmt = (
            select(Signal, Stock)
            .join(Stock, Signal.stock_id == Stock.id)
            .where(Signal.date == today, Signal.composite_score >= Decimal(str(min_score)))
            .order_by(Signal.composite_score.desc())
            .limit(n)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        signals = []
        for sig, stock in rows:
            # Get most recent DailyBar
            bar_stmt = (
                select(DailyBar)
                .where(DailyBar.stock_id == stock.id, DailyBar.date <= today)
                .order_by(DailyBar.date.desc())
                .limit(1)
            )
            bar_result = await self.session.execute(bar_stmt)
            bar = bar_result.scalar_one_or_none()

            # Get most recent TechnicalSnapshot
            tech_stmt = (
                select(TechnicalSnapshot)
                .where(TechnicalSnapshot.stock_id == stock.id, TechnicalSnapshot.date <= today)
                .order_by(TechnicalSnapshot.date.desc())
                .limit(1)
            )
            tech_result = await self.session.execute(tech_stmt)
            tech = tech_result.scalar_one_or_none()

            # Get most recent OptionsSnapshot
            opts_stmt = (
                select(OptionsSnapshot)
                .where(OptionsSnapshot.stock_id == stock.id, OptionsSnapshot.date <= today)
                .order_by(OptionsSnapshot.date.desc())
                .limit(1)
            )
            opts_result = await self.session.execute(opts_stmt)
            opts = opts_result.scalar_one_or_none()

            # Helper to convert Decimal/numeric to float
            def _f(v: object) -> float | None:
                return float(v) if v is not None else None

            # Extract technical data
            close = _f(bar.close) if bar else None
            vol_ratio = _f(tech.volume_ratio) if tech else None
            sma_50 = _f(tech.sma_50) if tech else None
            sma_200 = _f(tech.sma_200) if tech else None
            rsi_14 = _f(tech.rsi_14) if tech else None
            adx_14 = _f(tech.adx_14) if tech else None
            bb_pctb = _f(tech.bb_pctb) if tech else None

            # Determine dominant pattern from TechnicalSnapshot pattern columns
            pattern_scores = {}
            if tech:
                pattern_scores = {
                    "cup & handle": tech.pattern_cup_handle,
                    "ascending triangle": tech.pattern_triangle_ascending,
                    "bull flag": tech.pattern_flag_bull,
                    "falling wedge": tech.pattern_wedge_falling,
                    "double bottom": tech.pattern_double_bottom,
                    "inv head & shoulders": tech.pattern_head_shoulders_inv,
                    "channel up": tech.pattern_channel_up,
                    "consolidation": tech.pattern_consolidation_score,
                }
            pattern = self._detect_pattern_from_technicals(pattern_scores)

            # SMA bullish: sma_50 > sma_200
            sma_bullish: bool | None = None
            if sma_50 is not None and sma_200 is not None:
                sma_bullish = sma_50 > sma_200

            # Generate drivers based on technical indicators
            drivers = self._generate_drivers(
                rsi_14=rsi_14,
                adx_14=adx_14,
                bb_pctb=bb_pctb,
                vol_ratio=vol_ratio,
                sma_bullish=sma_bullish,
                pattern=pattern,
                composite_score=_f(sig.composite_score),
                breakout_probability=_f(sig.breakout_probability),
            )

            signals.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "composite_score": _f(sig.composite_score) or 0,
                "breakout_probability": _f(sig.breakout_probability) or 0,
                "date": sig.date.isoformat(),
                "price": close,
                "volume_ratio": vol_ratio,
                "sma_bullish": sma_bullish,
                "rsi_14": rsi_14,
                "pattern": pattern,
                "sector": stock.sector,
                "drivers": drivers,
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

    @staticmethod
    def _generate_drivers(
        rsi_14: float | None = None,
        adx_14: float | None = None,
        bb_pctb: float | None = None,
        vol_ratio: float | None = None,
        sma_bullish: bool | None = None,
        pattern: str | None = None,
        composite_score: float | None = None,
        breakout_probability: float | None = None,
    ) -> list[str]:
        """Generate human-readable driver strings explaining why this stock scored high."""
        drivers: list[str] = []

        # Momentum indicators
        if rsi_14 is not None:
            if rsi_14 > 70:
                drivers.append(f"Overbought momentum — watch for pullback")
            elif rsi_14 > 60:
                drivers.append(f"Strong momentum (RSI {rsi_14:.0f})")

        # Trend strength
        if adx_14 is not None and adx_14 > 25:
            drivers.append(f"Strong trend strength (ADX {adx_14:.0f})")

        # Volume
        if vol_ratio is not None and vol_ratio > 1.5:
            drivers.append(f"Unusual volume ({vol_ratio:.1f}x average)")

        # SMA trend
        if sma_bullish is not None:
            if sma_bullish:
                drivers.append("Bullish trend (above 200-day MA)")
            else:
                drivers.append("Below long-term trend")

        # Bollinger Bands
        if bb_pctb is not None:
            if bb_pctb > 0.8:
                drivers.append("Near upper Bollinger Band")
            elif bb_pctb < 0.2:
                drivers.append("Near lower Bollinger Band — potential bounce")

        # Chart pattern
        if pattern is not None:
            drivers.append(f"Chart pattern: {pattern}")

        # Overall conviction
        if composite_score is not None and composite_score > 80:
            drivers.append("High conviction signal")

        # Breakout probability
        if breakout_probability is not None and breakout_probability > 0.75:
            drivers.append(f"Strong breakout probability ({breakout_probability:.0%})")

        return drivers

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
