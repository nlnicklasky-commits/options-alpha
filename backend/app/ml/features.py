"""Feature engineering for ML pipeline.

Pulls from technical_snapshots, options_snapshots, and market_regimes tables,
joins into a wide DataFrame, adds lookback deltas, and removes redundant features.
"""

from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_regime import MarketRegime
from app.models.options import OptionsSnapshot
from app.models.technicals import TechnicalSnapshot

# 16 key metrics that get 5-day and 10-day rolling deltas
DELTA_FEATURES: list[str] = [
    "rsi_14",
    "bb_width",
    "volume_ratio",
    "price_vs_sma50_pct",
    "macd_histogram",
    "cmf_20",
    "obv_slope_10d",
    "adx_14",
    "stoch_k",
    "mfi_14",
    "atr_pct",
    "close_position",
    "pattern_consolidation_score",
    "rs_rank_percentile",
    "iv_rank",
    "pc_volume_ratio",
]

# Columns to pull from each table (excluding id, stock_id, date, created_at)
TECHNICAL_COLS: list[str] = [
    "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
    "ema_9", "ema_12", "ema_21", "ema_26", "ema_50",
    "price_vs_sma50_pct", "price_vs_sma200_pct", "sma50_vs_sma200_pct",
    "sma20_vs_sma50_pct", "sma50_slope_10d", "sma200_slope_10d",
    "rsi_14", "rsi_9", "stoch_k", "stoch_d", "stoch_rsi",
    "williams_r", "cci_20", "mfi_14",
    "macd_line", "macd_signal", "macd_histogram", "macd_histogram_slope",
    "adx_14", "plus_di", "minus_di",
    "aroon_up", "aroon_down", "aroon_oscillator",
    "atr_14", "atr_pct",
    "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_pctb",
    "keltner_upper", "keltner_lower", "bb_squeeze",
    "historical_vol_20", "historical_vol_60",
    "volume_sma_20", "volume_ratio", "obv", "obv_slope_10d",
    "ad_line", "cmf_20", "vwap_distance_pct",
    "daily_return", "gap_pct", "range_pct", "body_pct",
    "upper_shadow_pct", "lower_shadow_pct", "close_position",
    "higher_highs_5d", "higher_lows_5d",
    "consecutive_up_days", "consecutive_down_days",
    "pattern_wedge_falling", "pattern_wedge_rising",
    "pattern_triangle_ascending", "pattern_triangle_descending",
    "pattern_triangle_symmetric",
    "pattern_flag_bull", "pattern_flag_bear", "pattern_pennant",
    "pattern_cup_handle", "pattern_double_bottom",
    "pattern_head_shoulders_inv", "pattern_channel_up",
    "pattern_consolidation_score",
    "rs_vs_spy_20d", "rs_vs_sector_20d", "rs_rank_percentile",
    "distance_to_resistance_pct", "distance_to_support_pct",
    "near_52w_high_pct", "near_52w_low_pct",
]

OPTIONS_COLS: list[str] = [
    "iv_rank", "iv_percentile", "iv_30d", "iv_60d", "iv_skew",
    "iv_term_structure",
    "put_call_volume_ratio", "put_call_oi_ratio",
    "total_call_volume", "total_put_volume", "total_call_oi", "total_put_oi",
    "iv_vs_hv_ratio", "iv_call_atm", "iv_put_atm",
    "call_oi_change", "put_oi_change", "call_volume_vs_avg",
    "max_single_call_volume",
    "front_atm_call_spread_pct", "front_atm_call_volume", "front_atm_call_oi",
    "atm_delta", "atm_gamma", "atm_theta", "atm_vega",
]

REGIME_COLS: list[str] = [
    "vix_close", "vix_sma_20", "vix_percentile", "vvix",
    "advance_decline_ratio", "pct_above_sma200", "pct_above_sma50",
    "mcclellan_oscillator", "high_low_ratio",
    "spy_daily_return", "qqq_daily_return", "iwm_daily_return",
    "sector_dispersion", "xlk_vs_spy", "xly_vs_xlp",
    "us_10y_yield", "us_2y_yield", "yield_curve_spread",
]


def _decimal_to_float(val: object) -> float | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (int, float, np.integer, np.floating)):
        return float(val)
    if isinstance(val, bool):
        return float(val)
    return None


def _rows_to_df(rows: list[object], cols: list[str]) -> pd.DataFrame:
    """Convert SQLAlchemy rows to a DataFrame with stock_id + date columns."""
    records: list[dict] = []
    for row in rows:
        rec: dict = {"stock_id": row.stock_id, "date": row.date}
        for c in cols:
            val = getattr(row, c, None)
            if isinstance(val, bool):
                rec[c] = float(val)
            else:
                rec[c] = _decimal_to_float(val)
        records.append(rec)
    if not records:
        return pd.DataFrame(columns=["stock_id", "date"] + cols)
    return pd.DataFrame(records)


