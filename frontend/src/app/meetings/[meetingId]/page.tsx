"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Navbar } from "@/components/Navbar";
import { fetchMeetingDetail } from "@/lib/api";

/**
 * Legacy meeting URL (/meetings/:id) — redirects to the new nested route
 * /stores/:storeId/meetings/:meetingId once we know the store.
 */
export default function MeetingRedirectPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const { data: session } = useSession();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!meetingId) return;
    const token = (session as any)?.backendToken;

    fetchMeetingDetail(meetingId, token)
      .then((detail) => {
        router.replace(`/stores/${detail.meeting.store_id}/meetings/${meetingId}`);
      })
      .catch((err) => setError(err.message));
  }, [meetingId, session, router]);

  return (
    <>
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-6">
        {error ? (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
        ) : (
          <p className="text-gray-500">Redirecting to meeting...</p>
        )}
      </main>
    </>
  );
}
