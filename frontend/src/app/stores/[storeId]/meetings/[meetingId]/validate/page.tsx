"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import {
  approveUpload,
  fetchValidationProgress,
  type ValidationProgressResponse,
  type ClassifiedPage,
  type UnclassifiedPage,
  type RequiredDocumentCheck,
} from "@/lib/api";

const POLL_INTERVAL = 2000; // 2 seconds
const TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

export default function ValidationReviewPage() {
  const { storeId, meetingId } = useParams<{ storeId: string; meetingId: string }>();
  const router = useRouter();
  const { data: session } = useSession();

  // Progress state (polling mode)
  const [status, setStatus] = useState<string>("uploading");
  const [currentPage, setCurrentPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [classifiedPages, setClassifiedPages] = useState<ClassifiedPage[]>([]);
  const [unclassifiedPages, setUnclassifiedPages] = useState<UnclassifiedPage[]>([]);
  const [requiredDocuments, setRequiredDocuments] = useState<RequiredDocumentCheck[]>([]);
  const [completenessPercentage, setCompletenessPercentage] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  // UI state
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const token = (session as any)?.backendToken;
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const validationDone = status === "complete" || status === "error";

  const pollProgress = useCallback(async () => {
    if (!meetingId || !token) return;

    // Timeout check
    if (Date.now() - startTimeRef.current > TIMEOUT_MS) {
      setError("Validation timed out after 10 minutes. Please try re-uploading.");
      setStatus("error");
      return;
    }

    try {
      const data: ValidationProgressResponse = await fetchValidationProgress(meetingId, token);
      setStatus(data.status);
      setCurrentPage(data.current_page);
      setTotalPages(data.total_pages);
      setClassifiedPages(data.classified_pages);
      setUnclassifiedPages(data.unclassified_pages);
      setRequiredDocuments(data.required_documents);
      setCompletenessPercentage(data.completeness_percentage);
      setIsComplete(data.is_complete);

      if (data.error) {
        setError(data.error);
      }
    } catch {
      // Progress endpoint may not be ready yet — keep polling
    }
  }, [meetingId, token]);

  // Start polling on mount
  useEffect(() => {
    // Load total_pages from sessionStorage if available
    const storedPages = sessionStorage.getItem(`upload_total_pages_${meetingId}`);
    if (storedPages) {
      setTotalPages(parseInt(storedPages, 10));
      sessionStorage.removeItem(`upload_total_pages_${meetingId}`);
    }

    startTimeRef.current = Date.now();
    // Poll immediately, then every 2s
    pollProgress();
    pollingRef.current = setInterval(pollProgress, POLL_INTERVAL);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [meetingId, pollProgress]);

  // Stop polling when done
  useEffect(() => {
    if (validationDone && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, [validationDone]);

  async function handleApprove() {
    if (!meetingId) return;
    setApproving(true);
    setError(null);

    try {
      await approveUpload(meetingId, token);
      router.push(`/stores/${storeId}/meetings/${meetingId}`);
    } catch (err: any) {
      setError(err.message || "Processing failed");
      setApproving(false);
    }
  }

  // Group classified pages by document type
  const groupedPages: Record<string, number[]> = {};
  for (const cp of classifiedPages) {
    if (!groupedPages[cp.document_type]) {
      groupedPages[cp.document_type] = [];
    }
    groupedPages[cp.document_type].push(cp.page_number);
  }

  const progressPercent = totalPages > 0 ? Math.round((currentPage / totalPages) * 100) : 0;

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

        {/* Progress Bar (shown while validating) */}
        {!validationDone && (
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-gray-700">
                {status === "uploading" && "Preparing..."}
                {status === "counting_pages" && "Counting pages..."}
                {status === "validating" && `Processing page ${currentPage} of ${totalPages}`}
              </p>
              <span className="text-sm text-gray-500">{progressPercent}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div
                className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            {status === "validating" && totalPages > 0 && (
              <p className="text-xs text-gray-400 mt-2">
                {classifiedPages.length} classified, {unclassifiedPages.length} unclassified so far
              </p>
            )}
          </div>
        )}

        {/* Completeness Header (always shown once we have data) */}
        {(totalPages > 0) && (
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 uppercase tracking-wide">Packet Completeness</p>
                <p className={`text-3xl font-bold mt-1 ${
                  completenessPercentage === 100 ? "text-green-600" :
                  completenessPercentage >= 75 ? "text-yellow-600" :
                  "text-red-600"
                }`}>
                  {completenessPercentage}%
                </p>
              </div>
              <div className="text-right text-sm text-gray-500">
                <p>{totalPages} total pages</p>
                <p>{classifiedPages.length} classified, {unclassifiedPages.length} unclassified</p>
              </div>
            </div>
          </div>
        )}

        {/* Classified Pages — streams in as pages are processed */}
        {classifiedPages.length > 0 && (
          <div className="bg-white rounded-lg shadow border border-gray-200 mb-6">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold">Classified Pages</h2>
            </div>
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
          </div>
        )}

        {/* Unclassified Pages — only show when validation completed successfully */}
        {status === "complete" && (
          <div className={`rounded-lg shadow border mb-6 ${
            unclassifiedPages.length > 0
              ? "bg-yellow-50 border-yellow-200"
              : "bg-green-50 border-green-200"
          }`}>
            <div className="p-4 border-b border-inherit">
              <h2 className="text-lg font-semibold">
                {unclassifiedPages.length > 0
                  ? `Unclassified Pages (${unclassifiedPages.length})`
                  : "All Pages Classified"}
              </h2>
            </div>
            {unclassifiedPages.length > 0 ? (
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
                    {unclassifiedPages.map((page) => (
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
        )}

        {/* Required Documents Checklist — updates in real-time */}
        {requiredDocuments.length > 0 && (
          <div className="bg-white rounded-lg shadow border border-gray-200 mb-6">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold">Required Documents Checklist</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {requiredDocuments.map((doc) => (
                <div key={doc.name} className="px-4 py-3 flex items-start gap-3">
                  <span className={`mt-0.5 flex-shrink-0 text-lg ${
                    doc.found ? "text-green-600" : validationDone ? "text-red-500" : "text-gray-300"
                  }`}>
                    {doc.found ? "\u2713" : validationDone ? "\u2717" : "\u2022"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium ${
                      doc.found ? "" : validationDone ? "text-red-700" : "text-gray-500"
                    }`}>
                      {doc.name}
                    </p>
                    {doc.found ? (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Pages: {formatPageRange(doc.page_numbers)}
                      </p>
                    ) : validationDone ? (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {doc.where_to_find}
                      </p>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error action — offer re-upload when validation failed/timed out */}
        {status === "error" && (
          <div className="flex items-center justify-center bg-white rounded-lg shadow p-4 border border-gray-200">
            <Link
              href={`/stores/${storeId}/upload`}
              className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2 rounded transition-colors"
            >
              Re-upload Packet
            </Link>
          </div>
        )}

        {/* Action Buttons (only after validation complete) */}
        {status === "complete" && (
          <div className="flex items-center justify-between bg-white rounded-lg shadow p-4 border border-gray-200">
            <Link
              href={`/stores/${storeId}/upload`}
              className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded transition-colors"
            >
              Re-upload
            </Link>
            <div className="flex items-center gap-3">
              {!isComplete && (
                <p className="text-sm text-yellow-600">
                  {requiredDocuments.filter(d => !d.found).length} document(s) missing
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
