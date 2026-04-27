import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_session
from app.models import LedgerEntry, Merchant
from app.schemas import BalanceOut, LedgerEntryOut, LedgerPageOut, MerchantOut
from app.services.ledger import compute_available_balance, compute_held_balance


def paise_to_inr_str(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


router = APIRouter(prefix="/api/v1/merchants", tags=["merchants"])


@router.get("", response_model=list[MerchantOut])
async def list_merchants(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(
        select(Merchant).options(selectinload(Merchant.bank_accounts)).order_by(Merchant.created_at)
    )
    return result.scalars().all()


@router.get("/{merchant_id}/balance", response_model=BalanceOut)
async def get_balance(
    merchant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found")

    available = await compute_available_balance(session, merchant_id)
    held = await compute_held_balance(session, merchant_id)

    return BalanceOut(
        merchant_id=merchant_id,
        available_balance_paise=available,
        held_balance_paise=held,
        available_balance_inr=paise_to_inr_str(available),
        held_balance_inr=paise_to_inr_str(held),
    )


@router.get("/{merchant_id}/ledger", response_model=LedgerPageOut)
async def get_ledger(
    merchant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(Merchant).where(Merchant.id == merchant_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Merchant not found")

    count_result = await session.execute(
        select(func.count()).where(LedgerEntry.merchant_id == merchant_id)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    entries_result = await session.execute(
        select(LedgerEntry)
        .where(LedgerEntry.merchant_id == merchant_id)
        .order_by(LedgerEntry.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = entries_result.scalars().all()

    return LedgerPageOut(
        items=[LedgerEntryOut.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{merchant_id}/payouts")
async def get_merchant_payouts(
    merchant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    from app.models import Payout
    from app.schemas import PayoutListOut, PayoutOut

    result = await session.execute(select(Merchant).where(Merchant.id == merchant_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Merchant not found")

    count_result = await session.execute(
        select(func.count()).where(Payout.merchant_id == merchant_id)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    payouts_result = await session.execute(
        select(Payout)
        .where(Payout.merchant_id == merchant_id)
        .order_by(Payout.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = payouts_result.scalars().all()

    return PayoutListOut(
        items=[PayoutOut.model_validate(p) for p in items],
        total=total,
    )
