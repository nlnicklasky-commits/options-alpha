"""Signals router — today's top ML-scored opportunities."""

import logging
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.market_regime import MarketRegime
from app.models.signals import Signal
from app.models.stocks import Stock
from app.schemas.signals import SignalDetailResponse, SignalResponse
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


@router.get("/{symbol}", response_model=SignalDetailResponse)
async def get_signal_detail(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> SignalDetailResponse:
    """Get detailed signal data for a single stock."""
    today = date.today()

    # Get the signal for today
    stmt = (
        select(Signal, Stock)
        .join(Stock, Signal.stock_id == Stock.id)
        .where(Stock.symbol == symbol.upper(), Signal.date == today)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail=f"No signal found for {symbol} today")

    sig, stock = row
    scorer = ModelScorer(db)

    # Try to get component scores and top features via score_single
    component_scores: dict[str, float] = {}
    top_features: list[dict] = []
    try:
        score_result = await scorer.score_single(symbol.upper())
        component_scores = score_result.get("component_scores", {})
        top_features = score_result.get("top_features", [])
    except Exception:
        logger.warning("Could not compute component scores for %s", symbol)

    # Enrich with market data
    from app.models.daily_bars import DailyBar
    from app.models.technicals import TechnicalSnapshot

    bar_stmt = (
        select(DailyBar)
        .where(DailyBar.stock_id == stock.id, DailyBar.date <= today)
        .order_by(DailyBar.date.desc())
        .limit(1)
    )
    bar = (await db.execute(bar_stmt)).scalar_one_or_none()

    tech_stmt = (
        select(TechnicalSnapshot)
        .where(TechnicalSnapshot.stock_id == stock.id, TechnicalSnapshot.date <= today)
        .order_by(TechnicalSnapshot.date.desc())
        .limit(1)
    )
    tech = (await db.execute(tech_stmt)).scalar_one_or_none()

    def _f(v: object) -> float | None:
        return float(v) if v is not None else None

    close = _f(bar.close) if bar else None
    vol_ratio = _f(tech.volume_ratio) if tech else None
    sma_50 = _f(tech.sma_50) if tech else None
    sma_200 = _f(tech.sma_200) if tech else None
    rsi_14 = _f(tech.rsi_14) if tech else None
    adx_14 = _f(tech.adx_14) if tech else None
    bb_pctb = _f(tech.bb_pctb) if tech else None

    pattern_scores = {}
    if tech:
        pattern_scores = {
            "cup & handle": tech.pattern_cup_handle,
            "ascending triangle": tech.pattern_triangle_ascending,
            "bull flag": tech.pattern_flag_bull,
            "falling wedge": tech.pattern_wedge_falling,
            "double bottom": tech.pattern_double_bottom,
            "inv head & shoulders": tech.pattern_head_shoulders_inv,
            "channel up": tech.pattern_channel_up,
            "consolidation": tech.pattern_consolidation_score,
        }
    pattern = scorer._detect_pattern_from_technicals(pattern_scores)

    sma_bullish: bool | None = None
    if sma_50 is not None and sma_200 is not None:
        sma_bullish = sma_50 > sma_200

    drivers = scorer._generate_drivers(
        rsi_14=rsi_14, adx_14=adx_14, bb_pctb=bb_pctb,
        vol_ratio=vol_ratio, sma_bullish=sma_bullish, pattern=pattern,
        composite_score=_f(sig.composite_score),
        breakout_probability=_f(sig.breakout_probability),
    )

    return SignalDetailResponse(
        symbol=stock.symbol, name=stock.name,
        composite_score=_f(sig.composite_score) or 0,
        breakout_probability=_f(sig.breakout_probability) or 0,
        date=sig.date.isoformat(), price=close,
        volume_ratio=vol_ratio, sma_bullish=sma_bullish,
        rsi_14=rsi_14, adx_14=adx_14, bb_pctb=bb_pctb,
        pattern=pattern, sector=stock.sector, drivers=drivers,
        component_scores=component_scores, top_features=top_features,
    )
