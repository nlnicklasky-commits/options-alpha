"""Score router — detailed score for a single ticker."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.daily_bars import DailyBar
from app.models.stocks import Stock
from app.models.technicals import TechnicalSnapshot
from app.schemas.signals import ScoreResponse
from app.services.model_scorer import ModelScorer

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple TTL cache for score endpoint
_score_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # 5 minutes


@router.get("/{symbol}", response_model=ScoreResponse)
async def score_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed breakout score for one ticker."""
    cache_key = f"score:{symbol.upper()}"
    now = time.time()
    if cache_key in _score_cache:
        ts, data = _score_cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    scorer = ModelScorer(db)
    try:
        result = await scorer.score_single(symbol)
        _score_cache[cache_key] = (now, result)
        return result
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))


class ChartPoint(BaseModel):
    date: str
    close: float
    volume: int
    sma_50: float | None = None
    sma_200: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None


@router.get("/{symbol}/chart", response_model=list[ChartPoint])
async def get_chart_data(
    symbol: str,
    days: int = Query(default=120, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[ChartPoint]:
    """Get recent price data with technical overlays for charting."""
    stmt = select(Stock).where(Stock.symbol == symbol.upper())
    result = await db.execute(stmt)
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get daily bars with technicals joined on (stock_id, date)
    bars_stmt = (
        select(
            DailyBar.date,
            DailyBar.close,
            DailyBar.volume,
            TechnicalSnapshot.sma_50,
            TechnicalSnapshot.sma_200,
            TechnicalSnapshot.bb_upper,
            TechnicalSnapshot.bb_lower,
        )
        .outerjoin(
            TechnicalSnapshot,
            (DailyBar.stock_id == TechnicalSnapshot.stock_id)
            & (DailyBar.date == TechnicalSnapshot.date),
        )
        .where(DailyBar.stock_id == stock.id)
        .order_by(DailyBar.date.desc())
        .limit(days)
    )
    result = await db.execute(bars_stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No chart data for {symbol}")

    # Reverse to chronological order
    rows = list(reversed(rows))

    return [
        ChartPoint(
            date=row.date.isoformat(),
            close=float(row.close),
            volume=int(row.volume),
            sma_50=float(row.sma_50) if row.sma_50 else None,
            sma_200=float(row.sma_200) if row.sma_200 else None,
            bb_upper=float(row.bb_upper) if row.bb_upper else None,
            bb_lower=float(row.bb_lower) if row.bb_lower else None,
        )
        for row in rows
    ]
