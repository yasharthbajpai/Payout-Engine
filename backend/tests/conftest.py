"""
Shared test fixtures and database setup.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.models import Base, BankAccount, EntryType, LedgerEntry, Merchant
from app.database import get_async_session

TEST_DB_URL = "postgresql+asyncpg://paytopay:paytopay@localhost:5432/paytopay_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine):
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def create_test_merchant(session: AsyncSession, balance_paise: int = 10000) -> tuple:
    """Create a merchant with a given balance (via CREDIT entries) and return (merchant, bank_account)."""
    merchant = Merchant(
        id=uuid.uuid4(),
        name="Test Merchant",
        email=f"test-{uuid.uuid4()}@example.com",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(merchant)
    await session.flush()

    bank = BankAccount(
        id=uuid.uuid4(),
        merchant_id=merchant.id,
        account_number="50100000000001",
        ifsc_code="HDFC0000001",
        account_holder_name="Test User",
        is_primary=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(bank)

    credit = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=merchant.id,
        entry_type=EntryType.CREDIT,
        amount_paise=balance_paise,
        description="Test seed credit",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(credit)
    await session.commit()

    return merchant, bank
