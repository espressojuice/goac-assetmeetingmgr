"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { DataTable, formatCurrency, formatDate, type DataTableColumn } from "@/components/ui/DataTable";
import {
  fetchMeetingDetail,
  fetchMeetingDetailFlags,
  fetchMeetingData,
  type MeetingDetail,
  type MeetingFlagDetail,
  type MeetingDataResponse,
} from "@/lib/api";

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

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    processing: "bg-blue-100 text-blue-700",
    pending: "bg-gray-100 text-gray-600",
    error: "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded capitalize ${colors[status] || colors.pending}`}>
      {status}
    </span>
  );
}

// --- Stat Card ---
function StatCard({
  label,
  value,
  detail,
  valueColor,
}: {
  label: string;
  value: string | number;
  detail?: string;
  valueColor?: string;
}) {
  return (
    <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${valueColor || ""}`}>{value}</p>
      {detail && <p className="text-xs text-gray-500 mt-1">{detail}</p>}
    </div>
  );
}

// --- Flag Summary Bar ---
function FlagSummaryBar({ summary }: { summary: MeetingDetail["flags_summary"] }) {
  return (
    <div className="flex flex-wrap gap-3 text-sm mb-4">
      <span className="bg-red-100 text-red-700 px-3 py-1 rounded-full font-medium">
        {summary.red} Red
      </span>
      <span className="bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full font-medium">
        {summary.yellow} Yellow
      </span>
      <span className="bg-gray-100 text-gray-700 px-3 py-1 rounded-full font-medium">
        {summary.open} Open
      </span>
      <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full font-medium">
        {summary.responded} Responded
      </span>
      <span className="bg-red-50 text-red-600 px-3 py-1 rounded-full font-medium">
        {summary.overdue} Overdue
      </span>
    </div>
  );
}

// --- Flags Tab ---
function FlagsTab({ meetingId, token }: { meetingId: string; token?: string }) {
  const [flags, setFlags] = useState<MeetingFlagDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const filters: Record<string, string> = {};
    if (severityFilter) filters.severity = severityFilter;
    if (categoryFilter) filters.category = categoryFilter;
    if (statusFilter) filters.status = statusFilter;
    fetchMeetingDetailFlags(meetingId, filters, token)
      .then(setFlags)
      .catch(() => setFlags([]))
      .finally(() => setLoading(false));
  }, [meetingId, token, severityFilter, categoryFilter, statusFilter]);

  if (loading) return <p className="text-gray-500 p-4">Loading flags...</p>;

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
      {/* Filters */}
      <div className="p-4 border-b border-gray-200 flex flex-wrap gap-3">
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1">
          <option value="">All Severities</option>
          <option value="red">Red</option>
          <option value="yellow">Yellow</option>
        </select>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1">
          <option value="">All Categories</option>
          <option value="inventory">Inventory</option>
          <option value="parts">Parts</option>
          <option value="financial">Financial</option>
          <option value="operations">Operations</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1">
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="responded">Responded</option>
          <option value="escalated">Escalated</option>
        </select>
      </div>

      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left px-4 py-2 font-medium text-gray-600 w-10">Sev</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">Category</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">Message</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">Status</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">Assigned To</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">Deadline</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {flags.map((f) => (
            <>
              <tr
                key={f.id}
                className={`hover:bg-gray-50 cursor-pointer ${
                  f.severity === "red" ? "bg-red-50/50" : "bg-yellow-50/50"
                }`}
                onClick={() => setExpandedId(expandedId === f.id ? null : f.id)}
              >
                <td className="px-4 py-2">
                  <span className={`inline-block w-3 h-3 rounded-full ${
                    f.severity === "red" ? "bg-red-500" : "bg-yellow-400"
                  }`} />
                </td>
                <td className="px-4 py-2 capitalize">{f.category}</td>
                <td className="px-4 py-2 max-w-md truncate">{f.message}</td>
                <td className="px-4 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    f.status === "open" ? "bg-gray-100 text-gray-700" :
                    f.status === "responded" ? "bg-green-100 text-green-700" :
                    "bg-red-100 text-red-700"
                  }`}>
                    {f.status}
                  </span>
                  {f.is_overdue && f.status === "open" && (
                    <span className="ml-1 text-xs bg-red-600 text-white px-1.5 py-0.5 rounded">
                      OVERDUE
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {f.assigned_to?.name || "—"}
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {f.deadline ? formatDate(f.deadline) : "—"}
                </td>
              </tr>
              {expandedId === f.id && (
                <tr key={`${f.id}-detail`} className="bg-gray-50">
                  <td colSpan={6} className="px-6 py-3">
                    <div className="text-sm space-y-2">
                      <p><strong>Field:</strong> {f.field_name} = {f.field_value || "N/A"} (threshold: {f.threshold || "N/A"})</p>
                      <p><strong>Full message:</strong> {f.message}</p>
                      {f.response && (
                        <div className="bg-green-50 border border-green-200 rounded p-3 mt-2">
                          <p className="text-green-800"><strong>Response:</strong> {f.response.text}</p>
                          <p className="text-green-600 text-xs mt-1">
                            by {f.response.responder} at {f.response.submitted_at}
                          </p>
                        </div>
                      )}
                      {!f.response && f.status === "open" && (
                        <button className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-500 mt-1">
                          Respond
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>

      {flags.length === 0 && (
        <p className="text-gray-500 text-sm p-4">No flags match the current filters.</p>
      )}
    </div>
  );
}

// --- Category Data Section ---
function CollapsibleSection({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 mb-4">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <h3 className="font-semibold">
          {title}
          {count != null && (
            <span className="ml-2 text-sm font-normal text-gray-500">({count})</span>
          )}
        </h3>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// --- Inventory Tab ---
function InventoryTab({ meetingId, token }: { meetingId: string; token?: string }) {
  const [data, setData] = useState<MeetingDataResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMeetingData(meetingId, "inventory", token)
      .then(setData)
      .finally(() => setLoading(false));
  }, [meetingId, token]);

  if (loading) return <p className="text-gray-500 p-4">Loading inventory...</p>;
  if (!data) return <p className="text-gray-500 p-4">Failed to load data.</p>;

  const newVehicles = data.data.new_vehicles || [];
  const usedVehicles = data.data.used_vehicles || [];
  const serviceLoaners = data.data.service_loaners || [];
  const floorplan = data.data.floorplan_reconciliation || [];

  const flagRowClass = (row: Record<string, unknown>) =>
    row.flag ? (
      (row.flag as Record<string, unknown>).severity === "red" ? "bg-red-50" : "bg-yellow-50"
    ) : "";

  const newVehicleCols: DataTableColumn[] = [
    { header: "Stock #", accessor: "stock_number", sortable: true },
    { header: "Year", accessor: "year", sortable: true },
    { header: "Make", accessor: "make" },
    { header: "Model", accessor: "model" },
    { header: "Days", accessor: "days_in_stock", sortable: true },
    { header: "Floorplan", accessor: "floorplan_balance", sortable: true, formatter: (v) => formatCurrency(v) },
    { header: "Book Value", accessor: "book_value", formatter: (v) => formatCurrency(v) },
  ];

  const usedVehicleCols: DataTableColumn[] = [
    { header: "Stock #", accessor: "stock_number", sortable: true },
    { header: "Year", accessor: "year", sortable: true },
    { header: "Make", accessor: "make" },
    { header: "Model", accessor: "model" },
    { header: "Days", accessor: "days_in_stock", sortable: true },
    { header: "Book Value", accessor: "book_value", sortable: true, formatter: (v) => formatCurrency(v) },
    { header: "Market", accessor: "market_value", formatter: (v) => formatCurrency(v) },
    { header: "Source", accessor: "acquisition_source" },
  ];

  const loanerCols: DataTableColumn[] = [
    { header: "Stock #", accessor: "stock_number", sortable: true },
    { header: "Year", accessor: "year" },
    { header: "Make", accessor: "make" },
    { header: "Model", accessor: "model" },
    { header: "Days in Service", accessor: "days_in_service", sortable: true },
    { header: "Book Value", accessor: "book_value", formatter: (v) => formatCurrency(v) },
    {
      header: "Neg Equity",
      accessor: "negative_equity",
      sortable: true,
      formatter: (v) => (
        <span className="text-red-600 font-medium">{formatCurrency(v)}</span>
      ),
    },
  ];

  const floorplanCols: DataTableColumn[] = [
    { header: "Type", accessor: "reconciliation_type", formatter: (v) => String(v).replace("_", " ").toUpperCase() },
    { header: "Book Balance", accessor: "book_balance", formatter: (v) => formatCurrency(v) },
    { header: "Floorplan Balance", accessor: "floorplan_balance", formatter: (v) => formatCurrency(v) },
    {
      header: "Variance",
      accessor: "variance",
      sortable: true,
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        return (
          <span className={num !== 0 ? "text-red-600 font-medium" : "text-green-600"}>
            {formatCurrency(v)}
          </span>
        );
      },
    },
    { header: "Units (Book)", accessor: "unit_count_book" },
    { header: "Units (FP)", accessor: "unit_count_floorplan" },
  ];

  return (
    <>
      <CollapsibleSection title="New Vehicles" count={newVehicles.length} defaultOpen>
        <DataTable columns={newVehicleCols} data={newVehicles} rowClassName={flagRowClass} />
      </CollapsibleSection>
      <CollapsibleSection title="Used Vehicles" count={usedVehicles.length} defaultOpen>
        <DataTable columns={usedVehicleCols} data={usedVehicles} rowClassName={flagRowClass} />
      </CollapsibleSection>
      <CollapsibleSection title="Service Loaners" count={serviceLoaners.length}>
        <DataTable columns={loanerCols} data={serviceLoaners} rowClassName={flagRowClass} />
      </CollapsibleSection>
      <CollapsibleSection title="Floorplan Reconciliation" count={floorplan.length}>
        <DataTable columns={floorplanCols} data={floorplan} />
      </CollapsibleSection>
    </>
  );
}

// --- Financial Tab ---
function FinancialTab({ meetingId, token }: { meetingId: string; token?: string }) {
  const [data, setData] = useState<MeetingDataResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMeetingData(meetingId, "financial", token)
      .then(setData)
      .finally(() => setLoading(false));
  }, [meetingId, token]);

  if (loading) return <p className="text-gray-500 p-4">Loading financial data...</p>;
  if (!data) return <p className="text-gray-500 p-4">Failed to load data.</p>;

  const receivables = data.data.receivables || [];
  const chargebacks = data.data.fi_chargebacks || [];
  const contracts = data.data.contracts_in_transit || [];
  const prepaids = data.data.prepaids || [];
  const policyAdj = data.data.policy_adjustments || [];

  const receivableCols: DataTableColumn[] = [
    { header: "Type", accessor: "receivable_type", formatter: (v) => String(v).replace(/_/g, " ").replace(/\d+/, " $&") },
    { header: "Schedule", accessor: "schedule_number" },
    { header: "Current", accessor: "current_balance", formatter: (v) => formatCurrency(v) },
    {
      header: "Over 30",
      accessor: "over_30",
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        return <span className={num > 0 ? "text-yellow-600 font-medium" : ""}>{formatCurrency(v)}</span>;
      },
    },
    {
      header: "Over 60",
      accessor: "over_60",
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        return <span className={num > 0 ? "text-orange-600 font-medium" : ""}>{formatCurrency(v)}</span>;
      },
    },
    {
      header: "Over 90",
      accessor: "over_90",
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        return <span className={num > 0 ? "text-red-600 font-medium" : ""}>{formatCurrency(v)}</span>;
      },
    },
    { header: "Total", accessor: "total_balance", sortable: true, formatter: (v) => formatCurrency(v) },
  ];

  const chargebackCols: DataTableColumn[] = [
    { header: "Account #", accessor: "account_number" },
    { header: "Description", accessor: "account_description" },
    { header: "Current Balance", accessor: "current_balance", formatter: (v) => formatCurrency(v) },
    {
      header: "Over 90",
      accessor: "over_90_balance",
      sortable: true,
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        return <span className={num > 0 ? "text-red-600 font-medium" : ""}>{formatCurrency(v)}</span>;
      },
    },
  ];

  const contractCols: DataTableColumn[] = [
    { header: "Deal #", accessor: "deal_number" },
    { header: "Customer", accessor: "customer_name" },
    { header: "Sale Date", accessor: "sale_date", formatter: (v) => formatDate(v) },
    {
      header: "Days",
      accessor: "days_in_transit",
      sortable: true,
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        const color = num > 30 ? "text-red-600 font-medium" : num > 14 ? "text-yellow-600" : "";
        return <span className={color}>{num}</span>;
      },
    },
    { header: "Amount", accessor: "amount", formatter: (v) => formatCurrency(v) },
    { header: "Lender", accessor: "lender" },
  ];

  const prepaidCols: DataTableColumn[] = [
    { header: "GL Account", accessor: "gl_account" },
    { header: "Description", accessor: "description" },
    { header: "Amount", accessor: "amount", sortable: true, formatter: (v) => formatCurrency(v) },
  ];

  const policyCols: DataTableColumn[] = [
    { header: "GL Account", accessor: "gl_account" },
    { header: "Description", accessor: "description" },
    { header: "Amount", accessor: "amount", sortable: true, formatter: (v) => formatCurrency(v) },
    { header: "Date", accessor: "adjustment_date", formatter: (v) => formatDate(v) },
  ];

  return (
    <>
      <CollapsibleSection title="Receivables" count={receivables.length} defaultOpen>
        <DataTable columns={receivableCols} data={receivables} />
      </CollapsibleSection>
      <CollapsibleSection title="F&I Chargebacks" count={chargebacks.length}>
        <DataTable columns={chargebackCols} data={chargebacks} />
      </CollapsibleSection>
      <CollapsibleSection title="Contracts in Transit" count={contracts.length} defaultOpen>
        <DataTable columns={contractCols} data={contracts} />
      </CollapsibleSection>
      <CollapsibleSection title="Prepaids" count={prepaids.length}>
        <DataTable columns={prepaidCols} data={prepaids} />
      </CollapsibleSection>
      <CollapsibleSection title="Policy Adjustments" count={policyAdj.length}>
        <DataTable columns={policyCols} data={policyAdj} />
      </CollapsibleSection>
    </>
  );
}

