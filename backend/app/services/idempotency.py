import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import IdempotencyRecord


async def get_valid_idempotency_record(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    key: str,
) -> IdempotencyRecord | None:
    """
    Returns the stored record if it exists and is within the 24-hour TTL.
    Deletes expired records and returns None so the caller treats it as a new request.
    """
    result = await session.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.merchant_id == merchant_id,
            IdempotencyRecord.key == key,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    age_hours = (datetime.utcnow() - record.created_at).total_seconds() / 3600
    if age_hours > settings.idempotency_ttl_hours:
        await session.delete(record)
        await session.flush()
        return None

    return record


async def store_idempotency_record(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    key: str,
    response_status: int,
    response_body: dict,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        merchant_id=merchant_id,
        key=key,
        response_status=response_status,
        response_body=response_body,
    )
    session.add(record)
    return record
