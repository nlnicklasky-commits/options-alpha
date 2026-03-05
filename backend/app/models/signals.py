from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_signals_stock_date"),
        Index("ix_signals_stock_date_desc", "stock_id", "date", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    breakout_probability: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    technical_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    options_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    pattern_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    composite_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))

    suggested_strike: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    suggested_expiry: Mapped[date | None] = mapped_column(Date)
    suggested_entry_price: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    risk_reward_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    model_version: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    stock = relationship("Stock", back_populates="signals")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50))

    total_trades: Mapped[int | None] = mapped_column(Integer)
    win_rate: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    avg_return: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    max_drawdown: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    sharpe_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    profit_factor: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    parameters: Mapped[str | None] = mapped_column(Text)  # JSON string of params

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trades = relationship("BacktestTrade", back_populates="run", lazy="selectin")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[date | None] = mapped_column(Date)
    entry_price: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    exit_price: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    return_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    signal_score: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run = relationship("BacktestRun", back_populates="trades")
