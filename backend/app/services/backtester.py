"""Backtesting engine for breakout trading signals.

Loads a trained model, scores every stock on every day, simulates
ATM call option trades, and computes performance statistics.
"""

import json
import logging
import math
from datetime import date
from decimal import Decimal
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.features import FeatureBuilder
from app.ml.labels import _bs_call
from app.models.daily_bars import DailyBar
from app.models.options import OptionsSnapshot
from app.models.signals import BacktestRun, BacktestTrade
from app.models.stocks import Stock

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "ml" / "models"


def _load_model(model_path: str | None = None) -> dict:
    """Load model artifact from disk."""
    if model_path is None:
        latest_file = MODELS_DIR / "latest.txt"
        if not latest_file.exists():
            raise FileNotFoundError("No trained model found. Run training first.")
        model_name = latest_file.read_text().strip()
        model_path = str(MODELS_DIR / model_name)
    return joblib.load(model_path)


def _ensemble_predict(artifact: dict, X: pd.DataFrame) -> np.ndarray:
    """Get ensemble probabilities using meta-learner."""
    models = artifact["models"]
    meta = artifact["meta_learner"]
    feature_names = artifact["feature_names"]

    # Ensure correct feature order
    available = [f for f in feature_names if f in X.columns]
    missing = [f for f in feature_names if f not in X.columns]
    X_aligned = X.reindex(columns=feature_names, fill_value=0.0)

    stack = np.column_stack([
        model.predict_proba(X_aligned)[:, 1]
        for model in models.values()
    ])
    return meta.predict_proba(stack)[:, 1]


