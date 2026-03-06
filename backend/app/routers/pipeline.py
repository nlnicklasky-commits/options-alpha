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


async def _run_train(job_id: str, label_type: str) -> None:
    """Run model retraining in background."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from scripts.retrain_model import main as retrain_main

    _jobs[job_id]["status"] = "running"
    try:
        await retrain_main(label_type=label_type)
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
    background_tasks.add_task(_run_train, job_id, request.label_type)
    return JobStatus(
        job_id=job_id,
        status="starting",
        started_at=_jobs[job_id]["started_at"],
    )


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
