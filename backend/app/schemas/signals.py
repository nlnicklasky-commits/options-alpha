"""Pydantic schemas for signals and scoring endpoints."""

from pydantic import BaseModel


class SignalResponse(BaseModel):
    symbol: str
    composite_score: float
    breakout_probability: float
    model_version: str | None = None
    date: str | None = None
    pattern: str | None = None
    iv_rank: float | None = None
    price: float | None = None
    volume_ratio: float | None = None
    sector: str | None = None
    sma_bullish: bool | None = None


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