class Backtester:
    """Simulates trading on historical data using model predictions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_backtest(
        self,
        model_path: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        entry_threshold: float = 0.65,
        target_pct: float = 1.0,
        stop_pct: float = -0.5,
        max_days: int = 20,
        name: str = "backtest",
    ) -> int:
        """Run a full backtest. Returns backtest_run ID."""
        artifact = _load_model(model_path)
        feature_names = artifact["feature_names"]

        # Get all active stocks
        stmt = select(Stock).where(Stock.is_active.is_(True))
        result = await self.session.execute(stmt)
        stocks = result.scalars().all()
        stock_ids = [s.id for s in stocks]
        stock_map = {s.id: s.symbol for s in stocks}

        if not stock_ids:
            raise ValueError("No active stocks")

        CHUNK_SIZE = 200
        trades: list[dict] = []

        for chunk_start in range(0, len(stock_ids), CHUNK_SIZE):
            chunk_ids = stock_ids[chunk_start : chunk_start + CHUNK_SIZE]
            logger.info(
                "Processing chunk %d-%d of %d stocks",
                chunk_start, chunk_start + len(chunk_ids), len(stock_ids),
            )

            chunk_trades = await self._process_chunk(
                chunk_ids, start_date, end_date, artifact, feature_names,
                entry_threshold, target_pct, stop_pct, max_days,
            )
            trades.extend(chunk_trades)

        # Create backtest run record
        run = BacktestRun(
            name=name,
            start_date=start_date,
            end_date=end_date,
            model_version=artifact.get("version", "unknown"),
            total_trades=len(trades),
            parameters=json.dumps({
                "entry_threshold": entry_threshold,
                "target_pct": target_pct,
                "stop_pct": stop_pct,
                "max_days": max_days,
            }),
        )
        self.session.add(run)
        await self.session.flush()

        # Insert trades
        for t in trades:
            trade = BacktestTrade(run_id=run.id, **t)
            self.session.add(trade)

        await self.session.flush()

        # Compute and store stats
        stats = self._compute_stats_from_trades(trades)
        run.win_rate = Decimal(str(round(stats["win_rate"], 4)))
        run.avg_return = Decimal(str(round(stats["avg_return"], 4)))
        run.max_drawdown = Decimal(str(round(stats["max_drawdown"], 4)))
        run.sharpe_ratio = Decimal(str(round(stats["sharpe_ratio"], 4)))
        run.profit_factor = Decimal(str(round(stats["profit_factor"], 4)))
        run.sortino_ratio = Decimal(str(round(stats["sortino_ratio"], 4)))
        run.expectancy = Decimal(str(round(stats["expectancy"], 4)))
        if trades:
            avg_days = np.mean([
                (t["exit_date"] - t["entry_date"]).days
                for t in trades if t["exit_date"] is not None
            ]) if any(t["exit_date"] for t in trades) else 0
            run.avg_days_held = Decimal(str(round(avg_days, 2)))

        # Regime breakdown
        run.results_by_regime = self._breakdown_by_field(trades, "regime")
        run.results_by_score_bucket = self._breakdown_by_score(trades)
        run.results_by_pattern = self._breakdown_by_field(trades, "pattern_type")

        await self.session.commit()

        logger.info(
            "Backtest %d complete: %d trades, %.1f%% win rate, %.2f profit factor",
            run.id, len(trades), stats["win_rate"] * 100, stats["profit_factor"],
        )
        return run.id

    async def _process_chunk(
        self,
        chunk_ids: list[int],
        start_date: date,
        end_date: date,
        artifact: dict,
        feature_names: list[str],
        entry_threshold: float,
        target_pct: float,
        stop_pct: float,
        max_days: int,
    ) -> list[dict]:
        """Load data, score, and simulate trades for a chunk of stock IDs."""
        builder = FeatureBuilder(self.session)
        df = await builder.build_feature_matrix(chunk_ids, start_date, end_date)
        if df.empty:
            return []

        df = builder.add_lookback_features(df)

        # Fetch daily bars for this chunk
        bars_stmt = (
            select(DailyBar)
            .where(
                DailyBar.stock_id.in_(chunk_ids),
                DailyBar.date >= start_date,
                DailyBar.date <= end_date,
            )
            .order_by(DailyBar.stock_id, DailyBar.date)
        )
        bars_result = await self.session.execute(bars_stmt)
        bars_rows = bars_result.scalars().all()
        bars_data: dict[int, list[dict]] = {}
        for b in bars_rows:
            bars_data.setdefault(b.stock_id, []).append({
                "date": b.date,
                "close": float(b.close) if b.close is not None else 0.0,
                "high": float(b.high) if b.high is not None else 0.0,
                "low": float(b.low) if b.low is not None else 0.0,
            })

        # Fetch options snapshots for IV data for this chunk
        opts_stmt = (
            select(OptionsSnapshot)
            .where(
                OptionsSnapshot.stock_id.in_(chunk_ids),
                OptionsSnapshot.date >= start_date,
                OptionsSnapshot.date <= end_date,
            )
        )
        opts_result = await self.session.execute(opts_stmt)
        opts_rows = opts_result.scalars().all()
        iv_lookup: dict[tuple[int, date], float] = {}
        for o in opts_rows:
            if o.iv_30d is not None:
                iv_lookup[(o.stock_id, o.date)] = float(o.iv_30d)

        # Score each day and simulate trades
        unique_dates = sorted(df["date"].unique())
        trades: list[dict] = []

        for score_date in unique_dates:
            day_df = df[df["date"] == score_date].copy()
            if day_df.empty:
                continue

            X_day = day_df.reindex(columns=feature_names, fill_value=0.0)
            scores = _ensemble_predict(artifact, X_day)

            for i, (_, row) in enumerate(day_df.iterrows()):
                if scores[i] < entry_threshold:
                    continue

                sid = int(row["stock_id"])
                bars = bars_data.get(sid, [])
                if not bars:
                    continue

                bar_dates = [b["date"] for b in bars]
                try:
                    entry_idx = bar_dates.index(score_date)
                except ValueError:
                    continue

                entry_close = bars[entry_idx]["close"]
                if entry_close <= 0:
                    continue

                iv = iv_lookup.get((sid, score_date), 0.30)
                dte = 30
                strike = entry_close  # ATM
                r = 0.05

                call_entry = _bs_call(entry_close, strike, dte / 365.0, r, iv)
                if call_entry < 0.01:
                    continue

                exit_date_val = None
                exit_price_val = None
                return_pct = None

                for d in range(1, min(max_days + 1, len(bars) - entry_idx)):
                    future_bar = bars[entry_idx + d]
                    days_elapsed = d
                    t_remaining = max((dte - days_elapsed) / 365.0, 1 / 365.0)
                    iv_now = iv_lookup.get((sid, future_bar["date"]), iv)

                    call_now = _bs_call(future_bar["close"], strike, t_remaining, r, iv_now)
                    pnl_pct = (call_now - call_entry) / call_entry

                    if pnl_pct >= target_pct:
                        exit_date_val = future_bar["date"]
                        exit_price_val = future_bar["close"]
                        return_pct = pnl_pct
                        break
                    elif pnl_pct <= stop_pct:
                        exit_date_val = future_bar["date"]
                        exit_price_val = future_bar["close"]
                        return_pct = pnl_pct
                        break

                if exit_date_val is None and entry_idx + max_days < len(bars):
                    future_bar = bars[entry_idx + max_days]
                    t_remaining = max((dte - max_days) / 365.0, 1 / 365.0)
                    iv_now = iv_lookup.get((sid, future_bar["date"]), iv)
                    call_now = _bs_call(future_bar["close"], strike, t_remaining, r, iv_now)
                    exit_date_val = future_bar["date"]
                    exit_price_val = future_bar["close"]
                    return_pct = (call_now - call_entry) / call_entry

                if return_pct is None:
                    continue

                regime_label = row.get("regime_label", None)

                pattern_cols = [c for c in row.index if c.startswith("pattern_") and c != "pattern_consolidation_score"]
                dominant_pattern = None
                if pattern_cols:
                    pattern_vals = {c: float(row[c]) if pd.notna(row[c]) else 0.0 for c in pattern_cols}
                    if pattern_vals:
                        best_pattern = max(pattern_vals, key=pattern_vals.get)
                        if pattern_vals[best_pattern] > 30:
                            dominant_pattern = best_pattern.replace("pattern_", "")

                trades.append({
                    "stock_id": sid,
                    "entry_date": score_date,
                    "exit_date": exit_date_val,
                    "entry_price": Decimal(str(round(entry_close, 4))),
                    "exit_price": Decimal(str(round(exit_price_val, 4))) if exit_price_val else None,
                    "return_pct": Decimal(str(round(return_pct, 4))),
                    "signal_score": Decimal(str(round(float(scores[i]) * 100, 2))),
                    "pattern_type": dominant_pattern,
                    "regime": str(regime_label) if regime_label else None,
                })

        return trades

    async def compute_stats(self, backtest_id: int) -> dict:
        """Compute statistics for a completed backtest."""
        stmt = select(BacktestRun).where(BacktestRun.id == backtest_id)
        result = await self.session.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Backtest {backtest_id} not found")

        return {
            "win_rate": float(run.win_rate) if run.win_rate else 0.0,
            "avg_return": float(run.avg_return) if run.avg_return else 0.0,
            "max_drawdown": float(run.max_drawdown) if run.max_drawdown else 0.0,
            "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else 0.0,
            "profit_factor": float(run.profit_factor) if run.profit_factor else 0.0,
            "sortino_ratio": float(run.sortino_ratio) if run.sortino_ratio else 0.0,
            "expectancy": float(run.expectancy) if run.expectancy else 0.0,
            "avg_days_held": float(run.avg_days_held) if run.avg_days_held else 0.0,
            "total_trades": run.total_trades or 0,
        }

    async def results_by_regime(self, backtest_id: int) -> dict:
        """Break down results by market regime."""
        stmt = select(BacktestRun).where(BacktestRun.id == backtest_id)
        result = await self.session.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Backtest {backtest_id} not found")
        return run.results_by_regime or {}

    async def results_by_score(self, backtest_id: int) -> dict:
        """Break down results by score bucket."""
        stmt = select(BacktestRun).where(BacktestRun.id == backtest_id)
        result = await self.session.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Backtest {backtest_id} not found")
        return run.results_by_score_bucket or {}

    async def results_by_pattern(self, backtest_id: int) -> dict:
        """Break down results by dominant pattern type."""
        stmt = select(BacktestRun).where(BacktestRun.id == backtest_id)
        result = await self.session.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Backtest {backtest_id} not found")
        return run.results_by_pattern or {}

    async def equity_curve(self, backtest_id: int) -> list[dict]:
        """Cumulative P/L over time."""
        stmt = (
            select(BacktestTrade)
            .where(BacktestTrade.run_id == backtest_id)
            .order_by(BacktestTrade.exit_date)
        )
        result = await self.session.execute(stmt)
        trades = result.scalars().all()

        cumulative = Decimal("0")
        curve = []
        for t in trades:
            if t.return_pct is not None and t.exit_date is not None:
                cumulative += t.return_pct
                curve.append({
                    "date": t.exit_date.isoformat(),
                    "cumulative_pnl": float(cumulative),
                })
        return curve

    @staticmethod
    def _compute_stats_from_trades(trades: list[dict]) -> dict:
        """Compute summary statistics from trade list."""
        if not trades:
            return {
                "win_rate": 0.0, "avg_return": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "max_drawdown": 0.0, "sharpe_ratio": 0.0, "profit_factor": 0.0,
                "sortino_ratio": 0.0, "expectancy": 0.0,
            }

        returns = [float(t["return_pct"]) for t in trades if t["return_pct"] is not None]
        if not returns:
            return {
                "win_rate": 0.0, "avg_return": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "max_drawdown": 0.0, "sharpe_ratio": 0.0, "profit_factor": 0.0,
                "sortino_ratio": 0.0, "expectancy": 0.0,
            }

        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]

        win_rate = len(wins) / len(returns) if returns else 0
        avg_return = np.mean(returns)
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        # Profit factor
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit if gross_profit > 0 else 0.0

        # Max drawdown on cumulative equity
        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative
        max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Sharpe (annualized, ~252 trading days)
        std = np.std(returns)
        sharpe = (avg_return / std * math.sqrt(252)) if std > 0 else 0.0

        # Sortino (downside deviation)
        downside = [r for r in returns if r < 0]
        downside_std = np.std(downside) if downside else 0.0
        sortino = (avg_return / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

        # Expectancy = avg_win * win_rate + avg_loss * (1 - win_rate)
        expectancy = avg_win * win_rate + avg_loss * (1 - win_rate)

        return {
            "win_rate": win_rate,
            "avg_return": float(avg_return),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": float(sharpe),
            "profit_factor": float(profit_factor),
            "sortino_ratio": float(sortino),
            "expectancy": float(expectancy),
        }

    @staticmethod
    def _breakdown_by_field(trades: list[dict], field: str) -> dict:
        """Group trades by a field and compute stats per group."""
        groups: dict[str, list[float]] = {}
        for t in trades:
            key = t.get(field) or "unknown"
            ret = float(t["return_pct"]) if t["return_pct"] is not None else None
            if ret is not None:
                groups.setdefault(str(key), []).append(ret)

        result = {}
        for key, returns in groups.items():
            wins = [r for r in returns if r > 0]
            result[key] = {
                "count": len(returns),
                "win_rate": len(wins) / len(returns) if returns else 0,
                "avg_return": float(np.mean(returns)),
            }
        return result

    @staticmethod
    def _breakdown_by_score(trades: list[dict]) -> dict:
        """Group trades by score bucket (60-70, 70-80, 80-90, 90-100)."""
        buckets = {"60-70": [], "70-80": [], "80-90": [], "90-100": []}
        for t in trades:
            score = float(t.get("signal_score", 0))
            ret = float(t["return_pct"]) if t["return_pct"] is not None else None
            if ret is None:
                continue
            if score >= 90:
                buckets["90-100"].append(ret)
            elif score >= 80:
                buckets["80-90"].append(ret)
            elif score >= 70:
                buckets["70-80"].append(ret)
            elif score >= 60:
                buckets["60-70"].append(ret)

        result = {}
        for key, returns in buckets.items():
            if not returns:
                continue
            wins = [r for r in returns if r > 0]
            result[key] = {
                "count": len(returns),
                "win_rate": len(wins) / len(returns),
                "avg_return": float(np.mean(returns)),
            }
        return result
