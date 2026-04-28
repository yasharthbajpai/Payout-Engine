"""
Concurrency test: two simultaneous payout requests for a merchant with 10,000 paise (₹100).
Each requests 6,000 paise (₹60). Exactly one must succeed and one must fail.
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import create_test_merchant
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_concurrent_payouts_exactly_one_succeeds(client: AsyncClient, db_session: AsyncSession):
    """
    Concurrency invariant: two simultaneous 6000-paise requests against a
    10000-paise balance must produce exactly one 201 and one 422 (or 409).
    """
    merchant, bank = await create_test_merchant(db_session, balance_paise=10_000)

    headers_base = {
        "X-Merchant-Id": str(merchant.id),
        "Content-Type": "application/json",
    }
    body = {"amount_paise": 6000, "bank_account_id": str(bank.id)}

    async def attempt_payout(key: str):
        headers = {**headers_base, "Idempotency-Key": key}
        response = await client.post("/api/v1/payouts", json=body, headers=headers)
        return response.status_code

    key1 = str(uuid.uuid4())
    key2 = str(uuid.uuid4())

    statuses = await asyncio.gather(
        attempt_payout(key1),
        attempt_payout(key2),
    )

    successes = statuses.count(201)
    failures = sum(1 for s in statuses if s in (422, 409, 400))

    assert successes == 1, f"Expected exactly 1 success, got statuses: {statuses}"
    assert failures == 1, f"Expected exactly 1 failure, got statuses: {statuses}"


@pytest.mark.asyncio
async def test_concurrent_payouts_balance_integrity(client: AsyncClient, db_session: AsyncSession):
    """
    After one successful 6000-paise payout against a 10000-paise balance,
    the available balance must be 4000 paise (funds are held, not gone).
    """
    merchant, bank = await create_test_merchant(db_session, balance_paise=10_000)

    headers = {
        "X-Merchant-Id": str(merchant.id),
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    body = {"amount_paise": 6000, "bank_account_id": str(bank.id)}

    resp = await client.post("/api/v1/payouts", json=body, headers=headers)
    assert resp.status_code == 201

    balance_resp = await client.get(f"/api/v1/merchants/{merchant.id}/balance")
    assert balance_resp.status_code == 200
    balance = balance_resp.json()

    # Available = 10000 credit - 6000 hold = 4000
    assert balance["available_balance_paise"] == 4000
    assert balance["held_balance_paise"] == 6000
