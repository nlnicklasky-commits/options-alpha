from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MarketRegime(Base):
    __tablename__ = "market_regimes"
    __table_args__ = (
        UniqueConstraint("date", name="uq_market_regimes_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # VIX
    vix_close: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    vix_sma_20: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    vix_percentile: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Breadth
    advance_decline_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    pct_above_sma200: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    pct_above_sma50: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    new_highs: Mapped[int | None] = mapped_column(Integer)
    new_lows: Mapped[int | None] = mapped_column(Integer)
    mcclellan_oscillator: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Sector rotation
    leading_sector: Mapped[str | None] = mapped_column(String(100))
    lagging_sector: Mapped[str | None] = mapped_column(String(100))
    sector_dispersion: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Rates
    us_10y_yield: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    us_2y_yield: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    yield_curve_spread: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    fed_funds_rate: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Overall regime label
    regime_label: Mapped[str | None] = mapped_column(String(50))  # e.g. "bull", "bear", "neutral"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
