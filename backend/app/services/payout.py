import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BankAccount,
    EntryType,
    Merchant,
    Payout,
    PayoutStatus,
)
from app.schemas import PayoutOut
from app.services.idempotency import get_valid_idempotency_record, store_idempotency_record
from app.services.ledger import add_ledger_entry, compute_available_balance


class InsufficientBalanceError(HTTPException):
    def __init__(self, available: int, requested: int):
        super().__init__(
            status_code=422,
            detail=f"Insufficient balance. Available: {available} paise, requested: {requested} paise",
        )


async def create_payout(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    amount_paise: int,
    bank_account_id: uuid.UUID,
    idempotency_key: str,
) -> tuple[PayoutOut, int, bool]:
    """
    Creates a payout atomically with concurrency guard.

    Returns (payout_out, http_status_code, is_idempotent_replay).

    Concurrency safety:
      - We acquire a SELECT FOR UPDATE lock on the Merchant row.
      - All subsequent balance reads and ledger writes happen within that lock.
      - A second concurrent request for the same merchant blocks until the first
        transaction commits, at which point the balance reflects the first HOLD
        and the second request correctly sees insufficient funds.
    """
    # Check idempotency BEFORE acquiring the row lock to fast-exit duplicates.
    existing = await get_valid_idempotency_record(session, merchant_id, idempotency_key)
    if existing is not None:
        return PayoutOut(**existing.response_body), existing.response_status, True

    # --- Acquire exclusive row lock on the merchant ---
    # This is the critical section: any concurrent payout attempt for the same
    # merchant will block here until we commit, preventing double-spend.
    result = await session.execute(
        select(Merchant).where(Merchant.id == merchant_id).with_for_update()
    )
    merchant = result.scalar_one_or_none()
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # Verify bank account belongs to this merchant
    ba_result = await session.execute(
        select(BankAccount).where(
            BankAccount.id == bank_account_id,
            BankAccount.merchant_id == merchant_id,
        )
    )
    bank_account = ba_result.scalar_one_or_none()
    if bank_account is None:
        raise HTTPException(status_code=404, detail="Bank account not found for this merchant")

    # Compute available balance INSIDE the lock -- this is atomic w.r.t. other payout requests
    available = await compute_available_balance(session, merchant_id)
    if available < amount_paise:
        raise InsufficientBalanceError(available=available, requested=amount_paise)

    # Create payout record
    payout = Payout(
        merchant_id=merchant_id,
        bank_account_id=bank_account_id,
        amount_paise=amount_paise,
        status=PayoutStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    session.add(payout)
    await session.flush()  # populate payout.id

    # Create HOLD ledger entry in the same transaction
    await add_ledger_entry(
        session,
        merchant_id=merchant_id,
        entry_type=EntryType.HOLD,
        amount_paise=amount_paise,
        description=f"Hold for payout {payout.id}",
        reference_id=payout.id,
    )
    await session.flush()

    payout_out = PayoutOut.model_validate(payout)
    response_body = payout_out.model_dump(mode="json")

    # Store idempotency record so duplicate requests return the same response
    await store_idempotency_record(
        session,
        merchant_id=merchant_id,
        key=idempotency_key,
        response_status=201,
        response_body=response_body,
    )

    return payout_out, 201, False
