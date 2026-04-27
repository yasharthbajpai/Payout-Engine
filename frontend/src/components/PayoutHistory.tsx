import type { Payout, PayoutStatus } from "../types";

const STATUS_STYLES: Record<PayoutStatus, string> = {
  PENDING: "bg-yellow-900/50 text-yellow-300 border border-yellow-700",
  PROCESSING: "bg-blue-900/50 text-blue-300 border border-blue-700",
  COMPLETED: "bg-emerald-900/50 text-emerald-300 border border-emerald-700",
  FAILED: "bg-red-900/50 text-red-300 border border-red-700",
};

interface Props {
  payouts: Payout[];
  loading: boolean;
}

function formatPaise(paise: number): string {
  return `₹${(paise / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
  })}`;
}

export function PayoutHistory({ payouts, loading }: Props) {
  return (
    <div className="rounded-2xl bg-slate-800 border border-slate-700 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-100">
          Payout History
        </h2>
        <span className="text-xs text-slate-500">Auto-refreshes every 3s</span>
      </div>

      {loading && payouts.length === 0 ? (
        <div className="p-6 space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-10 bg-slate-700 rounded animate-pulse" />
          ))}
        </div>
      ) : payouts.length === 0 ? (
        <p className="px-6 py-8 text-sm text-slate-500 text-center">
          No payouts yet. Request one above.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700">
                <th className="px-6 py-3 text-left">ID</th>
                <th className="px-6 py-3 text-right">Amount</th>
                <th className="px-6 py-3 text-center">Status</th>
                <th className="px-6 py-3 text-center hidden sm:table-cell">
                  Attempts
                </th>
                <th className="px-6 py-3 text-right">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {payouts.map((payout) => (
                <tr
                  key={payout.id}
                  className="hover:bg-slate-750 transition-colors"
                >
                  <td className="px-6 py-3 font-mono text-xs text-slate-400">
                    {payout.id.slice(0, 8)}…
                  </td>
                  <td className="px-6 py-3 text-right font-semibold text-slate-200 font-mono">
                    {formatPaise(payout.amount_paise)}
                  </td>
                  <td className="px-6 py-3 text-center">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLES[payout.status]}`}
                    >
                      {payout.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-center text-slate-400 hidden sm:table-cell">
                    {payout.attempts}
                  </td>
                  <td className="px-6 py-3 text-right text-slate-500 whitespace-nowrap">
                    {new Date(payout.created_at).toLocaleDateString("en-IN", {
                      day: "2-digit",
                      month: "short",
                    })}{" "}
                    {new Date(payout.created_at).toLocaleTimeString("en-IN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
