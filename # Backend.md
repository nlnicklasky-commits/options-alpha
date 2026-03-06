# Backend
DATABASE_URL=postgresql+asyncpg://postgres:gEQVjlteQqniJBsXeDaYRmmWpnfxpUBw@metro.proxy.rlwy.net:24328/railway
POLYGON_API_KEY=S8JmUg9UaZ4E07BqQcYrfNiNXBmsogwz
ALPHA_VANTAGE_API_KEY=QEYLD6YNS7Y99WST
FRED_API_KEY=b93f0796f878f107fe53f693e74c223d
THETADATA_USERNAME=nl.nicklasky@gmail.com
THETADATA_PASSWORD=Y@nkees21

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000


# Add PostgreSQL
railway add --plugin postgresql

# Link to your backend service
railway link

# Set the root directory and env vars
railway variables set RAILWAY_DOCKERFILE_PATH=backend/Dockerfile
railway variables set DATABASE_URL=postgresql+asyncpg://postgres:gEQVjlteQqniJBsXeDaYRmmWpnfxpUBw@metro.proxy.rlwy.net:24328/railway
railway variables set POLYGON_API_KEY=S8JmUg9UaZ4E07BqQcYrfNiNXBmsogwz
railway variables set FRED_API_KEY=b93f0796f878f107fe53f693e74c223d
railway variables set ALPHA_VANTAGE_API_KEY=QEYLD6YNS7Y99WST
railway variables set THETADATA_USERNAME=nl.nicklasky@gmail.com
railway variables set THETADATA_PASSWORD=Y@nkees21

# Deploy
railway up --detach