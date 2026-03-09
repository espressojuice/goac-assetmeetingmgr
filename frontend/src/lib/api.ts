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

// --- Stores ---
export interface StoreDetail {
  id: string;
  name: string;
  code: string;
  brand: string | null;
  city: string;
  state: string;
  timezone: string;
  meeting_cadence: string | null;
  gm_name: string | null;
  gm_email: string | null;
  is_active: boolean;
  created_at: string;
  recent_meetings: MeetingBrief[];
}

export interface MeetingBrief {
  id: string;
  meeting_date: string;
  status: string;
  packet_url: string | null;
  flagged_items_url: string | null;
  created_at: string;
}

export function fetchStore(storeId: string, token?: string): Promise<StoreDetail> {
  return apiFetch(`/stores/${storeId}`, { token });
}

// --- Meetings ---
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
