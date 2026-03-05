"""Tests for technical indicator calculations.

Verifies RSI, MACD, Bollinger Bands, and moving average values against known correct outputs
using synthetic price data with predictable patterns.
"""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.services.technical_calc import TechnicalCalculator


def _make_bars(
    n: int = 250,
    start_price: float = 100.0,
    trend: float = 0.001,
    volatility: float = 0.02,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic daily OHLCV bars."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2024-01-02", periods=n)
    closes = [start_price]
    for _ in range(n - 1):
        ret = trend + volatility * rng.randn()
        closes.append(closes[-1] * (1 + ret))
    closes = np.array(closes)
    highs = closes * (1 + rng.uniform(0.002, 0.015, n))
    lows = closes * (1 - rng.uniform(0.002, 0.015, n))
    opens = closes * (1 + rng.uniform(-0.005, 0.005, n))
    volumes = rng.randint(1_000_000, 10_000_000, n).astype(float)

    return pd.DataFrame({
        "date": dates[:n],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


@pytest.fixture
def bars_df() -> pd.DataFrame:
    return _make_bars()


@pytest.fixture
def calc() -> TechnicalCalculator:
    return TechnicalCalculator()


class TestComputeHistorical:
    def test_returns_dataframe_with_all_feature_columns(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(bars_df)
        assert "date" in result.columns
        assert "rsi_14" in result.columns
        assert "macd_line" in result.columns
        assert "bb_upper" in result.columns
        assert "sma_50" in result.columns
        assert "sma_200" in result.columns

    def test_sma_values_correct(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        # SMA 10 at row 9 should be the mean of the first 10 closes
        expected_sma10 = bars_df["close"].iloc[:10].mean()
        actual_sma10 = result["sma_10"].iloc[9]
        assert abs(actual_sma10 - expected_sma10) < 0.01

    def test_rsi_range(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        rsi = result["rsi_14"].dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_bollinger_band_ordering(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        valid = result.dropna(subset=["bb_upper", "bb_middle", "bb_lower"])
        assert (valid["bb_upper"] >= valid["bb_middle"]).all()
        assert (valid["bb_middle"] >= valid["bb_lower"]).all()

    def test_macd_histogram_equals_line_minus_signal(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        valid = result.dropna(subset=["macd_line", "macd_signal", "macd_histogram"])
        diff = valid["macd_line"] - valid["macd_signal"]
        np.testing.assert_allclose(valid["macd_histogram"].values, diff.values, atol=0.001)

    def test_atr_positive(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        atr = result["atr_14"].dropna()
        assert (atr >= 0).all()

    def test_volume_ratio_around_one(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        vol_ratio = result["volume_ratio"].dropna()
        # With random volume, ratio should average ~1
        assert 0.5 < vol_ratio.mean() < 2.0

    def test_consecutive_days_non_negative(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df)
        assert (result["consecutive_up_days"].dropna() >= 0).all()
        assert (result["consecutive_down_days"].dropna() >= 0).all()


class TestComputeAll:
    def test_returns_dict_for_latest_bar(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_all(bars_df)
        assert isinstance(result, dict)
        assert "rsi_14" in result
        assert "sma_50" in result

    def test_decimal_types(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_all(bars_df)
        # Most values should be Decimal or None
        for key in ("rsi_14", "sma_50", "bb_upper", "macd_line", "atr_14"):
            val = result[key]
            assert val is None or isinstance(val, Decimal), f"{key} should be Decimal, got {type(val)}"

    def test_integer_types(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_all(bars_df)
        for key in ("higher_highs_5d", "higher_lows_5d", "consecutive_up_days", "consecutive_down_days"):
            val = result[key]
            assert val is None or isinstance(val, int), f"{key} should be int, got {type(val)}"

    def test_bb_squeeze_is_bool(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_all(bars_df)
        assert isinstance(result["bb_squeeze"], bool)

    def test_empty_bars_returns_empty_dict(self, calc: TechnicalCalculator) -> None:
        empty = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        result = calc.compute_all(empty)
        assert result == {}

    def test_short_bars_still_works(self, calc: TechnicalCalculator) -> None:
        bars = _make_bars(n=50)
        result = calc.compute_all(bars)
        assert isinstance(result, dict)
        # SMA 200 should be None with only 50 bars
        assert result.get("sma_200") is None


class TestRelativeStrength:
    def test_rs_vs_spy_computed_with_spy_data(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        spy_df = _make_bars(n=250, start_price=450, trend=0.001, seed=99)
        result = calc.compute_historical(bars_df, spy_df)
        rs = result["rs_vs_spy_20d"].dropna()
        assert len(rs) > 0

    def test_rs_vs_spy_nan_without_spy_data(self, calc: TechnicalCalculator, bars_df: pd.DataFrame) -> None:
        result = calc.compute_historical(bars_df, None)
        assert result["rs_vs_spy_20d"].isna().all()
