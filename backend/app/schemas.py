import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models import EntryType, PayoutStatus


# ---- Merchant ----

class BankAccountOut(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    account_number: str
    ifsc_code: str
    account_holder_name: str
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MerchantOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    created_at: datetime
    bank_accounts: list[BankAccountOut] = []

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    merchant_id: uuid.UUID
    available_balance_paise: int
    held_balance_paise: int
    available_balance_inr: str
    held_balance_inr: str


# ---- Ledger ----

class LedgerEntryOut(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    entry_type: EntryType
    amount_paise: int
    description: str
    reference_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LedgerPageOut(BaseModel):
    items: list[LedgerEntryOut]
    total: int
    page: int
    page_size: int


# ---- Payout ----

class PayoutCreateIn(BaseModel):
    amount_paise: int
    bank_account_id: uuid.UUID

    @field_validator("amount_paise")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_paise must be positive")
        return v


class PayoutOut(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    bank_account_id: uuid.UUID
    amount_paise: int
    status: PayoutStatus
    attempts: int
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PayoutListOut(BaseModel):
    items: list[PayoutOut]
    total: int


# ---- Error ----

class ErrorOut(BaseModel):
    detail: str
    code: str | None = None
