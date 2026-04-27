import type { LedgerEntry } from "../types";

const ENTRY_COLORS: Record<string, string> = {
  CREDIT: "text-emerald-400",
  DEBIT: "text-red-400",
  HOLD: "text-amber-400",
  RELEASE: "text-sky-400",
};

const ENTRY_SIGN: Record<string, string> = {
  CREDIT: "+",
  DEBIT: "−",
  HOLD: "↓",
  RELEASE: "↑",
};

interface Props {
  entries: LedgerEntry[];
  loading: boolean;
}

function formatPaise(paise: number): string {
  return `₹${(paise / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
  })}`;
}

export function LedgerTable({ entries, loading }: Props) {
  return (
    <div className="rounded-2xl bg-slate-800 border border-slate-700 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-100">
          Recent Transactions
        </h2>
      </div>

      {loading ? (
        <div className="p-6 space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-10 bg-slate-700 rounded animate-pulse" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <p className="px-6 py-8 text-sm text-slate-500 text-center">
          No transactions yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700">
                <th className="px-6 py-3 text-left">Type</th>
                <th className="px-6 py-3 text-right">Amount</th>
                <th className="px-6 py-3 text-left hidden md:table-cell">
                  Description
                </th>
                <th className="px-6 py-3 text-right">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  className="hover:bg-slate-750 transition-colors"
                >
                  <td className="px-6 py-3">
                    <span
                      className={`inline-flex items-center gap-1 font-medium ${ENTRY_COLORS[entry.entry_type]}`}
                    >
                      <span className="font-mono">
                        {ENTRY_SIGN[entry.entry_type]}
                      </span>
                      {entry.entry_type}
                    </span>
                  </td>
                  <td
                    className={`px-6 py-3 text-right font-mono font-semibold ${ENTRY_COLORS[entry.entry_type]}`}
                  >
                    {formatPaise(entry.amount_paise)}
                  </td>
                  <td className="px-6 py-3 text-slate-400 hidden md:table-cell max-w-xs truncate">
                    {entry.description}
                  </td>
                  <td className="px-6 py-3 text-right text-slate-500 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleDateString("en-IN", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
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
