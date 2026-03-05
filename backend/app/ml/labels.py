"""Label generation for ML pipeline.

Generates various training labels from daily bars and options data:
- Binary breakout (did stock gain X% within N days?)
- Max gain (continuous)
- Risk/reward ratio
- Simulated call option P/L using Black-Scholes
"""

import math
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_bars import DailyBar


def _to_float_series(series: pd.Series) -> pd.Series:
    """Convert a series that may contain Decimals to float."""
    return series.apply(lambda x: float(x) if isinstance(x, Decimal) else x).astype(float)


class LabelGenerator:
    """Generates training labels from price and options data."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def fetch_bars(self, stock_ids: list[int]) -> pd.DataFrame:
        """Fetch daily bars for given stocks, return as DataFrame."""
        if self.session is None:
            raise RuntimeError("Session required for fetch_bars")
        stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id.in_(stock_ids))
            .order_by(DailyBar.stock_id, DailyBar.date)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        records = []
        for r in rows:
            records.append({
                "stock_id": r.stock_id,
                "date": r.date,
                "open": float(r.open) if r.open is not None else None,
                "high": float(r.high) if r.high is not None else None,
                "low": float(r.low) if r.low is not None else None,
                "close": float(r.close) if r.close is not None else None,
                "volume": r.volume,
            })
        return pd.DataFrame(records) if records else pd.DataFrame(
            columns=["stock_id", "date", "open", "high", "low", "close", "volume"]
        )

    def label_breakout(
        self,
        bars_df: pd.DataFrame,
        threshold_pct: float = 0.10,
        horizon_days: int = 20,
    ) -> pd.Series:
        """Binary: did stock gain threshold_pct within horizon_days? Returns 0/1 Series."""
        close = _to_float_series(bars_df["close"])
        labels = pd.Series(np.nan, index=bars_df.index, dtype=float)

        for stock_id, group in bars_df.groupby("stock_id"):
            idx = group.index
            closes = close.loc[idx].values

            for i in range(len(closes)):
                if i + horizon_days >= len(closes):
                    # Not enough future data
                    continue
                future_closes = closes[i + 1 : i + 1 + horizon_days]
                max_future = np.nanmax(future_closes)
                gain = (max_future - closes[i]) / closes[i] if closes[i] > 0 else 0.0
                labels.iloc[idx[i]] = 1.0 if gain >= threshold_pct else 0.0

        return labels

    def label_max_gain(
        self,
        bars_df: pd.DataFrame,
        horizon_days: int = 20,
    ) -> pd.Series:
        """Continuous: max gain % within horizon. Returns Series of floats."""
        close = _to_float_series(bars_df["close"])
        labels = pd.Series(np.nan, index=bars_df.index, dtype=float)

        for stock_id, group in bars_df.groupby("stock_id"):
            idx = group.index
            closes = close.loc[idx].values

            for i in range(len(closes)):
                if i + horizon_days >= len(closes):
                    continue
                future_closes = closes[i + 1 : i + 1 + horizon_days]
                max_future = np.nanmax(future_closes)
                gain = (max_future - closes[i]) / closes[i] if closes[i] > 0 else 0.0
                labels.iloc[idx[i]] = gain

        return labels

    def label_risk_reward(
        self,
        bars_df: pd.DataFrame,
        horizon_days: int = 20,
    ) -> pd.Series:
        """Max gain / max drawdown within horizon. Returns Series."""
        close = _to_float_series(bars_df["close"])
        labels = pd.Series(np.nan, index=bars_df.index, dtype=float)

        for stock_id, group in bars_df.groupby("stock_id"):
            idx = group.index
            closes = close.loc[idx].values

            for i in range(len(closes)):
                if i + horizon_days >= len(closes):
                    continue
                future_closes = closes[i + 1 : i + 1 + horizon_days]
                entry = closes[i]
                if entry <= 0:
                    continue
                max_gain = (np.nanmax(future_closes) - entry) / entry
                max_dd = (entry - np.nanmin(future_closes)) / entry
                labels.iloc[idx[i]] = max_gain / max_dd if max_dd > 0.001 else max_gain / 0.001

        return labels

    def label_call_pnl(
        self,
        bars_df: pd.DataFrame,
        options_df: pd.DataFrame | None = None,
        dte: int = 30,
        strike: str = "ATM",
        horizon_days: int = 20,
    ) -> pd.Series:
        """Simulated call option P/L using Black-Scholes with actual IV data.

        Accounts for theta decay and IV change. If options_df is None or missing IV,
        uses a default IV of 30%.
        """
        close = _to_float_series(bars_df["close"])
        labels = pd.Series(np.nan, index=bars_df.index, dtype=float)

        # Build IV lookup: (stock_id, date) -> iv
        iv_lookup: dict[tuple[int, object], float] = {}
        if options_df is not None and "iv_30d" in options_df.columns:
            for _, row in options_df.iterrows():
                iv_val = row.get("iv_30d")
                if iv_val is not None and not (isinstance(iv_val, float) and math.isnan(iv_val)):
                    iv_lookup[(row["stock_id"], row["date"])] = float(iv_val)

        risk_free_rate = 0.05  # approximate

        for stock_id, group in bars_df.groupby("stock_id"):
            idx = group.index
            closes = close.loc[idx].values
            dates = bars_df.loc[idx, "date"].values

            for i in range(len(closes)):
                if i + horizon_days >= len(closes):
                    continue

                entry_price = closes[i]
                if entry_price <= 0:
                    continue

                # Get IV at entry
                iv_entry = iv_lookup.get((stock_id, dates[i]), 0.30)

                # Strike price
                if strike == "ATM":
                    strike_price = entry_price
                else:
                    strike_price = entry_price

                # Price call at entry using Black-Scholes
                t_entry = dte / 365.0
                call_entry = _bs_call(entry_price, strike_price, t_entry, risk_free_rate, iv_entry)

                if call_entry <= 0.01:
                    continue

                # Price call at exit (horizon_days later)
                exit_price = closes[i + horizon_days]
                days_elapsed = horizon_days
                t_exit = max((dte - days_elapsed) / 365.0, 1 / 365.0)

                # IV at exit: use lookup or assume same as entry
                iv_exit = iv_lookup.get((stock_id, dates[i + horizon_days]), iv_entry)
                call_exit = _bs_call(exit_price, strike_price, t_exit, risk_free_rate, iv_exit)

                pnl_pct = (call_exit - call_entry) / call_entry
                labels.iloc[idx[i]] = pnl_pct

        return labels


def _bs_call(s: float, k: float, t: float, r: float, sigma: float) -> float:
    """Black-Scholes call option price."""
    if t <= 0 or sigma <= 0 or s <= 0:
        return max(s - k, 0.0)

    d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return s * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
