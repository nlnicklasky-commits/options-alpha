from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OptionsSnapshot(Base):
    __tablename__ = "options_snapshots"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_options_snapshots_stock_date"),
        Index(
            "ix_options_snapshots_stock_date_desc",
            "stock_id",
            "date",
            postgresql_using="btree",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # IV metrics
    iv_rank: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_percentile: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_30d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_60d: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_skew: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_term_structure: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # Flow
    put_call_volume_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    put_call_oi_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    total_call_volume: Mapped[int | None] = mapped_column(BigInteger)
    total_put_volume: Mapped[int | None] = mapped_column(BigInteger)
    total_call_oi: Mapped[int | None] = mapped_column(BigInteger)
    total_put_oi: Mapped[int | None] = mapped_column(BigInteger)

    # IV detail
    iv_vs_hv_ratio: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_call_atm: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    iv_put_atm: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    # OI / volume changes
    call_oi_change: Mapped[int | None] = mapped_column(Integer)
    put_oi_change: Mapped[int | None] = mapped_column(Integer)
    call_volume_vs_avg: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    max_single_call_volume: Mapped[int | None] = mapped_column(Integer)

    # Front-month ATM call
    front_atm_call_bid: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    front_atm_call_ask: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    front_atm_call_spread_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    front_atm_call_volume: Mapped[int | None] = mapped_column(Integer)
    front_atm_call_oi: Mapped[int | None] = mapped_column(Integer)

    # ATM greeks (nearest ATM call)
    atm_delta: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    atm_gamma: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    atm_theta: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    atm_vega: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    stock = relationship("Stock", back_populates="options_snapshots")


class OptionsFlow(Base):
    __tablename__ = "options_flow"
    __table_args__ = (
        Index("ix_options_flow_stock_date", "stock_id", "date", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_type: Mapped[str] = mapped_column(String(4), nullable=False)  # CALL/PUT
    strike: Mapped[Numeric] = mapped_column(Numeric(12, 4), nullable=False)
    expiration: Mapped[date] = mapped_column(Date, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open_interest: Mapped[int] = mapped_column(BigInteger, nullable=False)
    premium: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    iv: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    delta: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    is_unusual: Mapped[bool | None] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
