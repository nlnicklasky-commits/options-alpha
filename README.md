# Options Alpha

Personal trading intelligence platform for systematized call options breakout trading.

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
cp ../.env.example ../.env  # edit with your credentials
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
Copy `.env.example` to `.env` and fill in your API keys. See `CLAUDE.md` for details.
