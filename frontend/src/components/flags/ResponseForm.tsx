"use client";

import { useState } from "react";
import { respondToFlag } from "@/lib/api";

interface ResponseFormProps {
  flagId: string;
  token?: string;
  existingResponse?: string | null;
  onSuccess?: () => void;
}

export function ResponseForm({ flagId, token, existingResponse, onSuccess }: ResponseFormProps) {
  const [text, setText] = useState(existingResponse || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const isValid = text.trim().length >= 10;
  const isReadOnly = !!existingResponse && !success;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;

    setSubmitting(true);
    setError(null);
    try {
      await respondToFlag(flagId, text.trim(), token);
      setSuccess(true);
      onSuccess?.();
    } catch (err: any) {
      setError(err.message || "Failed to submit response");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <p className="text-green-800 font-medium">Response submitted successfully.</p>
        <p className="text-green-700 text-sm mt-1">{text}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label htmlFor="response" className="block text-sm font-medium text-gray-700 mb-1">
          {existingResponse ? "Your Response" : "Write your response"}
        </label>
        <textarea
          id="response"
          value={text}
          onChange={(e) => setText(e.target.value)}
          readOnly={isReadOnly}
          rows={4}
          className={`w-full border rounded-lg px-3 py-2 text-sm ${
            isReadOnly ? "bg-gray-50 text-gray-600" : "bg-white"
          } ${text.length > 0 && text.length < 10 ? "border-red-300" : "border-gray-300"}`}
          placeholder="Describe the action taken or planned (minimum 10 characters)..."
        />
        <div className="flex justify-between text-xs mt-1">
          <span className={text.length > 0 && text.length < 10 ? "text-red-500" : "text-gray-400"}>
            {text.length > 0 && text.length < 10
              ? `${10 - text.length} more characters required`
              : `${text.length} characters`}
          </span>
          {!isReadOnly && (
            <span className="text-gray-400">Min 10 characters</span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 text-sm p-3 rounded">{error}</div>
      )}

      {!isReadOnly && (
        <button
          type="submit"
          disabled={!isValid || submitting}
          className={`px-4 py-2 rounded-lg text-sm font-medium text-white ${
            isValid && !submitting
              ? "bg-blue-600 hover:bg-blue-700"
              : "bg-gray-300 cursor-not-allowed"
          }`}
        >
          {submitting ? "Submitting..." : existingResponse ? "Update Response" : "Submit Response"}
        </button>
      )}
    </form>
  );
}
