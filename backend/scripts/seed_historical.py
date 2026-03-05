"""Seed historical stock and options data from external providers.

Usage:
    python scripts/seed_historical.py [--resume] [--symbols AAPL,MSFT,NVDA]

Pulls OHLCV data from Polygon.io, computes technicals, and stores in the database.
Supports checkpoint/resume via Stock.last_seeded_date.
"""
import argparse
import asyncio
import logging
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

# Add backend dir to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.stocks import Stock
from app.models.technicals import TechnicalSnapshot
from app.services.data_ingestion import (
    DataIngestionOrchestrator,
    update_last_seeded_date,
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
logger = logging.getLogger("seed")

# Lookback for historical bars
YEARS_BACK = 3
OPTIONS_DAYS_BACK = 365  # Theta Data free tier: 1yr


async def seed_stock(
    orchestrator: DataIngestionOrchestrator,
    tech_calc: TechnicalCalculator,
    pattern_det: PatternDetector,
    stock: Stock,
    start_date: date,
    end_date: date,
    spy_df: pd.DataFrame | None,
) -> bool:
    """Seed a single stock: bars → technicals → patterns. Returns True on success."""
    symbol = stock.symbol
    try:
        # 1. Fetch daily bars
        bars = await orchestrator.fetch_daily_bars(symbol, start_date, end_date)
        if not bars:
            logger.warning("No bars for %s", symbol)
            return False

        async with async_session() as session:
            count = await upsert_daily_bars(session, stock.id, bars)
            logger.debug("%s: upserted %d bars", symbol, count)

        # 2. Compute technicals
        bars_df = pd.DataFrame(bars)
        if len(bars_df) < 50:
            logger.warning("%s: only %d bars, skipping technicals", symbol, len(bars_df))
            async with async_session() as session:
                await update_last_seeded_date(session, stock.id, end_date)
            return True

        # Convert Decimal columns to float for ta library
        for col in ("open", "high", "low", "close"):
            bars_df[col] = bars_df[col].astype(float)
        bars_df["volume"] = bars_df["volume"].astype(float)

        features_df = tech_calc.compute_historical(bars_df, spy_df)

        # 3. Compute patterns for latest bar
        patterns = pattern_det.detect_all(bars_df)

        # 4. Store technical snapshots (batched upsert, 500 rows at a time)
        BATCH_SIZE = 500
        all_rows: list[dict] = []
        last_date = features_df["date"].iloc[-1]

        for _, row in features_df.iterrows():
            snapshot_data: dict[str, Any] = {"stock_id": stock.id, "date": row["date"]}
            for col in features_df.columns:
                if col == "date":
                    continue
                val = row[col]
                if pd.isna(val):
                    snapshot_data[col] = None
                elif isinstance(val, bool):
                    snapshot_data[col] = val
                elif col in ("volume_sma_20", "obv"):
                    snapshot_data[col] = int(val)
                elif col in (
                    "higher_highs_5d", "higher_lows_5d",
                    "consecutive_up_days", "consecutive_down_days",
                ):
                    snapshot_data[col] = int(val)
                else:
                    snapshot_data[col] = Decimal(str(round(float(val), 4)))

            # Add pattern scores to the latest snapshot only
            if row["date"] == last_date:
                snapshot_data.update(patterns)

            all_rows.append(snapshot_data)

        async with async_session() as session:
            for i in range(0, len(all_rows), BATCH_SIZE):
                batch = all_rows[i : i + BATCH_SIZE]
                stmt = pg_insert(TechnicalSnapshot).values(batch)
                update_cols = {
                    col: stmt.excluded[col]
                    for col in batch[0]
                    if col not in ("stock_id", "date")
                }
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_technical_snapshots_stock_date",
                    set_=update_cols,
                )
                await session.execute(stmt)
            await session.commit()

        # 5. Fetch and store options data (last 365 days)
        try:
            opts_start = end_date - timedelta(days=OPTIONS_DAYS_BACK)
            eod_records = await orchestrator.fetch_options_eod(symbol, opts_start, end_date)
            if eod_records:
                snapshot = orchestrator.theta.aggregate_options_snapshot(
                    eod_records, end_date
                )
                if snapshot:
                    async with async_session() as session:
                        await upsert_options_snapshot(session, stock.id, snapshot)
                logger.debug("%s: stored options snapshot from %d EOD records", symbol, len(eod_records))
        except Exception:
            logger.warning("Options data failed for %s, continuing", symbol, exc_info=True)

        # 6. Update checkpoint
        async with async_session() as session:
            await update_last_seeded_date(session, stock.id, end_date)

        return True
    except Exception:
        logger.exception("Failed to seed %s", symbol)
        return False


