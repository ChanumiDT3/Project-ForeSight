# Project-ForeSight
Predictive maintenance system that turns equipment sensor readings into prioritized alerts and work orders, helping teams fix machines before they fail.

## Running locally

There is no sign-in in the MVP. On first load the app shows a **"Let us know who you are!"** popup with a dropdown of active users from `GET /v1/users`.

### Backend (FastAPI + SQLite, port 3001)

Run from `backend/`. The app does **not** read `.env` by itself, so load it into the shell first (copy `.env.example` to `.env`).

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
set -a; . ./.env; set +a          # Windows PowerShell: set each variable with $env:NAME="value"
alembic upgrade head              # creates the tables
python -m app.seed_users          # optional: loads/updates seed/users.json
uvicorn app.main:app --host 127.0.0.1 --port 3001
```

If the users table is empty at startup, the backend loads `seed/users.json` automatically (Priya Sharma, Raj Patel, Ana Silva, Mei Chen). Set `FORESIGHT_SEED_USERS_ON_STARTUP=false` to turn this off. Run `python -m app.seed_users` to apply later edits to the seed file.

### Frontend (React + Vite, port 3000)

Run from `frontend/`:

```bash
npm install
npm run dev -- --port 3000
```

The dev server proxies `/v1` and `/health` to `VITE_BACKEND_PROXY_TARGET` (default `http://localhost:3001`). If the popup says the ForeSight server was not found, check that the backend is running and the proxy target points to it.
