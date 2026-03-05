from datetime import date, datetime

from sqlalchemy import ARRAY, Boolean, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(200))
    market_cap: Mapped[int | None] = mapped_column(Numeric(16, 0))
    avg_volume_30d: Mapped[int | None] = mapped_column(Numeric(16, 0))
    index_membership: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seeded_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    daily_bars = relationship("DailyBar", back_populates="stock", lazy="selectin")
    technical_snapshots = relationship(
        "TechnicalSnapshot", back_populates="stock", lazy="selectin"
    )
    options_snapshots = relationship("OptionsSnapshot", back_populates="stock", lazy="selectin")
    signals = relationship("Signal", back_populates="stock", lazy="selectin")
