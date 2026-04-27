import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import Payout
from app.schemas import PayoutCreateIn, PayoutOut
from app.services.payout import InsufficientBalanceError, create_payout

router = APIRouter(prefix="/api/v1/payouts", tags=["payouts"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PayoutOut)
async def create_payout_endpoint(
    body: PayoutCreateIn,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    merchant_id: uuid.UUID = Header(..., alias="X-Merchant-Id"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Creates a payout for the authenticated merchant.

    Idempotency: supply a unique UUID in the `Idempotency-Key` header.
    Re-sending the same key returns the original response without creating a duplicate.
    Keys are scoped per merchant and expire after 24 hours.
    """
    try:
        async with session.begin():
            payout_out, http_status, is_replay = await create_payout(
                session,
                merchant_id=merchant_id,
                amount_paise=body.amount_paise,
                bank_account_id=body.bank_account_id,
                idempotency_key=idempotency_key,
            )
    except InsufficientBalanceError:
        raise
    except IntegrityError:
        # Rare: concurrent request with same idempotency key committed first.
        # Re-open a session to read back the stored idempotency record.
        from app.database import AsyncSessionLocal
        from app.services.idempotency import get_valid_idempotency_record
        async with AsyncSessionLocal() as new_session:
            record = await get_valid_idempotency_record(new_session, merchant_id, idempotency_key)
            if record:
                response.status_code = record.response_status
                return PayoutOut(**record.response_body)
        raise HTTPException(status_code=409, detail="Conflict: duplicate request in flight")

    response.status_code = http_status
    if is_replay:
        response.headers["Idempotent-Replayed"] = "true"

    # Enqueue background processing
    if not is_replay:
        from app.worker.tasks import process_payout
        process_payout.apply_async(args=[str(payout_out.id)], countdown=1)

    return payout_out


@router.get("/{payout_id}", response_model=PayoutOut)
async def get_payout(
    payout_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(Payout).where(Payout.id == payout_id))
    payout = result.scalar_one_or_none()
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout not found")
    return PayoutOut.model_validate(payout)