def _regime_rows_to_df(rows: list[object]) -> pd.DataFrame:
    records: list[dict] = []
    for row in rows:
        rec: dict = {"date": row.date}
        for c in REGIME_COLS:
            rec[c] = _decimal_to_float(getattr(row, c, None))
        rec["regime_label"] = row.regime_label
        records.append(rec)
    if not records:
        return pd.DataFrame(columns=["date"] + REGIME_COLS + ["regime_label"])
    return pd.DataFrame(records)


class FeatureBuilder:
    """Builds feature matrices from DB tables for ML training."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._feature_names: list[str] = []

    async def build_feature_matrix(
        self,
        stock_ids: list[int],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Pull technical, options, and regime data and join into one wide DataFrame."""
        tech_df, opts_df, regime_df = await self._fetch_all(stock_ids, start_date, end_date)

        # Merge technical + options on (stock_id, date)
        if opts_df.empty:
            df = tech_df.copy()
        else:
            # Rename put_call_volume_ratio -> pc_volume_ratio for delta features
            if "put_call_volume_ratio" in opts_df.columns:
                opts_df = opts_df.rename(columns={"put_call_volume_ratio": "pc_volume_ratio"})
            df = tech_df.merge(opts_df, on=["stock_id", "date"], how="left")

        # Merge regime data on date (broadcast to all stocks)
        if not regime_df.empty:
            df = df.merge(regime_df, on="date", how="left")
        else:
            for c in REGIME_COLS + ["regime_label"]:
                if c not in df.columns:
                    df[c] = np.nan

        # Ensure pc_volume_ratio alias exists
        if "pc_volume_ratio" not in df.columns and "put_call_volume_ratio" in df.columns:
            df["pc_volume_ratio"] = df["put_call_volume_ratio"]
        elif "pc_volume_ratio" not in df.columns:
            df["pc_volume_ratio"] = np.nan

        df = df.sort_values(["stock_id", "date"]).reset_index(drop=True)
        return df

    def add_lookback_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add 5-day and 10-day rolling deltas for 16 key metrics."""
        df = df.sort_values(["stock_id", "date"]).copy()

        for feat in DELTA_FEATURES:
            if feat not in df.columns:
                continue
            grouped = df.groupby("stock_id")[feat]
            df[f"{feat}_delta_5d"] = grouped.diff(5)
            df[f"{feat}_delta_10d"] = grouped.diff(10)

        return df

    def remove_redundant(self, df: pd.DataFrame, threshold: float = 0.95) -> pd.DataFrame:
        """Drop features with >threshold correlation, keeping the one with higher variance."""
        meta_cols = {"stock_id", "date", "regime_label"}
        feature_cols = [c for c in df.columns if c not in meta_cols]
        numeric_df = df[feature_cols].select_dtypes(include=[np.number])
        if numeric_df.shape[1] < 2:
            self._feature_names = list(numeric_df.columns)
            return df

        corr = numeric_df.corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))

        to_drop: set[str] = set()
        for col in upper.columns:
            correlated = upper.index[upper[col] > threshold].tolist()
            for corr_col in correlated:
                if corr_col in to_drop:
                    continue
                # Keep the one with higher variance
                if numeric_df[col].var() >= numeric_df[corr_col].var():
                    to_drop.add(corr_col)
                else:
                    to_drop.add(col)

        df = df.drop(columns=list(to_drop))
        self._feature_names = [
            c for c in df.columns
            if c not in meta_cols and c in df.select_dtypes(include=[np.number]).columns
        ]
        return df

    def get_feature_names(self) -> list[str]:
        """Return final feature column names after pruning."""
        return list(self._feature_names)

    async def _fetch_all(
        self,
        stock_ids: list[int],
        start_date: date,
        end_date: date,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Fetch all three data sources."""
        # Technical snapshots
        tech_stmt = (
            select(TechnicalSnapshot)
            .where(
                TechnicalSnapshot.stock_id.in_(stock_ids),
                TechnicalSnapshot.date >= start_date,
                TechnicalSnapshot.date <= end_date,
            )
            .order_by(TechnicalSnapshot.stock_id, TechnicalSnapshot.date)
        )
        tech_result = await self.session.execute(tech_stmt)
        tech_rows = tech_result.scalars().all()
        tech_df = _rows_to_df(tech_rows, TECHNICAL_COLS)

        # Options snapshots
        opts_stmt = (
            select(OptionsSnapshot)
            .where(
                OptionsSnapshot.stock_id.in_(stock_ids),
                OptionsSnapshot.date >= start_date,
                OptionsSnapshot.date <= end_date,
            )
            .order_by(OptionsSnapshot.stock_id, OptionsSnapshot.date)
        )
        opts_result = await self.session.execute(opts_stmt)
        opts_rows = opts_result.scalars().all()
        opts_df = _rows_to_df(opts_rows, OPTIONS_COLS)

        # Market regimes (not per-stock)
        regime_stmt = (
            select(MarketRegime)
            .where(
                MarketRegime.date >= start_date,
                MarketRegime.date <= end_date,
            )
            .order_by(MarketRegime.date)
        )
        regime_result = await self.session.execute(regime_stmt)
        regime_rows = regime_result.scalars().all()
        regime_df = _regime_rows_to_df(regime_rows)

        return tech_df, opts_df, regime_df
