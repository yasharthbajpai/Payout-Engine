"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-27

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "bank_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("account_number", sa.String(30), nullable=False),
        sa.Column("ifsc_code", sa.String(11), nullable=False),
        sa.Column("account_holder_name", sa.String(255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "payouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="payout_status_enum"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, default=0),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("merchant_id", "idempotency_key", name="uq_payout_merchant_idempotency"),
    )
    op.create_index("ix_payouts_merchant_id", "payouts", ["merchant_id"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum("CREDIT", "DEBIT", "HOLD", "RELEASE", name="entry_type_enum"),
            nullable=False,
        ),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ledger_entries_merchant_id", "ledger_entries", ["merchant_id"])
    op.create_index("ix_ledger_entries_created_at", "ledger_entries", ["created_at"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("merchant_id", "key", name="uq_idempotency_merchant_key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_ledger_entries_created_at", "ledger_entries")
    op.drop_index("ix_ledger_entries_merchant_id", "ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_payouts_merchant_id", "payouts")
    op.drop_table("payouts")
    op.drop_table("bank_accounts")
    op.drop_table("merchants")
    op.execute("DROP TYPE IF EXISTS entry_type_enum")
    op.execute("DROP TYPE IF EXISTS payout_status_enum")
