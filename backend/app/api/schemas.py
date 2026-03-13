"""Pydantic response schemas for API endpoints."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Packet Validation ---

class FoundDocument(BaseModel):
    name: str
    page_numbers: list[int]


class MissingDocument(BaseModel):
    name: str
    where_to_find: str


class PacketValidationResult(BaseModel):
    found_documents: list[FoundDocument]
    missing_documents: list[MissingDocument]
    completeness_percentage: float
    is_complete: bool
    total_pages: int


# --- Detailed Packet Validation (for review page) ---

class ClassifiedPage(BaseModel):
    page_number: int
    document_type: str
    confidence: int  # match score from classifier
    subtype: Optional[str] = None  # e.g., "F&I Chargeback — New Over 90", "GL 0504 New"
    needs_user_input: bool = False  # True when GL 0504 New/Used can't be auto-determined


class UnclassifiedPage(BaseModel):
    page_number: int
    snippet: str  # first ~120 chars of page text for identification


class RequiredDocumentCheck(BaseModel):
    name: str
    found: bool
    page_numbers: list[int] = []
    where_to_find: str


class DetailedValidationResult(BaseModel):
    classified_pages: list[ClassifiedPage]
    unclassified_pages: list[UnclassifiedPage]
    required_documents: list[RequiredDocumentCheck]
    completeness_percentage: float
    is_complete: bool
    total_pages: int


# --- Upload ---

class ValidationUploadResponse(BaseModel):
    """Response from upload endpoint — validation only, no processing yet."""
    meeting_id: str
    store_id: str
    total_pages: int
    validation: DetailedValidationResult


class UploadResponse(BaseModel):
    meeting_id: str
    pages_extracted: int
    records_parsed: dict[str, int]
    flags_generated: dict[str, int]
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None
    validation: Optional[PacketValidationResult] = None


class BulkUploadResponse(BaseModel):
    meeting_id: str
    files_processed: int
    total_pages_extracted: int
    records_parsed: dict[str, int]
    flags_generated: dict[str, int]
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None
    validation: Optional[PacketValidationResult] = None


class UploadAcceptedResponse(BaseModel):
    """Response from upload endpoint — file saved, validation starting in background."""
    meeting_id: str
    store_id: str
    total_pages: int


class ValidationProgressResponse(BaseModel):
    """Real-time progress of background validation."""
    status: str  # uploading | counting_pages | validating | complete | error
    current_page: int = 0
    total_pages: int = 0
    classified_pages: list[ClassifiedPage] = []
    unclassified_pages: list[UnclassifiedPage] = []
    required_documents: list[RequiredDocumentCheck] = []
    completeness_percentage: float = 0.0
    is_complete: bool = False
    error: Optional[str] = None


class ApproveResponse(BaseModel):
    """Response from approve endpoint — full processing results."""
    meeting_id: str
    pages_extracted: int
    records_parsed: dict[str, int]
    flags_generated: dict[str, int]
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None


# --- Flags ---

class FlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    store_id: uuid.UUID
    category: str
    severity: str
    field_name: str
    field_value: Optional[str] = None
    threshold: Optional[str] = None
    message: str
    status: str
    response_text: Optional[str] = None
    responded_by: Optional[str] = None
    responded_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


class FlagStatsResponse(BaseModel):
    total: int
    yellow: int
    red: int
    open: int
    responded: int
    by_category: dict[str, int]


class FlagRespondRequest(BaseModel):
    response_text: str
    responded_by: str


# --- Flag Workflow ---

class FlagAssignRequest(BaseModel):
    assigned_to_id: str


class FlagRespondWorkflowRequest(BaseModel):
    response_text: str = Field(..., min_length=10)


class FlagEscalateRequest(BaseModel):
    reason: Optional[str] = None


class MyFlagResponse(BaseModel):
    id: str
    assignment_id: str
    category: str
    severity: str
    message: str
    field_name: str
    field_value: Optional[str] = None
    threshold: Optional[str] = None
    status: str
    assignment_status: str
    store_id: str
    store_name: str
    meeting_id: str
    meeting_date: str
    deadline: str
    is_overdue: bool
    days_overdue: int
    escalation_level: int
    response_text: Optional[str] = None
    responded_at: Optional[str] = None
    created_at: Optional[str] = None


class AutoAssignResponse(BaseModel):
    assigned_count: int
    unassigned_count: int
    by_category: dict[str, int]


class OverdueFlagResponse(BaseModel):
    id: str
    assignment_id: str
    category: str
    severity: str
    message: str
    status: str
    store_name: str
    meeting_date: str
    deadline: str
    days_overdue: int
    assigned_to_name: str
    assigned_to_email: str


# --- Stores ---

class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    brand: Optional[str] = None
    city: str
    state: str
    timezone: str
    meeting_cadence: Optional[str] = None
    gm_name: Optional[str] = None
    gm_email: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime


class StoreCreateRequest(BaseModel):
    name: str
    code: str
    city: str
    state: str
    brand: Optional[str] = None
    meeting_cadence: str = "biweekly"
    gm_name: Optional[str] = None
    gm_email: Optional[str] = None


class MeetingBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_date: datetime.date
    status: str
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None
    created_at: datetime.datetime


class StoreDetailResponse(StoreResponse):
    recent_meetings: list[MeetingBriefResponse] = []


# --- Rich Store Detail (v2) ---

class StoreInfo(BaseModel):
    id: str
    name: str
    code: str
    brand: Optional[str] = None
    city: str
    state: str
    timezone: str
    gm_name: Optional[str] = None
    gm_email: Optional[str] = None
    meeting_cadence: Optional[str] = None
    is_active: bool


class StoreStats(BaseModel):
    total_meetings: int
    total_flags_all_time: int
    current_open_flags: int
    current_overdue_flags: int
    response_rate: float
    avg_flags_per_meeting: float
    most_common_flag_category: Optional[str] = None
    recurring_issues_count: int


class MeetingFlagSummary(BaseModel):
    total: int
    red: int
    yellow: int
    open: int
    responded: int
    response_rate: float = 0.0


class RecentMeetingItem(BaseModel):
    id: str
    meeting_date: str
    status: str
    packet_generated_at: Optional[str] = None
    flags: MeetingFlagSummary
    response_rate: float
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None


class StoreUserItem(BaseModel):
    id: str
    name: str
    email: str
    role_at_store: str


class RichStoreDetailResponse(BaseModel):
    store: StoreInfo
    stats: StoreStats
    recent_meetings: List[RecentMeetingItem]
    users: List[StoreUserItem]


class FlagTrendMeeting(BaseModel):
    date: str
    red: int
    yellow: int
    responded: int
    response_rate: float


class FlagTrendsResponse(BaseModel):
    meetings: List[FlagTrendMeeting]


# --- Meeting Detail ---

class ExecutiveSummary(BaseModel):
    new_vehicle_count: int
    new_vehicle_floorplan_total: float
    used_vehicle_count: int
    used_over_60_days: int
    used_over_90_days: int
    used_over_90_exposure: float
    service_loaner_count: int
    service_loaner_neg_equity_total: float
    parts_turnover: Optional[float] = None
    open_ro_count: int
    receivables_over_30_total: float
    missing_titles_count: int
    contracts_in_transit_count: int
    floorplan_variance: Optional[float] = None


class FlagsByCategoryItem(BaseModel):
    red: int = 0
    yellow: int = 0


class FlagsSummary(BaseModel):
    total: int
    red: int
    yellow: int
    open: int
    responded: int
    overdue: int
    by_category: Dict[str, FlagsByCategoryItem]


class MeetingInfo(BaseModel):
    id: str
    store_id: str
    store_name: str
    meeting_date: str
    status: str
    packet_generated_at: Optional[str] = None
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None
    notes: Optional[str] = None


class MeetingDetailResponse(BaseModel):
    meeting: MeetingInfo
    executive_summary: ExecutiveSummary
    flags_summary: FlagsSummary


class AssignedToInfo(BaseModel):
    id: str
    name: str
    email: str
    deadline: Optional[str] = None
    assignment_status: Optional[str] = None


class FlagResponseInfo(BaseModel):
    text: str
    submitted_at: Optional[str] = None
    responder: Optional[str] = None


class MeetingFlagDetailResponse(BaseModel):
    id: str
    category: str
    severity: str
    message: str
    field_name: str
    field_value: Optional[str] = None
    threshold: Optional[str] = None
    status: str
    assigned_to: Optional[AssignedToInfo] = None
    response: Optional[FlagResponseInfo] = None
    deadline: Optional[str] = None
    is_overdue: bool
    escalation_level: int
    created_at: Optional[str] = None


# --- Meetings ---

class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    meeting_date: datetime.date
    status: str
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None
    packet_generated_at: Optional[datetime.datetime] = None
    notes: Optional[str] = None
    created_at: datetime.datetime


class MeetingSummaryResponse(BaseModel):
    meeting: MeetingResponse
    store: StoreResponse
    record_counts: dict[str, int]
    flags: list[FlagResponse]
    flag_stats: FlagStatsResponse


class MeetingDataResponse(BaseModel):
    meeting_id: str
    category: str
    data: dict[str, list[dict]]
