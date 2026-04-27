import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { createPayout } from "../api/client";
import type { BankAccount } from "../types";

interface Props {
  merchantId: string;
  bankAccounts: BankAccount[];
  onSuccess: () => void;
}

export function PayoutForm({ merchantId, bankAccounts, onSuccess }: Props) {
  const [amountInr, setAmountInr] = useState("");
  const [bankAccountId, setBankAccountId] = useState(
    bankAccounts[0]?.id ?? ""
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const rupees = parseFloat(amountInr);
    if (isNaN(rupees) || rupees <= 0) {
      setError("Enter a valid amount in rupees.");
      return;
    }

    const paise = Math.round(rupees * 100);
    const idempotencyKey = uuidv4();

    setLoading(true);
    try {
      const payout = await createPayout(merchantId, idempotencyKey, {
        amount_paise: paise,
        bank_account_id: bankAccountId,
      });
      setSuccess(`Payout ${payout.id.slice(0, 8)}… created (${payout.status})`);
      setAmountInr("");
      onSuccess();
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ?? "Failed to create payout.";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl bg-slate-800 border border-slate-700 p-6">
      <h2 className="text-base font-semibold text-slate-100 mb-4">
        Request Payout
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">
            Amount (₹)
          </label>
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={amountInr}
            onChange={(e) => setAmountInr(e.target.value)}
            placeholder="e.g. 500.00"
            className="w-full rounded-lg bg-slate-900 border border-slate-600 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            required
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">
            Bank Account
          </label>
          <select
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            className="w-full rounded-lg bg-slate-900 border border-slate-600 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {bankAccounts.map((ba) => (
              <option key={ba.id} value={ba.id}>
                {ba.account_holder_name} — ···{ba.account_number.slice(-4)} (
                {ba.ifsc_code})
              </option>
            ))}
          </select>
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-950 border border-red-800 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        {success && (
          <p className="text-xs text-emerald-400 bg-emerald-950 border border-emerald-800 rounded-lg px-3 py-2">
            {success}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-white transition-colors"
        >
          {loading ? "Processing…" : "Request Payout"}
        </button>
      </form>
    </div>
  );
}
