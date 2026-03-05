#!/usr/bin/env bash
set -euo pipefail

# Options Alpha deployment script
# Pushes to git (triggers Railway + Vercel deploys), then verifies health.

BACKEND_URL="${BACKEND_URL:-https://your-app.up.railway.app}"
FRONTEND_URL="${FRONTEND_URL:-https://your-app.vercel.app}"

echo "==> Pushing to git (triggers Railway + Vercel deploys)..."
git push origin main

echo ""
echo "==> Waiting 30s for deploys to start..."
sleep 30

# Check Railway deploy status (requires Railway CLI: npm i -g @railway/cli)
if command -v railway &> /dev/null; then
    echo "==> Railway deploy status:"
    railway status 2>/dev/null || echo "    (Run 'railway login' and 'railway link' to connect)"
else
    echo "==> Railway CLI not installed. Install with: npm i -g @railway/cli"
fi

# Check Vercel deploy status (requires Vercel CLI: npm i -g vercel)
if command -v vercel &> /dev/null; then
    echo ""
    echo "==> Vercel deploy status:"
    vercel ls --limit 1 2>/dev/null || echo "    (Run 'vercel login' and 'vercel link' to connect)"
else
    echo "==> Vercel CLI not installed. Install with: npm i -g vercel"
fi

echo ""
echo "==> Checking backend health..."
for i in 1 2 3 4 5; do
    response=$(curl -sf "${BACKEND_URL}/api/health" 2>/dev/null) && break
    echo "    Attempt $i/5 - waiting 15s..."
    sleep 15
done

if [ -n "${response:-}" ]; then
    echo "    Backend health: $response"
else
    echo "    Backend health check failed after 5 attempts"
    exit 1
fi

echo ""
echo "==> Checking data freshness..."
data_response=$(curl -sf "${BACKEND_URL}/api/health/data" 2>/dev/null) || true
if [ -n "${data_response:-}" ]; then
    echo "    Data health: $data_response"
else
    echo "    Data health check not available (may be first deploy)"
fi

echo ""
echo "==> Deploy complete!"
echo "    Backend:  ${BACKEND_URL}"
echo "    Frontend: ${FRONTEND_URL}"
