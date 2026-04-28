from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.merchants import router as merchants_router
from app.api.payouts import router as payouts_router
from app.database import async_engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created via Alembic in production; this is a dev fallback.
    yield


app = FastAPI(
    title="Playto Payout Engine",
    version="1.0.0",
    description="Merchant payout engine with ledger, concurrency-safe balance, and idempotent payouts.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(merchants_router)
app.include_router(payouts_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
