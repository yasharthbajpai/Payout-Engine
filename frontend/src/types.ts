export type EntryType = "CREDIT" | "DEBIT" | "HOLD" | "RELEASE";
export type PayoutStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface BankAccount {
  id: string;
  merchant_id: string;
  account_number: string;
  ifsc_code: string;
  account_holder_name: string;
  is_primary: boolean;
  created_at: string;
}

export interface Merchant {
  id: string;
  name: string;
  email: string;
  created_at: string;
  bank_accounts: BankAccount[];
}

export interface Balance {
  merchant_id: string;
  available_balance_paise: number;
  held_balance_paise: number;
  available_balance_inr: string;
  held_balance_inr: string;
}

export interface LedgerEntry {
  id: string;
  merchant_id: string;
  entry_type: EntryType;
  amount_paise: number;
  description: string;
  reference_id: string | null;
  created_at: string;
}

export interface LedgerPage {
  items: LedgerEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface Payout {
  id: string;
  merchant_id: string;
  bank_account_id: string;
  amount_paise: number;
  status: PayoutStatus;
  attempts: number;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
}

export interface PayoutList {
  items: Payout[];
  total: number;
}

export interface PayoutCreateRequest {
  amount_paise: number;
  bank_account_id: string;
}
