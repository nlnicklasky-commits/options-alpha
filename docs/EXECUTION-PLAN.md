# Options Alpha — Claude Code Execution Plan

This document is a step-by-step build guide. Open Claude Code in the `options-alpha/` directory and feed it these phases one at a time. Each phase has the exact prompt to paste.

---

## Pre-Flight Checklist

Before starting, you need:
1. **Polygon.io API key** — Sign up at polygon.io (free tier is fine to start, 5 req/min)
2. **Theta Data account** — Sign up at thetadata.net (free tier: 1yr historical options EOD, 30 req/min)
3. **Railway account** — railway.app, create a PostgreSQL database ($5/mo hobby plan)
4. **Vercel account** — vercel.com, linked to your GitHub (free)
5. **FRED API key** — Free at fred.stlouisfed.org/docs/api/api_key.html
6. **Alpha Vantage API key** — Free at alphavantage.co/support/#api-key

All data sources start FREE. Upgrade only if/when needed:
- Polygon Stocks Developer ($79/mo) — if rate limits slow down historical seeding
- Theta Data Value/Standard ($25-50/mo) — when you need 4-8yr options history for backtesting

Once you have these, create a `.env` file from `.env.example` and fill in the values.

---

## Phase 1: Project Scaffold + Database

### Prompt for Claude Code:

```
I'm building Options Alpha — a personal trading intelligence platform. Read CLAUDE.md for full context.

PHASE 1: Scaffold the entire project and set up the database.

1. BACKEND (FastAPI):
   - Initialize with pyproject.toml using: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, httpx, pandas, numpy, ta, scikit-learn, xgboost, lightgbm, joblib, python-dotenv, yfinance, fredapi, thetadata
   - Create app/main.py with CORS middleware (allow all origins for now), lifespan handler
   - Create app/config.py using pydantic-settings BaseSettings loading from .env
   - Create app/database.py with async SQLAlchemy engine + sessionmaker
   - Create ALL ORM models in app/models/:
     * stocks.py: Stock table (symbol, name, sector, industry, market_cap, avg_volume_30d, index_membership VARCHAR[] e.g. ['sp500','russell2000'], is_active, last_seeded_date DATE nullable for checkpoint/resume)
     * daily_bars.py: DailyBar (stock_id FK, date, OHLCV, vwap, num_trades) — UNIQUE(stock_id, date)
     * technicals.py: TechnicalSnapshot with ALL 82 technical indicator columns from the schema below
     * options.py: OptionsSnapshot (IV metrics, flow, greeks), OptionsFlow (individual unusual trades)
     * market_regime.py: MarketRegime (VIX, breadth, sector rotation, rates)
     * signals.py: Signal (breakout_probability, scores, suggested trade), BacktestRun, BacktestTrade
     * journal.py: TradeJournal (entry/exit, P/L, notes, tags)
   - Set up Alembic with async support, create initial migration for ALL tables
   - Create empty router files in app/routers/ for: scan, score, backtest, signals, journal, pipeline, options_chain
   - Create empty service files in app/services/ for: data_ingestion, technical_calc, pattern_detect, options_analysis, feature_engine, model_scorer, backtester
   - Create empty ML pipeline in app/ml/: features.py, labels.py, train.py, evaluate.py
   - Create Dockerfile for Railway deployment
   - Create railway.toml

2. FRONTEND (Next.js 14):
   - Initialize with: npx create-next-app@latest frontend --typescript --tailwind --app --src-dir=false --import-alias="@/*"
   - Install: shadcn/ui (init + add button, card, table, input, select, badge, tabs, dialog, dropdown-menu, separator, skeleton), recharts, lucide-react
   - Create app/layout.tsx with a sidebar nav: Dashboard, Scanner, Backtest, Journal
   - Create placeholder pages: app/page.tsx (dashboard), app/scanner/page.tsx, app/backtest/page.tsx, app/journal/page.tsx, app/ticker/[symbol]/page.tsx
   - Create lib/api.ts with typed fetch wrapper pointing to NEXT_PUBLIC_API_URL
   - Create component stubs: ScoreCard, SignalTable, TechnicalChart, BacktestResults, TradeJournal

3. ROOT:
   - Create .gitignore (Python, Node, .env, __pycache__, node_modules, .next, *.joblib, data/)
   - Create README.md with setup instructions
   - Initialize git repo

TECHNICAL SNAPSHOT COLUMNS (put ALL of these in the TechnicalSnapshot model):
Moving Averages: sma_10, sma_20, sma_50, sma_100, sma_200, ema_9, ema_12, ema_21, ema_26, ema_50
MA Derived: price_vs_sma50_pct, price_vs_sma200_pct, sma50_vs_sma200_pct, sma20_vs_sma50_pct, sma50_slope_10d, sma200_slope_10d
Momentum: rsi_14, rsi_9, stoch_k, stoch_d, stoch_rsi, williams_r, cci_20, mfi_14
Trend: macd_line, macd_signal, macd_histogram, macd_histogram_slope, adx_14, plus_di, minus_di, aroon_up, aroon_down, aroon_oscillator
Volatility: atr_14, atr_pct, bb_upper, bb_middle, bb_lower, bb_width, bb_pctb, keltner_upper, keltner_lower, bb_squeeze (bool), historical_vol_20, historical_vol_60
Volume: volume_sma_20 (bigint), volume_ratio, obv (bigint), obv_slope_10d, ad_line, cmf_20, vwap_distance_pct
Price Action: daily_return, gap_pct, range_pct, body_pct, upper_shadow_pct, lower_shadow_pct, close_position, higher_highs_5d (int), higher_lows_5d (int), consecutive_up_days (int), consecutive_down_days (int)
Patterns (NUMERIC 5,2 scores 0-100): pattern_wedge_falling, pattern_wedge_rising, pattern_triangle_ascending, pattern_triangle_descending, pattern_triangle_symmetric, pattern_flag_bull, pattern_flag_bear, pattern_pennant, pattern_cup_handle, pattern_double_bottom, pattern_head_shoulders_inv, pattern_channel_up, pattern_consolidation_score
Relative Strength: rs_vs_spy_20d, rs_vs_sector_20d, rs_rank_percentile
Support/Resistance: distance_to_resistance_pct, distance_to_support_pct, near_52w_high_pct, near_52w_low_pct

Use NUMERIC(12,4) for prices, NUMERIC(8,4) for percentages, NUMERIC(5,2) for scores, BIGINT for volume/OBV. Every time-series table gets UNIQUE(stock_id, date) and INDEX on (stock_id, date DESC).
```

