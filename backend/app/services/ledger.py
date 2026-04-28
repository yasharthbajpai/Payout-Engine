import uuid
from datetime import datetime, timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import EntryType, LedgerEntry


async def compute_available_balance(session: AsyncSession, merchant_id: uuid.UUID) -> int:
    """
    Derives available balance purely via a DB-level SUM(CASE...) query.
    Never fetches rows into Python for arithmetic.
    """
    result = await session.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.entry_type.in_([EntryType.CREDIT, EntryType.RELEASE]), LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            )
            - func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.entry_type.in_([EntryType.DEBIT, EntryType.HOLD]), LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(LedgerEntry.merchant_id == merchant_id)
    )
    return int(result.scalar_one())


async def compute_held_balance(session: AsyncSession, merchant_id: uuid.UUID) -> int:
    """
    Held balance = sum of HOLD entries - sum of RELEASE/DEBIT entries that
    correspond to those holds (i.e. entries that have a reference_id).
    """
    result = await session.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.entry_type == EntryType.HOLD, LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            )
            - func.coalesce(
                func.sum(
                    case(
                        (
                            LedgerEntry.entry_type.in_([EntryType.RELEASE, EntryType.DEBIT]),
                            LedgerEntry.amount_paise,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(
            LedgerEntry.merchant_id == merchant_id,
            LedgerEntry.reference_id.isnot(None),
        )
    )
    return max(0, int(result.scalar_one()))


async def add_ledger_entry(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    entry_type: EntryType,
    amount_paise: int,
    description: str,
    reference_id: uuid.UUID | None = None,
) -> LedgerEntry:
    entry = LedgerEntry(
        merchant_id=merchant_id,
        entry_type=entry_type,
        amount_paise=amount_paise,
        description=description,
        reference_id=reference_id,
    )
    session.add(entry)
    return entry


# Sync versions for Celery workers

def sync_compute_available_balance(session: Session, merchant_id: uuid.UUID) -> int:
    result = session.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.entry_type.in_([EntryType.CREDIT, EntryType.RELEASE]), LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            )
            - func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.entry_type.in_([EntryType.DEBIT, EntryType.HOLD]), LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(LedgerEntry.merchant_id == merchant_id)
    )
    return int(result.scalar_one())


def sync_add_ledger_entry(
    session: Session,
    merchant_id: uuid.UUID,
    entry_type: EntryType,
    amount_paise: int,
    description: str,
    reference_id: uuid.UUID | None = None,
) -> LedgerEntry:
    entry = LedgerEntry(
        merchant_id=merchant_id,
        entry_type=entry_type,
        amount_paise=amount_paise,
        description=description,
        reference_id=reference_id,
    )
    session.add(entry)
    return entry
