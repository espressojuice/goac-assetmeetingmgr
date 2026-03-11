"""In-memory progress tracking for async packet validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationProgress:
    status: str = "uploading"  # uploading | counting_pages | validating | complete | error
    current_page: int = 0
    total_pages: int = 0
    classified_pages: list[dict] = field(default_factory=list)
    unclassified_pages: list[dict] = field(default_factory=list)
    required_documents: list[dict] = field(default_factory=list)
    completeness_percentage: float = 0.0
    is_complete: bool = False
    error: Optional[str] = None


# In-memory store keyed by meeting_id (str)
_progress_store: dict[str, ValidationProgress] = {}


def set_progress(meeting_id: str, progress: ValidationProgress) -> None:
    _progress_store[meeting_id] = progress


def get_progress(meeting_id: str) -> Optional[ValidationProgress]:
    return _progress_store.get(meeting_id)


def clear_progress(meeting_id: str) -> None:
    _progress_store.pop(meeting_id, None)
