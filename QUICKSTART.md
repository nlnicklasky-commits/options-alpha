# Quick Start — Options Alpha

## Step 1: Get your API keys (5 minutes)

All free:

1. **Polygon.io** → [polygon.io/dashboard/signup](https://polygon.io/dashboard/signup) → copy API key from dashboard
2. **Theta Data** → [thetadata.net](https://www.thetadata.net/) → sign up → get username + password
3. **FRED** → [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html) → request key
4. **Alpha Vantage** → [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) → claim key

## Step 2: Set up Railway database (5 minutes)

1. Go to [railway.app](https://railway.app) → sign up / log in
2. New Project → Provision PostgreSQL
3. Click the database → Variables tab → copy `DATABASE_URL`
4. Change the URL prefix from `postgresql://` to `postgresql+asyncpg://`

## Step 3: Create .env file

```bash
cd Documents/Projects/options-alpha
cp .env.example .env
# Fill in all the keys you just got
```

## Step 4: Open Claude Code and build

```bash
cd Documents/Projects/options-alpha
claude --permission-mode bypassPermissions
```

Then paste the Phase 1 prompt from `EXECUTION-PLAN.md`.

Wait for it to finish, verify, then paste Phase 2, etc.

## Phase Order

| Phase | Paste prompt from EXECUTION-PLAN.md | Time |
|-------|-------------------------------------|------|
| 1 | Project Scaffold + Database | ~25 min |
| 2 | Data Ingestion Pipeline | ~40 min |
| 3 | ML Pipeline + Backtester | ~50 min |
| 4 | Frontend Dashboard (can run parallel with 2-3) | ~40 min |
| 5 | Deployment | ~20 min |
| 6 | Integration Testing | ~40 min |

Total: ~3-4 hours of Claude Code time.

## After building: Seed your data

```bash
# Test with 5 stocks first
cd backend
python scripts/seed_historical.py --symbols AAPL,MSFT,NVDA,TSLA,AMD

# Then run the full seed overnight (~8-10 hrs on free tier)
python scripts/seed_historical.py
```

## Daily operation

The Railway cron handles daily updates automatically. Just check your dashboard.
