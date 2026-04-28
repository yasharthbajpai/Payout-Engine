import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBalance, fetchLedger, fetchMerchants, fetchPayouts } from "./api/client";
import { BalanceCard } from "./components/BalanceCard";
import { LedgerTable } from "./components/LedgerTable";
import { PayoutForm } from "./components/PayoutForm";
import { PayoutHistory } from "./components/PayoutHistory";
import type { Balance, LedgerEntry, Merchant, Payout } from "./types";

export default function App() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [balance, setBalance] = useState<Balance | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [payoutsLoading, setPayoutsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchMerchants()
      .then((data) => {
        setMerchants(data);
        if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch(() => setError("Could not load merchants. Is the backend running?"));
  }, []);

  const loadData = useCallback(async (id: string) => {
    if (!id) return;
    setBalanceLoading(true);
    setLedgerLoading(true);
    setPayoutsLoading(true);
    try {
      const [bal, led, pay] = await Promise.all([
        fetchBalance(id),
        fetchLedger(id),
        fetchPayouts(id),
      ]);
      setBalance(bal);
      setLedger(led.items);
      setPayouts(pay.items);
    } catch {
      // silently ignore polling errors
    } finally {
      setBalanceLoading(false);
      setLedgerLoading(false);
      setPayoutsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setBalance(null);
    setLedger([]);
    setPayouts([]);
    loadData(selectedId);

    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => loadData(selectedId), 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedId, loadData]);

  const selectedMerchant = merchants.find((m) => m.id === selectedId);

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">
              P
            </div>
            <span className="font-semibold text-slate-100">Playto Pay</span>
            <span className="hidden sm:inline text-slate-500 text-sm">
              Payout Engine
            </span>
          </div>

          {merchants.length > 0 && (
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="rounded-lg bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 max-w-xs"
            >
              {merchants.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {error && (
          <div className="rounded-xl bg-red-950 border border-red-800 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {selectedMerchant && (
          <div>
            <h1 className="text-xl font-bold text-slate-100">
              {selectedMerchant.name}
            </h1>
            <p className="text-sm text-slate-500">{selectedMerchant.email}</p>
          </div>
        )}

        {/* Balance cards */}
        <BalanceCard balance={balance} loading={balanceLoading} />

        {/* Payout form + history */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            {selectedMerchant && (
              <PayoutForm
                merchantId={selectedId}
                bankAccounts={selectedMerchant.bank_accounts}
                onSuccess={() => loadData(selectedId)}
              />
            )}
          </div>
          <div className="lg:col-span-2">
            <PayoutHistory payouts={payouts} loading={payoutsLoading} />
          </div>
        </div>

        {/* Ledger */}
        <LedgerTable entries={ledger} loading={ledgerLoading} />
      </main>

      <footer className="border-t border-slate-800 mt-12 py-6 text-center text-xs text-slate-600">
        Playto Payout Engine — FastAPI + PostgreSQL + Celery + React
      </footer>
    </div>
  );
}
