"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import {
  approveUpload,
  type DetailedValidationResult,
  type ApproveResponse,
} from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ValidationReviewPage() {
  const { storeId, meetingId } = useParams<{ storeId: string; meetingId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();

  const [validation, setValidation] = useState<DetailedValidationResult | null>(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const token = (session as any)?.backendToken;

  // Load validation data from sessionStorage (set by upload page)
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(`validation_${meetingId}`);
      if (stored) {
        setValidation(JSON.parse(stored));
      } else {
        setError("No validation data found. Please re-upload the packet.");
      }
    } catch {
      setError("Failed to load validation data.");
    }
  }, [meetingId]);

  async function handleApprove() {
    if (!meetingId) return;
    setApproving(true);
    setError(null);

    try {
      await approveUpload(meetingId, token);
      // Clean up stored validation data
      sessionStorage.removeItem(`validation_${meetingId}`);
      // Redirect to meeting detail page
      router.push(`/stores/${storeId}/meetings/${meetingId}`);
    } catch (err: any) {
      setError(err.message || "Processing failed");
      setApproving(false);
    }
  }

  // Group classified pages by document type
  const groupedPages: Record<string, number[]> = {};
  if (validation) {
    for (const cp of validation.classified_pages) {
      if (!groupedPages[cp.document_type]) {
        groupedPages[cp.document_type] = [];
      }
      groupedPages[cp.document_type].push(cp.page_number);
    }
  }

  return (
    <>
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 py-6">
        {/* Breadcrumb */}
        <nav className="text-sm text-gray-500 mb-4 flex items-center gap-1">
          <Link href="/dashboard" className="text-blue-600 hover:underline">Dashboard</Link>
          <span>/</span>
          <Link href={`/stores/${storeId}`} className="text-blue-600 hover:underline">Store</Link>
          <span>/</span>
          <span className="text-gray-700">Validation Review</span>
        </nav>

        <h1 className="text-2xl font-bold mb-6">Packet Validation Review</h1>

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6">{error}</div>
        )}

        {!validation && !error && (
          <p className="text-gray-500">Loading validation data...</p>
        )}

        {validation && (
          <>
            {/* Completeness Header */}
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 uppercase tracking-wide">Packet Completeness</p>
                  <p className={`text-3xl font-bold mt-1 ${
                    validation.completeness_percentage === 100 ? "text-green-600" :
                    validation.completeness_percentage >= 75 ? "text-yellow-600" :
                    "text-red-600"
                  }`}>
                    {validation.completeness_percentage}%
                  </p>
                </div>
                <div className="text-right text-sm text-gray-500">
                  <p>{validation.total_pages} total pages</p>
                  <p>{validation.classified_pages.length} classified, {validation.unclassified_pages.length} unclassified</p>
                </div>
              </div>
            </div>

            {/* Section 1: Classified Pages */}
            <div className="bg-white rounded-lg shadow border border-gray-200 mb-6">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold">Classified Pages</h2>
              </div>
              {Object.keys(groupedPages).length === 0 ? (
                <p className="text-gray-500 p-4">No pages were classified.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Document Type</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Pages</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {Object.entries(groupedPages).map(([docType, pages]) => (
                      <tr key={docType}>
                        <td className="px-4 py-3 font-medium">{docType}</td>
                        <td className="px-4 py-3 text-gray-600">
                          {formatPageRange(pages)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Section 2: Unclassified Pages */}
            <div className={`rounded-lg shadow border mb-6 ${
              validation.unclassified_pages.length > 0
                ? "bg-yellow-50 border-yellow-200"
                : "bg-green-50 border-green-200"
            }`}>
              <div className="p-4 border-b border-inherit">
                <h2 className="text-lg font-semibold">
                  {validation.unclassified_pages.length > 0
                    ? `Unclassified Pages (${validation.unclassified_pages.length})`
                    : "All Pages Classified"}
                </h2>
              </div>
              {validation.unclassified_pages.length > 0 ? (
                <div className="p-4">
                  <p className="text-sm text-yellow-700 mb-3">
                    The following pages could not be matched to a known document type.
                    They may be cover pages, supplementary documents, or unrecognized formats.
                  </p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr>
                        <th className="text-left px-3 py-2 font-medium text-gray-600 w-20">Page</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Preview</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-yellow-200">
                      {validation.unclassified_pages.map((page) => (
                        <tr key={page.page_number}>
                          <td className="px-3 py-2 font-mono">{page.page_number}</td>
                          <td className="px-3 py-2 text-gray-600 truncate max-w-md" title={page.snippet}>
                            {page.snippet}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="p-4 text-green-700 text-sm">
                  Every page in the uploaded PDF was successfully matched to a document type.
                </p>
              )}
            </div>

            {/* Section 3: Required Documents Checklist */}
            <div className="bg-white rounded-lg shadow border border-gray-200 mb-6">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold">Required Documents Checklist</h2>
              </div>
              <div className="divide-y divide-gray-100">
                {validation.required_documents.map((doc) => (
                  <div key={doc.name} className="px-4 py-3 flex items-start gap-3">
                    <span className={`mt-0.5 flex-shrink-0 text-lg ${doc.found ? "text-green-600" : "text-red-500"}`}>
                      {doc.found ? "\u2713" : "\u2717"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`font-medium ${doc.found ? "" : "text-red-700"}`}>
                        {doc.name}
                      </p>
                      {doc.found ? (
                        <p className="text-xs text-gray-400 mt-0.5">
                          Pages: {formatPageRange(doc.page_numbers)}
                        </p>
                      ) : (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {doc.where_to_find}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-between bg-white rounded-lg shadow p-4 border border-gray-200">
              <Link
                href={`/stores/${storeId}`}
                className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded transition-colors"
              >
                Re-upload
              </Link>
              <div className="flex items-center gap-3">
                {!validation.is_complete && (
                  <p className="text-sm text-yellow-600">
                    {validation.required_documents.filter(d => !d.found).length} document(s) missing
                  </p>
                )}
                <button
                  onClick={handleApprove}
                  disabled={approving}
                  className={`text-sm font-medium px-6 py-2 rounded transition-colors ${
                    approving
                      ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                      : "bg-blue-600 hover:bg-blue-500 text-white"
                  }`}
                >
                  {approving ? "Processing..." : "Approve & Process"}
                </button>
              </div>
            </div>
          </>
        )}
      </main>
    </>
  );
}

/** Format page numbers into compact ranges: [1,2,3,5,7,8] -> "1-3, 5, 7-8" */
function formatPageRange(pages: number[]): string {
  if (pages.length === 0) return "";
  const sorted = [...pages].sort((a, b) => a - b);
  const ranges: string[] = [];
  let start = sorted[0];
  let end = sorted[0];

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === end + 1) {
      end = sorted[i];
    } else {
      ranges.push(start === end ? `${start}` : `${start}-${end}`);
      start = sorted[i];
      end = sorted[i];
    }
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`);
  return ranges.join(", ");
}
