from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import backtest, journal, options_chain, pipeline, scan, score, signals


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    # Startup
    yield
    # Shutdown


app = FastAPI(title="Options Alpha", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/api/scan", tags=["scan"])
app.include_router(score.router, prefix="/api/score", tags=["score"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(options_chain.router, prefix="/api/options", tags=["options"])


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
