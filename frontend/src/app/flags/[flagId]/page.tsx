"use client";

import { useSession } from "next-auth/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { ResponseForm } from "@/components/flags/ResponseForm";
import { fetchMyFlags, type MyFlagItem } from "@/lib/api";

function SeverityBadge({ severity }: { severity: string }) {
  const color = severity === "red" ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${color}`}>
      {severity}
    </span>
  );
}

export default function FlagDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const flagId = params.flagId as string;

  const [flag, setFlag] = useState<MyFlagItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const token = (session as any)?.backendToken;

  useEffect(() => {
    fetchMyFlags(token)
      .then((flags) => {
        const found = flags.find((f) => f.id === flagId);
        if (found) setFlag(found);
        else setError("Flag not found or not assigned to you");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, flagId]);

  return (
    <>
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-6">
        <button
          onClick={() => router.push("/flags")}
          className="text-sm text-blue-600 hover:text-blue-800 mb-4 inline-flex items-center gap-1"
        >
          &larr; Back to My Flags
        </button>

        {loading && <p className="text-gray-500 py-8 text-center">Loading flag...</p>}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
        )}

        {flag && (
          <div className="space-y-6">
            {/* Flag detail */}
            <div className="bg-white border rounded-lg p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <SeverityBadge severity={flag.severity} />
                <span className="text-xs font-medium text-gray-500 uppercase">{flag.category}</span>
                {flag.escalation_level > 0 && (
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-100 text-orange-800">
                    RECURRING ({flag.escalation_level + 1}{flag.escalation_level === 1 ? "nd" : flag.escalation_level === 2 ? "rd" : "th"} occurrence)
                  </span>
                )}
              </div>

              <h2 className="text-lg font-semibold text-gray-900 mb-4">{flag.message}</h2>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Store</span>
                  <p className="font-medium">{flag.store_name}</p>
                </div>
                <div>
                  <span className="text-gray-500">Meeting Date</span>
                  <p className="font-medium">{flag.meeting_date}</p>
                </div>
                <div>
                  <span className="text-gray-500">Field</span>
                  <p className="font-medium">{flag.field_name}: {flag.field_value || "N/A"}</p>
                </div>
                <div>
                  <span className="text-gray-500">Threshold</span>
                  <p className="font-medium">{flag.threshold || "N/A"}</p>
                </div>
                <div>
                  <span className="text-gray-500">Status</span>
                  <p className="font-medium capitalize">{flag.status}</p>
                </div>
                <div>
                  <span className="text-gray-500">Deadline</span>
                  <p className={`font-medium ${flag.is_overdue ? "text-red-600" : ""}`}>
                    {flag.deadline}
                    {flag.is_overdue && ` (${flag.days_overdue} days overdue)`}
                  </p>
                </div>
              </div>
            </div>

            {/* Response form */}
            <div className="bg-white border rounded-lg p-6 shadow-sm">
              <h3 className="text-base font-semibold mb-4">
                {flag.response_text ? "Your Response" : "Submit Response"}
              </h3>
              <ResponseForm
                flagId={flag.id}
                token={token}
                existingResponse={flag.response_text}
                onSuccess={() => {
                  setTimeout(() => router.push("/flags"), 1500);
                }}
              />
            </div>
          </div>
        )}
      </main>
    </>
  );
}
