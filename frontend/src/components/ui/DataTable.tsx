"use client";

import { useState, useMemo } from "react";

export interface DataTableColumn<T = Record<string, unknown>> {
  header: string;
  accessor: string;
  sortable?: boolean;
  formatter?: (value: unknown, row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T = Record<string, unknown>> {
  columns: DataTableColumn<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string;
  emptyMessage?: string;
}

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce((acc: unknown, key) => {
    if (acc && typeof acc === "object") return (acc as Record<string, unknown>)[key];
    return undefined;
  }, obj);
}

export function formatCurrency(value: unknown): string {
  if (value == null) return "—";
  const num = typeof value === "number" ? value : parseFloat(String(value));
  if (isNaN(num)) return "—";
  return num.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatDate(value: unknown): string {
  if (!value) return "—";
  const str = String(value);
  if (str.length === 10 && str.includes("-")) {
    const [y, m, d] = str.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }
  return str;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  rowClassName,
  emptyMessage = "No data available.",
}: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const handleSort = (accessor: string) => {
    if (sortCol === accessor) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortCol(accessor);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    if (!sortCol) return data;
    return [...data].sort((a, b) => {
      const aVal = getNestedValue(a, sortCol);
      const bVal = getNestedValue(b, sortCol);
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, sortCol, sortDir]);

  if (data.length === 0) {
    return (
      <p className="text-gray-500 text-sm p-4">{emptyMessage}</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 sticky top-0">
          <tr>
            {columns.map((col) => (
              <th
                key={col.accessor}
                className={`text-left px-4 py-2 font-medium text-gray-600 whitespace-nowrap ${
                  col.sortable ? "cursor-pointer select-none hover:text-gray-900" : ""
                } ${col.className || ""}`}
                onClick={col.sortable ? () => handleSort(col.accessor) : undefined}
              >
                {col.header}
                {col.sortable && sortCol === col.accessor && (
                  <span className="ml-1">{sortDir === "asc" ? "▲" : "▼"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sorted.map((row, idx) => (
            <tr
              key={idx}
              className={`hover:bg-gray-50 ${onRowClick ? "cursor-pointer" : ""} ${
                rowClassName ? rowClassName(row) : ""
              }`}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => {
                const val = getNestedValue(row, col.accessor);
                return (
                  <td key={col.accessor} className={`px-4 py-2 ${col.className || ""}`}>
                    {col.formatter ? col.formatter(val, row) : val != null ? String(val) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
