const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  token?: string;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, headers: extraHeaders, ...rest } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((extraHeaders as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1${path}`, { headers, ...rest });
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      // Sign out via NextAuth to clear session, then redirect to home.
      // Using dynamic import to avoid circular deps and SSR issues.
      const { signOut } = await import("next-auth/react");
      await signOut({ callbackUrl: "/" });
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// --- Dashboard ---
export interface StoreDashboardItem {
  id: string;
  name: string;
  code: string;
  last_meeting_date: string | null;
  next_meeting_date: string | null;
  flags: {
    total: number;
    red: number;
    yellow: number;
    open: number;
    responded: number;
  };
  response_rate: number;
  overdue_count: number;
  recurring_issues: number;
}

export interface DashboardTotals {
  total_stores: number;
  total_open_flags: number;
  total_overdue: number;
  avg_response_rate: number;
  meetings_this_week: number;
}

export interface DashboardData {
  stores: StoreDashboardItem[];
  totals: DashboardTotals;
}

export function fetchDashboard(token?: string): Promise<DashboardData> {
  return apiFetch("/dashboard", { token });
}

// --- Stores (Rich Detail) ---
export interface StoreInfo {
  id: string;
  name: string;
  code: string;
  brand: string | null;
  city: string;
  state: string;
  timezone: string;
  gm_name: string | null;
  gm_email: string | null;
  meeting_cadence: string | null;
  is_active: boolean;
}

export interface StoreStats {
  total_meetings: number;
  total_flags_all_time: number;
  current_open_flags: number;
  current_overdue_flags: number;
  response_rate: number;
  avg_flags_per_meeting: number;
  most_common_flag_category: string | null;
  recurring_issues_count: number;
}

export interface MeetingFlagSummary {
  total: number;
  red: number;
  yellow: number;
  open: number;
  responded: number;
  response_rate: number;
}

export interface RecentMeetingItem {
  id: string;
  meeting_date: string;
  status: string;
  packet_generated_at: string | null;
  flags: MeetingFlagSummary;
  response_rate: number;
  packet_url: string | null;
  flagged_items_url: string | null;
}

export interface StoreUserItem {
  id: string;
  name: string;
  email: string;
  role_at_store: string;
}

export interface StoreDetail {
  store: StoreInfo;
  stats: StoreStats;
  recent_meetings: RecentMeetingItem[];
  users: StoreUserItem[];
}

export interface FlagTrendMeeting {
  date: string;
  red: number;
  yellow: number;
  responded: number;
  response_rate: number;
}

export interface FlagTrendsData {
  meetings: FlagTrendMeeting[];
}

export function fetchStoreDetail(storeId: string, token?: string): Promise<StoreDetail> {
  return apiFetch(`/stores/${storeId}`, { token });
}

export function fetchStoreFlagTrends(storeId: string, token?: string): Promise<FlagTrendsData> {
  return apiFetch(`/stores/${storeId}/flag-trends`, { token });
}

export function fetchStoreMeetings(storeId: string, token?: string, limit?: number): Promise<RecentMeetingItem[]> {
  const params = limit ? `?limit=${limit}` : "";
  return apiFetch(`/stores/${storeId}/meetings${params}`, { token });
}

// --- Meeting Detail ---
export interface MeetingInfo {
  id: string;
  store_id: string;
  store_name: string;
  meeting_date: string;
  status: string;
  packet_generated_at: string | null;
  packet_url: string | null;
  flagged_items_url: string | null;
  notes: string | null;
}

export interface ExecutiveSummary {
  new_vehicle_count: number;
  new_vehicle_floorplan_total: number;
  used_vehicle_count: number;
  used_over_60_days: number;
  used_over_90_days: number;
  used_over_90_exposure: number;
  service_loaner_count: number;
  service_loaner_neg_equity_total: number;
  parts_turnover: number | null;
  open_ro_count: number;
  receivables_over_30_total: number;
  missing_titles_count: number;
  contracts_in_transit_count: number;
  floorplan_variance: number | null;
}

export interface FlagsByCategoryItem {
  red: number;
  yellow: number;
}

export interface FlagsSummary {
  total: number;
  red: number;
  yellow: number;
  open: number;
  responded: number;
  overdue: number;
  by_category: Record<string, FlagsByCategoryItem>;
}

export interface MeetingDetail {
  meeting: MeetingInfo;
  executive_summary: ExecutiveSummary;
  flags_summary: FlagsSummary;
}

export interface AssignedToInfo {
  id: string;
  name: string;
  email: string;
  deadline: string | null;
  assignment_status: string | null;
}

export interface FlagResponseInfoType {
  text: string;
  submitted_at: string | null;
  responder: string | null;
}

export interface MeetingFlagDetail {
  id: string;
  category: string;
  severity: string;
  message: string;
  field_name: string;
  field_value: string | null;
  threshold: string | null;
  status: string;
  assigned_to: AssignedToInfo | null;
  response: FlagResponseInfoType | null;
  deadline: string | null;
  is_overdue: boolean;
  escalation_level: number;
  created_at: string | null;
}

export interface MeetingDataResponse {
  meeting_id: string;
  category: string;
  data: Record<string, Record<string, unknown>[]>;
}

export function fetchMeetingDetail(meetingId: string, token?: string): Promise<MeetingDetail> {
  return apiFetch(`/meetings/${meetingId}`, { token });
}

export function fetchMeetingData(meetingId: string, category: string, token?: string): Promise<MeetingDataResponse> {
  return apiFetch(`/meetings/${meetingId}/data/${category}`, { token });
}

export function fetchMeetingDetailFlags(
  meetingId: string,
  filters?: { severity?: string; category?: string; status?: string; sort_by?: string },
  token?: string,
): Promise<MeetingFlagDetail[]> {
  const params = new URLSearchParams();
  if (filters?.severity) params.set("severity", filters.severity);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.sort_by) params.set("sort_by", filters.sort_by);
  const qs = params.toString();
  return apiFetch(`/meetings/${meetingId}/flags${qs ? `?${qs}` : ""}`, { token });
}

// --- Meetings (legacy) ---
export interface MeetingSummary {
  meeting: {
    id: string;
    store_id: string;
    meeting_date: string;
    status: string;
    packet_url: string | null;
    flagged_items_url: string | null;
    created_at: string;
  };
  store: {
    id: string;
    name: string;
    code: string;
  };
  record_counts: Record<string, number>;
  flags: FlagItem[];
  flag_stats: FlagStats;
}

export interface FlagItem {
  id: string;
  meeting_id: string;
  store_id: string;
  category: string;
  severity: string;
  field_name: string;
  field_value: string | null;
  threshold: string | null;
  message: string;
  status: string;
  response_text: string | null;
  responded_by: string | null;
  responded_at: string | null;
  created_at: string;
}

export interface FlagStats {
  total: number;
  yellow: number;
  red: number;
  open: number;
  responded: number;
  by_category: Record<string, number>;
}

export function fetchMeetingSummary(meetingId: string, token?: string): Promise<MeetingSummary> {
  return apiFetch(`/packets/${meetingId}/summary`, { token });
}

export function fetchMeetingFlags(meetingId: string, token?: string): Promise<FlagItem[]> {
  return apiFetch(`/flags/${meetingId}`, { token });
}

// --- Flag Workflow ---
export interface MyFlagItem {
  id: string;
  assignment_id: string;
  category: string;
  severity: string;
  message: string;
  field_name: string;
  field_value: string | null;
  threshold: string | null;
  status: string;
  assignment_status: string;
  store_id: string;
  store_name: string;
  meeting_id: string;
  meeting_date: string;
  deadline: string;
  is_overdue: boolean;
  days_overdue: number;
  escalation_level: number;
  response_text: string | null;
  responded_at: string | null;
  created_at: string | null;
}

export function fetchMyFlags(
  token?: string,
  filters?: { status?: string; store_id?: string },
): Promise<MyFlagItem[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.store_id) params.set("store_id", filters.store_id);
  const qs = params.toString();
  return apiFetch(`/flags/my/assigned${qs ? `?${qs}` : ""}`, { token });
}

export function assignFlag(
  flagId: string,
  assignedToId: string,
  token?: string,
): Promise<{ id: string; flag_id: string; assigned_to_id: string; deadline: string; status: string }> {
  return apiFetch(`/flags/${flagId}/assign`, {
    method: "POST",
    body: JSON.stringify({ assigned_to_id: assignedToId }),
    token,
  });
}

export function respondToFlag(
  flagId: string,
  responseText: string,
  token?: string,
): Promise<{ id: string; flag_id: string; response_text: string; created_at: string | null }> {
  return apiFetch(`/flags/${flagId}/respond-workflow`, {
    method: "POST",
    body: JSON.stringify({ response_text: responseText }),
    token,
  });
}

export function escalateFlag(
  flagId: string,
  reason?: string,
  token?: string,
): Promise<{ id: string; status: string; escalation_level: number }> {
  return apiFetch(`/flags/${flagId}/escalate`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
    token,
  });
}

export function autoAssignMeetingFlags(
  meetingId: string,
  token?: string,
): Promise<{ assigned_count: number; unassigned_count: number; by_category: Record<string, number> }> {
  return apiFetch(`/meetings/${meetingId}/auto-assign`, {
    method: "POST",
    token,
  });
}

// --- Notifications ---
export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  reference_id: string | null;
  is_read: boolean;
  created_at: string | null;
}

export function fetchNotifications(
  token?: string,
  unreadOnly?: boolean,
  limit?: number,
): Promise<NotificationItem[]> {
  const params = new URLSearchParams();
  if (unreadOnly) params.set("unread_only", "true");
  if (limit) params.set("limit", String(limit));
  const qs = params.toString();
  return apiFetch(`/notifications${qs ? `?${qs}` : ""}`, { token });
}

export function fetchUnreadCount(token?: string): Promise<{ unread_count: number }> {
  return apiFetch("/notifications/unread-count", { token });
}

export function markNotificationRead(notificationId: string, token?: string): Promise<{ id: string; is_read: boolean }> {
  return apiFetch(`/notifications/${notificationId}/read`, { method: "PATCH", token });
}

export function markAllNotificationsRead(token?: string): Promise<{ status: string }> {
  return apiFetch("/notifications/read-all", { method: "POST", token });
}

// --- Upload Validation ---

export interface ClassifiedPage {
  page_number: number;
  document_type: string;
  confidence: number;
}

export interface UnclassifiedPage {
  page_number: number;
  snippet: string;
}

export interface RequiredDocumentCheck {
  name: string;
  found: boolean;
  page_numbers: number[];
  where_to_find: string;
}

export interface DetailedValidationResult {
  classified_pages: ClassifiedPage[];
  unclassified_pages: UnclassifiedPage[];
  required_documents: RequiredDocumentCheck[];
  completeness_percentage: number;
  is_complete: boolean;
  total_pages: number;
}

export interface ValidationUploadResponse {
  meeting_id: string;
  store_id: string;
  total_pages: number;
  validation: DetailedValidationResult;
}

export interface UploadAcceptedResponse {
  meeting_id: string;
  store_id: string;
  total_pages: number;
}

export interface ValidationProgressResponse {
  status: string;
  current_page: number;
  total_pages: number;
  classified_pages: ClassifiedPage[];
  unclassified_pages: UnclassifiedPage[];
  required_documents: RequiredDocumentCheck[];
  completeness_percentage: number;
  is_complete: boolean;
  error: string | null;
}

export interface ApproveResponse {
  meeting_id: string;
  pages_extracted: number;
  records_parsed: Record<string, number>;
  flags_generated: Record<string, number>;
  packet_url: string | null;
  flagged_items_url: string | null;
}

export async function uploadForValidation(
  file: File,
  storeId: string,
  meetingDate: string,
  token?: string,
): Promise<UploadAcceptedResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("store_id", storeId);
  formData.append("meeting_date", meetingDate);

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json();
}

export async function uploadBulkForValidation(
  files: File[],
  storeId: string,
  meetingDate: string,
  token?: string,
): Promise<UploadAcceptedResponse> {
  const formData = new FormData();
  formData.append("store_id", storeId);
  formData.append("meeting_date", meetingDate);
  files.forEach((f) => formData.append("files", f));

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/upload/bulk`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json();
}

export function fetchValidationProgress(
  meetingId: string,
  token?: string,
): Promise<ValidationProgressResponse> {
  return apiFetch(`/upload/${meetingId}/progress`, { token });
}

export function approveUpload(meetingId: string, token?: string): Promise<ApproveResponse> {
  return apiFetch(`/upload/${meetingId}/approve`, { method: "POST", token });
}

// --- Auth ---
export interface AuthCallbackResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
}

export function authCallback(data: {
  email: string;
  name: string;
  google_id: string;
  avatar_url?: string;
}): Promise<AuthCallbackResponse> {
  return apiFetch("/auth/callback", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
