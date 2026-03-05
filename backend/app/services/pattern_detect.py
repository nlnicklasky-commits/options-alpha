import logging
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _to_score(val: float) -> Decimal | None:
    """Clamp to 0-100 and convert to Decimal."""
    if np.isnan(val) or np.isinf(val):
        return None
    return Decimal(str(round(max(0.0, min(100.0, val)), 2)))


def _fit_trendline(prices: np.ndarray) -> tuple[float, float]:
    """Fit linear regression, return (slope, r_squared)."""
    if len(prices) < 3:
        return 0.0, 0.0
    x = np.arange(len(prices), dtype=float)
    mask = ~np.isnan(prices)
    if mask.sum() < 3:
        return 0.0, 0.0
    coeffs = np.polyfit(x[mask], prices[mask], 1)
    predicted = np.polyval(coeffs, x[mask])
    ss_res = np.sum((prices[mask] - predicted) ** 2)
    ss_tot = np.sum((prices[mask] - np.mean(prices[mask])) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(coeffs[0]), float(r2)


def _count_touches(prices: np.ndarray, line_values: np.ndarray, tolerance_pct: float = 0.01) -> int:
    """Count how many prices are within tolerance of the trendline."""
    if len(prices) == 0:
        return 0
    tol = np.abs(line_values) * tolerance_pct
    tol = np.maximum(tol, 0.01)
    return int(np.sum(np.abs(prices - line_values) <= tol))


class PatternDetector:
    """Detect chart patterns and score them 0-100.

    Each pattern method analyses recent price action (20-60 bars)
    and returns a confidence score.
    """

    def detect_all(self, bars_df: pd.DataFrame) -> dict[str, Any]:
        """Run all pattern detectors on the latest data.

        Args:
            bars_df: DataFrame with date, open, high, low, close, volume.
                     Needs at least 60 bars of history.

        Returns:
            Dict of pattern scores (Decimal 0-100 or None).
        """
        df = bars_df.copy().sort_values("date").reset_index(drop=True)

        if len(df) < 30:
            return {k: None for k in self._all_pattern_keys()}

        h = df["high"].astype(float).values
        l = df["low"].astype(float).values
        c = df["close"].astype(float).values
        v = df["volume"].astype(float).values

        return {
            "pattern_wedge_falling": _to_score(self._wedge(h, l, v, falling=True)),
            "pattern_wedge_rising": _to_score(self._wedge(h, l, v, falling=False)),
            "pattern_triangle_ascending": _to_score(self._triangle(h, l, v, kind="ascending")),
            "pattern_triangle_descending": _to_score(self._triangle(h, l, v, kind="descending")),
            "pattern_triangle_symmetric": _to_score(self._triangle(h, l, v, kind="symmetric")),
            "pattern_flag_bull": _to_score(self._flag(h, l, c, v, bull=True)),
            "pattern_flag_bear": _to_score(self._flag(h, l, c, v, bull=False)),
            "pattern_pennant": _to_score(self._pennant(h, l, c, v)),
            "pattern_cup_handle": _to_score(self._cup_and_handle(h, l, c, v)),
            "pattern_double_bottom": _to_score(self._double_bottom(h, l, c)),
            "pattern_head_shoulders_inv": _to_score(self._inverse_head_shoulders(h, l, c)),
            "pattern_channel_up": _to_score(self._channel_up(h, l)),
            "pattern_consolidation_score": _to_score(self._consolidation(h, l, c, v)),
        }

    @staticmethod
    def _all_pattern_keys() -> list[str]:
        return [
            "pattern_wedge_falling", "pattern_wedge_rising",
            "pattern_triangle_ascending", "pattern_triangle_descending",
            "pattern_triangle_symmetric",
            "pattern_flag_bull", "pattern_flag_bear", "pattern_pennant",
            "pattern_cup_handle", "pattern_double_bottom",
            "pattern_head_shoulders_inv", "pattern_channel_up",
            "pattern_consolidation_score",
        ]

    # -- Individual pattern detectors --------------------------------------

    def _wedge(self, h: np.ndarray, l: np.ndarray, v: np.ndarray, falling: bool) -> float:
        """Detect wedge pattern: converging trendlines on highs/lows."""
        for window in (40, 30, 20):
            if len(h) < window:
                continue
            highs = h[-window:]
            lows = l[-window:]
            vols = v[-window:]

            high_slope, high_r2 = _fit_trendline(highs)
            low_slope, low_r2 = _fit_trendline(lows)

            # Both slopes should point the same direction for a wedge
            if falling and (high_slope >= 0 or low_slope >= 0):
                continue
            if not falling and (high_slope <= 0 or low_slope <= 0):
                continue

            # Converging: high slope and low slope getting closer
            convergence = abs(high_slope) - abs(low_slope)
            if falling:
                converging = high_slope < low_slope  # Upper falls faster
            else:
                converging = high_slope > low_slope  # Upper rises faster? No, upper rises slower
                converging = low_slope > high_slope

            if not converging:
                continue

            # Score components
            fit_quality = (high_r2 + low_r2) / 2 * 40  # 0-40
            vol_decline = 0.0
            if len(vols) >= 10:
                early_vol = np.mean(vols[:len(vols) // 3])
                late_vol = np.mean(vols[-len(vols) // 3:])
                if early_vol > 0:
                    vol_decline = max(0, (early_vol - late_vol) / early_vol) * 30  # 0-30

            x = np.arange(len(highs), dtype=float)
            high_line = np.polyval(np.polyfit(x, highs, 1), x)
            low_line = np.polyval(np.polyfit(x, lows, 1), x)
            high_touches = _count_touches(highs, high_line) * 5  # 0-30
            low_touches = _count_touches(lows, low_line) * 5

            score = fit_quality + vol_decline + min(30, high_touches + low_touches)
            return min(100, score)

        return 0.0

    def _triangle(self, h: np.ndarray, l: np.ndarray, v: np.ndarray, kind: str) -> float:
        """Detect triangle patterns."""
        for window in (40, 30, 20):
            if len(h) < window:
                continue
            highs = h[-window:]
            lows = l[-window:]

            high_slope, high_r2 = _fit_trendline(highs)
            low_slope, low_r2 = _fit_trendline(lows)

            price_range = np.mean(highs) - np.mean(lows)
            if price_range <= 0:
                continue
            norm_high_slope = high_slope / price_range * window
            norm_low_slope = low_slope / price_range * window

            if kind == "ascending":
                # Flat top, rising bottom
                if abs(norm_high_slope) > 0.3 or norm_low_slope < 0.05:
                    continue
            elif kind == "descending":
                # Flat bottom, falling top
                if abs(norm_low_slope) > 0.3 or norm_high_slope > -0.05:
                    continue
            elif kind == "symmetric":
                # Both converging
                if norm_high_slope >= 0 or norm_low_slope <= 0:
                    continue
            else:
                continue

            fit_quality = (high_r2 + low_r2) / 2 * 50
            convergence_rate = abs(high_slope - low_slope) / price_range * window
            convergence_score = min(30, convergence_rate * 100)

            vols = v[-window:]
            vol_score = 0.0
            if len(vols) >= 10:
                early = np.mean(vols[:len(vols) // 3])
                late = np.mean(vols[-len(vols) // 3:])
                if early > 0:
                    vol_score = max(0, (early - late) / early) * 20

            return min(100, fit_quality + convergence_score + vol_score)

        return 0.0

    def _flag(self, h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray, bull: bool) -> float:
        """Detect flag pattern: strong move (pole) then tight consolidation."""
        if len(c) < 30:
            return 0.0

        # Look for pole: strong move in last 15-30 bars followed by consolidation
        for pole_len in (10, 15, 8):
            cons_len = min(15, len(c) - pole_len - 5)
            if cons_len < 5:
                continue

            pole_start = -(pole_len + cons_len)
            pole_end = -cons_len
            pole = c[pole_start:pole_end]
            consolidation = c[-cons_len:]

            pole_move = (pole[-1] - pole[0]) / pole[0] * 100
            if bull and pole_move < 5:
                continue
            if not bull and pole_move > -5:
                continue

            # Consolidation should be tight
            cons_range = (np.max(consolidation) - np.min(consolidation)) / np.mean(consolidation) * 100
            pole_range = abs(pole_move)

            if cons_range > pole_range * 0.5:
                continue  # Consolidation too wide

            pole_score = min(40, abs(pole_move) * 3)
            tightness_score = max(0, 30 - cons_range * 3)

            cons_slope, _ = _fit_trendline(consolidation)
            # Flag should slope slightly against the pole direction
            slope_score = 0.0
            if bull and cons_slope < 0:
                slope_score = 20
            elif not bull and cons_slope > 0:
                slope_score = 20
            elif abs(cons_slope) < 0.1:
                slope_score = 10

            return min(100, pole_score + tightness_score + slope_score)

        return 0.0

    def _pennant(self, h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray) -> float:
        """Pennant: strong move + symmetric triangle consolidation."""
        if len(c) < 25:
            return 0.0

        # Find pole
        for pole_len in (10, 8):
            cons_len = min(15, len(c) - pole_len - 3)
            if cons_len < 5:
                continue

            pole = c[-(pole_len + cons_len):-cons_len]
            pole_move = abs((pole[-1] - pole[0]) / pole[0] * 100)
            if pole_move < 5:
                continue

            cons_h = h[-cons_len:]
            cons_l = l[-cons_len:]
            h_slope, _ = _fit_trendline(cons_h)
            l_slope, _ = _fit_trendline(cons_l)

            # Pennant: converging (high slope down, low slope up)
            if h_slope >= 0 or l_slope <= 0:
                continue

            pole_score = min(40, pole_move * 3)
            convergence = abs(h_slope) + abs(l_slope)
            conv_score = min(30, convergence * 500)
            vol_score = 0.0
            if len(v) >= cons_len:
                cons_v = v[-cons_len:]
                if np.mean(cons_v[:3]) > 0:
                    vol_score = max(0, 1 - np.mean(cons_v[-3:]) / np.mean(cons_v[:3])) * 30

            return min(100, pole_score + conv_score + vol_score)

        return 0.0

    def _cup_and_handle(self, h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray) -> float:
        """Cup and handle: U-shaped base with handle pullback."""
        if len(c) < 40:
            return 0.0

        # Look for U-shape in last 30-60 bars
        for window in (50, 40, 30):
            if len(c) < window:
                continue
            segment = c[-window:]
            mid = len(segment) // 2

            left = segment[:mid]
            right = segment[mid:]

            # Cup: left side descends, right side ascends
            left_slope, _ = _fit_trendline(left)
            right_slope, _ = _fit_trendline(right)

            if left_slope >= 0 or right_slope <= 0:
                continue

            # Symmetry: similar depth on both sides
            left_low = np.min(left)
            right_low = np.min(right)
            cup_low = min(left_low, right_low)
            lip = max(segment[0], segment[-1])

            depth = (lip - cup_low) / lip * 100
            if depth < 5 or depth > 40:
                continue

            symmetry = 1 - abs(np.argmin(left) / len(left) - (1 - np.argmin(right) / len(right)))
            sym_score = max(0, symmetry) * 30

            depth_score = min(30, depth * 2)

            # Handle: small pullback at the end
            handle_score = 0.0
            if len(c) > window + 5:
                handle = c[-5:]
                if handle[-1] < handle[0] and (handle[0] - handle[-1]) / handle[0] * 100 < depth * 0.5:
                    handle_score = 20

            # Right side should approach the left lip
            lip_approach = 1 - abs(segment[-1] - segment[0]) / segment[0]
            lip_score = max(0, lip_approach) * 20

            return min(100, sym_score + depth_score + handle_score + lip_score)

        return 0.0

    def _double_bottom(self, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> float:
        """Double bottom: two lows at similar level with rally between."""
        if len(l) < 30:
            return 0.0

        for window in (40, 30, 20):
            if len(l) < window:
                continue
            lows = l[-window:]
            closes = c[-window:]

            # Find two lowest points
            sorted_idx = np.argsort(lows)
            first_low_idx = sorted_idx[0]
            # Second low must be at least 5 bars away
            second_low_idx = None
            for idx in sorted_idx[1:]:
                if abs(idx - first_low_idx) >= 5:
                    second_low_idx = idx
                    break

            if second_low_idx is None:
                continue

            low1 = lows[first_low_idx]
            low2 = lows[second_low_idx]

            # Lows should be within 3% of each other
            if abs(low1 - low2) / min(low1, low2) * 100 > 3:
                continue

            # Rally between the lows
            left_idx = min(first_low_idx, second_low_idx)
            right_idx = max(first_low_idx, second_low_idx)
            between = closes[left_idx:right_idx + 1]
            if len(between) < 3:
                continue
            neckline = np.max(between)
            rally_pct = (neckline - min(low1, low2)) / min(low1, low2) * 100

            if rally_pct < 3:
                continue

            # Score
            symmetry = 1 - abs(low1 - low2) / min(low1, low2)
            sym_score = symmetry * 40
            rally_score = min(30, rally_pct * 3)

            # Recent price should be near/above neckline
            current = closes[-1]
            neckline_score = 0.0
            if current >= neckline * 0.98:
                neckline_score = 30

            return min(100, sym_score + rally_score + neckline_score)

        return 0.0

    def _inverse_head_shoulders(self, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> float:
        """Inverse H&S: three troughs, middle lowest."""
        if len(l) < 40:
            return 0.0

        for window in (50, 40, 30):
            if len(l) < window:
                continue
            lows = l[-window:]

            third = len(lows) // 3
            left_section = lows[:third]
            mid_section = lows[third:2 * third]
            right_section = lows[2 * third:]

            left_trough = np.min(left_section)
            head = np.min(mid_section)
            right_trough = np.min(right_section)

            # Head must be lower than both shoulders
            if head >= left_trough or head >= right_trough:
                continue

            # Shoulders should be at similar level
            shoulder_diff = abs(left_trough - right_trough) / min(left_trough, right_trough) * 100
            if shoulder_diff > 5:
                continue

            head_depth = (min(left_trough, right_trough) - head) / min(left_trough, right_trough) * 100
            if head_depth < 2:
                continue

            sym_score = max(0, (1 - shoulder_diff / 5)) * 40
            depth_score = min(30, head_depth * 5)

            # Neckline break
            neckline = max(
                np.max(c[np.argmin(left_section):np.argmin(left_section) + third]),
                np.max(c[third + np.argmin(mid_section):third + np.argmin(mid_section) + third]) if third + np.argmin(mid_section) + third <= len(c) else 0,
            ) if len(c) >= window else 0
            neckline_score = 30 if c[-1] >= neckline * 0.98 and neckline > 0 else 0

            return min(100, sym_score + depth_score + neckline_score)

        return 0.0

    def _channel_up(self, h: np.ndarray, l: np.ndarray) -> float:
        """Ascending channel: parallel uptrending support and resistance."""
        if len(h) < 20:
            return 0.0

        for window in (40, 30, 20):
            if len(h) < window:
                continue
            highs = h[-window:]
            lows = l[-window:]

            h_slope, h_r2 = _fit_trendline(highs)
            l_slope, l_r2 = _fit_trendline(lows)

            # Both sloping up
            if h_slope <= 0 or l_slope <= 0:
                continue

            # Parallel: similar slopes
            price_range = np.mean(highs) - np.mean(lows)
            if price_range <= 0:
                continue
            slope_diff = abs(h_slope - l_slope) / price_range * window
            if slope_diff > 0.5:
                continue

            parallel_score = max(0, (1 - slope_diff * 2)) * 40
            fit_score = (h_r2 + l_r2) / 2 * 40
            strength_score = min(20, abs(h_slope) / price_range * window * 100)

            return min(100, parallel_score + fit_score + strength_score)

        return 0.0

    def _consolidation(self, h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray) -> float:
        """Consolidation / coiled spring score: composite of BB width compression,
        ATR compression, and volume decline."""
        if len(c) < 30:
            return 0.0

        recent = 20
        c_recent = c[-recent:]
        h_recent = h[-recent:]
        l_recent = l[-recent:]
        v_recent = v[-recent:]

        # BB width percentile (low = tight)
        bb_mid = pd.Series(c).rolling(20).mean().iloc[-1]
        bb_std = pd.Series(c).rolling(20).std().iloc[-1]
        if bb_mid > 0 and not np.isnan(bb_std):
            bb_width = bb_std / bb_mid * 100
            # Compare to longer history
            all_bb_std = pd.Series(c).rolling(20).std()
            all_bb_width = all_bb_std / pd.Series(c).rolling(20).mean() * 100
            valid = all_bb_width.dropna()
            if len(valid) > 0:
                bb_pctile = (valid < bb_width).sum() / len(valid) * 100
                bb_score = max(0, (100 - bb_pctile))  # Lower percentile = more compressed
            else:
                bb_score = 0.0
        else:
            bb_score = 0.0

        # ATR compression
        tr = np.maximum(h_recent - l_recent, np.abs(h_recent - np.roll(c[-recent - 1:-1], 0)[-recent:]))
        atr_recent = np.mean(tr[-5:])
        atr_longer = np.mean(tr)
        atr_score = 0.0
        if atr_longer > 0:
            atr_ratio = atr_recent / atr_longer
            atr_score = max(0, (1 - atr_ratio)) * 100

        # Volume decline
        vol_score = 0.0
        if len(v_recent) >= 10:
            early_vol = np.mean(v_recent[:10])
            late_vol = np.mean(v_recent[-5:])
            if early_vol > 0:
                vol_score = max(0, (early_vol - late_vol) / early_vol) * 100

        # Composite: weight BB 40%, ATR 30%, Volume 30%
        return bb_score * 0.4 + atr_score * 0.3 + vol_score * 0.3
