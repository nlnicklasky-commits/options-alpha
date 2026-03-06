import asyncio
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory job status tracker
_jobs: dict[str, dict[str, Any]] = {}


class SeedRequest(BaseModel):
    symbols: list[str] | None = None
    resume: bool = True


class TrainRequest(BaseModel):
    label_type: str = "breakout"
    start_date: str | None = None
    end_date: str | None = None


class JobStatus(BaseModel):
    job_id: str
    status: str  # "running", "completed", "failed"
    started_at: str
    completed_at: str | None = None
    message: str | None = None


async def _run_seed(job_id: str, symbols: list[str] | None, resume: bool) -> None:
    """Run seed_historical in background."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from scripts.seed_historical import main as seed_main

    _jobs[job_id]["status"] = "running"
    try:
        await seed_main(resume=resume, symbols=symbols)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["message"] = "Seed completed successfully"
    except Exception as exc:
        logger.exception("Seed job %s failed", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["message"] = str(exc)
    finally:
        _jobs[job_id]["completed_at"] = datetime.now().isoformat()


async def _run_daily(job_id: str) -> None:
    """Run daily_update in background."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from scripts.daily_update import main as daily_main

    _jobs[job_id]["status"] = "running"
    try:
        await daily_main()
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["message"] = "Daily update completed successfully"
    except Exception as exc:
        logger.exception("Daily job %s failed", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["message"] = str(exc)
    finally:
        _jobs[job_id]["completed_at"] = datetime.now().isoformat()


async def _run_train(job_id: str, label_type: str, start_date: str | None = None, end_date: str | None = None) -> None:
    """Run model retraining in background."""
    import sys
    from datetime import date as date_cls
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from scripts.retrain_model import main as retrain_main

    _jobs[job_id]["status"] = "running"
    try:
        sd = date_cls.fromisoformat(start_date) if start_date else None
        ed = date_cls.fromisoformat(end_date) if end_date else None
        await retrain_main(start_date=sd, end_date=ed, label_type=label_type)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["message"] = "Model training completed successfully"
    except Exception as exc:
        logger.exception("Train job %s failed", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["message"] = str(exc)
    finally:
        _jobs[job_id]["completed_at"] = datetime.now().isoformat()


@router.post("/seed", response_model=JobStatus)
async def trigger_seed(request: SeedRequest, background_tasks: BackgroundTasks) -> JobStatus:
    """Trigger historical data seeding as a background task."""
    job_id = f"seed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _jobs[job_id] = {
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "message": None,
    }
    background_tasks.add_task(_run_seed, job_id, request.symbols, request.resume)
    return JobStatus(
        job_id=job_id,
        status="starting",
        started_at=_jobs[job_id]["started_at"],
    )


@router.post("/daily", response_model=JobStatus)
async def trigger_daily(background_tasks: BackgroundTasks) -> JobStatus:
    """Trigger daily data update as a background task."""
    job_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _jobs[job_id] = {
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "message": None,
    }
    background_tasks.add_task(_run_daily, job_id)
    return JobStatus(
        job_id=job_id,
        status="starting",
        started_at=_jobs[job_id]["started_at"],
    )


@router.post("/train", response_model=JobStatus)
async def trigger_train(request: TrainRequest, background_tasks: BackgroundTasks) -> JobStatus:
    """Trigger model retraining as a background task."""
    job_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _jobs[job_id] = {
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "message": None,
    }
    background_tasks.add_task(_run_train, job_id, request.label_type, request.start_date, request.end_date)
    return JobStatus(
        job_id=job_id,
        status="starting",
        started_at=_jobs[job_id]["started_at"],
    )


@router.get("/debug/db-counts")
async def debug_db_counts() -> dict:
    """Temporary: check row counts in each table."""
    from sqlalchemy import text
    from app.database import async_session

    async with async_session() as session:
        tables = [
            "stocks", "daily_bars", "technical_snapshots",
            "options_snapshots", "options_flow", "market_regimes",
            "signals", "model_artifacts",
        ]
        counts = {}
        for t in tables:
            try:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                counts[t] = result.scalar()
            except Exception as e:
                counts[t] = f"error: {e}"

        # Also get a sample technical snapshot
        try:
            result = await session.execute(
                text("SELECT stock_id, date, sma_50, rsi_14 FROM technical_snapshots LIMIT 3")
            )
            rows = result.all()
            counts["sample_technicals"] = [
                {"stock_id": r[0], "date": str(r[1]), "sma_50": str(r[2]), "rsi_14": str(r[3])}
                for r in rows
            ]
        except Exception as e:
            counts["sample_technicals"] = f"error: {e}"

        return counts


@router.get("/debug/test-technicals")
async def debug_test_technicals() -> dict:
    """Temporary: test technical computation + upsert for one stock."""
    import traceback
    from datetime import date as date_cls, timedelta
    from decimal import Decimal

    import pandas as pd
    from sqlalchemy import select, text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.database import async_session
    from app.models.stocks import Stock
    from app.models.technicals import TechnicalSnapshot
    from app.services.data_ingestion import DataIngestionOrchestrator
    from app.services.technical_calc import TechnicalCalculator

    result: dict = {"steps": []}

    try:
        # 1. Get a stock
        async with async_session() as session:
            stmt = select(Stock).where(Stock.symbol == "AAPL")
            res = await session.execute(stmt)
            stock = res.scalar_one_or_none()
            if not stock:
                return {"error": "AAPL not found in stocks table"}
            result["stock_id"] = stock.id
            result["steps"].append("Got AAPL stock record")

        # 2. Get bars from DB
        async with async_session() as session:
            bars_res = await session.execute(
                text("SELECT date, open, high, low, close, volume FROM daily_bars WHERE stock_id = :sid ORDER BY date LIMIT 800"),
                {"sid": stock.id},
            )
            bars_rows = bars_res.all()
            result["bars_count"] = len(bars_rows)
            result["steps"].append(f"Got {len(bars_rows)} bars from DB")

        if not bars_rows:
            return {**result, "error": "No bars in DB for AAPL"}

        # 3. Build DataFrame
        bars_df = pd.DataFrame(bars_rows, columns=["date", "open", "high", "low", "close", "volume"])
        for col in ("open", "high", "low", "close"):
            bars_df[col] = bars_df[col].astype(float)
        bars_df["volume"] = bars_df["volume"].astype(float)
        result["steps"].append("Built bars DataFrame")

        # 4. Compute technicals
        tech_calc = TechnicalCalculator()
        features_df = tech_calc.compute_historical(bars_df)
        result["features_shape"] = list(features_df.shape)
        result["feature_columns"] = list(features_df.columns[:10])
        result["steps"].append(f"Computed technicals: {features_df.shape}")

        if features_df.empty:
            return {**result, "error": "compute_historical returned empty DataFrame"}

        # 5. Build one row for upsert
        row = features_df.iloc[-1]
        snapshot_data: dict = {"stock_id": stock.id, "date": row["date"]}
        for col in features_df.columns:
            if col == "date":
                continue
            val = row[col]
            if pd.isna(val):
                snapshot_data[col] = None
            elif isinstance(val, (bool,)):
                snapshot_data[col] = val
            elif col in ("volume_sma_20", "obv"):
                snapshot_data[col] = int(val)
            elif col in ("higher_highs_5d", "higher_lows_5d", "consecutive_up_days", "consecutive_down_days"):
                snapshot_data[col] = int(val)
            else:
                snapshot_data[col] = Decimal(str(round(float(val), 4)))

        result["snapshot_keys"] = list(snapshot_data.keys())[:15]
        result["snapshot_sample"] = {k: str(v) for k, v in list(snapshot_data.items())[:8]}
        result["steps"].append("Built snapshot dict")

        # 6. Try upsert
        async with async_session() as session:
            stmt = pg_insert(TechnicalSnapshot).values([snapshot_data])
            update_cols = {
                col: stmt.excluded[col]
                for col in snapshot_data
                if col not in ("stock_id", "date")
            }
            stmt = stmt.on_conflict_do_update(
                constraint="uq_technical_snapshots_stock_date",
                set_=update_cols,
            )
            await session.execute(stmt)
            await session.commit()
            result["steps"].append("Upsert succeeded!")

        # 7. Verify
        async with async_session() as session:
            count_res = await session.execute(text("SELECT COUNT(*) FROM technical_snapshots"))
            result["technicals_count_after"] = count_res.scalar()
            result["steps"].append("Verification complete")

    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()

    return result


@router.get("/status", response_model=list[JobStatus])
async def get_pipeline_status() -> list[JobStatus]:
    """Get status of all pipeline jobs."""
    return [
        JobStatus(
            job_id=job_id,
            status=info["status"],
            started_at=info["started_at"],
            completed_at=info.get("completed_at"),
            message=info.get("message"),
        )
        for job_id, info in sorted(_jobs.items(), key=lambda x: x[1]["started_at"], reverse=True)
    ]


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    """Get status of a specific pipeline job."""
    if job_id not in _jobs:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    info = _jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=info["status"],
        started_at=info["started_at"],
        completed_at=info.get("completed_at"),
        message=info.get("message"),
    )
