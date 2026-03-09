"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import {
  fetchMeetingSummary,
  fetchMeetingFlags,
  type MeetingSummary,
  type FlagItem,
} from "@/lib/api";

type Tab = "summary" | "flags" | "responses";

export default function MeetingDetailPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const { data: session } = useSession();
  const [summary, setSummary] = useState<MeetingSummary | null>(null);
  const [flags, setFlags] = useState<FlagItem[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!meetingId) return;
    const token = (session as any)?.backendToken;

    Promise.all([
      fetchMeetingSummary(meetingId, token),
      fetchMeetingFlags(meetingId, token),
    ])
      .then(([sum, fl]) => {
        setSummary(sum);
        setFlags(fl);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [meetingId, session]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "summary", label: "Packet Data" },
    { key: "flags", label: `Flags (${flags.length})` },
    { key: "responses", label: "Responses" },
  ];

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <>
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-6">
        {summary && (
          <Link
            href={`/stores/${summary.store.id}`}
            className="text-blue-600 hover:underline text-sm mb-4 inline-block"
          >
            &larr; Back to {summary.store.name}
          </Link>
        )}

        {loading && <p className="text-gray-500">Loading meeting...</p>}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">
            {error}
          </div>
        )}

        {summary && (
          <>
            {/* Meeting header */}
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-2xl font-bold">
                    Meeting: {summary.meeting.meeting_date}
                  </h1>
                  <p className="text-sm text-gray-500 mt-1">
                    {summary.store.name} &middot;{" "}
                    <span className="capitalize">
                      {summary.meeting.status}
                    </span>
                  </p>
                </div>
                <div className="flex gap-2">
                  {summary.meeting.packet_url && (
                    <a
                      href={`${apiBase}/api/v1/packets/${meetingId}`}
                      className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-500"
                    >
                      Download Packet
                    </a>
                  )}
                  {summary.meeting.flagged_items_url && (
                    <a
                      href={`${apiBase}/api/v1/packets/${meetingId}/flagged-items`}
                      className="text-sm bg-red-600 text-white px-3 py-1.5 rounded hover:bg-red-500"
                    >
                      Download Flags PDF
                    </a>
                  )}
                </div>
              </div>

              {/* Flag stats */}
              <div className="flex gap-4 mt-4 text-sm">
                <span>
                  Total: <strong>{summary.flag_stats.total}</strong>
                </span>
                <span className="text-red-600">
                  Red: <strong>{summary.flag_stats.red}</strong>
                </span>
                <span className="text-yellow-600">
                  Yellow: <strong>{summary.flag_stats.yellow}</strong>
                </span>
                <span>
                  Open: <strong>{summary.flag_stats.open}</strong>
                </span>
                <span className="text-green-600">
                  Responded: <strong>{summary.flag_stats.responded}</strong>
                </span>
              </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200 mb-4">
              <nav className="flex gap-6">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab.key
                        ? "border-blue-600 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab content */}
            {activeTab === "summary" && (
              <div className="bg-white rounded-lg shadow p-5 border border-gray-200">
                <h3 className="font-semibold mb-3">Record Counts</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(summary.record_counts).map(
                    ([key, count]) => (
                      <div key={key} className="text-sm">
                        <span className="text-gray-500">{key}:</span>{" "}
                        <strong>{count}</strong>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}

            {activeTab === "flags" && (
              <FlagTable flags={flags} />
            )}

            {activeTab === "responses" && (
              <div className="bg-white rounded-lg shadow p-5 border border-gray-200">
                <h3 className="font-semibold mb-3">Responses</h3>
                {flags.filter((f) => f.status === "responded").length === 0 ? (
                  <p className="text-gray-500 text-sm">
                    No responses yet.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {flags
                      .filter((f) => f.status === "responded")
                      .map((f) => (
                        <div
                          key={f.id}
                          className="border border-gray-200 rounded p-3"
                        >
                          <p className="text-sm font-medium">{f.message}</p>
                          <p className="text-sm text-green-700 mt-1">
                            Response: {f.response_text}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            by {f.responded_by} at {f.responded_at}
                          </p>
                        </div>
                      ))}
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

function FlagTable({ flags }: { flags: FlagItem[] }) {
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  const filtered = flags.filter((f) => {
    if (severityFilter && f.severity !== severityFilter) return false;
    if (categoryFilter && f.category !== categoryFilter) return false;
    return true;
  });

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
      {/* Filters */}
      <div className="p-4 border-b border-gray-200 flex gap-3">
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1"
        >
          <option value="">All Severities</option>
          <option value="red">Red</option>
          <option value="yellow">Yellow</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1"
        >
          <option value="">All Categories</option>
          <option value="inventory">Inventory</option>
          <option value="parts">Parts</option>
          <option value="financial">Financial</option>
          <option value="operations">Operations</option>
        </select>
      </div>

      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left px-4 py-2 font-medium text-gray-600">
              Severity
            </th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">
              Category
            </th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">
              Field
            </th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">
              Message
            </th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {filtered.map((f) => (
            <tr key={f.id} className="hover:bg-gray-50">
              <td className="px-4 py-2">
                <span
                  className={`inline-block w-3 h-3 rounded-full ${
                    f.severity === "red" ? "bg-red-500" : "bg-yellow-400"
                  }`}
                />
              </td>
              <td className="px-4 py-2 capitalize">{f.category}</td>
              <td className="px-4 py-2">{f.field_name}</td>
              <td className="px-4 py-2">{f.message}</td>
              <td className="px-4 py-2">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    f.status === "open"
                      ? "bg-red-100 text-red-700"
                      : f.status === "responded"
                      ? "bg-green-100 text-green-700"
                      : "bg-orange-100 text-orange-700"
                  }`}
                >
                  {f.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {filtered.length === 0 && (
        <p className="text-gray-500 text-sm p-4">
          No flags match the current filters.
        </p>
      )}
    </div>
  );
}
