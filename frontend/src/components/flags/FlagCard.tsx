"use client";

import Link from "next/link";
import type { MyFlagItem } from "@/lib/api";

function SeverityBadge({ severity }: { severity: string }) {
  const color = severity === "red" ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${color}`}>
      {severity}
    </span>
  );
}

function formatDeadline(deadline: string): string {
  const d = new Date(deadline + "T09:00:00");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }) + " 9:00 AM CT";
}

export function FlagCard({ flag }: { flag: MyFlagItem }) {
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <SeverityBadge severity={flag.severity} />
            <span className="text-xs font-medium text-gray-500 uppercase">{flag.category}</span>
            {flag.escalation_level > 0 && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-100 text-orange-800">
                RECURRING ({flag.escalation_level + 1}{flag.escalation_level === 1 ? "nd" : flag.escalation_level === 2 ? "rd" : "th"} occurrence)
              </span>
            )}
          </div>

          <p className="text-sm text-gray-900 font-medium mb-2">{flag.message}</p>

          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
            <span>{flag.store_name}</span>
            <span>Meeting: {flag.meeting_date}</span>
          </div>

          <div className="mt-2 text-xs">
            {flag.is_overdue ? (
              <span className="text-red-600 font-bold">
                OVERDUE — {flag.days_overdue} day{flag.days_overdue !== 1 ? "s" : ""} past deadline
              </span>
            ) : (
              <span className="text-gray-500">
                Due by {formatDeadline(flag.deadline)}
              </span>
            )}
          </div>

          {flag.response_text && (
            <div className="mt-2 p-2 bg-green-50 rounded text-xs text-green-800">
              <span className="font-medium">Response:</span> {flag.response_text}
            </div>
          )}
        </div>

        <div className="flex-shrink-0">
          {flag.status === "open" ? (
            <Link
              href={`/flags/${flag.id}`}
              className="inline-flex items-center px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700"
            >
              Respond
            </Link>
          ) : (
            <span className="inline-flex items-center px-3 py-1.5 bg-green-100 text-green-800 text-sm font-medium rounded">
              Responded
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
