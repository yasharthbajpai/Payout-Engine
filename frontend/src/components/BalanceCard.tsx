import type { Balance } from "../types";

interface Props {
  balance: Balance | null;
  loading: boolean;
}

export function BalanceCard({ balance, loading }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div className="rounded-2xl bg-slate-800 border border-slate-700 p-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-1">
          Available Balance
        </p>
        {loading || !balance ? (
          <div className="h-9 w-36 bg-slate-700 rounded animate-pulse" />
        ) : (
          <p className="text-3xl font-bold text-emerald-400">
            {balance.available_balance_inr}
          </p>
        )}
        {balance && !loading && (
          <p className="text-xs text-slate-500 mt-1">
            {balance.available_balance_paise.toLocaleString()} paise
          </p>
        )}
      </div>

      <div className="rounded-2xl bg-slate-800 border border-slate-700 p-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-1">
          Held Balance
        </p>
        {loading || !balance ? (
          <div className="h-9 w-36 bg-slate-700 rounded animate-pulse" />
        ) : (
          <p className="text-3xl font-bold text-amber-400">
            {balance.held_balance_inr}
          </p>
        )}
        {balance && !loading && (
          <p className="text-xs text-slate-500 mt-1">
            {balance.held_balance_paise.toLocaleString()} paise
          </p>
        )}
      </div>
    </div>
  );
}
