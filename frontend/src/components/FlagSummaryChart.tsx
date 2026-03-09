"use client";

import type { StoreDashboardItem } from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  inventory: "#3b82f6",
  parts: "#f59e0b",
  financial: "#ef4444",
  operations: "#10b981",
};

export function FlagSummaryChart({ stores }: { stores: StoreDashboardItem[] }) {
  // Aggregate flags across stores — we don't have per-category breakdown from dashboard,
  // so show a simple red/yellow distribution
  const totalRed = stores.reduce((sum, s) => sum + s.flags.red, 0);
  const totalYellow = stores.reduce((sum, s) => sum + s.flags.yellow, 0);
  const total = totalRed + totalYellow;

  if (total === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-5 border border-gray-200">
        <h3 className="font-semibold mb-3">Flag Distribution</h3>
        <p className="text-gray-500 text-sm">No flags to display</p>
      </div>
    );
  }

  const redPct = Math.round((totalRed / total) * 100);
  const yellowPct = 100 - redPct;

  return (
    <div className="bg-white rounded-lg shadow p-5 border border-gray-200">
      <h3 className="font-semibold mb-3">Flag Distribution</h3>
      <div className="flex items-center gap-4 mb-3">
        <div className="flex-1 h-6 rounded-full overflow-hidden bg-gray-200 flex">
          <div
            className="bg-red-500 h-full transition-all"
            style={{ width: `${redPct}%` }}
          />
          <div
            className="bg-yellow-400 h-full transition-all"
            style={{ width: `${yellowPct}%` }}
          />
        </div>
      </div>
      <div className="flex gap-6 text-sm">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-500 inline-block" />
          Red: {totalRed} ({redPct}%)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-yellow-400 inline-block" />
          Yellow: {totalYellow} ({yellowPct}%)
        </span>
      </div>
    </div>
  );
}