### Verification:
- `cd backend && pip install -e . && alembic upgrade head` succeeds against local or Railway PG
- `cd frontend && npm run build` succeeds
- All model files import without errors
- `.gitignore` covers all sensitive/generated files

### Estimated time: 20-30 minutes with Claude Code

---

## Phase 2: Data Ingestion Pipeline

### Prompt for Claude Code:

```
Read CLAUDE.md. We're on Phase 2: Build the data ingestion pipeline.

1. Create app/services/data_ingestion.py with provider-agnostic interfaces:

   - DataProvider ABC (abstract base class):
     * Abstract methods: get_daily_bars(), get_options_eod(), get_options_chain()
     * Concrete providers implement this interface → easy to swap sources later

   - PolygonClient class (implements DataProvider) using httpx.AsyncClient:
     * get_stock_universe() — fetch S&P 500 + Russell 2000 tickers (~2500 unique stocks). Use Polygon's /v3/reference/tickers endpoint with market=stocks, active=true. Also fetch index membership from Wikipedia (S&P 500 list) and iShares IWM holdings CSV for Russell 2000. Store in stocks table with index_membership column (sp500, russell2000, both).
     * get_daily_bars(symbol, start_date, end_date) — /v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}. Handles pagination. Upserts into daily_bars.
     * IMPORTANT: On free tier (5 req/min), seeding 2500 stocks × 3yr = slow. Implement checkpoint/resume so it can be interrupted and continued. Log progress to DB (stocks.last_seeded_date).

   - ThetaDataClient class (implements DataProvider):
     * Uses thetadata Python package (pip install thetadata)
     * get_options_eod(symbol, start_date, end_date) — fetch historical EOD options data: strikes, IV, greeks, volume, OI for all contracts. Aggregate into per-stock daily options_snapshots (ATM IV, IV rank, put/call ratios, etc.)
     * get_options_flow(symbol, date) — fetch trade-level data, detect unusual activity (volume > 2x OI, large premium trades). Store in options_flow.
     * NOTE: Free tier gives 1yr EOD history at 30 req/min. Use rate limiter.

   - YFinanceClient class:
     * get_current_options_chain(symbol) — Use yfinance to get current options chains as supplement/fallback. Parse strikes, IV, greeks, volume, OI. Free with no rate limit.

   - AlphaVantageClient class (backup for stocks):
     * get_daily_bars(symbol) — TIME_SERIES_DAILY_ADJUSTED, outputsize=full

   - FREDClient class:
     * get_macro_data(start_date) — Pull: DGS10 (10Y yield), DGS2 (2Y yield), VIXCLS (VIX). Store in market_regime.

   - ALL clients must: use exponential backoff on rate limits, log errors, handle missing data gracefully
   - Create a DataIngestionOrchestrator that coordinates across providers (tries primary, falls back to secondary)

2. Create app/services/technical_calc.py:
   - TechnicalCalculator class that takes a DataFrame of OHLCV data and computes ALL 82 technical features
   - Use the `ta` library (technical analysis library for Python — `pip install ta`) for standard indicators
   - Custom implementations for:
     * MA slopes (linear regression over 10-day window of MA values)
     * MACD histogram slope (3-day linear regression)
     * Bollinger squeeze detection (BB inside Keltner channels)
     * Volume analysis (OBV slope via linear regression)
     * Price action features (consecutive days, higher highs/lows counting)
     * Relative strength vs SPY (needs SPY daily bars loaded first)
   - compute_all(stock_id, bars_df) → returns dict of all 82 features for latest date
   - compute_historical(stock_id, bars_df) → returns DataFrame with features for all dates (for training)

3. Create app/services/pattern_detect.py:
   - PatternDetector class that scores chart patterns 0-100:
     * Wedge detection (falling/rising): Find converging trendlines on highs and lows over 20-60 bar windows. Score based on: number of touches (more = higher), convergence rate, volume decline during pattern.
     * Triangle detection (ascending/descending/symmetric): Flat resistance + rising support (ascending), etc.
     * Flag/pennant: Strong move (flagpole) followed by tight consolidation. Measure pole magnitude and consolidation tightness.
     * Cup and handle: U-shaped base with handle pullback. Measure symmetry, depth, handle characteristics.
     * Double bottom: Two lows at similar level with rally between. Measure symmetry, neckline.
     * Inverse head & shoulders: Three troughs, middle lowest. Measure symmetry.
     * Consolidation score: Composite of BB width percentile, ATR compression, volume decline — a general "coiled spring" metric.
   - detect_all(bars_df) → dict of all pattern scores for the latest bar

4. Create scripts/seed_historical.py:
   - Async script that:
     * Fetches stock universe: S&P 500 + Russell 2000 (~2500 unique stocks)
       - S&P 500: scrape current list from Wikipedia or use Polygon reference data
       - Russell 2000: fetch from iShares IWM holdings CSV (ishares.com) or Polygon
       - Store index_membership on each stock record
     * For each stock: fetches 3 years of daily bars from Polygon
     * Computes technical snapshots for all historical dates
     * Fetches 1yr historical options EOD from Theta Data for each stock
     * Fetches macro data from FRED
     * Logs progress (X/2500 stocks complete, estimated time remaining)
     * MUST handle interruption gracefully — track last_seeded_date per stock, skip already-seeded stocks on restart
     * On Polygon free tier (5 req/min): full seed takes ~8-10 hours. Print ETA. Consider running overnight.
   - Use asyncio.Semaphore to limit concurrent API calls (respect rate limits per provider)
   - Add --resume flag to continue from last checkpoint
   - Add --symbols flag to seed specific tickers for testing (e.g. --symbols AAPL,MSFT,NVDA)

5. Create scripts/daily_update.py:
   - Async script for daily cron:
     * Fetch latest bars for all active stocks
     * Compute today's technical snapshot
     * Fetch today's options snapshots
     * Fetch today's macro data
     * Run ML scorer on all stocks (Phase 3)
     * Log summary

6. Wire up the /api/pipeline router:
   - POST /api/pipeline/seed — trigger seed_historical (background task)
   - POST /api/pipeline/daily — trigger daily_update (background task)
   - GET /api/pipeline/status — check progress of running jobs

IMPORTANT: Use `ta` library (pip install ta), NOT ta-lib (requires C compilation). The `ta` library is pure Python and has all the indicators we need.
```

