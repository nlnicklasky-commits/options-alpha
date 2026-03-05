"""Options chain router — returns latest options snapshot for a symbol."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.options import OptionsSnapshot
from app.models.stocks import Stock
from app.models.technicals import TechnicalSnapshot

router = APIRouter()


class OptionsData(BaseModel):
    iv_rank: float | None = None
    iv: float | None = None
    hv: float | None = None
    put_call_ratio: float | None = None


@router.get("/{symbol}", response_model=OptionsData)
async def get_options_data(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> OptionsData:
    """Get latest options snapshot for a symbol."""
    stmt = select(Stock).where(Stock.symbol == symbol.upper())
    result = await db.execute(stmt)
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get latest options snapshot
    opts_stmt = (
        select(OptionsSnapshot)
        .where(OptionsSnapshot.stock_id == stock.id)
        .order_by(OptionsSnapshot.date.desc())
        .limit(1)
    )
    opts_result = await db.execute(opts_stmt)
    opts = opts_result.scalar_one_or_none()

    # Get latest HV from technicals
    tech_stmt = (
        select(TechnicalSnapshot.historical_vol_20)
        .where(TechnicalSnapshot.stock_id == stock.id)
        .order_by(TechnicalSnapshot.date.desc())
        .limit(1)
    )
    tech_result = await db.execute(tech_stmt)
    hv = tech_result.scalar_one_or_none()

    if not opts:
        return OptionsData(hv=float(hv) if hv else None)

    return OptionsData(
        iv_rank=float(opts.iv_rank) if opts.iv_rank else None,
        iv=float(opts.iv_30d) if opts.iv_30d else None,
        hv=float(hv) if hv else None,
        put_call_ratio=float(opts.put_call_volume_ratio) if opts.put_call_volume_ratio else None,
    )
