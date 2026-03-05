import logging
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import ta

logger = logging.getLogger(__name__)


def _to_decimal(val: Any) -> Decimal | None:
    """Safely convert a numeric value to Decimal."""
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return None
    return Decimal(str(round(float(val), 4)))


def _linear_slope(series: pd.Series, window: int) -> pd.Series:
    """Rolling linear regression slope over `window` bars."""
    def _slope(arr: np.ndarray) -> float:
        if len(arr) < 2 or np.isnan(arr).any():
            return np.nan
        x = np.arange(len(arr), dtype=float)
        coeffs = np.polyfit(x, arr, 1)
        return float(coeffs[0])
    return series.rolling(window, min_periods=window).apply(_slope, raw=True)


class TechnicalCalculator:
    """Compute all 82 technical indicators from OHLCV data.

    Uses the `ta` library for standard indicators and custom implementations
    for derived features.
    """

    def compute_all(self, bars_df: pd.DataFrame, spy_df: pd.DataFrame | None = None) -> dict[str, Any]:
        """Compute all features for the latest bar.

        Args:
            bars_df: DataFrame with columns [date, open, high, low, close, volume].
                     Must have enough history (at least 200 bars).
            spy_df: Optional SPY bars for relative strength computation.

        Returns:
            Dict of {feature_name: Decimal | int | bool | None} for the latest date.
        """
        full = self.compute_historical(bars_df, spy_df)
        if full.empty:
            return {}
        latest = full.iloc[-1]
        result: dict[str, Any] = {}
        for col in full.columns:
            val = latest[col]
            if col in ("date",):
                continue
            if isinstance(val, (bool, np.bool_)):
                result[col] = bool(val)
            elif col in (
                "higher_highs_5d", "higher_lows_5d",
                "consecutive_up_days", "consecutive_down_days",
                "volume_sma_20", "obv",
            ):
                result[col] = int(val) if pd.notna(val) else None
            else:
                result[col] = _to_decimal(val)
        return result

    def compute_historical(
        self, bars_df: pd.DataFrame, spy_df: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """Compute all features for every bar in the DataFrame.

        Returns a DataFrame indexed by date with all 82+ feature columns.
        """
        df = bars_df.copy()
        if df.empty:
            return pd.DataFrame()
        df = df.sort_values("date").reset_index(drop=True)

        o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

        # ====== Moving Averages (10 cols) ======
        df["sma_10"] = c.rolling(10).mean()
        df["sma_20"] = c.rolling(20).mean()
        df["sma_50"] = c.rolling(50).mean()
        df["sma_100"] = c.rolling(100).mean()
        df["sma_200"] = c.rolling(200).mean()
        df["ema_9"] = c.ewm(span=9, adjust=False).mean()
        df["ema_12"] = c.ewm(span=12, adjust=False).mean()
        df["ema_21"] = c.ewm(span=21, adjust=False).mean()
        df["ema_26"] = c.ewm(span=26, adjust=False).mean()
        df["ema_50"] = c.ewm(span=50, adjust=False).mean()

        # ====== MA Derived (6 cols) ======
        df["price_vs_sma50_pct"] = ((c - df["sma_50"]) / df["sma_50"]) * 100
        df["price_vs_sma200_pct"] = ((c - df["sma_200"]) / df["sma_200"]) * 100
        df["sma50_vs_sma200_pct"] = ((df["sma_50"] - df["sma_200"]) / df["sma_200"]) * 100
        df["sma20_vs_sma50_pct"] = ((df["sma_20"] - df["sma_50"]) / df["sma_50"]) * 100
        df["sma50_slope_10d"] = _linear_slope(df["sma_50"], 10)
        df["sma200_slope_10d"] = _linear_slope(df["sma_200"], 10)

        # ====== Momentum (8 cols) ======
        df["rsi_14"] = ta.momentum.rsi(c, window=14)
        df["rsi_9"] = ta.momentum.rsi(c, window=9)
        stoch = ta.momentum.StochasticOscillator(h, l, c, window=14, smooth_window=3)
        df["stoch_k"] = stoch.stoch()
        df["stoch_d"] = stoch.stoch_signal()
        df["stoch_rsi"] = ta.momentum.stochrsi(c, window=14)
        df["williams_r"] = ta.momentum.williams_r(h, l, c, lbp=14)
        df["cci_20"] = ta.trend.cci(h, l, c, window=20)
        df["mfi_14"] = ta.volume.money_flow_index(h, l, c, v, window=14)

        # ====== Trend (10 cols) ======
        macd_ind = ta.trend.MACD(c, window_slow=26, window_fast=12, window_sign=9)
        df["macd_line"] = macd_ind.macd()
        df["macd_signal"] = macd_ind.macd_signal()
        df["macd_histogram"] = macd_ind.macd_diff()
        df["macd_histogram_slope"] = _linear_slope(df["macd_histogram"], 3)

        adx_ind = ta.trend.ADXIndicator(h, l, c, window=14)
        df["adx_14"] = adx_ind.adx()
        df["plus_di"] = adx_ind.adx_pos()
        df["minus_di"] = adx_ind.adx_neg()

        aroon_ind = ta.trend.AroonIndicator(h, l, window=25)
        df["aroon_up"] = aroon_ind.aroon_up()
        df["aroon_down"] = aroon_ind.aroon_down()
        df["aroon_oscillator"] = df["aroon_up"] - df["aroon_down"]

        # ====== Volatility (12 cols) ======
        atr_ind = ta.volatility.AverageTrueRange(h, l, c, window=14)
        df["atr_14"] = atr_ind.average_true_range()
        df["atr_pct"] = (df["atr_14"] / c) * 100

        bb_ind = ta.volatility.BollingerBands(c, window=20, window_dev=2)
        df["bb_upper"] = bb_ind.bollinger_hband()
        df["bb_middle"] = bb_ind.bollinger_mavg()
        df["bb_lower"] = bb_ind.bollinger_lband()
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"] * 100
        df["bb_pctb"] = bb_ind.bollinger_pband()

        kc_ind = ta.volatility.KeltnerChannel(h, l, c, window=20, window_atr=10)
        df["keltner_upper"] = kc_ind.keltner_channel_hband()
        df["keltner_lower"] = kc_ind.keltner_channel_lband()

        df["bb_squeeze"] = (df["bb_upper"] < df["keltner_upper"]) & (df["bb_lower"] > df["keltner_lower"])

        log_returns = np.log(c / c.shift(1))
        df["historical_vol_20"] = log_returns.rolling(20).std() * np.sqrt(252) * 100
        df["historical_vol_60"] = log_returns.rolling(60).std() * np.sqrt(252) * 100

        # ====== Volume (7 cols) ======
        df["volume_sma_20"] = v.rolling(20).mean()
        df["volume_ratio"] = v / df["volume_sma_20"]

        df["obv"] = ta.volume.on_balance_volume(c, v)
        df["obv_slope_10d"] = _linear_slope(df["obv"], 10)

        df["ad_line"] = ta.volume.acc_dist_index(h, l, c, v)
        df["cmf_20"] = ta.volume.chaikin_money_flow(h, l, c, v, window=20)

        # VWAP distance (simplified: use day's typical price vs rolling vwap proxy)
        typical = (h + l + c) / 3
        cum_vol = v.rolling(20).sum()
        cum_tpv = (typical * v).rolling(20).sum()
        rolling_vwap = cum_tpv / cum_vol
        df["vwap_distance_pct"] = ((c - rolling_vwap) / rolling_vwap) * 100

        # ====== Price Action (11 cols) ======
        df["daily_return"] = c.pct_change() * 100
        df["gap_pct"] = ((o - c.shift(1)) / c.shift(1)) * 100

        day_range = h - l
        df["range_pct"] = (day_range / c) * 100

        body = (c - o).abs()
        df["body_pct"] = (body / day_range.replace(0, np.nan)) * 100

        upper_shadow = h - pd.concat([o, c], axis=1).max(axis=1)
        df["upper_shadow_pct"] = (upper_shadow / day_range.replace(0, np.nan)) * 100

        lower_shadow = pd.concat([o, c], axis=1).min(axis=1) - l
        df["lower_shadow_pct"] = (lower_shadow / day_range.replace(0, np.nan)) * 100

        df["close_position"] = ((c - l) / day_range.replace(0, np.nan))

        # Higher highs / higher lows counts over 5 days
        df["higher_highs_5d"] = sum(
            (h.shift(i) > h.shift(i + 1)).astype(int) for i in range(5)
        )
        df["higher_lows_5d"] = sum(
            (l.shift(i) > l.shift(i + 1)).astype(int) for i in range(5)
        )

        # Consecutive up/down days
        up = (c > c.shift(1)).astype(int)
        down = (c < c.shift(1)).astype(int)
        df["consecutive_up_days"] = up.groupby((up != up.shift()).cumsum()).cumsum()
        df["consecutive_down_days"] = down.groupby((down != down.shift()).cumsum()).cumsum()

        # ====== Relative Strength (3 cols) ======
        if spy_df is not None and not spy_df.empty:
            spy = spy_df.sort_values("date").reset_index(drop=True)
            spy_ret = spy["close"].pct_change()
            stock_ret = c.pct_change()
            # Align on date — use merge
            merged = df[["date"]].copy()
            merged["stock_ret"] = stock_ret.values
            spy_aligned = spy[["date", "close"]].rename(columns={"close": "spy_close"})
            spy_aligned["spy_ret"] = spy_ret.values
            merged = merged.merge(spy_aligned[["date", "spy_ret"]], on="date", how="left")
            rs_20 = merged["stock_ret"].rolling(20).sum() - merged["spy_ret"].rolling(20).sum()
            df["rs_vs_spy_20d"] = rs_20.values * 100
        else:
            df["rs_vs_spy_20d"] = np.nan

        df["rs_vs_sector_20d"] = np.nan  # Requires sector data — computed in orchestrator
        df["rs_rank_percentile"] = np.nan  # Requires cross-sectional data

        # ====== Support / Resistance (4 cols) ======
        high_52w = h.rolling(252, min_periods=50).max()
        low_52w = l.rolling(252, min_periods=50).min()
        df["near_52w_high_pct"] = ((c - high_52w) / high_52w) * 100
        df["near_52w_low_pct"] = ((c - low_52w) / low_52w) * 100

        # Resistance: nearest prior swing high above current price
        # Support: nearest prior swing low below current price
        # Simplified: use rolling 20-bar high/low as proxy
        resistance = h.rolling(20).max()
        support = l.rolling(20).min()
        df["distance_to_resistance_pct"] = ((resistance - c) / c) * 100
        df["distance_to_support_pct"] = ((c - support) / c) * 100

        # Drop helper columns, keep only feature columns
        feature_cols = [
            # MA
            "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
            "ema_9", "ema_12", "ema_21", "ema_26", "ema_50",
            # MA Derived
            "price_vs_sma50_pct", "price_vs_sma200_pct", "sma50_vs_sma200_pct",
            "sma20_vs_sma50_pct", "sma50_slope_10d", "sma200_slope_10d",
            # Momentum
            "rsi_14", "rsi_9", "stoch_k", "stoch_d", "stoch_rsi",
            "williams_r", "cci_20", "mfi_14",
            # Trend
            "macd_line", "macd_signal", "macd_histogram", "macd_histogram_slope",
            "adx_14", "plus_di", "minus_di",
            "aroon_up", "aroon_down", "aroon_oscillator",
            # Volatility
            "atr_14", "atr_pct",
            "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_pctb",
            "keltner_upper", "keltner_lower", "bb_squeeze",
            "historical_vol_20", "historical_vol_60",
            # Volume
            "volume_sma_20", "volume_ratio", "obv", "obv_slope_10d",
            "ad_line", "cmf_20", "vwap_distance_pct",
            # Price Action
            "daily_return", "gap_pct", "range_pct", "body_pct",
            "upper_shadow_pct", "lower_shadow_pct", "close_position",
            "higher_highs_5d", "higher_lows_5d",
            "consecutive_up_days", "consecutive_down_days",
            # Relative Strength
            "rs_vs_spy_20d", "rs_vs_sector_20d", "rs_rank_percentile",
            # Support/Resistance
            "distance_to_resistance_pct", "distance_to_support_pct",
            "near_52w_high_pct", "near_52w_low_pct",
        ]

        result = df[["date"] + feature_cols].copy()
        return result