async def main(resume: bool = False, symbols: list[str] | None = None) -> None:
    end_date = date.today()
    start_date = end_date - timedelta(days=YEARS_BACK * 365)

    orchestrator = DataIngestionOrchestrator()

    try:
        # Step 1: Build stock universe (or filter to specific symbols)
        if symbols:
            logger.info("Seeding specific symbols: %s", symbols)
            async with async_session() as session:
                result = await session.execute(select(Stock).where(Stock.symbol.in_(symbols)))
                stocks = list(result.scalars().all())
                if not stocks:
                    # Insert them first
                    for sym in symbols:
                        from app.services.data_ingestion import upsert_stock
                        await upsert_stock(session, {
                            "symbol": sym, "name": sym, "is_active": True,
                            "index_membership": [],
                        })
                    result = await session.execute(select(Stock).where(Stock.symbol.in_(symbols)))
                    stocks = list(result.scalars().all())
        else:
            logger.info("Building stock universe (S&P 500 + Russell 2000)...")
            async with async_session() as session:
                await orchestrator.build_stock_universe(session)
                result = await session.execute(
                    select(Stock).where(Stock.is_active == True).order_by(Stock.symbol)  # noqa: E712
                )
                stocks = list(result.scalars().all())

        logger.info("Total stocks to seed: %d", len(stocks))

        # Filter out already-seeded stocks if resuming
        if resume:
            stocks = [s for s in stocks if s.last_seeded_date is None or s.last_seeded_date < end_date]
            logger.info("After resume filter: %d stocks remaining", len(stocks))

        # Step 2: Fetch SPY data for relative strength calculations
        logger.info("Fetching SPY data for relative strength...")
        spy_bars = await orchestrator.fetch_daily_bars("SPY", start_date, end_date)
        spy_df: pd.DataFrame | None = None
        if spy_bars:
            spy_df = pd.DataFrame(spy_bars)
            for col in ("open", "high", "low", "close"):
                spy_df[col] = spy_df[col].astype(float)

        # Step 3: Seed each stock
        tech_calc = TechnicalCalculator()
        pattern_det = PatternDetector()

        completed = 0
        failed = 0
        t0 = time.time()

        for i, stock in enumerate(stocks):
            success = await seed_stock(
                orchestrator, tech_calc, pattern_det, stock, start_date, end_date, spy_df
            )
            if success:
                completed += 1
            else:
                failed += 1

            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(stocks) - i - 1) / rate if rate > 0 else 0
            logger.info(
                "[%d/%d] %s %s | %.1f stocks/min | ETA: %.0f min",
                i + 1, len(stocks), stock.symbol,
                "OK" if success else "FAIL",
                rate * 60, remaining / 60,
            )

        # Step 4: Fetch macro data from FRED
        logger.info("Fetching macro data from FRED...")
        macro_records = await orchestrator.fetch_macro_data(start_date)
        async with async_session() as session:
            for record in macro_records:
                await upsert_market_regime(session, record)
        logger.info("Stored %d macro data points", len(macro_records))

        logger.info(
            "Seed complete: %d succeeded, %d failed, %.1f minutes total",
            completed, failed, (time.time() - t0) / 60,
        )

    finally:
        await orchestrator.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed historical data")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols (e.g. AAPL,MSFT)")
    args = parser.parse_args()

    symbol_list = args.symbols.split(",") if args.symbols else None
    asyncio.run(main(resume=args.resume, symbols=symbol_list))
