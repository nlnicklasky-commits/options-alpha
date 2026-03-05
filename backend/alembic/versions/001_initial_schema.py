"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- stocks ---
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column("market_cap", sa.Numeric(16, 0), nullable=True),
        sa.Column("avg_volume_30d", sa.Numeric(16, 0), nullable=True),
        sa.Column("index_membership", sa.ARRAY(sa.String(20)), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seeded_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], unique=True)

    # --- daily_bars ---
    op.create_table(
        "daily_bars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("vwap", sa.Numeric(12, 4), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.UniqueConstraint("stock_id", "date", name="uq_daily_bars_stock_date"),
    )
    op.create_index(
        "ix_daily_bars_stock_date_desc",
        "daily_bars",
        ["stock_id", sa.text("date DESC")],
    )

    # --- technical_snapshots ---
    ts_cols = [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
    ]
    # Moving Averages (NUMERIC 12,4)
    for name in [
        "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
        "ema_9", "ema_12", "ema_21", "ema_26", "ema_50",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(12, 4), nullable=True))
    # MA Derived (NUMERIC 8,4)
    for name in [
        "price_vs_sma50_pct", "price_vs_sma200_pct", "sma50_vs_sma200_pct",
        "sma20_vs_sma50_pct", "sma50_slope_10d", "sma200_slope_10d",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    # Momentum (NUMERIC 8,4)
    for name in [
        "rsi_14", "rsi_9", "stoch_k", "stoch_d", "stoch_rsi",
        "williams_r", "cci_20", "mfi_14",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    # Trend (NUMERIC 8,4)
    for name in [
        "macd_line", "macd_signal", "macd_histogram", "macd_histogram_slope",
        "adx_14", "plus_di", "minus_di",
        "aroon_up", "aroon_down", "aroon_oscillator",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    # Volatility
    for name in ["atr_14"]:
        ts_cols.append(sa.Column(name, sa.Numeric(12, 4), nullable=True))
    ts_cols.append(sa.Column("atr_pct", sa.Numeric(8, 4), nullable=True))
    for name in ["bb_upper", "bb_middle", "bb_lower"]:
        ts_cols.append(sa.Column(name, sa.Numeric(12, 4), nullable=True))
    for name in ["bb_width", "bb_pctb"]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    for name in ["keltner_upper", "keltner_lower"]:
        ts_cols.append(sa.Column(name, sa.Numeric(12, 4), nullable=True))
    ts_cols.append(sa.Column("bb_squeeze", sa.Boolean(), nullable=True))
    for name in ["historical_vol_20", "historical_vol_60"]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    # Volume
    ts_cols.append(sa.Column("volume_sma_20", sa.BigInteger(), nullable=True))
    ts_cols.append(sa.Column("volume_ratio", sa.Numeric(8, 4), nullable=True))
    ts_cols.append(sa.Column("obv", sa.BigInteger(), nullable=True))
    for name in ["obv_slope_10d"]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    ts_cols.append(sa.Column("ad_line", sa.Numeric(16, 4), nullable=True))
    for name in ["cmf_20", "vwap_distance_pct"]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    # Price Action
    for name in [
        "daily_return", "gap_pct", "range_pct", "body_pct",
        "upper_shadow_pct", "lower_shadow_pct", "close_position",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    for name in [
        "higher_highs_5d", "higher_lows_5d",
        "consecutive_up_days", "consecutive_down_days",
    ]:
        ts_cols.append(sa.Column(name, sa.SmallInteger(), nullable=True))
    # Patterns (NUMERIC 5,2)
    for name in [
        "pattern_wedge_falling", "pattern_wedge_rising",
        "pattern_triangle_ascending", "pattern_triangle_descending",
        "pattern_triangle_symmetric",
        "pattern_flag_bull", "pattern_flag_bear", "pattern_pennant",
        "pattern_cup_handle", "pattern_double_bottom",
        "pattern_head_shoulders_inv", "pattern_channel_up",
        "pattern_consolidation_score",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(5, 2), nullable=True))
    # Relative Strength (NUMERIC 8,4)
    for name in ["rs_vs_spy_20d", "rs_vs_sector_20d", "rs_rank_percentile"]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    # Support / Resistance (NUMERIC 8,4)
    for name in [
        "distance_to_resistance_pct", "distance_to_support_pct",
        "near_52w_high_pct", "near_52w_low_pct",
    ]:
        ts_cols.append(sa.Column(name, sa.Numeric(8, 4), nullable=True))
    ts_cols.append(
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        )
    )
    ts_cols.extend([
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.UniqueConstraint("stock_id", "date", name="uq_technical_snapshots_stock_date"),
    ])
    op.create_table("technical_snapshots", *ts_cols)
    op.create_index(
        "ix_technical_snapshots_stock_date_desc",
        "technical_snapshots",
        ["stock_id", sa.text("date DESC")],
    )

    # --- options_snapshots ---
    op.create_table(
        "options_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("iv_rank", sa.Numeric(8, 4), nullable=True),
        sa.Column("iv_percentile", sa.Numeric(8, 4), nullable=True),
        sa.Column("iv_30d", sa.Numeric(8, 4), nullable=True),
        sa.Column("iv_60d", sa.Numeric(8, 4), nullable=True),
        sa.Column("iv_skew", sa.Numeric(8, 4), nullable=True),
        sa.Column("iv_term_structure", sa.Numeric(8, 4), nullable=True),
        sa.Column("put_call_volume_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("put_call_oi_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("total_call_volume", sa.BigInteger(), nullable=True),
        sa.Column("total_put_volume", sa.BigInteger(), nullable=True),
        sa.Column("total_call_oi", sa.BigInteger(), nullable=True),
        sa.Column("total_put_oi", sa.BigInteger(), nullable=True),
        sa.Column("atm_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("atm_gamma", sa.Numeric(8, 4), nullable=True),
        sa.Column("atm_theta", sa.Numeric(8, 4), nullable=True),
        sa.Column("atm_vega", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.UniqueConstraint("stock_id", "date", name="uq_options_snapshots_stock_date"),
    )
    op.create_index(
        "ix_options_snapshots_stock_date_desc",
        "options_snapshots",
        ["stock_id", sa.text("date DESC")],
    )

    # --- options_flow ---
    op.create_table(
        "options_flow",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("contract_type", sa.String(4), nullable=False),
        sa.Column("strike", sa.Numeric(12, 4), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("open_interest", sa.BigInteger(), nullable=False),
        sa.Column("premium", sa.Numeric(12, 4), nullable=True),
        sa.Column("iv", sa.Numeric(8, 4), nullable=True),
        sa.Column("delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("is_unusual", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
    )
    op.create_index(
        "ix_options_flow_stock_date",
        "options_flow",
        ["stock_id", "date"],
    )

    # --- market_regimes ---
    op.create_table(
        "market_regimes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("vix_close", sa.Numeric(8, 4), nullable=True),
        sa.Column("vix_sma_20", sa.Numeric(8, 4), nullable=True),
        sa.Column("vix_percentile", sa.Numeric(8, 4), nullable=True),
        sa.Column("advance_decline_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("pct_above_sma200", sa.Numeric(8, 4), nullable=True),
        sa.Column("pct_above_sma50", sa.Numeric(8, 4), nullable=True),
        sa.Column("new_highs", sa.Integer(), nullable=True),
        sa.Column("new_lows", sa.Integer(), nullable=True),
        sa.Column("mcclellan_oscillator", sa.Numeric(8, 4), nullable=True),
        sa.Column("leading_sector", sa.String(100), nullable=True),
        sa.Column("lagging_sector", sa.String(100), nullable=True),
        sa.Column("sector_dispersion", sa.Numeric(8, 4), nullable=True),
        sa.Column("us_10y_yield", sa.Numeric(8, 4), nullable=True),
        sa.Column("us_2y_yield", sa.Numeric(8, 4), nullable=True),
        sa.Column("yield_curve_spread", sa.Numeric(8, 4), nullable=True),
        sa.Column("fed_funds_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("regime_label", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_market_regimes_date"),
    )
    op.create_index("ix_market_regimes_date", "market_regimes", ["date"])

    # --- signals ---
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("breakout_probability", sa.Numeric(8, 4), nullable=True),
        sa.Column("technical_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("options_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("pattern_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("composite_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("suggested_strike", sa.Numeric(12, 4), nullable=True),
        sa.Column("suggested_expiry", sa.Date(), nullable=True),
        sa.Column("suggested_entry_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("risk_reward_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.UniqueConstraint("stock_id", "date", name="uq_signals_stock_date"),
    )
    op.create_index(
        "ix_signals_stock_date_desc",
        "signals",
        ["stock_id", sa.text("date DESC")],
    )

    # --- backtest_runs ---
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("avg_return", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(8, 4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("profit_factor", sa.Numeric(8, 4), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- backtest_trades ---
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=True),
        sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("return_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("signal_score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.id"]),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
    )

    # --- trade_journal ---
    op.create_table(
        "trade_journal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False, server_default="LONG"),
        sa.Column("contract_type", sa.String(4), nullable=True),
        sa.Column("strike", sa.Numeric(12, 4), nullable=True),
        sa.Column("expiration", sa.Date(), nullable=True),
        sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pnl", sa.Numeric(12, 4), nullable=True),
        sa.Column("return_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("setup_type", sa.String(100), nullable=True),
        sa.Column("signal_score_at_entry", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String(50)), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
    )


def downgrade() -> None:
    op.drop_table("trade_journal")
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
    op.drop_table("signals")
    op.drop_table("market_regimes")
    op.drop_table("options_flow")
    op.drop_table("options_snapshots")
    op.drop_table("technical_snapshots")
    op.drop_table("daily_bars")
    op.drop_table("stocks")
