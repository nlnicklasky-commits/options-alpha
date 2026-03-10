# Options Alpha — Deployment Readiness Report

## Code Fixes Applied (Already Done)

### 1. vercel.json — Removed broken env var interpolation
**Problem:** `${NEXT_PUBLIC_API_URL}` was used as a string literal — Vercel does NOT interpolate environment variables in vercel.json. This meant the rewrite rule would literally proxy to the string `${NEXT_PUBLIC_API_URL}/api/:path*`.
**Fix:** Removed the broken rewrite from vercel.json. The `next.config.ts` rewrites handle proxying correctly since they use runtime JavaScript interpolation at build time.

### 2. frontend/lib/api.ts — Switched to relative paths
**Problem:** `api.ts` prefixed all requests with `NEXT_PUBLIC_API_URL`, which on the client side would make cross-origin requests directly to the Railway backend. This required CORS to be perfectly configured.
**Fix:** All API calls now use relative `/api/...` paths. Next.js rewrites proxy these to the backend server-side, completely eliminating CORS issues.

### 3. frontend/next.config.ts — Added BACKEND_URL env var
**Problem:** Only supported `NEXT_PUBLIC_API_URL` (which gets baked into client-side JS). Now that we proxy everything, we only need a server-side env var.
**Fix:** Added `BACKEND_URL` as the primary env var (server-only, not exposed to browser), with `NEXT_PUBLIC_API_URL` fallback for backward compat.

### 4. frontend/.env.local — Created for local dev
New file with `BACKEND_URL=http://localhost:8000` for local development.

### 5. deploy.sh — Removed placeholder URLs
**Problem:** Had hardcoded `https://your-app.up.railway.app` and `https://your-app.vercel.app`.
**Fix:** Now requires `BACKEND_URL` and `FRONTEND_URL` to be set as env vars, with clear error message if missing.

---

## Deployment Steps (Manual — Do These Now)

### Step 1: Deploy Backend to Railway

The backend is already configured for Railway (Dockerfile, railway.toml, start.sh all exist). The database is already provisioned (metro.proxy.rlwy.net:24328).

**In Railway Dashboard:**

1. Go to https://railway.app → your project
2. If no service exists yet, click "New Service" → "GitHub Repo" → select `nlnicklasky-commits/options-alpha`
3. Set **Root Directory** to `backend`
4. Add these **Environment Variables** (Settings → Variables):

```
DATABASE_URL=postgresql+asyncpg://postgres:gEQVjlteQqniJBsXeDaYRmmWpnfxpUBw@metro.proxy.rlwy.net:24328/railway
POLYGON_API_KEY=<your polygon key from backend/.env>
ALPHA_VANTAGE_API_KEY=<your key from backend/.env>
FRED_API_KEY=<your key from backend/.env>
VERCEL_FRONTEND_URL=https://<your-vercel-app>.vercel.app
```

5. Under **Settings → Networking**, generate a **Public Domain** (e.g., `options-alpha-backend.up.railway.app`)
6. Note the public URL — you'll need it for Vercel setup

**Verify:** Once deployed, visit `https://<your-railway-url>/api/health` — should return `{"status":"ok"}`

### Step 2: Deploy Frontend to Vercel

1. Go to https://vercel.com → "Add New Project"
2. Import from GitHub: `nlnicklasky-commits/options-alpha`
3. Set **Root Directory** to `frontend`
4. Set **Framework Preset** to "Next.js"
5. Add **Environment Variable**:

```
BACKEND_URL=https://<your-railway-url-from-step-1>
```

6. Click "Deploy"

**Verify:** Visit the Vercel URL → should load the dashboard. Check browser DevTools Network tab — API calls to `/api/signals` should return data (proxied through Vercel to Railway).

### Step 3: Update Railway CORS (After Vercel Deploy)

Go back to Railway and update the env var:

```
VERCEL_FRONTEND_URL=https://<your-actual-vercel-url>.vercel.app
```

Note: Since we're now using server-side rewrites (not client-side CORS), this is only needed as a safety net for any direct API calls.

### Step 4: Run Database Migrations

SSH into Railway or use the Railway CLI:

```bash
railway run alembic upgrade head
```

Or trigger via the pipeline endpoint after deployment:
```bash
curl -X POST https://<your-railway-url>/api/pipeline/run-daily
```

### Step 5: Seed Historical Data

This is a long-running process (3 years of data for S&P 500 + Russell 2000). Run it:

```bash
# From your local machine (needs DATABASE_URL set)
cd backend
python scripts/seed_historical.py --resume

# Or to test with a few symbols first:
python scripts/seed_historical.py --symbols AAPL,MSFT,NVDA,TSLA,AMZN
```

### Step 6: Train the ML Model

After seeding data:

```bash
# Via API endpoint:
curl -X POST https://<your-railway-url>/api/pipeline/retrain

# Or locally:
cd backend
python -c "
import asyncio
from app.database import async_session
from app.ml.train import ModelTrainer
async def run():
    async with async_session() as session:
        trainer = ModelTrainer(session)
        result = await trainer.full_training_run()
        print(result)
asyncio.run(run())
"
```

---

## Known Limitations (Non-Blocking)

1. **Theta Data (historical options):** Connects to localhost:25510 — won't work on Railway. Not a blocker because yfinance handles current options chains and the backtester uses Black-Scholes pricing.

2. **Railway cron jobs:** The in-app scheduler (main.py) handles daily pipeline and weekly retraining via asyncio. The Railway dashboard cron entries mentioned in railway.toml comments are optional redundancy.

3. **Rate limiting:** Polygon.io free tier is 5 calls/minute. Historical seeding will be slow (~1 stock per minute). The rate limiter handles this automatically.

4. **Model cold start:** First deploy won't have a trained model. The scorer gracefully returns "no model loaded" until Step 6 is completed.

---

## Architecture Summary

```
User Browser
    ↓ (relative /api/* calls)
Vercel (Next.js SSR)
    ↓ (next.config.ts rewrites proxy /api/* → Railway)
Railway (FastAPI + PostgreSQL)
    ↓ (data providers)
Polygon.io / Alpha Vantage / FRED / yfinance
```

No CORS needed — all API traffic is proxied server-side through Vercel's Next.js rewrites.
