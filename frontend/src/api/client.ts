import axios from "axios";
import type {
  Balance,
  LedgerPage,
  Merchant,
  Payout,
  PayoutCreateRequest,
  PayoutList,
} from "../types";

const BASE = "/api/v1";

export const api = axios.create({ baseURL: BASE });

export async function fetchMerchants(): Promise<Merchant[]> {
  const { data } = await api.get("/merchants");
  return data;
}

export async function fetchBalance(merchantId: string): Promise<Balance> {
  const { data } = await api.get(`/merchants/${merchantId}/balance`);
  return data;
}

export async function fetchLedger(
  merchantId: string,
  page = 1,
  pageSize = 20
): Promise<LedgerPage> {
  const { data } = await api.get(`/merchants/${merchantId}/ledger`, {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function fetchPayouts(
  merchantId: string,
  page = 1,
  pageSize = 20
): Promise<PayoutList> {
  const { data } = await api.get(`/merchants/${merchantId}/payouts`, {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function createPayout(
  merchantId: string,
  idempotencyKey: string,
  payload: PayoutCreateRequest
): Promise<Payout> {
  const { data } = await api.post("/payouts", payload, {
    headers: {
      "X-Merchant-Id": merchantId,
      "Idempotency-Key": idempotencyKey,
    },
  });
  return data;
}
