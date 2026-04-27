import random
import uuid
from datetime import datetime, timedelta

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SyncSessionLocal
from app.models import EntryType, Payout, PayoutStatus, transition_payout, InvalidStateTransition
from app.services.ledger import sync_add_ledger_entry
from app.worker.celery_app import celery_app

logger = get_task_logger(__name__)

MAX_ATTEMPTS = 3
STUCK_THRESHOLD_SECONDS = 30


@celery_app.task(name="app.worker.tasks.process_payout", bind=True, max_retries=0)
def process_payout(self, payout_id: str) -> dict:
    """
    Simulates bank settlement:
      - 70% success  -> PROCESSING -> COMPLETED + DEBIT entry
      - 20% failure  -> PROCESSING -> FAILED   + RELEASE entry (funds returned atomically)
      - 10% hang     -> stays in PROCESSING (retry sweep will pick it up)
    """
    pid = uuid.UUID(payout_id)

    with SyncSessionLocal() as session:
        with session.begin():
            payout = session.execute(
                select(Payout).where(Payout.id == pid).with_for_update()
            ).scalar_one_or_none()

            if payout is None:
                logger.error("Payout %s not found", payout_id)
                return {"error": "not_found"}

            if payout.status != PayoutStatus.PENDING:
                logger.warning("Payout %s is not PENDING (status=%s), skipping", payout_id, payout.status)
                return {"status": payout.status}

            try:
                transition_payout(payout, PayoutStatus.PROCESSING)
            except InvalidStateTransition as exc:
                logger.error("Invalid transition: %s", exc)
                return {"error": str(exc)}

            payout.attempts += 1
            session.flush()

    # Simulate network call outside transaction so we don't hold locks during I/O
    outcome = _simulate_bank_call()

    if outcome == "hang":
        logger.info("Payout %s is hanging (will be retried by sweep)", payout_id)
        return {"status": "hanging"}

    with SyncSessionLocal() as session:
        with session.begin():
            payout = session.execute(
                select(Payout).where(Payout.id == pid).with_for_update()
            ).scalar_one_or_none()

            if payout is None or payout.status != PayoutStatus.PROCESSING:
                return {"status": payout.status if payout else "missing"}

            if outcome == "success":
                transition_payout(payout, PayoutStatus.COMPLETED)
                sync_add_ledger_entry(
                    session,
                    merchant_id=payout.merchant_id,
                    entry_type=EntryType.DEBIT,
                    amount_paise=payout.amount_paise,
                    description=f"Payout {payout.id} completed",
                    reference_id=payout.id,
                )
                logger.info("Payout %s completed successfully", payout_id)

            elif outcome == "failure":
                transition_payout(payout, PayoutStatus.FAILED)
                sync_add_ledger_entry(
                    session,
                    merchant_id=payout.merchant_id,
                    entry_type=EntryType.RELEASE,
                    amount_paise=payout.amount_paise,
                    description=f"Payout {payout.id} failed – funds released",
                    reference_id=payout.id,
                )
                logger.info("Payout %s failed, funds released", payout_id)

    return {"status": outcome}


@celery_app.task(name="app.worker.tasks.retry_stuck_payouts")
def retry_stuck_payouts() -> dict:
    """
    Periodic sweep: finds payouts stuck in PROCESSING for > 30 seconds.
    - attempts < MAX_ATTEMPTS: re-enqueue process_payout with exponential backoff.
    - attempts >= MAX_ATTEMPTS: mark FAILED and release funds atomically.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=STUCK_THRESHOLD_SECONDS)
    retried = 0
    failed = 0

    # Read stuck payouts in a short read transaction, then process each individually.
    with SyncSessionLocal() as session:
        with session.begin():
            stuck_ids = [
                row.id
                for row in session.execute(
                    select(Payout.id).where(
                        Payout.status == PayoutStatus.PROCESSING,
                        Payout.updated_at < cutoff,
                    )
                ).scalars()
            ]

    for payout_id_stuck in stuck_ids:
        # Re-read with FOR UPDATE inside its own transaction so we hold the lock
        # only for the duration of this single payout's update.
        with SyncSessionLocal() as session:
            with session.begin():
                payout_locked = session.execute(
                    select(Payout).where(Payout.id == payout_id_stuck).with_for_update()
                ).scalar_one_or_none()

                if payout_locked is None or payout_locked.status != PayoutStatus.PROCESSING:
                    continue

                if payout_locked.attempts < MAX_ATTEMPTS:
                    delay = (2 ** payout_locked.attempts) * 5  # 10s, 20s, 40s
                    process_payout.apply_async(args=[str(payout_locked.id)], countdown=delay)
                    logger.info(
                        "Re-enqueued stuck payout %s (attempt %d) with delay %ds",
                        payout_locked.id, payout_locked.attempts, delay,
                    )
                    retried += 1
                else:
                    transition_payout(payout_locked, PayoutStatus.FAILED)
                    sync_add_ledger_entry(
                        session,
                        merchant_id=payout_locked.merchant_id,
                        entry_type=EntryType.RELEASE,
                        amount_paise=payout_locked.amount_paise,
                        description=(
                            f"Payout {payout_locked.id} timed out after "
                            f"{MAX_ATTEMPTS} attempts – funds released"
                        ),
                        reference_id=payout_locked.id,
                    )
                    logger.info("Payout %s exhausted retries, marked FAILED", payout_locked.id)
                    failed += 1

    return {"retried": retried, "failed": failed}


def _simulate_bank_call() -> str:
    """70% success, 20% failure, 10% hang."""
    roll = random.random()
    if roll < 0.70:
        return "success"
    elif roll < 0.90:
        return "failure"
    else:
        return "hang"
