#!/bin/sh
# Skip alembic for now — just test if uvicorn can start
exec python -c "
import sys
print('=== Python startup test ===', file=sys.stderr, flush=True)
try:
    print('=== Importing app... ===', file=sys.stderr, flush=True)
    from app.main import app
    print('=== Import OK ===', file=sys.stderr, flush=True)
except Exception as e:
    print(f'=== IMPORT FAILED: {e} ===', file=sys.stderr, flush=True)
    sys.exit(1)

import os
port = int(os.environ.get('PORT', 8000))
print(f'=== Starting uvicorn on port {port} ===', file=sys.stderr, flush=True)

import uvicorn
uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')
"