// --- Operations Tab ---
function OperationsTab({ meetingId, token }: { meetingId: string; token?: string }) {
  const [data, setData] = useState<MeetingDataResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMeetingData(meetingId, "operations", token)
      .then(setData)
      .finally(() => setLoading(false));
  }, [meetingId, token]);

  if (loading) return <p className="text-gray-500 p-4">Loading operations data...</p>;
  if (!data) return <p className="text-gray-500 p-4">Failed to load data.</p>;

  const openROs = data.data.open_repair_orders || [];
  const warrantyClaims = data.data.warranty_claims || [];
  const missingTitles = data.data.missing_titles || [];
  const slowAccounting = data.data.slow_to_accounting || [];

  const flagRowClass = (row: Record<string, unknown>) =>
    row.flag ? (
      (row.flag as Record<string, unknown>).severity === "red" ? "bg-red-50" : "bg-yellow-50"
    ) : "";

  const roCols: DataTableColumn[] = [
    { header: "RO #", accessor: "ro_number", sortable: true },
    { header: "Open Date", accessor: "open_date", formatter: (v) => formatDate(v) },
    {
      header: "Days Open",
      accessor: "days_open",
      sortable: true,
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        const color = num > 30 ? "text-red-600 font-medium" : num > 14 ? "text-yellow-600" : "";
        return <span className={color}>{num}</span>;
      },
    },
    { header: "Customer", accessor: "customer_name" },
    { header: "Type", accessor: "service_type" },
    { header: "Amount", accessor: "amount", formatter: (v) => formatCurrency(v) },
  ];

  const warrantyCols: DataTableColumn[] = [
    { header: "Claim #", accessor: "claim_number", sortable: true },
    { header: "Date", accessor: "claim_date", formatter: (v) => formatDate(v) },
    { header: "Amount", accessor: "amount", sortable: true, formatter: (v) => formatCurrency(v) },
    { header: "Status", accessor: "status" },
  ];

  const titleCols: DataTableColumn[] = [
    { header: "Stock #", accessor: "stock_number", sortable: true },
    { header: "Deal #", accessor: "deal_number" },
    { header: "Customer", accessor: "customer_name" },
    {
      header: "Days Missing",
      accessor: "days_missing",
      sortable: true,
      formatter: (v) => <span className="text-red-600 font-medium">{String(v)}</span>,
    },
  ];

  const slowCols: DataTableColumn[] = [
    { header: "Deal #", accessor: "deal_number", sortable: true },
    { header: "Sale Date", accessor: "sale_date", formatter: (v) => formatDate(v) },
    {
      header: "Days",
      accessor: "days_to_accounting",
      sortable: true,
      formatter: (v) => {
        const num = typeof v === "number" ? v : 0;
        const color = num > 14 ? "text-red-600 font-medium" : num > 7 ? "text-yellow-600" : "";
        return <span className={color}>{num}</span>;
      },
    },
    { header: "Customer", accessor: "customer_name" },
    { header: "Salesperson", accessor: "salesperson" },
  ];

  return (
    <>
      <CollapsibleSection title="Open Repair Orders" count={openROs.length} defaultOpen>
        <DataTable columns={roCols} data={openROs} rowClassName={flagRowClass} />
      </CollapsibleSection>
      <CollapsibleSection title="Warranty Claims" count={warrantyClaims.length}>
        <DataTable columns={warrantyCols} data={warrantyClaims} />
      </CollapsibleSection>
      <CollapsibleSection title="Missing Titles" count={missingTitles.length} defaultOpen>
        <DataTable
          columns={titleCols}
          data={missingTitles}
          rowClassName={() => "bg-red-50"}
        />
      </CollapsibleSection>
      <CollapsibleSection title="Slow to Accounting" count={slowAccounting.length}>
        <DataTable columns={slowCols} data={slowAccounting} rowClassName={flagRowClass} />
      </CollapsibleSection>
    </>
  );
}