### Verification:
- Run seed script against Polygon with 5 test tickers — data appears in DB
- Technical calculator produces non-null values for all 82 features on sample data
- Pattern detector returns scores 0-100 for test cases
- Daily update script works end-to-end for 1 ticker

### Estimated time: 30-45 minutes

---

## Phase 3: ML Pipeline + Backtester

### Prompt for Claude Code:

```
Read CLAUDE.md. Phase 3: Build the ML training pipeline and backtester.

1. Create app/ml/features.py:
   - FeatureBuilder class:
     * build_feature_matrix(stock_ids, start_date, end_date) → pulls from technical_snapshots + options_snapshots + market_regime tables, joins into one wide DataFrame
     * add_lookback_features(df) → for 16 key metrics (rsi_14, bb_width, volume_ratio, price_vs_sma50, macd_histogram, cmf_20, obv_slope, adx_14, stoch_k, mfi_14, atr_pct, close_position, pattern_consolidation_score, rs_rank_percentile, iv_rank, pc_volume_ratio), add 5-day and 10-day rolling deltas
     * remove_redundant(df, threshold=0.95) → drop features with >0.95 correlation, keeping the one with higher variance
     * get_feature_names() → list of final feature column names
   - TOTAL features before pruning: ~126. After correlation filter: ~40-60.

2. Create app/ml/labels.py:
   - LabelGenerator class:
     * label_breakout(bars_df, threshold_pct=0.10, horizon_days=20) → binary: did stock gain threshold% within horizon days? Returns Series of 0/1.
     * label_max_gain(bars_df, horizon_days=20) → continuous: max gain % within horizon. Returns Series.
     * label_risk_reward(bars_df, horizon_days=20) → max gain / max drawdown within horizon.
     * label_call_pnl(bars_df, options_df, dte=30, strike='ATM', horizon_days=20) → simulated call option P/L using Black-Scholes with actual IV data. Accounts for theta decay and IV change. This is the ultimate label.
   - Each method must handle edge cases: not enough future data (drop those rows), stocks that get delisted (mark appropriately).

3. Create app/ml/train.py:
   - ModelTrainer class:
     * prepare_data(start_date, end_date, label_type='breakout') → calls FeatureBuilder and LabelGenerator, handles NaN filling (forward fill then drop), returns X, y, dates
     * walk_forward_split(X, y, dates, train_years=3, val_months=6) → generator yielding (X_train, y_train, X_val, y_val) tuples, rolling forward by val_months each iteration
     * train_ensemble(X_train, y_train) → trains XGBoost + LightGBM + RandomForest, returns dict of fitted models
     * evaluate(models, X_val, y_val) → returns dict with accuracy, precision, recall, f1, AUC-ROC, profit_factor (using predicted signals on val set)
     * train_meta_learner(models, X_val, y_val) → LogisticRegression on stacked predictions from base models
     * save_model(models, meta_learner, version) → joblib dump to app/ml/models/ensemble_v{version}.joblib
     * full_training_run() → orchestrates everything, logs all metrics, saves best model
   - XGBoost params: max_depth=6, n_estimators=500, learning_rate=0.05, early_stopping_rounds=50, scale_pos_weight=auto (handle class imbalance)
   - LightGBM params: num_leaves=31, n_estimators=500, learning_rate=0.05, is_unbalance=True
   - RandomForest params: n_estimators=300, max_depth=10, class_weight='balanced'

4. Create app/ml/evaluate.py:
   - ModelEvaluator class:
     * classification_report(y_true, y_pred, y_proba) → precision, recall, f1, AUC-ROC
     * feature_importance(models) → aggregate importance across ensemble, return top 30 features
     * score_distribution(y_proba) → histogram of predicted probabilities
     * calibration_curve(y_true, y_proba) → are 80% confidence predictions actually right 80% of the time?
     * regime_breakdown(y_true, y_pred, regime_labels) → performance by market regime

5. Create app/services/backtester.py:
   - Backtester class:
     * run_backtest(model_path, start_date, end_date, entry_threshold=0.65, target_pct=1.0, stop_pct=-0.5, max_days=20) →
       - Load model, score every stock on every day in range
       - When score > entry_threshold: simulate buying ATM call at that day's close
       - Track position: exit at target_pct gain, stop_pct loss, or max_days expiry
       - Record every trade in backtest_trades table
     * compute_stats(backtest_id) → win_rate, avg_win, avg_loss, profit_factor, max_drawdown, sharpe, sortino, expectancy
     * results_by_regime(backtest_id) → break down stats by BULL/BEAR/CHOPPY
     * results_by_score(backtest_id) → break down by score bucket (60-70, 70-80, 80-90, 90-100)
     * results_by_pattern(backtest_id) → break down by dominant pattern type
     * equity_curve(backtest_id) → cumulative P/L over time as list of (date, cumulative_pnl)
   - Store results in backtest_runs and backtest_trades tables

6. Create app/services/model_scorer.py:
   - ModelScorer class:
     * load_model(version='latest') → load ensemble from joblib
     * score_single(symbol) → compute features for today, run through ensemble, return composite score + component breakdown
     * score_universe() → score all active stocks, store in signals table, return top N
     * get_top_signals(n=20, min_score=60) → query signals table for today's best opportunities

7. Wire up routers:
   - GET /api/signals — today's top signals with scores and component breakdown
   - GET /api/score/{symbol} — detailed score for one ticker
   - POST /api/backtest — run backtest with parameters, return backtest_id
   - GET /api/backtest/{id} — get backtest results, stats, equity curve
   - GET /api/backtest/{id}/trades — paginated trade list from backtest

8. Create scripts/retrain_model.py:
   - Weekly cron script: pull latest data, retrain, evaluate against holdout, save if improved, update 'latest' symlink
```

