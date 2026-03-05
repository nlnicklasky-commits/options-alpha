"""Backtest router — run backtests and retrieve results."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.signals import BacktestRun, BacktestTrade
from app.models.stocks import Stock
from app.schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    BacktestStats,
    BacktestTradeResponse,
    EquityCurvePoint,
)
from app.services.backtester import Backtester

router = APIRouter()


@router.post("", response_model=dict)
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run a backtest with given parameters. Returns backtest_id."""
    bt = Backtester(db)
    try:
        backtest_id = await bt.run_backtest(
            model_path=request.model_path,
            start_date=request.start_date,
            end_date=request.end_date,
            entry_threshold=request.entry_threshold,
            target_pct=request.target_pct,
            stop_pct=request.stop_pct,
            max_days=request.max_days,
            name=request.name,
        )
        return {"backtest_id": backtest_id}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    """Get backtest results, stats, and equity curve."""
    stmt = select(BacktestRun).where(BacktestRun.id == backtest_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    bt = Backtester(db)
    stats = await bt.compute_stats(backtest_id)
    curve = await bt.equity_curve(backtest_id)

    return BacktestResponse(
        id=run.id,
        name=run.name,
        start_date=run.start_date.isoformat(),
        end_date=run.end_date.isoformat(),
        model_version=run.model_version,
        stats=BacktestStats(**stats),
        equity_curve=[EquityCurvePoint(**p) for p in curve],
        results_by_regime=run.results_by_regime or {},
        results_by_score_bucket=run.results_by_score_bucket or {},
        results_by_pattern=run.results_by_pattern or {},
    )


@router.get("/{backtest_id}/trades", response_model=list[BacktestTradeResponse])
async def get_backtest_trades(
    backtest_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[BacktestTradeResponse]:
    """Get paginated trade list from a backtest."""
    run_stmt = select(BacktestRun).where(BacktestRun.id == backtest_id)
    run_result = await db.execute(run_stmt)
    if not run_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Backtest not found")

    offset = (page - 1) * per_page
    stmt = (
        select(BacktestTrade, Stock.symbol)
        .outerjoin(Stock, BacktestTrade.stock_id == Stock.id)
        .where(BacktestTrade.run_id == backtest_id)
        .order_by(BacktestTrade.entry_date)
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        BacktestTradeResponse(
            id=trade.id,
            stock_id=trade.stock_id,
            symbol=symbol,
            entry_date=trade.entry_date.isoformat(),
            exit_date=trade.exit_date.isoformat() if trade.exit_date else None,
            entry_price=float(trade.entry_price) if trade.entry_price else 0.0,
            exit_price=float(trade.exit_price) if trade.exit_price else None,
            return_pct=float(trade.return_pct) if trade.return_pct else None,
            signal_score=float(trade.signal_score) if trade.signal_score else None,
            pattern_type=trade.pattern_type,
            regime=trade.regime,
        )
        for trade, symbol in rows
    ]
