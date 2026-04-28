"""
Seed script: creates 3 merchants with bank accounts, credit history, and sample payouts.
Run with: python -m app.seed
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SyncSessionLocal
from app.models import (
    BankAccount,
    EntryType,
    LedgerEntry,
    Merchant,
    Payout,
    PayoutStatus,
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


MERCHANTS = [
    {
        "name": "Arjun Sharma Designs",
        "email": "arjun@arjundesigns.in",
        "bank": {
            "account_number": "50100123456789",
            "ifsc_code": "HDFC0001234",
            "account_holder_name": "Arjun Sharma",
        },
        "credits": [
            (75000, "Payment from Acme Corp USA – Project Alpha"),
            (120000, "Payment from DesignHub SF – Logo Redesign"),
            (55000, "Payment from TechStart NYC – UI Kit"),
            (200000, "Payment from GlobalBrand Ltd – Brand Identity"),
            (35000, "Payment from SmallBiz Inc – Business Cards"),
        ],
    },
    {
        "name": "Priya Consulting",
        "email": "priya@priyaconsulting.io",
        "bank": {
            "account_number": "919012345678901",
            "ifsc_code": "ICIC0002345",
            "account_holder_name": "Priya Nair",
        },
        "credits": [
            (300000, "Consulting retainer – Stripe Integration"),
            (150000, "Advisory fee – Q1 Growth Strategy"),
            (80000, "Workshop delivery – Remote Teams"),
            (250000, "Consulting retainer – Payments Architecture"),
            (45000, "Speaking engagement – FinTech Summit"),
        ],
    },
    {
        "name": "Dev Studio by Rahul",
        "email": "rahul@devstudio.dev",
        "bank": {
            "account_number": "62011234567890",
            "ifsc_code": "SBIN0003456",
            "account_holder_name": "Rahul Gupta",
        },
        "credits": [
            (500000, "Full-stack project – E-commerce Platform"),
            (180000, "API development – Mobile Backend"),
            (90000, "Code review and audit – Startup SaaS"),
            (220000, "DevOps setup – CI/CD Pipeline"),
            (60000, "Bug fixes – Legacy System"),
        ],
    },
]


def seed():
    with SyncSessionLocal() as session:
        existing = session.query(Merchant).count()
        if existing > 0:
            print("Database already seeded. Skipping.")
            return

        for i, data in enumerate(MERCHANTS):
            merchant = Merchant(
                id=uuid.uuid4(),
                name=data["name"],
                email=data["email"],
                created_at=utcnow() - timedelta(days=90 - i * 10),
            )
            session.add(merchant)
            session.flush()

            bank = BankAccount(
                id=uuid.uuid4(),
                merchant_id=merchant.id,
                account_number=data["bank"]["account_number"],
                ifsc_code=data["bank"]["ifsc_code"],
                account_holder_name=data["bank"]["account_holder_name"],
                is_primary=True,
                created_at=merchant.created_at,
            )
            session.add(bank)

            # Seed credit entries spread over last 90 days
            total_credited = 0
            for j, (amount, desc) in enumerate(data["credits"]):
                days_ago = 80 - j * 12
                entry = LedgerEntry(
                    id=uuid.uuid4(),
                    merchant_id=merchant.id,
                    entry_type=EntryType.CREDIT,
                    amount_paise=amount,
                    description=desc,
                    created_at=utcnow() - timedelta(days=days_ago),
                )
                session.add(entry)
                total_credited += amount

            # Seed 2 completed payouts with corresponding ledger entries
            payout_amounts = [int(total_credited * 0.10), int(total_credited * 0.15)]
            for k, payout_amount in enumerate(payout_amounts):
                days_ago = 20 - k * 7
                payout_id = uuid.uuid4()
                idempotency_key = str(uuid.uuid4())

                payout = Payout(
                    id=payout_id,
                    merchant_id=merchant.id,
                    bank_account_id=bank.id,
                    amount_paise=payout_amount,
                    status=PayoutStatus.COMPLETED,
                    attempts=1,
                    idempotency_key=idempotency_key,
                    created_at=utcnow() - timedelta(days=days_ago),
                    updated_at=utcnow() - timedelta(days=days_ago) + timedelta(seconds=30),
                )
                session.add(payout)

                # HOLD then DEBIT (reflecting completed payout lifecycle)
                session.add(LedgerEntry(
                    id=uuid.uuid4(),
                    merchant_id=merchant.id,
                    entry_type=EntryType.HOLD,
                    amount_paise=payout_amount,
                    description=f"Hold for payout {payout_id}",
                    reference_id=payout_id,
                    created_at=utcnow() - timedelta(days=days_ago),
                ))
                session.add(LedgerEntry(
                    id=uuid.uuid4(),
                    merchant_id=merchant.id,
                    entry_type=EntryType.DEBIT,
                    amount_paise=payout_amount,
                    description=f"Payout {payout_id} completed",
                    reference_id=payout_id,
                    created_at=utcnow() - timedelta(days=days_ago) + timedelta(seconds=30),
                ))

            session.commit()
            print(f"Seeded: {merchant.name} (id={merchant.id})")

        print("Seeding complete.")


if __name__ == "__main__":
    seed()
