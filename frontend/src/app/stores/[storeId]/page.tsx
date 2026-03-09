"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import {
  fetchStoreDetail,
  fetchStoreFlagTrends,
  type StoreDetail,
  type FlagTrendsData,
} from "@/lib/api";
import { FlagTrendChart } from "@/components/FlagTrendChart";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatMeetingDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function ResponseRateBadge({ rate }: { rate: number }) {
  const color =
    rate >= 80
      ? "bg-green-100 text-green-700"
      : rate >= 50
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";
  return (
    <span className={`text-sm font-medium px-2 py-0.5 rounded ${color}`}>
      {rate}%
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    processing: "bg-blue-100 text-blue-700",
    pending: "bg-gray-100 text-gray-600",
    error: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded capitalize ${colors[status] || colors.pending}`}
    >
      {status}
    </span>
  );
}

export default function StoreDetailPage() {
  const { storeId } = useParams<{ storeId: string }>();
  const { data: session } = useSession();
  const [detail, setDetail] = useState<StoreDetail | null>(null);
  const [trends, setTrends] = useState<FlagTrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usersOpen, setUsersOpen] = useState(false);

  useEffect(() => {
    if (!storeId) return;
    const token = (session as any)?.backendToken;

    Promise.all([
      fetchStoreDetail(storeId, token),
      fetchStoreFlagTrends(storeId, token),
    ])
      .then(([d, t]) => {
        setDetail(d);
        setTrends(t);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [storeId, session]);

  const store = detail?.store;
  const stats = detail?.stats;

  return (
    <>
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Link
          href="/dashboard"
          className="text-blue-600 hover:underline text-sm mb-4 inline-block"
        >
          &larr; Back to Dashboard
        </Link>

        {loading && <p className="text-gray-500">Loading store...</p>}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">
            {error}
          </div>
        )}

        {detail && store && stats && (
          <>
            {/* Header Section */}
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h1 className="text-2xl font-bold">{store.name}</h1>
                    {store.brand && (
                      <span className="text-xs font-medium bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                        {store.brand}
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>
                      {store.city}, {store.state}
                    </p>
                    {store.gm_name && (
                      <p>
                        GM: {store.gm_name}
                        {store.gm_email && (
                          <span className="text-gray-400">
                            {" "}
                            ({store.gm_email})
                          </span>
                        )}
                      </p>
                    )}
                    {store.meeting_cadence && (
                      <p className="capitalize">
                        {store.meeting_cadence} meetings
                      </p>
                    )}
                  </div>
                </div>
                <Link
                  href={`/stores/${storeId}/upload`}
                  className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
                >
                  Upload Reports
                </Link>
              </div>
            </div>

            {/* Stats Bar */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-500">Total Meetings</p>
                <p className="text-2xl font-bold">{stats.total_meetings}</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-500">Open Flags</p>
                <p className="text-2xl font-bold">{stats.current_open_flags}</p>
                <div className="flex gap-2 mt-1">
                  <span className="text-xs text-red-600">
                    {stats.total_flags_all_time > 0
                      ? `${Math.round((stats.current_open_flags / stats.total_flags_all_time) * 100)}% of all-time`
                      : ""}
                  </span>
                </div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-500">Response Rate</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-2xl font-bold">{stats.response_rate}%</p>
                  <ResponseRateBadge rate={stats.response_rate} />
                </div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-500">Overdue Flags</p>
                <p
                  className={`text-2xl font-bold ${stats.current_overdue_flags > 0 ? "text-red-600" : ""}`}
                >
                  {stats.current_overdue_flags}
                </p>
              </div>
            </div>

            {/* Flag Trend Chart */}
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
              <h2 className="text-lg font-semibold mb-4">Flag Trends</h2>
              {trends && trends.meetings.length > 0 ? (
                <>
                  <FlagTrendChart data={trends.meetings} />
                  {trends.meetings.length === 1 && (
                    <p className="text-sm text-gray-400 mt-3 text-center">
                      Trend data available after 2+ meetings
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-gray-400 text-center py-8">
                  No meeting data available for trend chart
                </p>
              )}
            </div>

            {/* Recent Meetings */}
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-3">Recent Meetings</h2>
              {detail.recent_meetings.length === 0 ? (
                <div className="bg-white rounded-lg shadow p-8 border border-gray-200 text-center">
                  <p className="text-gray-500">
                    No meetings recorded yet. Upload R&R reports to get started.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {detail.recent_meetings.map((meeting) => (
                    <div
                      key={meeting.id}
                      className="bg-white rounded-lg shadow p-4 border border-gray-200"
                    >
                      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <p className="font-medium">
                              {formatMeetingDate(meeting.meeting_date)}
                            </p>
                            <StatusBadge status={meeting.status} />
                          </div>
                          <div className="flex flex-wrap gap-3 text-sm text-gray-600">
                            <span>
                              <span className="text-red-600 font-medium">
                                {meeting.flags.red}
                              </span>{" "}
                              red,{" "}
                              <span className="text-amber-500 font-medium">
                                {meeting.flags.yellow}
                              </span>{" "}
                              yellow &mdash;{" "}
                              <ResponseRateBadge rate={meeting.response_rate} />{" "}
                              responded
                            </span>
                            {meeting.flags.open > 0 &&
                              meeting.flags.open !==
                                meeting.flags.total && (
                                <span className="text-red-600 font-medium">
                                  {meeting.flags.open} overdue
                                </span>
                              )}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Link
                            href={`/stores/${storeId}/meetings/${meeting.id}`}
                            className="text-sm bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded transition-colors"
                          >
                            View Details
                          </Link>
                          {meeting.packet_url && (
                            <a
                              href={`${API_BASE}${meeting.packet_url}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded transition-colors"
                            >
                              Packet
                            </a>
                          )}
                          {meeting.flagged_items_url && (
                            <a
                              href={`${API_BASE}${meeting.flagged_items_url}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm bg-red-50 hover:bg-red-100 text-red-700 px-3 py-1.5 rounded transition-colors"
                            >
                              Flagged Items
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Store Users (Collapsible) */}
            {detail.users.length > 0 && (
              <div className="bg-white rounded-lg shadow border border-gray-200 mb-6">
                <button
                  onClick={() => setUsersOpen(!usersOpen)}
                  className="w-full flex items-center justify-between p-4 text-left"
                >
                  <h2 className="text-lg font-semibold">
                    Store Users ({detail.users.length})
                  </h2>
                  <span className="text-gray-400">
                    {usersOpen ? "▲" : "▼"}
                  </span>
                </button>
                {usersOpen && (
                  <div className="px-4 pb-4">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-500 border-b">
                          <th className="pb-2 font-medium">Name</th>
                          <th className="pb-2 font-medium">Email</th>
                          <th className="pb-2 font-medium">Role</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.users.map((user) => (
                          <tr key={user.id} className="border-b last:border-0">
                            <td className="py-2">{user.name}</td>
                            <td className="py-2 text-gray-500">{user.email}</td>
                            <td className="py-2">{user.role_at_store}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="text-xs text-gray-400 mt-3">
                      Manage Users (coming soon)
                    </p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
