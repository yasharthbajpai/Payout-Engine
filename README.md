# Playto Payout Engine

A production-grade payout engine for Indian merchants collecting international payments. Merchants accumulate balance when their customers pay (in USD, stored as INR paise) and withdraw to their Indian bank accounts.

## Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + SQLAlchemy (async) |
| Database | PostgreSQL 16 |
| Background Jobs | Celery + Redis |
| Frontend | Vite + React + TypeScript + Tailwind CSS |
| Infrastructure | Docker + Docker Compose |

## Quick Start

### Prerequisites

- Docker and Docker Compose installed

### 1. Clone and start

```bash
git clone <repo-url>
cd paytopay
docker-compose up --build
```

This starts:
- PostgreSQL on port `5432`
- Redis on port `6379`
- FastAPI backend on port `8000`
- Celery worker + Celery Beat (background workers)
- React frontend on port `5173`

Wait ~20 seconds for all services to be healthy.

### 2. Run migrations

Migrations run automatically when the `backend` service starts (via `alembic upgrade head` in the docker-compose command).

### 3. Seed test data

```bash
docker-compose exec backend python -m app.seed
```

This creates 3 merchants with:
- 5 credit entries each (simulating past customer payments)
- 2 completed payouts each

### 4. Open the dashboard

Visit [http://localhost:5173](http://localhost:5173)

### 5. API docs

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

---

## Development (without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up local Postgres and Redis, then:
export DATABASE_URL="postgresql+asyncpg://paytopay:paytopay@localhost:5432/paytopay"
export SYNC_DATABASE_URL="postgresql+psycopg2://paytopay:paytopay@localhost:5432/paytopay"
export REDIS_URL="redis://localhost:6379/0"

alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

### Celery workers

```bash
# In a separate terminal:
celery -A app.worker.celery_app worker --loglevel=info

# In another terminal:
celery -A app.worker.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Running Tests

```bash
# Make sure a test database exists:
createdb paytopay_test  # or via psql

cd backend
pytest -v
```

Tests require a running PostgreSQL instance at `localhost:5432` with a `paytopay_test` database.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/merchants` | List all merchants |
| `GET` | `/api/v1/merchants/{id}/balance` | Available + held balance |
| `GET` | `/api/v1/merchants/{id}/ledger` | Paginated ledger entries |
| `GET` | `/api/v1/merchants/{id}/payouts` | Payout history |
| `POST` | `/api/v1/payouts` | Create payout (requires headers) |
| `GET` | `/api/v1/payouts/{id}` | Payout status |

### Creating a payout

```bash
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: <merchant-uuid>" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"amount_paise": 50000, "bank_account_id": "<bank-account-uuid>"}'
```

---

## Architecture

```
Frontend (React) ──HTTP──► FastAPI backend ──enqueue──► Redis
                                │                         │
                                ▼                         ▼
                          PostgreSQL          Celery Worker + Beat
                          (ledger,              (process payouts,
                           payouts)              retry sweep)
```

### Key design decisions

- **Paise integers**: All monetary amounts use `BigInteger` in paise. No floats, no decimals.
- **Derived balance**: Balance is never stored — it's computed via `SUM(CASE...)` at query time.
- **Row-level locking**: `SELECT FOR UPDATE` on the merchant row serialises concurrent payout requests.
- **Atomic state transitions**: HOLD/RELEASE/DEBIT ledger entries are always written in the same transaction as the status change.
- **Idempotency**: Each `(merchant_id, idempotency_key)` pair is stored; replays return the cached response.

See [EXPLAINER.md](./EXPLAINER.md) for detailed technical answers.

---

## Live Deployment

| Service | Platform | URL |
|---|---|---|
| Frontend | Vercel | [payout-engine-three.vercel.app](https://payout-engine-three.vercel.app) |
| Backend API | Railway | [backend-production-cf00.up.railway.app](https://backend-production-cf00.up.railway.app) |
| API Docs | Railway | [backend-production-cf00.up.railway.app/docs](https://backend-production-cf00.up.railway.app/docs) |
| PostgreSQL | Railway | Managed (internal) |
| Redis | Railway | Managed (internal) |
| Celery Worker + Beat | Railway | Internal service |

### Deployment architecture

- **Frontend** is a static Vite build served by Vercel. API calls to `/api/*` are proxied to the Railway backend via Vercel rewrites (`frontend/vercel.json`).
- **Backend, Celery, Postgres, Redis** all run on Railway. The backend auto-runs migrations and seeds on startup.

### Deploying your own instance

**Backend (Railway):**

1. Create a Railway project with Postgres and Redis plugins
2. Add a service from the GitHub repo with root directory `backend`
3. Set environment variables:
   - `DATABASE_URL` — Postgres URL with `postgresql+asyncpg://` prefix
   - `SYNC_DATABASE_URL` — Postgres URL with `postgresql+psycopg2://` prefix
   - `REDIS_URL` — Redis URL from Railway
   - `SECRET_KEY` — any random string
4. Set start command: `sh -c "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT"`
5. Add a Celery worker service (same repo, root `backend`) with start command: `sh start_celery.sh`

**Frontend (Vercel):**

1. Import the GitHub repo on Vercel
2. Set root directory to `frontend`
3. Deploy — no environment variables needed
4. Update `frontend/vercel.json` to point the rewrite to your Railway backend URL
