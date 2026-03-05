# Options Alpha

## Project Overview
A personal trading intelligence platform that systematizes call options breakout trading. Uses ML to score stocks for breakout probability, integrates options data for optimal entry, and presents everything in a dashboard.

**Owner**: Nick (nl.nicklasky@gmail.com) — sole user, no auth needed beyond obscure URL.

## Architecture
- **Frontend**: Next.js 14 App Router + Tailwind + shadcn/ui + Recharts → Vercel
- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL → Railway
- **ML**: scikit-learn, XGBoost, LightGBM (joblib serialized models)
- **Data**: Polygon.io (stocks primary), Theta Data (options primary), Alpha Vantage (backup), FRED (macro), yfinance (current options chains)

## Commands

### Frontend (from `frontend/`)
```bash
npm run dev          # Dev server
npm run build        # Production build
npm run lint         # ESLint
npm run type-check   # TypeScript check
```

### Backend (from `backend/`)
```bash
uvicorn app.main:app --reload              # Dev server
pytest                                      # Run tests
ruff check app/                            # Lint
ruff format app/                           # Format
alembic upgrade head                       # Run migrations
alembic revision --autogenerate -m "msg"   # Create migration
python scripts/seed_historical.py          # Seed historical data
python scripts/daily_update.py             # Daily data refresh
python scripts/retrain_model.py            # Retrain ML models
```

## Code Standards

### Python (Backend)
- ALWAYS use async/await for database operations and HTTP calls
- Use Pydantic v2 models for ALL request/response schemas
- Use SQLAlchemy 2.0 style (select() not query())
- Type hints on ALL functions — no exceptions
- Use `httpx.AsyncClient` for external API calls, never `requests`
- Environment variables via `pydantic-settings`, never hardcoded
- Error handling: raise HTTPException with meaningful messages
- IMPORTANT: ALL numeric financial data uses `Decimal` in Python, `NUMERIC` in SQL — never float

### TypeScript (Frontend)
- Use App Router (app/ directory), NEVER pages/
- Server Components by default, "use client" only when needed
- Use `fetch` with Next.js caching, not axios
- All API calls go through `/app/api/` proxy routes to backend
- Components use shadcn/ui primitives — do NOT install other UI libraries
- Charts use Recharts — do NOT use Chart.js or other charting libs
- IMPORTANT: No localStorage or sessionStorage usage

### SQL / Database
- ALL migrations via Alembic — never raw SQL in application code
- Use NUMERIC(12,4) for prices, NUMERIC(8,4) for percentages, NUMERIC(5,2) for scores
- Every table gets created_at TIMESTAMP DEFAULT NOW()
- Indexes on (stock_id, date DESC) for ALL time-series tables
- Use UNIQUE constraints on (stock_id, date) to prevent duplicates

### ML Pipeline
- Walk-forward validation ONLY — never random train/test split
- Save models with joblib, version in filename (model_v{date}.joblib)
- Feature engineering in dedicated module, not scattered in training code
- Log all training runs: features used, hyperparameters, metrics

## Project Structure
```
options-alpha/
├── CLAUDE.md
├── .env.example
├── frontend/            # Next.js 14
│   ├── app/
│   │   ├── page.tsx     # Dashboard
│   │   ├── scanner/     # Screener
│   │   ├── ticker/[symbol]/  # Ticker deep-dive
│   │   ├── backtest/    # Backtest results
│   │   ├── journal/     # Trade journal
│   │   └── api/         # Proxy routes
│   ├── components/      # Reusable components
│   └── lib/             # Utils, API client
├── backend/             # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py    # pydantic-settings
│   │   ├── database.py  # async SQLAlchemy
│   │   ├── models/      # ORM models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── routers/     # API routes
│   │   ├── services/    # Business logic
│   │   └── ml/          # ML pipeline
│   ├── alembic/         # Migrations
│   ├── scripts/         # Data scripts
│   └── tests/
└── notebooks/           # Jupyter exploration
```

## Environment Variables
```
# Backend
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/options_alpha
POLYGON_API_KEY=
ALPHA_VANTAGE_API_KEY=
FRED_API_KEY=
THETADATA_USERNAME=
THETADATA_PASSWORD=

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Data Source Strategy
All data clients live behind an abstract interface so providers can be swapped without rewriting business logic.

| Data | Free Source | Paid Upgrade |
|------|-----------|-------------|
| Stock OHLCV (historical) | Polygon.io free (5 req/min) | Polygon Stocks Developer $79/mo |
| Technical indicators | Computed in-house from OHLCV using `ta` library | — |
| Options EOD (historical) | Theta Data free (1yr, 30 req/min) | Theta Data Value/Standard ($25-50/mo, 4-8yr) |
| Options chains (current) | yfinance (free, no rate limit) | — |
| Greeks + IV | Theta Data free tier includes these | — |
| Macro (VIX, yields, breadth) | FRED API (free) + CBOE CSV downloads | — |
| Pattern detection | Computed in-house | — |

Start at $0/mo. Upgrade Polygon ($79/mo) if rate-limited during seeding. Upgrade Theta Data when backtesting options labels.

## Key Design Decisions
1. Stock universe: S&P 500 + Russell 2000 = ~2500 unique stocks (minimal overlap). Use index membership at time of data point to avoid survivorship bias.
2. Breakout label: 10% gain within 20 trading days (primary), also test 7% and 15%
3. Options data: Theta Data free tier for 1yr historical EOD + yfinance for current chains. Upgrade to Theta Data paid for deeper history.
4. No auth: Random Vercel URL is sufficient security for personal use
5. Model retraining: Weekly via cron, manual trigger available
6. Data abstraction: All external data access through provider-agnostic interfaces (easy to swap sources)

## Gotchas
- Polygon.io rate limits: 5 req/min on free, unlimited on paid. Use exponential backoff.
- Theta Data requires Theta Terminal running locally for API access. For server deployment, use their REST API endpoint instead.
- Theta Data free tier: 1yr EOD only, 30 req/min. Enough for initial model, upgrade for deeper backtest.
- yfinance options data is CURRENT only — no historical. Historical options comes from Theta Data.
- Railway free tier has 500 hours/month. Use Hobby plan ($5/mo) for always-on.
- Alembic async requires `sqlalchemy[asyncio]` and `asyncpg` — not psycopg2.
- XGBoost on Railway needs `xgboost` in requirements, not conda. Works fine with pip.
