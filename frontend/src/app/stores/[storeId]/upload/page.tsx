"use client";

import { useSession } from "next-auth/react";
import { useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { uploadForValidation, uploadBulkForValidation } from "@/lib/api";

export default function UploadPage() {
  const { storeId } = useParams<{ storeId: string }>();
  const { data: session } = useSession();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [meetingDate, setMeetingDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const token = (session as any)?.backendToken;

  function addFiles(newFiles: File[]) {
    const pdfs = newFiles.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length === 0) {
      setError("Only PDF files are accepted.");
      return;
    }
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => `${f.name}_${f.size}`));
      const unique = pdfs.filter((f) => !existing.has(`${f.name}_${f.size}`));
      return [...prev, ...unique];
    });
    setError(null);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleUpload() {
    if (!storeId || files.length === 0) return;
    setUploading(true);
    setError(null);

    try {
      const result =
        files.length === 1
          ? await uploadForValidation(files[0], storeId, meetingDate, token)
          : await uploadBulkForValidation(files, storeId, meetingDate, token);

      // Store validation data for the review page
      sessionStorage.setItem(
        `validation_${result.meeting_id}`,
        JSON.stringify(result.validation)
      );

      // Redirect to validation review page
      router.push(
        `/stores/${storeId}/meetings/${result.meeting_id}/validate`
      );
    } catch (err: any) {
      setError(err.message || "Upload failed");
      setUploading(false);
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  return (
    <>
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 py-6">
        <nav className="text-sm text-gray-500 mb-4 flex items-center gap-1">
          <Link href="/dashboard" className="text-blue-600 hover:underline">Dashboard</Link>
          <span>/</span>
          <Link href={`/stores/${storeId}`} className="text-blue-600 hover:underline">Store</Link>
          <span>/</span>
          <span className="text-gray-700">Upload Reports</span>
        </nav>

        <h1 className="text-2xl font-bold mb-6">Upload R&R Reports</h1>

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">{error}</div>
        )}

        {/* Meeting Date */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Meeting Date
          </label>
          <input
            type="date"
            value={meetingDate}
            onChange={(e) => setMeetingDate(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm w-48"
          />
        </div>

        {/* Drop Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            addFiles(Array.from(e.dataTransfer.files));
          }}
          className={`border-2 border-dashed rounded-lg p-8 text-center mb-4 transition-colors ${
            dragActive ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-gray-50"
          }`}
        >
          <p className="text-gray-600 mb-2">Drag & drop PDF files here</p>
          <p className="text-gray-400 text-sm mb-3">or</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-sm bg-gray-200 hover:bg-gray-300 text-gray-700 px-4 py-2 rounded transition-colors"
          >
            Choose Files
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              if (e.target.files) addFiles(Array.from(e.target.files));
              e.target.value = "";
            }}
          />
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="bg-white rounded-lg shadow border border-gray-200 mb-4 divide-y divide-gray-100">
            {files.map((f, i) => (
              <div key={`${f.name}_${f.size}`} className="px-4 py-2 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium">{f.name}</span>
                  <span className="text-xs text-gray-400 ml-2">{formatSize(f.size)}</span>
                </div>
                <button
                  onClick={() => removeFile(i)}
                  className="text-gray-400 hover:text-red-500 text-lg leading-none"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={uploading || files.length === 0}
          className={`w-full text-sm font-medium px-4 py-3 rounded transition-colors ${
            uploading || files.length === 0
              ? "bg-gray-300 text-gray-500 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 text-white"
          }`}
        >
          {uploading ? "Uploading & Validating..." : "Upload & Validate"}
        </button>
      </main>
    </>
  );
}
