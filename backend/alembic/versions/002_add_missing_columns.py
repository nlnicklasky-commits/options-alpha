"""add missing columns to options_snapshots, signals, market_regimes, backtest_runs, backtest_trades

Revision ID: 002
Revises: 001
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- options_snapshots: IV detail, OI/volume, front-month ATM call ---
    op.add_column("options_snapshots", sa.Column("iv_vs_hv_ratio", sa.Numeric(8, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("iv_call_atm", sa.Numeric(8, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("iv_put_atm", sa.Numeric(8, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("call_oi_change", sa.Integer(), nullable=True))
    op.add_column("options_snapshots", sa.Column("put_oi_change", sa.Integer(), nullable=True))
    op.add_column("options_snapshots", sa.Column("call_volume_vs_avg", sa.Numeric(8, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("max_single_call_volume", sa.Integer(), nullable=True))
    op.add_column("options_snapshots", sa.Column("front_atm_call_bid", sa.Numeric(12, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("front_atm_call_ask", sa.Numeric(12, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("front_atm_call_spread_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("options_snapshots", sa.Column("front_atm_call_volume", sa.Integer(), nullable=True))
    op.add_column("options_snapshots", sa.Column("front_atm_call_oi", sa.Integer(), nullable=True))

    # --- signals: additional scores, confidence, dte, feature importance ---
    op.add_column("signals", sa.Column("momentum_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("signals", sa.Column("volume_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("signals", sa.Column("regime_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("signals", sa.Column("expected_move_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("signals", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("signals", sa.Column("suggested_dte", sa.Integer(), nullable=True))
    op.add_column("signals", sa.Column("feature_importance_json", JSONB(), nullable=True))

    # --- market_regimes: VVIX, breadth derived, index returns, sector rotation signals ---
    op.add_column("market_regimes", sa.Column("vvix", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_regimes", sa.Column("high_low_ratio", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_regimes", sa.Column("spy_daily_return", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_regimes", sa.Column("qqq_daily_return", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_regimes", sa.Column("iwm_daily_return", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_regimes", sa.Column("xlk_vs_spy", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_regimes", sa.Column("xly_vs_xlp", sa.Numeric(8, 4), nullable=True))

    # --- backtest_runs: additional metrics, result breakdowns ---
    op.add_column("backtest_runs", sa.Column("sortino_ratio", sa.Numeric(8, 4), nullable=True))
    op.add_column("backtest_runs", sa.Column("avg_days_held", sa.Numeric(8, 2), nullable=True))
    op.add_column("backtest_runs", sa.Column("expectancy", sa.Numeric(8, 4), nullable=True))
    op.add_column("backtest_runs", sa.Column("results_by_regime", JSONB(), nullable=True))
    op.add_column("backtest_runs", sa.Column("results_by_score_bucket", JSONB(), nullable=True))
    op.add_column("backtest_runs", sa.Column("results_by_pattern", JSONB(), nullable=True))

    # --- backtest_trades: pattern + regime context ---
    op.add_column("backtest_trades", sa.Column("pattern_type", sa.String(50), nullable=True))
    op.add_column("backtest_trades", sa.Column("regime", sa.String(20), nullable=True))


def downgrade() -> None:
    # backtest_trades
    op.drop_column("backtest_trades", "regime")
    op.drop_column("backtest_trades", "pattern_type")

    # backtest_runs
    op.drop_column("backtest_runs", "results_by_pattern")
    op.drop_column("backtest_runs", "results_by_score_bucket")
    op.drop_column("backtest_runs", "results_by_regime")
    op.drop_column("backtest_runs", "expectancy")
    op.drop_column("backtest_runs", "avg_days_held")
    op.drop_column("backtest_runs", "sortino_ratio")

    # market_regimes
    op.drop_column("market_regimes", "xly_vs_xlp")
    op.drop_column("market_regimes", "xlk_vs_spy")
    op.drop_column("market_regimes", "iwm_daily_return")
    op.drop_column("market_regimes", "qqq_daily_return")
    op.drop_column("market_regimes", "spy_daily_return")
    op.drop_column("market_regimes", "high_low_ratio")
    op.drop_column("market_regimes", "vvix")

    # signals
    op.drop_column("signals", "feature_importance_json")
    op.drop_column("signals", "suggested_dte")
    op.drop_column("signals", "confidence")
    op.drop_column("signals", "expected_move_pct")
    op.drop_column("signals", "regime_score")
    op.drop_column("signals", "volume_score")
    op.drop_column("signals", "momentum_score")

    # options_snapshots
    op.drop_column("options_snapshots", "front_atm_call_oi")
    op.drop_column("options_snapshots", "front_atm_call_volume")
    op.drop_column("options_snapshots", "front_atm_call_spread_pct")
    op.drop_column("options_snapshots", "front_atm_call_ask")
    op.drop_column("options_snapshots", "front_atm_call_bid")
    op.drop_column("options_snapshots", "max_single_call_volume")
    op.drop_column("options_snapshots", "call_volume_vs_avg")
    op.drop_column("options_snapshots", "put_oi_change")
    op.drop_column("options_snapshots", "call_oi_change")
    op.drop_column("options_snapshots", "iv_put_atm")
    op.drop_column("options_snapshots", "iv_call_atm")
    op.drop_column("options_snapshots", "iv_vs_hv_ratio")
