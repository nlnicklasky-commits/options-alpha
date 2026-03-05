FROM python:3.11-slim

WORKDIR /app

# System deps for numpy, pandas, and LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