// --- Main Page ---
export default function MeetingDetailPage() {
  const { storeId, meetingId } = useParams<{ storeId: string; meetingId: string }>();
  const { data: session } = useSession();
  const [detail, setDetail] = useState<MeetingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const token = (session as any)?.backendToken;

  useEffect(() => {
    if (!meetingId) return;
    fetchMeetingDetail(meetingId, token)
      .then(setDetail)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [meetingId, token]);

  const meeting = detail?.meeting;
  const exec = detail?.executive_summary;
  const flagsSummary = detail?.flags_summary;

  const tabs: TabItem[] = [
    { key: "flags", label: "Flags", count: flagsSummary?.total },
    { key: "inventory", label: "Inventory" },
    { key: "financial", label: "Financial" },
    { key: "operations", label: "Operations" },
  ];

  return (
    <>
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Breadcrumb */}
        <nav className="text-sm text-gray-500 mb-4 flex items-center gap-1">
          <Link href="/dashboard" className="text-blue-600 hover:underline">Dashboard</Link>
          <span>/</span>
          {meeting ? (
            <>
              <Link href={`/stores/${storeId}`} className="text-blue-600 hover:underline">
                {meeting.store_name}
              </Link>
              <span>/</span>
              <span className="text-gray-700">{formatMeetingDate(meeting.meeting_date)}</span>
            </>
          ) : (
            <span>Meeting</span>
          )}
        </nav>

        {loading && <p className="text-gray-500">Loading meeting...</p>}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">{error}</div>
        )}

        {detail && meeting && exec && flagsSummary && (
          <>
            {/* Header */}
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200 mb-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-2xl font-bold">
                    {formatMeetingDate(meeting.meeting_date)}
                  </h1>
                  <p className="text-sm text-gray-500 mt-1">
                    {meeting.store_name} &middot; <StatusBadge status={meeting.status} />
                  </p>
                </div>
                <div className="flex gap-2">
                  {meeting.packet_url && (
                    <a
                      href={`${API_BASE}/api/v1/packets/${meetingId}`}
                      className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-500"
                    >
                      Download Packet PDF
                    </a>
                  )}
                  {meeting.flagged_items_url && (
                    <a
                      href={`${API_BASE}/api/v1/packets/${meetingId}/flagged-items`}
                      className="text-sm bg-red-600 text-white px-3 py-1.5 rounded hover:bg-red-500"
                    >
                      Download Flagged Items PDF
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Executive Summary */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
              <StatCard
                label="New Vehicles"
                value={exec.new_vehicle_count}
                detail={`${formatCurrency(exec.new_vehicle_floorplan_total)} floorplan`}
              />
              <StatCard
                label="Used Vehicles"
                value={exec.used_vehicle_count}
                detail={`${exec.used_over_60_days} over 60d, ${exec.used_over_90_days} over 90d (${formatCurrency(exec.used_over_90_exposure)})`}
              />
              <StatCard
                label="Service Loaners"
                value={exec.service_loaner_count}
                detail={`${formatCurrency(exec.service_loaner_neg_equity_total)} neg equity`}
                valueColor="text-red-600"
              />
              <StatCard
                label="Parts Turnover"
                value={exec.parts_turnover != null ? exec.parts_turnover.toFixed(1) : "N/A"}
                valueColor={
                  exec.parts_turnover == null ? "" :
                  exec.parts_turnover < 1.0 ? "text-red-600" :
                  exec.parts_turnover < 2.0 ? "text-yellow-600" : "text-green-600"
                }
              />
              <StatCard label="Open ROs" value={exec.open_ro_count} />
              <StatCard
                label="Missing Titles"
                value={exec.missing_titles_count}
                valueColor={exec.missing_titles_count > 0 ? "text-red-600" : ""}
              />
              <StatCard label="Contracts in Transit" value={exec.contracts_in_transit_count} />
              <StatCard
                label="Receivables Over 30"
                value={formatCurrency(exec.receivables_over_30_total)}
                valueColor={exec.receivables_over_30_total === 0 ? "text-green-600" : "text-red-600"}
              />
            </div>

            {/* Floorplan Variance */}
            <div className="bg-white rounded-lg shadow p-4 border border-gray-200 mb-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500 uppercase tracking-wide">Floorplan Variance</p>
                <p className={`text-xl font-bold ${
                  exec.floorplan_variance && exec.floorplan_variance !== 0 ? "text-red-600" : "text-green-600"
                }`}>
                  {formatCurrency(exec.floorplan_variance ?? 0)}
                </p>
              </div>
            </div>

            {/* Flag Summary Bar */}
            <FlagSummaryBar summary={flagsSummary} />

            {/* Tabbed Content */}
            <Tabs tabs={tabs} defaultTab="flags">
              {(activeTab) => (
                <>
                  {activeTab === "flags" && <FlagsTab meetingId={meetingId} token={token} />}
                  {activeTab === "inventory" && <InventoryTab meetingId={meetingId} token={token} />}
                  {activeTab === "financial" && <FinancialTab meetingId={meetingId} token={token} />}
                  {activeTab === "operations" && <OperationsTab meetingId={meetingId} token={token} />}
                </>
              )}
            </Tabs>
          </>
        )}
      </main>
    </>
  );
}
