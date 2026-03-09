"use client";

import Link from "next/link";
import type { StoreDashboardItem } from "@/lib/api";

export function StoreCard({ store }: { store: StoreDashboardItem }) {
  const { flags, response_rate } = store;

  return (
    <Link
      href={`/stores/${store.id}`}
      className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow p-5 border border-gray-200"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-lg">{store.name}</h3>
          <p className="text-sm text-gray-500">{store.code}</p>
        </div>
        {store.last_meeting_date && (
          <span className="text-xs text-gray-400">
            Last: {store.last_meeting_date}
          </span>
        )}
      </div>

      {/* Flag counts */}
      <div className="flex gap-3 mb-3">
        <span className="inline-flex items-center gap-1 text-sm">
          <span className="w-3 h-3 rounded-full bg-red-500 inline-block" />
          {flags.red} red
        </span>
        <span className="inline-flex items-center gap-1 text-sm">
          <span className="w-3 h-3 rounded-full bg-yellow-400 inline-block" />
          {flags.yellow} yellow
        </span>
        <span className="text-sm text-gray-500">
          {flags.open} open
        </span>
      </div>

      {/* Response rate bar */}
      <div className="mb-2">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Response Rate</span>
          <span>{response_rate}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${Math.min(response_rate, 100)}%` }}
          />
        </div>
      </div>

      {store.overdue_count > 0 && (
        <p className="text-xs text-red-600 font-medium">
          {store.overdue_count} overdue flags
        </p>
      )}
    </Link>
  );
}
