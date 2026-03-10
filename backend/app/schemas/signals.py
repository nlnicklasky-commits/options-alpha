"""Pydantic schemas for signals and scoring endpoints."""

from pydantic import BaseModel


class DriverInfo(BaseModel):
    """Structured signal driver with human-readable explanation."""
    label: str
    description: str
    signal: str
    category: str = "other"


class SignalResponse(BaseModel):
    symbol: str
    name: str | None = None
    composite_score: float
    breakout_probability: float
    date: str | None = None
    price: float | None = None
    volume_ratio: float | None = None
    sma_bullish: bool | None = None
    rsi_14: float | None = None
    pattern: str | None = None
    sector: str | None = None
    drivers: list[DriverInfo] = []


class SignalDetailResponse(BaseModel):
    symbol: str
    name: str | None = None
    composite_score: float
    breakout_probability: float
    date: str | None = None
    price: float | None = None
    volume_ratio: float | None = None
    sma_bullish: bool | None = None
    rsi_14: float | None = None
    adx_14: float | None = None
    bb_pctb: float | None = None
    pattern: str | None = None
    sector: str | None = None
    drivers: list[DriverInfo] = []
    # Sub-scores (computed on-the-fly via score_single if available)
    component_scores: dict[str, float] = {}
    top_features: list[dict] = []


class ComponentScores(BaseModel):
    xgboost: float | None = None
    lightgbm: float | None = None
    random_forest: float | None = None


class FeatureDriver(BaseModel):
    feature: str
    importance: float
    value: float | None = None


class ScoreResponse(BaseModel):
    symbol: str
    date: str
    composite_score: float
    breakout_probability: float
    component_scores: dict[str, float] = {}
    top_features: list[FeatureDriver] = []
