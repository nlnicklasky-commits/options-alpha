"""Pydantic schemas for backtest endpoints."""

from datetime import date

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    name: str = "backtest"
    start_date: date
    end_date: date
    model_path: str | None = None
    entry_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    target_pct: float = Field(default=1.0)
    stop_pct: float = Field(default=-0.5)
    max_days: int = Field(default=20, ge=1)


class BacktestStats(BaseModel):
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    sortino_ratio: float = 0.0
    expectancy: float = 0.0
    avg_days_held: float = 0.0
    total_trades: int = 0


class EquityCurvePoint(BaseModel):
    date: str
    cumulative_pnl: float


class BacktestResponse(BaseModel):
    id: int
    name: str
    start_date: str
    end_date: str
    model_version: str | None = None
    stats: BacktestStats
    equity_curve: list[EquityCurvePoint] = []
    results_by_regime: dict = {}
    results_by_score_bucket: dict = {}
    results_by_pattern: dict = {}


class BacktestTradeResponse(BaseModel):
    id: int
    stock_id: int
    symbol: str | None = None
    entry_date: str
    exit_date: str | None = None
    entry_price: float
    exit_price: float | None = None
    return_pct: float | None = None
    signal_score: float | None = None
    pattern_type: str | None = None
    regime: str | None = None
