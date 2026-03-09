"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { FlagCard } from "@/components/flags/FlagCard";
import { fetchMyFlags, type MyFlagItem } from "@/lib/api";

type StatusFilter = "all" | "open" | "overdue" | "responded";

export default function MyFlagsPage() {
  const { data: session } = useSession();
  const [flags, setFlags] = useState<MyFlagItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    const token = (session as any)?.backendToken;
    const filters: { status?: string } = {};
    if (statusFilter === "overdue") filters.status = "overdue";
    else if (statusFilter !== "all") filters.status = statusFilter;

    setLoading(true);
    fetchMyFlags(token, filters)
      .then(setFlags)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [session, statusFilter]);

  const openCount = flags.filter((f) => f.status === "open").length;
  const overdueCount = flags.filter((f) => f.is_overdue).length;
  const respondedCount = flags.filter((f) => f.status === "responded").length;

  const displayFlags = statusFilter === "all"
    ? flags
    : statusFilter === "overdue"
      ? flags.filter((f) => f.is_overdue)
      : flags.filter((f) => f.status === statusFilter);

  return (
    <>
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">My Flags</h1>
            <p className="text-sm text-gray-500 mt-1">
              Flags assigned to you that require a response
            </p>
          </div>
          <div className="flex gap-2">
            {openCount > 0 && (
              <span className="px-2.5 py-1 bg-blue-100 text-blue-800 text-xs font-bold rounded-full">
                {openCount} open
              </span>
            )}
            {overdueCount > 0 && (
              <span className="px-2.5 py-1 bg-red-100 text-red-800 text-xs font-bold rounded-full">
                {overdueCount} overdue
              </span>
            )}
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex gap-2 mb-4">
          {(["all", "open", "overdue", "responded"] as StatusFilter[]).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-sm rounded-lg font-medium ${
                statusFilter === s
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {loading && <p className="text-gray-500 py-8 text-center">Loading flags...</p>}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">{error}</div>
        )}

        {!loading && !error && displayFlags.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg font-medium">No flags to show</p>
            <p className="text-sm mt-1">
              {statusFilter === "all"
                ? "You have no assigned flags."
                : `No ${statusFilter} flags.`}
            </p>
          </div>
        )}

        <div className="space-y-3">
          {displayFlags.map((flag) => (
            <FlagCard key={flag.id} flag={flag} />
          ))}
        </div>

        {!loading && (
          <div className="mt-6 text-xs text-gray-400 text-center">
            {flags.length} total flag{flags.length !== 1 ? "s" : ""} assigned
            {respondedCount > 0 && ` · ${respondedCount} responded`}
          </div>
        )}
      </main>
    </>
  );
}
