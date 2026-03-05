"""Tests for label generation.

Verifies breakout labeling, max gain, risk/reward, and call P/L labels
on known price sequences where the correct label is deterministic.
"""

import math

import numpy as np
import pandas as pd
import pytest

from app.ml.labels import LabelGenerator, _bs_call


@pytest.fixture
def generator() -> LabelGenerator:
    return LabelGenerator(session=None)


def _make_bars(close_values: list[float], stock_id: int = 1) -> pd.DataFrame:
    """Build bars DataFrame from a list of close prices."""
    n = len(close_values)
    dates = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({
        "stock_id": [stock_id] * n,
        "date": dates[:n],
        "open": close_values,
        "high": [c * 1.01 for c in close_values],
        "low": [c * 0.99 for c in close_values],
        "close": close_values,
        "volume": [1_000_000] * n,
    })


# --- Black-Scholes tests ---

class TestBlackScholes:
    def test_atm_call_positive(self) -> None:
        price = _bs_call(s=100, k=100, t=30 / 365, r=0.05, sigma=0.30)
        assert price > 0

    def test_deep_itm_near_intrinsic(self) -> None:
        # Deep ITM: S=150, K=100, should be ~50 + time value
        price = _bs_call(s=150, k=100, t=30 / 365, r=0.05, sigma=0.30)
        assert price > 49  # At least intrinsic value

    def test_deep_otm_near_zero(self) -> None:
        # Deep OTM: S=50, K=100
        price = _bs_call(s=50, k=100, t=30 / 365, r=0.05, sigma=0.30)
        assert price < 1

    def test_zero_vol_returns_intrinsic(self) -> None:
        price = _bs_call(s=110, k=100, t=1.0, r=0.0, sigma=0.0)
        assert abs(price - 10.0) < 0.01

    def test_expired_returns_intrinsic(self) -> None:
        price = _bs_call(s=110, k=100, t=0, r=0.05, sigma=0.30)
        assert abs(price - 10.0) < 0.01


# --- Breakout label tests ---

class TestLabelBreakout:
    def test_simple_breakout(self, generator: LabelGenerator) -> None:
        """Stock goes from 100 to 115 within 5 days → breakout at 10% threshold."""
        closes = [100.0, 102.0, 105.0, 108.0, 115.0, 120.0, 118.0, 115.0, 110.0, 108.0,
                  106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0, 99.0, 98.0, 97.0,
                  96.0, 95.0, 94.0, 93.0, 92.0]
        bars_df = _make_bars(closes)
        labels = generator.label_breakout(bars_df, threshold_pct=0.10, horizon_days=20)

        # First bar (100): max future within 20 days includes 120 → 20% gain → label=1
        assert labels.iloc[0] == 1.0

    def test_no_breakout(self, generator: LabelGenerator) -> None:
        """Flat price → no breakout."""
        closes = [100.0] * 30
        bars_df = _make_bars(closes)
        labels = generator.label_breakout(bars_df, threshold_pct=0.10, horizon_days=20)
        # All labels with enough horizon should be 0
        valid = labels.dropna()
        assert (valid == 0.0).all()

    def test_last_bars_are_nan(self, generator: LabelGenerator) -> None:
        """Last horizon_days bars shouldn't have labels (not enough future data)."""
        closes = [100.0] * 30
        bars_df = _make_bars(closes)
        labels = generator.label_breakout(bars_df, threshold_pct=0.10, horizon_days=20)
        # Last 20 bars should be NaN
        assert labels.iloc[-1] != labels.iloc[-1]  # NaN check

    def test_custom_threshold(self, generator: LabelGenerator) -> None:
        """5% threshold should flag smaller gains."""
        closes = [100.0, 102.0, 106.0, 103.0, 101.0, 100.0, 99.0, 98.0, 97.0, 96.0,
                  95.0, 94.0, 93.0, 92.0, 91.0, 90.0, 89.0, 88.0, 87.0, 86.0,
                  85.0, 84.0, 83.0, 82.0, 81.0]
        bars_df = _make_bars(closes)
        labels = generator.label_breakout(bars_df, threshold_pct=0.05, horizon_days=20)
        # First bar: max future gain = 6% → above 5% threshold
        assert labels.iloc[0] == 1.0

    def test_multiple_stocks(self, generator: LabelGenerator) -> None:
        """Labels computed per stock independently."""
        bars1 = _make_bars([100.0, 115.0, 120.0] + [100.0] * 22, stock_id=1)
        bars2 = _make_bars([100.0] * 25, stock_id=2)
        combined = pd.concat([bars1, bars2]).reset_index(drop=True)
        labels = generator.label_breakout(combined, threshold_pct=0.10, horizon_days=20)
        # Stock 1 first bar should be breakout, stock 2 should not
        stock1_label = labels.iloc[0]
        stock2_start = 25
        stock2_label = labels.iloc[stock2_start]
        assert stock1_label == 1.0
        assert stock2_label == 0.0


# --- Max gain label tests ---

class TestLabelMaxGain:
    def test_steady_uptrend(self, generator: LabelGenerator) -> None:
        """Steady 1% daily gain should have specific max gain within horizon."""
        closes = [100.0 * (1.01 ** i) for i in range(30)]
        bars_df = _make_bars(closes)
        labels = generator.label_max_gain(bars_df, horizon_days=10)
        # First bar: max gain within 10 days = (100 * 1.01^10 - 100) / 100 ≈ 10.46%
        expected = (1.01 ** 10 - 1)
        assert abs(labels.iloc[0] - expected) < 0.01


# --- Risk/reward label tests ---

class TestLabelRiskReward:
    def test_positive_risk_reward(self, generator: LabelGenerator) -> None:
        """Stock with big gain and small drawdown should have high R:R."""
        closes = [100.0, 99.0, 110.0, 115.0, 120.0] + [120.0] * 20
        bars_df = _make_bars(closes)
        labels = generator.label_risk_reward(bars_df, horizon_days=20)
        rr = labels.iloc[0]
        assert rr > 1.0  # Gain far exceeds drawdown


# --- Call P/L label tests ---

class TestLabelCallPnl:
    def test_big_rally_positive_pnl(self, generator: LabelGenerator) -> None:
        """Stock rallying 20% should produce positive call P/L."""
        closes = [100.0 + i * 1.0 for i in range(25)]  # From 100 to 124
        bars_df = _make_bars(closes)
        labels = generator.label_call_pnl(bars_df, dte=30, horizon_days=20)
        # The call should gain significantly from the price increase
        valid = labels.dropna()
        assert len(valid) > 0
        assert valid.iloc[0] > 0  # Positive P/L

    def test_flat_market_negative_pnl(self, generator: LabelGenerator) -> None:
        """Flat price should produce negative call P/L due to theta decay."""
        closes = [100.0] * 25
        bars_df = _make_bars(closes)
        labels = generator.label_call_pnl(bars_df, dte=30, horizon_days=20)
        valid = labels.dropna()
        assert len(valid) > 0
        assert valid.iloc[0] < 0  # Theta decay

    def test_with_options_iv_data(self, generator: LabelGenerator) -> None:
        """When options_df provides IV, it should use those values."""
        closes = [100.0 + i for i in range(25)]
        bars_df = _make_bars(closes)
        # Provide options data with high IV
        opts_df = pd.DataFrame({
            "stock_id": [1] * 25,
            "date": bars_df["date"],
            "iv_30d": [0.50] * 25,  # 50% IV
        })
        labels = generator.label_call_pnl(bars_df, options_df=opts_df, dte=30, horizon_days=20)
        valid = labels.dropna()
        assert len(valid) > 0
