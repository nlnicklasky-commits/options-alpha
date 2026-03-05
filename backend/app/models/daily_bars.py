from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DailyBar(Base):
    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_daily_bars_stock_date"),
        Index("ix_daily_bars_stock_date_desc", "stock_id", "date", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vwap: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    num_trades: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    stock = relationship("Stock", back_populates="daily_bars")
