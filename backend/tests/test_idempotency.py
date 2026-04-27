"""
Idempotency test: the same Idempotency-Key submitted twice must return
the same response and create exactly one payout + one HOLD entry.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerEntry, Payout, EntryType
from tests.conftest import create_test_merchant


@pytest.mark.asyncio
async def test_idempotent_payout_same_response(client: AsyncClient, db_session: AsyncSession):
    """
    Submitting the same idempotency key twice must return identical responses.
    """
    merchant, bank = await create_test_merchant(db_session, balance_paise=50_000)

    headers = {
        "X-Merchant-Id": str(merchant.id),
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    body = {"amount_paise": 10_000, "bank_account_id": str(bank.id)}

    resp1 = await client.post("/api/v1/payouts", json=body, headers=headers)
    resp2 = await client.post("/api/v1/payouts", json=body, headers=headers)

    assert resp1.status_code == 201
    assert resp2.status_code == 201

    data1 = resp1.json()
    data2 = resp2.json()

    assert data1["id"] == data2["id"], "Idempotent replays must return the same payout ID"
    assert data1["amount_paise"] == data2["amount_paise"]
    assert data1["status"] == data2["status"]

    assert resp2.headers.get("Idempotent-Replayed") == "true"


@pytest.mark.asyncio
async def test_idempotent_payout_single_record(client: AsyncClient, db_session: AsyncSession):
    """
    Exactly one Payout row and one HOLD LedgerEntry must exist after two
    identical requests.
    """
    merchant, bank = await create_test_merchant(db_session, balance_paise=50_000)
    idem_key = str(uuid.uuid4())

    headers = {
        "X-Merchant-Id": str(merchant.id),
        "Idempotency-Key": idem_key,
        "Content-Type": "application/json",
    }
    body = {"amount_paise": 10_000, "bank_account_id": str(bank.id)}

    await client.post("/api/v1/payouts", json=body, headers=headers)
    await client.post("/api/v1/payouts", json=body, headers=headers)

    payout_count = (await db_session.execute(
        select(func.count()).where(
            Payout.merchant_id == merchant.id,
            Payout.idempotency_key == idem_key,
        )
    )).scalar_one()

    hold_count = (await db_session.execute(
        select(func.count()).where(
            LedgerEntry.merchant_id == merchant.id,
            LedgerEntry.entry_type == EntryType.HOLD,
        )
    )).scalar_one()

    assert payout_count == 1, f"Expected 1 payout, found {payout_count}"
    assert hold_count == 1, f"Expected 1 HOLD entry, found {hold_count}"


@pytest.mark.asyncio
async def test_different_keys_create_separate_payouts(client: AsyncClient, db_session: AsyncSession):
    """
    Different idempotency keys must create distinct payouts.
    """
    merchant, bank = await create_test_merchant(db_session, balance_paise=50_000)

    body = {"amount_paise": 5_000, "bank_account_id": str(bank.id)}

    resp1 = await client.post("/api/v1/payouts", json=body, headers={
        "X-Merchant-Id": str(merchant.id),
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    })
    resp2 = await client.post("/api/v1/payouts", json=body, headers={
        "X-Merchant-Id": str(merchant.id),
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    })

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["id"] != resp2.json()["id"]
