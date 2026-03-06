from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TechnicalSnapshot(Base):
    __tablename__ = "technical_snapshots"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_technical_snapshots_stock_date"),
        Index(
            "ix_technical_snapshots_stock_date_desc",
            "stock_id",
            "date",
            postgresql_using="btree",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Moving Averages (NUMERIC 12,4)
    sma_10: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    sma_20: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    sma_50: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    sma_100: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    sma_200: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    ema_9: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    ema_12: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    ema_21: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    ema_26: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    ema_50: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))

    # MA Derived (NUMERIC 8,4)
    price_vs_sma50_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    price_vs_sma200_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    sma50_vs_sma200_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    sma20_vs_sma50_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    sma50_slope_10d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    sma200_slope_10d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Momentum (NUMERIC 8,4)
    rsi_14: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    rsi_9: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    stoch_k: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    stoch_d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    stoch_rsi: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    williams_r: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    cci_20: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    mfi_14: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Trend (NUMERIC 8,4)
    macd_line: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    macd_signal: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    macd_histogram: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    macd_histogram_slope: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    adx_14: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    plus_di: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    minus_di: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    aroon_up: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    aroon_down: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    aroon_oscillator: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Volatility (NUMERIC 8,4 for pct, 12,4 for prices)
    atr_14: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    atr_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    bb_upper: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    bb_middle: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    bb_lower: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    bb_width: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    bb_pctb: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    keltner_upper: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    keltner_lower: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    bb_squeeze: Mapped[bool | None] = mapped_column(Boolean)
    historical_vol_20: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    historical_vol_60: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Volume (BIGINT for absolute, NUMERIC 8,4 for ratios)
    volume_sma_20: Mapped[int | None] = mapped_column(BigInteger)
    volume_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    obv: Mapped[int | None] = mapped_column(BigInteger)
    obv_slope_10d: Mapped[Numeric | None] = mapped_column(Numeric(20, 4))
    ad_line: Mapped[Numeric | None] = mapped_column(Numeric(20, 4))
    cmf_20: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    vwap_distance_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Price Action (NUMERIC 8,4 for pct, SmallInteger for counts)
    daily_return: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    gap_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    range_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    body_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    upper_shadow_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    lower_shadow_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    close_position: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    higher_highs_5d: Mapped[int | None] = mapped_column(SmallInteger)
    higher_lows_5d: Mapped[int | None] = mapped_column(SmallInteger)
    consecutive_up_days: Mapped[int | None] = mapped_column(SmallInteger)
    consecutive_down_days: Mapped[int | None] = mapped_column(SmallInteger)

    # Patterns (NUMERIC 5,2 scores 0-100)
    pattern_wedge_falling: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_wedge_rising: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_triangle_ascending: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_triangle_descending: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_triangle_symmetric: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_flag_bull: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_flag_bear: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_pennant: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_cup_handle: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_double_bottom: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_head_shoulders_inv: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_channel_up: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_consolidation_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))

    # Relative Strength (NUMERIC 8,4)
    rs_vs_spy_20d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    rs_vs_sector_20d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    rs_rank_percentile: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Support / Resistance (NUMERIC 8,4)
    distance_to_resistance_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    distance_to_support_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    near_52w_high_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    near_52w_low_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    stock = relationship("Stock", back_populates="technical_snapshots")