### Verification:
- Train on sample data (even 50 stocks × 1 year) — model saves successfully
- Score a single ticker — returns valid 0-100 composite score
- Run mini backtest — produces win rate, equity curve
- All API endpoints return valid JSON

### Estimated time: 45-60 minutes

---

## Phase 4: Frontend Dashboard

### Prompt for Claude Code:

```
Read CLAUDE.md. Phase 4: Build the full frontend dashboard.

All data comes from the FastAPI backend. Use the fetch wrapper in lib/api.ts. Every page should handle loading states (skeleton loaders) and error states gracefully.

1. app/page.tsx — DASHBOARD (Server Component with client islands):
   - Header: "Options Alpha" with last-updated timestamp
   - Top row: 4 summary cards — Total Signals Today, Avg Score, Best Signal (ticker + score), Market Regime
   - Main content: SignalTable component showing today's top 20 signals:
     * Columns: Rank, Symbol, Composite Score (color-coded: green >80, yellow 60-80, red <60), Pattern, IV Rank, Price, Volume Ratio
     * Click row → navigate to /ticker/[symbol]
     * Sortable by any column
   - Right sidebar: Market Regime panel — VIX level, breadth indicators, regime classification badge (BULL/BEAR/CHOPPY)
   - Style: Dark theme (zinc-900 bg, zinc-800 cards, emerald/amber/rose for score colors). This is a trading dashboard — make it feel like a Bloomberg terminal, not a SaaS landing page.

2. app/scanner/page.tsx — SCREENER ("use client"):
   - Filter bar:
     * Min composite score (slider 0-100)
     * Pattern type (multi-select: wedge, triangle, flag, cup, etc.)
     * Sector (multi-select)
     * IV Rank range (min-max slider)
     * Min volume ratio
     * SMA 50 > 200 toggle (on by default)
   - Results table (same as SignalTable but filtered)
   - "Scan Now" button that triggers a fresh scan via POST /api/scan with filters
   - Show count of results: "47 stocks match your criteria"

3. app/ticker/[symbol]/page.tsx — TICKER DEEP DIVE:
   - Header: Symbol, Company Name, Price, Daily Change
   - Score Card (large): Composite Score circle + breakdown bars for technical, momentum, volume, options, pattern, regime
   - Technical Chart (Recharts):
     * Price line with SMA 50, SMA 200 overlays
     * Volume bars below
     * Bollinger Bands as shaded area
     * Pattern annotation if detected (e.g. "Falling Wedge" label on chart)
   - Options Panel:
     * IV Rank gauge (0-100)
     * IV vs HV comparison
     * Put/Call ratio
     * Unusual flow table (recent unusual options activity)
     * Suggested trade: strike, expiry, estimated cost, risk/reward
   - Signal History: table of past signals for this ticker with outcomes (did it work?)

4. app/backtest/page.tsx — BACKTEST RESULTS ("use client"):
   - Parameter form: model version, date range, entry threshold, target %, stop %, max days
   - "Run Backtest" button → POST /api/backtest
   - Results display (once run completes):
     * Summary cards: Total Trades, Win Rate, Profit Factor, Sharpe, Max Drawdown, Expectancy
     * Equity curve chart (Recharts area chart, cumulative P/L over time)
     * Win rate by score bucket (bar chart)
     * Win rate by pattern type (bar chart)
     * Win rate by market regime (bar chart)
     * Full trade log table (sortable, filterable)

5. app/journal/page.tsx — TRADE JOURNAL ("use client"):
   - "New Entry" dialog form: symbol (autocomplete from stocks), entry date, entry price, strike, expiry, contracts, notes, tags
   - Journal table: all trades, sortable by date, P/L, symbol
   - Edit/close trade: add exit date, exit price, exit reason
   - Summary stats at top: Total P/L, Win Rate, Avg Win, Avg Loss, Best Trade, Worst Trade
   - Filter by: date range, symbol, tags, open/closed

6. Layout & Navigation:
   - Sidebar nav with icons (lucide-react): LayoutDashboard, Search, BarChart3, BookOpen
   - Active state highlighting
   - Collapsible on mobile
   - Dark theme throughout: bg-zinc-950, cards bg-zinc-900, borders border-zinc-800
   - All text: zinc-100 primary, zinc-400 secondary

IMPORTANT:
- Use shadcn/ui for all base components. Do NOT use any other UI library.
- Use Recharts for ALL charts. Do NOT use Chart.js or d3 directly.
- Every number should be formatted: prices to 2 decimals, percentages to 1 decimal with % suffix, large numbers with commas.
- Score colors: >= 80 text-emerald-400, 60-79 text-amber-400, < 60 text-rose-400
```

