# EXPLAINER

Short, specific answers to the five technical questions.

---

## 1. The Ledger

**Balance calculation query:**

```python
# backend/app/services/ledger.py

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
```

This translates to SQL:

```sql
SELECT
  COALESCE(SUM(CASE WHEN entry_type IN ('CREDIT','RELEASE') THEN amount_paise ELSE 0 END), 0)
  - COALESCE(SUM(CASE WHEN entry_type IN ('DEBIT','HOLD')   THEN amount_paise ELSE 0 END), 0)
FROM ledger_entries
WHERE merchant_id = :merchant_id;
```

**Why model it this way?**

Credits and debits are modeled as separate signed entries rather than a single running balance column for three reasons:

1. **Auditability**: Every paise movement has a row with a description and a `reference_id`. You can reconstruct the full history from the ledger alone.
2. **Correctness**: A running balance stored in a column is vulnerable to race conditions that update it with `SET balance = balance - amount`. Our approach derives the balance inside the same locked transaction as the check, making the check-and-deduct atomic.
3. **Four entry types** (CREDIT, DEBIT, HOLD, RELEASE) give us the ability to compute both *available* balance (excluding held funds) and *held* balance independently, which is essential for the payout lifecycle.

---

## 2. The Lock

**Exact code that prevents concurrent overdraft:**

```python
# backend/app/services/payout.py  (create_payout function)

async with session.begin():
    # ── CRITICAL SECTION ──────────────────────────────────────────
    # Acquire an exclusive row-level lock on the merchant.
    # A second concurrent request for the same merchant will block
    # here at the database level until this transaction commits.
    result = await session.execute(
        select(Merchant).where(Merchant.id == merchant_id).with_for_update()
    )
    merchant = result.scalar_one_or_none()

    # Compute available balance INSIDE the lock.
    # Any HOLD entries written by concurrent transactions are invisible
    # until they commit; but they can't commit until we release our lock.
    available = await compute_available_balance(session, merchant_id)

    if available < amount_paise:
        raise InsufficientBalanceError(available=available, requested=amount_paise)

    # Write HOLD entry and Payout record atomically.
    payout = Payout(...)
    session.add(payout)
    await session.flush()
    await add_ledger_entry(session, entry_type=EntryType.HOLD, ...)
    # ── END CRITICAL SECTION ──────────────────────────────────────
```

**Database primitive:** PostgreSQL row-level exclusive lock via `SELECT ... FOR UPDATE`. When two requests arrive simultaneously:

- Request A acquires the lock and sees balance = 10,000 paise.
- Request B hits `SELECT ... FOR UPDATE` and **blocks** — PostgreSQL queues it.
- Request A writes a 6,000 paise HOLD entry and commits, releasing the lock.
- Request B is unblocked, re-reads balance = 4,000 paise, and sees insufficient funds (requested 6,000). It raises `InsufficientBalanceError` (HTTP 422).

The key insight is that the balance re-read happens **inside** the lock. Without `FOR UPDATE`, both requests could read the same balance before either commits, passing the check and double-spending.

---

## 3. The Idempotency

**How the system recognises a key it has seen before:**

We store an `idempotency_records` table with a `UNIQUE(merchant_id, key)` constraint. The value stored is the original HTTP response (status code + body JSON).

```python
# backend/app/services/idempotency.py

async def get_valid_idempotency_record(session, merchant_id, key):
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
    if age_hours > settings.idempotency_ttl_hours:  # 24 hours
        await session.delete(record)
        return None

    return record
```

**What happens if the first request is still in-flight when the second arrives?**

The first request has not yet inserted the `IdempotencyRecord` (that happens at the end of the transaction). The second request therefore finds no record and also proceeds through the flow — but it hits the `UNIQUE(merchant_id, key)` constraint when trying to insert its own `IdempotencyRecord`, raising a SQLAlchemy `IntegrityError`.

We catch this in the API handler:

```python
# backend/app/api/payouts.py

except IntegrityError:
    # The first request beat us to it — read back its stored response.
    record = await get_valid_idempotency_record(new_session, merchant_id, idempotency_key)
    if record:
        return PayoutOut(**record.response_body)
    raise HTTPException(status_code=409, detail="Conflict: duplicate request in flight")
```

This means the second in-flight request either returns the stored result (if the first committed) or a 409 (if something went wrong), but never creates a duplicate payout. The `UNIQUE` constraint is the database-level safety net.

---

## 4. The State Machine

**Where failed-to-completed (and all illegal transitions) are blocked:**

```python
# backend/app/models.py

VALID_TRANSITIONS: dict[PayoutStatus, set[PayoutStatus]] = {
    PayoutStatus.PENDING:    {PayoutStatus.PROCESSING},
    PayoutStatus.PROCESSING: {PayoutStatus.COMPLETED, PayoutStatus.FAILED},
    PayoutStatus.COMPLETED:  set(),   # terminal — no outbound transitions
    PayoutStatus.FAILED:     set(),   # terminal — no outbound transitions
}

def transition_payout(payout: Payout, new_status: PayoutStatus) -> None:
    if new_status not in VALID_TRANSITIONS[payout.status]:
        raise InvalidStateTransition(
            f"Cannot transition payout from {payout.status} to {new_status}"
        )
    payout.status = new_status
    payout.updated_at = utcnow()
```

`VALID_TRANSITIONS[PayoutStatus.FAILED]` is an empty set, so **any** attempt to transition away from FAILED raises `InvalidStateTransition`. Specifically, `failed → completed` is blocked because `COMPLETED not in set()`.

Every status change in the codebase (in `tasks.py` and the retry sweep) goes through `transition_payout`, so no code path can bypass this check. The Celery task also re-reads the payout with `SELECT FOR UPDATE` before transitioning, preventing a stale-state update from a delayed worker.

---

## 5. The AI Audit

**What AI generated (subtly wrong locking):**

When I prompted for the concurrency-safe payout creation, the AI initially returned this pattern:

```python
# AI-generated (WRONG)
async def create_payout(session, merchant_id, amount_paise, ...):
    available = await compute_available_balance(session, merchant_id)  # ← outside lock
    if available < amount_paise:
        raise InsufficientBalanceError()

    async with session.begin():
        payout = Payout(...)
        session.add(payout)
        await add_ledger_entry(session, entry_type=EntryType.HOLD, ...)
```

**The bug:** The balance check (`compute_available_balance`) runs *before* acquiring any lock. Two concurrent requests can both read the same balance, both pass the check, and both insert HOLD entries — resulting in a double-spend. The `session.begin()` only prevents partial writes; it does not serialise the check-then-write sequence across concurrent connections.

**What I replaced it with:**

```python
# Corrected
async with session.begin():
    # Lock the merchant row FIRST — this is the gate
    await session.execute(
        select(Merchant).where(Merchant.id == merchant_id).with_for_update()
    )
    # THEN compute balance — now it's inside the lock
    available = await compute_available_balance(session, merchant_id)
    if available < amount_paise:
        raise InsufficientBalanceError()
    # Write atomically within the same transaction
    ...
```

The fix moves the balance read *inside* the transaction that holds the `FOR UPDATE` lock on the merchant row. The second concurrent request must wait for the first transaction to commit before it can acquire the lock — by which time the HOLD entry is visible and the balance is correctly reduced.
