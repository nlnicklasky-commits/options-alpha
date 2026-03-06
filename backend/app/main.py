import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, time as dt_time, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import async_session
from app.routers import backtest, journal, options_chain, pipeline, score, signals

logger = logging.getLogger("scheduler")

# US Eastern timezone offset (UTC-5, or UTC-4 during DST)
ET_OFFSET = timezone(timedelta(hours=-5))

# Schedule: daily pipeline at 6:30 PM ET (after market close + data settle)
DAILY_RUN_HOUR = 18
DAILY_RUN_MINUTE = 30

# Weekly retrain on Saturdays at 2 AM ET
RETRAIN_DAY = 5  # Saturday
RETRAIN_HOUR = 2


async def _scheduler_loop() -> None:
    """Simple background scheduler — runs daily pipeline and weekly retraining."""
    logger.info("Scheduler started: daily at %d:%02d ET, retrain on Sat %d:00 ET",
                DAILY_RUN_HOUR, DAILY_RUN_MINUTE, RETRAIN_HOUR)
    last_daily_date = None
    last_retrain_date = None

    while True:
        try:
            now_et = datetime.now(ET_OFFSET)
            today = now_et.date()

            # Daily pipeline: after 6:30 PM ET on weekdays, once per day
            if (now_et.weekday() < 5
                    and now_et.hour >= DAILY_RUN_HOUR
                    and now_et.minute >= DAILY_RUN_MINUTE
                    and last_daily_date != today):
                logger.info("Scheduler: triggering daily pipeline for %s", today)
                last_daily_date = today
                try:
                    from scripts.daily_update import main as daily_main
                    await daily_main()
                    # Score after data refresh
                    from app.services.model_scorer import ModelScorer
                    async with async_session() as session:
                        scorer = ModelScorer(session)
                        loaded = scorer.load_model()
                        if not loaded:
                            loaded = await scorer._try_load_from_db()
                        if loaded:
                            results = await scorer.score_universe(min_score=0.0)
                            logger.info("Scheduler: scored %d stocks", len(results))
                    logger.info("Scheduler: daily pipeline complete")
                except Exception:
                    logger.exception("Scheduler: daily pipeline failed")

            # Weekly retrain: Saturday at 2 AM ET
            if (now_et.weekday() == RETRAIN_DAY
                    and now_et.hour >= RETRAIN_HOUR
                    and last_retrain_date != today):
                logger.info("Scheduler: triggering weekly retrain for %s", today)
                last_retrain_date = today
                try:
                    from scripts.retrain_model import main as retrain_main
                    await retrain_main(label_type="breakout")
                    logger.info("Scheduler: retrain complete")
                except Exception:
                    logger.exception("Scheduler: retrain failed")

        except Exception:
            logger.exception("Scheduler loop error")

        # Check every 5 minutes
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    # Startup: launch background scheduler
    scheduler_task = asyncio.create_task(_scheduler_loop())
    yield
    # Shutdown: cancel scheduler
    scheduler_task.cancel()


app = FastAPI(title="Options Alpha", version="0.1.0", lifespan=lifespan)

# CORS: allow Vercel production domain + localhost for dev
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
vercel_url = os.environ.get("VERCEL_FRONTEND_URL")
if vercel_url:
    allowed_origins.append(vercel_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(score.router, prefix="/api/score", tags=["score"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(options_chain.router, prefix="/api/options", tags=["options"])


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Basic health check — verifies DB connection."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/health/data")
async def health_data() -> dict:
    """Check data freshness — warns if latest stock data is >1 trading day old."""
    try:
        async with async_session() as session:
            result = await session.execute(
                text("SELECT MAX(date) FROM daily_bars")
            )
            latest_date = result.scalar()

        if latest_date is None:
            return {"status": "warn", "message": "No stock data found"}

        today = datetime.now(timezone.utc).date()
        # Count business days between latest_date and today
        bdays = 0
        d = latest_date
        while d < today:
            d += timedelta(days=1)
            if d.weekday() < 5:  # Mon-Fri
                bdays += 1
        age = today - latest_date
        stale = bdays > 2
        return {
            "status": "warn" if stale else "ok",
            "latest_data_date": str(latest_date),
            "age_days": age.days,
            "message": "Data is stale" if stale else "Data is fresh",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
