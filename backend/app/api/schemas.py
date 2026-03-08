"""Pydantic response schemas for API endpoints."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# --- Upload ---

class UploadResponse(BaseModel):
    meeting_id: str
    pages_extracted: int
    records_parsed: dict[str, int]
    flags_generated: dict[str, int]
    packet_url: Optional[str] = None
    flagged_items_url: Optional[str] = None


class BulkUploadResponse(BaseModel):
    meeting_id: str
    files_processed: int
    total_pages_extracted: int
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
