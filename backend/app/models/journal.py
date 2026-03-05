from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TradeJournal(Base):
    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[date | None] = mapped_column(Date)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="LONG")

    # Option details
    contract_type: Mapped[str | None] = mapped_column(String(4))  # CALL/PUT
    strike: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    expiration: Mapped[date | None] = mapped_column(Date)

    entry_price: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    exit_price: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    pnl: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    return_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    setup_type: Mapped[str | None] = mapped_column(String(100))
    signal_score_at_entry: Mapped[Numeric | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
