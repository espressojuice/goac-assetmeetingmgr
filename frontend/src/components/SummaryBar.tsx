"use client";

import type { DashboardTotals } from "@/lib/api";

export function SummaryBar({ totals }: { totals: DashboardTotals }) {
  const stats = [
    { label: "Total Stores", value: totals.total_stores },
    { label: "Open Flags", value: totals.total_open_flags, highlight: true },
    { label: "Overdue", value: totals.total_overdue, highlight: true },
    { label: "Avg Response Rate", value: `${totals.avg_response_rate}%` },
    { label: "Meetings This Week", value: totals.meetings_this_week },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
      {stats.map((s) => (
        <div
          key={s.label}
          className="bg-white rounded-lg shadow p-4 border border-gray-200"
        >
          <p className="text-xs text-gray-500 uppercase tracking-wide">
            {s.label}
          </p>
          <p
            className={`text-2xl font-bold mt-1 ${
              s.highlight && typeof s.value === "number" && s.value > 0
                ? "text-red-600"
                : ""
            }`}
          >
            {s.value}
          </p>
        </div>
      ))}
    </div>
  );
}
