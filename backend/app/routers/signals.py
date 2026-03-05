"""Signals router — today's top ML-scored opportunities."""

import logging
import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.market_regime import MarketRegime
from app.schemas.signals import SignalResponse
from app.services.model_scorer import ModelScorer

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple TTL cache for signals endpoint
_signals_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 300  # 5 minutes


@router.get("", response_model=list[SignalResponse])
async def get_signals(
    n: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=60.0, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get today's top signals with scores."""
    cache_key = f"signals:{n}:{min_score}"
    now = time.time()
    if cache_key in _signals_cache:
        ts, data = _signals_cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    try:
        scorer = ModelScorer(db)
        result = await scorer.get_top_signals(n=n, min_score=min_score)
        _signals_cache[cache_key] = (now, result)
        return result
    except FileNotFoundError:
        logger.warning("No trained model found — returning empty signals")
        return []
    except Exception:
        logger.exception("Error fetching signals")
        return []


class BreadthData(BaseModel):
    advance_decline: float
    pct_above_200sma: float
    new_highs_lows: float


class RegimeResponse(BaseModel):
    regime: str
    vix: float
    breadth: BreadthData


@router.get("/regime", response_model=RegimeResponse)
async def get_market_regime(
    db: AsyncSession = Depends(get_db),
) -> RegimeResponse:
    """Get the most recent market regime data."""
    stmt = select(MarketRegime).order_by(MarketRegime.date.desc()).limit(1)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        return RegimeResponse(
            regime="CHOPPY",
            vix=0.0,
            breadth=BreadthData(advance_decline=0.0, pct_above_200sma=0.0, new_highs_lows=0.0),
        )

    # Map regime_label to BULL/BEAR/CHOPPY
    label = (row.regime_label or "neutral").upper()
    if label in ("BULL", "BULLISH"):
        regime = "BULL"
    elif label in ("BEAR", "BEARISH"):
        regime = "BEAR"
    else:
        regime = "CHOPPY"

    new_highs = row.new_highs or 0
    new_lows = row.new_lows or 1
    hl_ratio = float(new_highs) / max(float(new_lows), 1.0)

    return RegimeResponse(
        regime=regime,
        vix=float(row.vix_close) if row.vix_close else 0.0,
        breadth=BreadthData(
            advance_decline=float(row.advance_decline_ratio) if row.advance_decline_ratio else 0.0,
            pct_above_200sma=float(row.pct_above_sma200) if row.pct_above_sma200 else 0.0,
            new_highs_lows=round(hl_ratio, 2),
        ),
    )
