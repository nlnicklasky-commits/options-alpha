import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import async_session
from app.routers import backtest, journal, options_chain, pipeline, score, signals


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    # Startup
    yield
    # Shutdown


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