### Verification:
- `npm run build` succeeds with zero errors
- All pages render with skeleton loaders when API is unavailable
- Score colors work correctly across thresholds
- Navigation between all pages works
- Responsive on mobile (sidebar collapses)

### Estimated time: 30-45 minutes

---

## Phase 5: Deployment

### Prompt for Claude Code:

```
Read CLAUDE.md. Phase 5: Deploy to Railway (backend) and Vercel (frontend).

1. RAILWAY (Backend):
   - Verify Dockerfile is correct:
     * Python 3.11 base
     * Install system deps for numpy/pandas
     * pip install from pyproject.toml
     * CMD: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   - Verify railway.toml has correct build/start config
   - Add all env vars to Railway: DATABASE_URL, POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY, FRED_API_KEY
   - Set up Railway cron job for daily_update.py (runs at 6:30 PM ET / 22:30 UTC, after market close)
   - Set up Railway cron job for retrain_model.py (runs Sundays at 2:00 AM ET / 06:00 UTC)

2. VERCEL (Frontend):
   - Verify next.config.js has correct config:
     * Output: standalone (for optimal Vercel deployment)
     * API rewrites: /api/* → Railway backend URL
   - Add env vars: NEXT_PUBLIC_API_URL pointing to Railway backend URL
   - Verify vercel.json if needed for rewrites

3. CORS:
   - Update backend CORS to allow the Vercel domain specifically (in addition to localhost for dev)

4. Health checks:
   - Add GET /api/health endpoint that checks DB connection and returns status
   - Add GET /api/health/data endpoint that checks latest data freshness (warn if data is >1 day old)

5. Create a simple deployment script at scripts/deploy.sh:
   - git push (triggers both Railway and Vercel deploys)
   - Check Railway deploy status
   - Check Vercel deploy status
   - Hit /api/health to verify

Make sure the backend Dockerfile actually works — test it with `docker build` locally if possible.
```

