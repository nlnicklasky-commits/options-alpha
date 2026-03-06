#!/bin/sh
exec python -c "
import sys, os, subprocess

# Run alembic migrations (sync engine via psycopg2)
print('=== Running alembic migrations ===', file=sys.stderr, flush=True)
result = subprocess.run(['alembic', 'upgrade', 'head'], capture_output=True, text=True)
print(result.stdout, file=sys.stderr, flush=True)
if result.stderr:
    print(result.stderr, file=sys.stderr, flush=True)
if result.returncode != 0:
    print(f'=== Alembic failed with exit code {result.returncode} ===', file=sys.stderr, flush=True)
    sys.exit(1)
print('=== Migrations complete ===', file=sys.stderr, flush=True)

# Start uvicorn
from app.main import app
import uvicorn
port = int(os.environ.get('PORT', 8000))
print(f'=== Starting uvicorn on port {port} ===', file=sys.stderr, flush=True)
uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')
"
