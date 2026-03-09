"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { fetchStore, type StoreDetail } from "@/lib/api";

export default function StoreDetailPage() {
  const { storeId } = useParams<{ storeId: string }>();
  const { data: session } = useSession();
  const [store, setStore] = useState<StoreDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!storeId) return;
    const token = (session as any)?.backendToken;
    fetchStore(storeId, token)
      .then(setStore)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [storeId, session]);

  return (
    <>
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 py-6">
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

        {store && (
          <>
            {/* Store header */}
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
              <h1 className="text-2xl font-bold">{store.name}</h1>
              <div className="mt-2 text-sm text-gray-600 space-y-1">
                <p>Code: {store.code}</p>
                {store.brand && <p>Brand: {store.brand}</p>}
                <p>
                  Location: {store.city}, {store.state}
                </p>
                {store.gm_name && <p>GM: {store.gm_name}</p>}
                {store.meeting_cadence && (
                  <p>Meeting Cadence: {store.meeting_cadence}</p>
                )}
              </div>
            </div>

            {/* Recent meetings */}
            <h2 className="text-lg font-semibold mb-3">Recent Meetings</h2>
            {store.recent_meetings.length === 0 ? (
              <p className="text-gray-500">No meetings yet.</p>
            ) : (
              <div className="space-y-3">
                {store.recent_meetings.map((meeting) => (
                  <Link
                    key={meeting.id}
                    href={`/meetings/${meeting.id}`}
                    className="block bg-white rounded-lg shadow p-4 border border-gray-200 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">
                          {meeting.meeting_date}
                        </p>
                        <p className="text-sm text-gray-500 capitalize">
                          Status: {meeting.status}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        {meeting.packet_url && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                            Packet
                          </span>
                        )}
                        {meeting.flagged_items_url && (
                          <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">
                            Flags
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
