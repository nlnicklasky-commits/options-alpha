"""Daily data refresh pipeline.

Usage:
    python scripts/daily_update.py

Fetches latest daily bars, computes technicals, updates options snapshots,
refreshes market regime data, and generates new signals.
"""
import asyncio
import logging
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.daily_bars import DailyBar
from app.models.stocks import Stock
from app.models.technicals import TechnicalSnapshot
from app.services.data_ingestion import (
    DataIngestionOrchestrator,
    upsert_daily_bars,
    upsert_market_regime,
    upsert_options_snapshot,
)
from app.services.pattern_detect import PatternDetector
from app.services.technical_calc import TechnicalCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily")

# Need enough history for 200-day SMA
LOOKBACK_DAYS = 300


async def update_stock(
    orchestrator: DataIngestionOrchestrator,
    tech_calc: TechnicalCalculator,
    pattern_det: PatternDetector,
    stock: Stock,
    today: date,
    spy_df: pd.DataFrame | None,
) -> bool:
    """Update a single stock with today's data."""
    symbol = stock.symbol
    try:
        # Fetch recent bars (need lookback for indicator calculations)
        start = today - timedelta(days=LOOKBACK_DAYS)
        bars = await orchestrator.fetch_daily_bars(symbol, start, today)
        if not bars:
            return False

        # Upsert bars
        async with async_session() as session:
            await upsert_daily_bars(session, stock.id, bars)

        # Compute technicals for today
        bars_df = pd.DataFrame(bars)
        for col in ("open", "high", "low", "close"):
            bars_df[col] = bars_df[col].astype(float)
        bars_df["volume"] = bars_df["volume"].astype(float)

        latest_features = tech_calc.compute_all(bars_df, spy_df)
        patterns = pattern_det.detect_all(bars_df)
        latest_features.update(patterns)

        # Store today's technical snapshot
        snapshot_data = {"stock_id": stock.id, "date": today}
        for k, v in latest_features.items():
            snapshot_data[k] = v

        async with async_session() as session:
            stmt = pg_insert(TechnicalSnapshot).values(**snapshot_data)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_technical_snapshots_stock_date",
                set_={k: v for k, v in snapshot_data.items() if k not in ("stock_id", "date")},
            )
            await session.execute(stmt)
            await session.commit()

        # Fetch and store today's options data
        try:
            eod_records = await orchestrator.fetch_options_eod(
                symbol, today - timedelta(days=7), today
            )
            if eod_records:
                snapshot = orchestrator.theta.aggregate_options_snapshot(
                    eod_records, today
                )
                if snapshot:
                    async with async_session() as session:
                        await upsert_options_snapshot(session, stock.id, snapshot)
        except Exception:
            logger.warning("Options data failed for %s, continuing", symbol, exc_info=True)

        return True
    except Exception:
        logger.exception("Failed to update %s", symbol)
        return False


async def main() -> None:
    today = date.today()
    logger.info("Daily update for %s", today)

    orchestrator = DataIngestionOrchestrator()

    try:
        # Get all active stocks
        async with async_session() as session:
            result = await session.execute(
                select(Stock).where(Stock.is_active == True).order_by(Stock.symbol)  # noqa: E712
            )
            stocks = list(result.scalars().all())

        logger.info("Updating %d stocks", len(stocks))

        # Fetch SPY for relative strength
        start = today - timedelta(days=LOOKBACK_DAYS)
        spy_bars = await orchestrator.fetch_daily_bars("SPY", start, today)
        spy_df: pd.DataFrame | None = None
        if spy_bars:
            spy_df = pd.DataFrame(spy_bars)
            for col in ("open", "high", "low", "close"):
                spy_df[col] = spy_df[col].astype(float)

        tech_calc = TechnicalCalculator()
        pattern_det = PatternDetector()

        completed = 0
        failed = 0
        t0 = time.time()

        for i, stock in enumerate(stocks):
            success = await update_stock(
                orchestrator, tech_calc, pattern_det, stock, today, spy_df
            )
            if success:
                completed += 1
            else:
                failed += 1

            if (i + 1) % 100 == 0:
                logger.info("[%d/%d] completed", i + 1, len(stocks))

        # Update macro data
        logger.info("Fetching macro data...")
        macro_records = await orchestrator.fetch_macro_data(today - timedelta(days=7))
        async with async_session() as session:
            for record in macro_records:
                await upsert_market_regime(session, record)

        elapsed = time.time() - t0
        logger.info(
            "Daily update complete: %d OK, %d failed, %.1f min",
            completed, failed, elapsed / 60,
        )

    finally:
        await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(main())
