"""Journal router — CRUD for trade journal entries."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.journal import TradeJournal
from app.models.stocks import Stock

router = APIRouter()


class JournalEntryCreate(BaseModel):
    symbol: str
    entry_date: str
    entry_price: float
    strike: float | None = None
    expiry: str | None = None
    contracts: int = 1
    notes: str | None = None
    tags: list[str] = []


class JournalEntryClose(BaseModel):
    exit_date: str
    exit_price: float
    exit_reason: str | None = None


class JournalEntryResponse(BaseModel):
    id: int
    symbol: str
    entry_date: str
    entry_price: float
    strike: float | None = None
    expiry: str | None = None
    contracts: int
    exit_date: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl: float | None = None
    notes: str | None = None
    tags: list[str]
    status: str


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal(
    db: AsyncSession = Depends(get_db),
) -> list[JournalEntryResponse]:
    """List all journal entries."""
    stmt = (
        select(TradeJournal, Stock.symbol)
        .join(Stock, TradeJournal.stock_id == Stock.id)
        .order_by(TradeJournal.entry_date.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        JournalEntryResponse(
            id=entry.id,
            symbol=symbol,
            entry_date=entry.entry_date.isoformat(),
            entry_price=float(entry.entry_price) if entry.entry_price else 0.0,
            strike=float(entry.strike) if entry.strike else None,
            expiry=entry.expiration.isoformat() if entry.expiration else None,
            contracts=entry.quantity,
            exit_date=entry.exit_date.isoformat() if entry.exit_date else None,
            exit_price=float(entry.exit_price) if entry.exit_price else None,
            exit_reason=entry.setup_type,
            pnl=float(entry.pnl) if entry.pnl else None,
            notes=entry.notes,
            tags=entry.tags or [],
            status="closed" if entry.exit_date else "open",
        )
        for entry, symbol in rows
    ]


@router.post("", response_model=JournalEntryResponse)
async def create_journal_entry(
    body: JournalEntryCreate,
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    """Create a new journal entry."""
    from datetime import date as date_cls

    stmt = select(Stock).where(Stock.symbol == body.symbol.upper())
    result = await db.execute(stmt)
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {body.symbol} not found")

    entry = TradeJournal(
        stock_id=stock.id,
        entry_date=date_cls.fromisoformat(body.entry_date),
        entry_price=Decimal(str(body.entry_price)),
        strike=Decimal(str(body.strike)) if body.strike is not None else None,
        expiration=date_cls.fromisoformat(body.expiry) if body.expiry else None,
        quantity=body.contracts,
        notes=body.notes,
        tags=body.tags if body.tags else None,
        direction="LONG",
        contract_type="CALL",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return JournalEntryResponse(
        id=entry.id,
        symbol=stock.symbol,
        entry_date=entry.entry_date.isoformat(),
        entry_price=float(entry.entry_price),
        strike=float(entry.strike) if entry.strike else None,
        expiry=entry.expiration.isoformat() if entry.expiration else None,
        contracts=entry.quantity,
        exit_date=None,
        exit_price=None,
        exit_reason=None,
        pnl=None,
        notes=entry.notes,
        tags=entry.tags or [],
        status="open",
    )


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
async def close_journal_entry(
    entry_id: int,
    body: JournalEntryClose,
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    """Close a trade -- set exit date/price, compute PnL."""
    from datetime import date as date_cls

    stmt = select(TradeJournal).where(TradeJournal.id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    entry.exit_date = date_cls.fromisoformat(body.exit_date)
    entry.exit_price = Decimal(str(body.exit_price))
    entry.setup_type = body.exit_reason

    # PnL = (exit - entry) * contracts * 100 (options multiplier)
    entry_price = float(entry.entry_price)
    pnl = (body.exit_price - entry_price) * entry.quantity * 100
    entry.pnl = Decimal(str(round(pnl, 4)))

    if entry_price > 0:
        entry.return_pct = Decimal(str(round((body.exit_price - entry_price) / entry_price, 4)))

    await db.commit()
    await db.refresh(entry)

    # Get symbol
    stock_stmt = select(Stock.symbol).where(Stock.id == entry.stock_id)
    stock_result = await db.execute(stock_stmt)
    symbol = stock_result.scalar_one()

    return JournalEntryResponse(
        id=entry.id,
        symbol=symbol,
        entry_date=entry.entry_date.isoformat(),
        entry_price=float(entry.entry_price),
        strike=float(entry.strike) if entry.strike else None,
        expiry=entry.expiration.isoformat() if entry.expiration else None,
        contracts=entry.quantity,
        exit_date=entry.exit_date.isoformat() if entry.exit_date else None,
        exit_price=float(entry.exit_price) if entry.exit_price else None,
        exit_reason=entry.setup_type,
        pnl=float(entry.pnl) if entry.pnl else None,
        notes=entry.notes,
        tags=entry.tags or [],
        status="closed" if entry.exit_date else "open",
    )
