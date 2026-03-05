#!/bin/sh
set -e

echo "=== Running migrations ===" >&2
alembic upgrade head 2>&1 >&2
echo "=== Migrations done ===" >&2

echo "=== Testing app import ===" >&2
python -c "from app.main import app; print('Import OK', flush=True)" 2>&1 >&2
echo "=== Import test passed ===" >&2

echo "=== Starting uvicorn on port ${PORT:-8000} ===" >&2
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" 2>&1