### Verification:
- Backend health endpoint returns 200 from Railway URL
- Frontend loads from Vercel URL
- Frontend can fetch data from backend (CORS works)
- Cron jobs are scheduled in Railway

### Estimated time: 15-20 minutes

---

## Phase 6: Integration Testing + Polish

### Prompt for Claude Code:

```
Read CLAUDE.md. Phase 6: End-to-end integration testing and polish.

1. Run the full pipeline end-to-end:
   - Seed 10 test stocks (AAPL, MSFT, NVDA, TSLA, AMZN, META, GOOGL, AMD, NFLX, CRM) with 1 year of data
   - Compute all technical indicators
   - Train a model on this small dataset
   - Score all 10 stocks
   - Run a backtest
   - Verify signals appear on the dashboard

2. Fix any issues found during integration:
   - NaN handling in features (forward fill, then drop rows with any remaining NaN)
   - Date alignment between tables (ensure all joins work on stock_id + date)
   - API response serialization (Decimal → float for JSON, dates → ISO strings)
   - Loading states on frontend when backend is slow

3. Add error handling everywhere:
   - Backend: catch Polygon API failures, return partial results with warnings
   - Frontend: show meaningful error messages, not generic "Something went wrong"
   - Data pipeline: skip failed stocks, log errors, continue with rest

4. Performance:
   - Add database connection pooling (pool_size=5, max_overflow=10)
   - Add response caching on heavy endpoints (signals, score) with 5-minute TTL
   - Ensure all SQL queries use the indexes we created
   - Frontend: use React.memo on expensive chart components

5. Write backend tests (pytest):
   - test_technical_calc.py: verify RSI, MACD, Bollinger values against known correct outputs
   - test_pattern_detect.py: verify wedge detection on synthetic data
   - test_labels.py: verify breakout labeling on known price sequences
   - test_api.py: endpoint smoke tests (each returns 200 with valid schema)
```

### Verification:
- Full pipeline: seed → compute → train → score → backtest works end-to-end
- All 5 frontend pages display real data
- pytest passes all tests
- No unhandled errors in logs

### Estimated time: 30-45 minutes

---

## Running Order Summary

| Phase | What | Claude Code Time | Depends On |
|-------|------|-------------------|------------|
| 1 | Scaffold + DB | 20-30 min | Nothing |
| 2 | Data Pipeline | 30-45 min | Phase 1 |
| 3 | ML + Backtest | 45-60 min | Phase 2 |
| 4 | Frontend | 30-45 min | Phase 1 (can start after scaffold, parallel with 2-3) |
| 5 | Deploy | 15-20 min | Phases 1-4 |
| 6 | Integration | 30-45 min | Phase 5 |

**Total estimated: 3-4 hours of Claude Code time**

---

## Claude Code Settings

Add to `.claude/settings.json` in the project:

```json
{
  "permissions": {
    "allow": [
      "Bash(npm *)",
      "Bash(npx *)",
      "Bash(pip *)",
      "Bash(python *)",
      "Bash(uvicorn *)",
      "Bash(alembic *)",
      "Bash(pytest *)",
      "Bash(ruff *)",
      "Bash(git *)",
      "Bash(docker *)",
      "Bash(cd *)",
      "Bash(ls *)",
      "Bash(cat *)",
      "Bash(mkdir *)",
      "Bash(cp *)",
      "Bash(mv *)"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(git push --force)"
    ]
  }
}
```

---

## Tips for Running This

1. **Run in bypass permissions mode** for faster execution: `claude --permission-mode bypassPermissions`
2. **One phase at a time** — paste each phase prompt, let it complete, verify, then move to next
3. **If Claude Code gets stuck**, interrupt with Esc and give it a hint about what went wrong
4. **Phase 4 (frontend) can run in parallel** with Phases 2-3 if you open a second terminal
5. **Keep the plan document open** as reference — Claude Code will read CLAUDE.md automatically but this has more detail
6. **After Phase 6**, you'll have a working system. Then we iterate: tune the model, add features, improve the UI based on what you see
