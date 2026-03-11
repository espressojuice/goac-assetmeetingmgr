"""Packet Completeness Validator — scans a PDF to identify which required documents are present."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Union

import pdfplumber

from app.api.schemas import (
    ClassifiedPage,
    DetailedValidationResult,
    FoundDocument,
    MissingDocument,
    PacketValidationResult,
    RequiredDocumentCheck,
    UnclassifiedPage,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Document definitions — order matters for disambiguation.
# Each entry: (doc_id, name, where_to_find, primary_patterns, negative_patterns)
#
# primary_patterns: at least one must match for a page to be a candidate.
# negative_patterns: if any match, the page is NOT this document (used for
#   disambiguation of overlapping keywords).
# ---------------------------------------------------------------------------

_DOCUMENT_DEFS: list[tuple[int, str, str, list[re.Pattern], list[re.Pattern]]] = []


def _pat(patterns: list[str], flags: int = re.IGNORECASE) -> list[re.Pattern]:
    return [re.compile(p, flags) for p in patterns]


def _register(
    doc_id: int,
    name: str,
    where_to_find: str,
    primary: list[str],
    negative: list[str] | None = None,
) -> None:
    _DOCUMENT_DEFS.append((
        doc_id,
        name,
        where_to_find,
        _pat(primary),
        _pat(negative) if negative else [],
    ))


# 1. Reynolds Employee List
# Real packets show employee names with job titles (SALES, TECH, SERVICE MANAGER)
# without a formal "Employee List" header.
_register(1, "Reynolds Employee List",
          "Reynolds -> Dynamic Reporting -> Employee List",
          [r"EMPLOYEE\s*(LIST|ROSTER)", r"PERSONNEL\s*(LIST|REPORT)",
           r"(?:SALES|TECH|SERVICE\s+(?:ADVISOR|MANAGER)|WASH\s+BAY|LUBE\s+TECH|FI\s+MANAGER)\s*\n"])

# 2. Parts 2213
_register(2, "Parts 2213",
          "Reynolds -> Reports -> 2213 Parts Inventory",
          [r"\b2213\b", r"PARTS\s+INVENTORY"])

# 3. Parts 2222
_register(3, "Parts 2222",
          "Reynolds -> Reports -> 2222 Parts Analysis",
          [r"\b2222\b", r"PARTS\s+ANALYSIS", r"MONTHLY\s+ANALYSIS",
           r"STORE\s+\d+\s+BRANCH"])

# 4. Service and Parts Receivables
_register(4, "Service and Parts Receivables",
          "Reynolds -> Schedule Summary -> Service & Parts",
          [r"SERVICE.*RECEIVABLE", r"PARTS?\s+RECEIVABLE",
           r"SCHEDULE\s+SUMMARY.*(?:SERVICE|PARTS)",
           r"P\s*&\s*S\s*\(\s*200\s*\)"])

# 5. Warranty Claims
_register(5, "Warranty Claims",
          "Reynolds -> Schedule Summary -> Warranty Claims",
          [r"WARRANTY.*CLAIM", r"SCHEDULE\s+263\b", r"WARRANTY"])

# 6. Open RO List (3617)
_register(6, "Open RO List (3617)",
          "Reynolds -> Reports -> 3617 Open RO List",
          [r"\b3617\b", r"OPEN\s+R\.?O\.?", r"REPAIR\s+ORDER"])

# 7. Loaner Inventory
# Real packets reference "SRV LOANERS (277)" on summary pages.
_register(7, "Loaner Inventory",
          "Reynolds -> Schedule Summary -> Loaner Inventory",
          [r"SERVICE?\s+LOANER", r"SRV\s+LOANER", r"LOANER\s+INVENTOR",
           r"SCHEDULE\s+277\b", r"\(277\)"])

# 8. GL 0504 New & Used — must NOT contain chargeback keywords
_register(8, "GL 0504 New & Used",
          "Reynolds -> GL -> 0504 -> New & Used",
          [r"(?:GL|GENERAL\s+LEDGER).*0504", r"\b0504\b.*(?:NEW|USED)",
           r"\b0504\b"],
          negative=[r"CHARGEBACK", r"F\s*&\s*I\s+CHARGEBACK"])

# 9. New Inventory
# Real packets: "NEW (237)" on summary pages.
_register(9, "New Inventory",
          "Reynolds -> Schedule Summary -> New Inventory (Sch 237)",
          [r"NEW\s+VEHICLE", r"NEW\s+CAR", r"SCHEDULE\s+237\b",
           r"NEW\s*\(\s*237\s*\)", r"\(237\)"])

# 10. Used Inventory
# Real packets: "USED (240)" on summary pages.
_register(10, "Used Inventory",
           "Reynolds -> Schedule Summary -> Used Inventory (Sch 240)",
           [r"USED\s+VEHICLE", r"USED\s+CAR", r"SCHEDULE\s+240\b",
            r"USED\s*\(\s*240\s*\)", r"\(240\)"])

# 11. Wholesale Deals in Range — requires "DEAL" or date-range context
_register(11, "Wholesale Deals in Range",
           "Reynolds -> Dynamic Reporting -> Wholesale Deals",
           [r"WHOLESALE\s+DEAL", r"WHOLESALE.*(?:RANGE|FROM|THRU|THROUGH)"],
           negative=[r"SCHEDULE\s+SUMMARY"])

# 12. GL 0504 Chargebacks — requires chargeback context
_register(12, "GL 0504 Chargebacks",
           "Reynolds -> GL -> 0504 -> Chargebacks",
           [r"CHARGEBACK.*0504", r"0504.*CHARGEBACK",
            r"F\s*&\s*I\s+CHARGEBACK", r"CHARGEBACK"])

# 13. Contracts in Transit
_register(13, "Contracts in Transit",
           "Reynolds -> Schedule Summary -> CIT (Sch 200)",
           [r"CONTRACT\S?\s+IN\s+TRANSIT", r"\bCIT\b", r"SCHEDULE\s+200\b",
            r"\(\s*200\s*\)"])

# 14. Slow to Accounting
_register(14, "Slow to Accounting",
           "Reynolds -> Reports -> Slow to Accounting",
           [r"SLOW[\s-]+TO[\s-]+ACCOUNTING"])

# 15. Wholesales (schedule summary) — broader wholesale without "DEAL"
# Real packets: "WHOLEASALE (220)" (OCR typo) on summary pages.
_register(15, "Wholesales",
           "Reynolds -> Schedule Summary -> Wholesales",
           [r"WHOL[EA]SALE", r"SCHEDULE\s+SUMMARY.*WHOLESALE",
            r"\(\s*220\s*\)"],
           negative=[r"WHOLESALE\s+DEAL", r"WHOLESALE.*(?:RANGE|FROM|THRU|THROUGH)"])

# 16. Missing Titles
_register(16, "Missing Titles",
           "Google Sheets -- maintained manually outside R&R",
           [r"MISSING\s+TITLE", r"TITLE.*(?:MISSING|OPEN|OUTSTANDING)"])


class PacketValidator:
    """Scans a PDF and checks which of the 16 required documents are present."""

    # Priority order for disambiguation: higher-priority doc wins when a page
    # matches multiple documents.  More specific documents get higher priority.
    _PRIORITY: dict[int, int] = {
        # Specific GL 0504 variants beat generic
        12: 90,  # GL 0504 Chargebacks
        8: 85,   # GL 0504 New & Used
        # Specific wholesale variant beats generic
        11: 80,  # Wholesale Deals in Range
        15: 30,  # Wholesales (generic)
        # Everything else defaults to 50
    }

    def validate(self, source: Union[str, bytes, Path]) -> PacketValidationResult:
        """Validate a PDF for packet completeness.

        Args:
            source: file path (str/Path) or raw PDF bytes.

        Returns:
            PacketValidationResult with found/missing documents.
        """
        pages_text = self._extract_text(source)
        total_pages = len(pages_text)

        # Track which document each page is assigned to (page_idx -> doc_id)
        page_assignments: dict[int, int] = {}
        # Track pages per document (doc_id -> list of 1-based page numbers)
        doc_pages: dict[int, list[int]] = {}

        for page_idx, text in enumerate(pages_text):
            if not text or not text.strip():
                continue

            best_doc_id = self._classify_page(text)
            if best_doc_id is not None:
                page_assignments[page_idx] = best_doc_id
                doc_pages.setdefault(best_doc_id, []).append(page_idx + 1)

        # Build results
        found: list[FoundDocument] = []
        missing: list[MissingDocument] = []

        for doc_id, name, where_to_find, _, _ in _DOCUMENT_DEFS:
            if doc_id in doc_pages:
                found.append(FoundDocument(
                    name=name,
                    page_numbers=sorted(doc_pages[doc_id]),
                ))
            else:
                missing.append(MissingDocument(
                    name=name,
                    where_to_find=where_to_find,
                ))

        completeness = (len(found) / len(_DOCUMENT_DEFS)) * 100.0 if _DOCUMENT_DEFS else 0.0

        return PacketValidationResult(
            found_documents=found,
            missing_documents=missing,
            completeness_percentage=round(completeness, 1),
            is_complete=len(missing) == 0,
            total_pages=total_pages,
        )

    def validate_detailed(self, source: Union[str, bytes, Path]) -> DetailedValidationResult:
        """Validate a PDF and return page-level classification detail.

        Returns per-page classification with scores, unclassified page snippets,
        and the full 16-document checklist.
        """
        pages_text = self._extract_text(source)
        total_pages = len(pages_text)

        classified_pages: list[ClassifiedPage] = []
        unclassified_pages: list[UnclassifiedPage] = []
        # doc_id -> list of 1-based page numbers
        doc_pages: dict[int, list[int]] = {}

        for page_idx, text in enumerate(pages_text):
            page_num = page_idx + 1
            if not text or not text.strip():
                # Blank page — treat as unclassified
                unclassified_pages.append(UnclassifiedPage(
                    page_number=page_num,
                    snippet="(blank page)",
                ))
                continue

            best_doc_id, best_score = self._classify_page_with_score(text)
            if best_doc_id is not None:
                # Look up doc name
                doc_name = next(
                    name for did, name, _, _, _ in _DOCUMENT_DEFS if did == best_doc_id
                )
                classified_pages.append(ClassifiedPage(
                    page_number=page_num,
                    document_type=doc_name,
                    confidence=best_score,
                ))
                doc_pages.setdefault(best_doc_id, []).append(page_num)
            else:
                # Extract snippet: first non-empty line, up to 120 chars
                snippet = ""
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped:
                        snippet = stripped[:120]
                        break
                unclassified_pages.append(UnclassifiedPage(
                    page_number=page_num,
                    snippet=snippet or "(no readable text)",
                ))

        # Build the 16-document checklist
        required_documents: list[RequiredDocumentCheck] = []
        found_count = 0
        for doc_id, name, where_to_find, _, _ in _DOCUMENT_DEFS:
            found = doc_id in doc_pages
            if found:
                found_count += 1
            required_documents.append(RequiredDocumentCheck(
                name=name,
                found=found,
                page_numbers=sorted(doc_pages.get(doc_id, [])),
                where_to_find=where_to_find,
            ))

        completeness = (found_count / len(_DOCUMENT_DEFS)) * 100.0 if _DOCUMENT_DEFS else 0.0

        return DetailedValidationResult(
            classified_pages=classified_pages,
            unclassified_pages=unclassified_pages,
            required_documents=required_documents,
            completeness_percentage=round(completeness, 1),
            is_complete=found_count == len(_DOCUMENT_DEFS),
            total_pages=total_pages,
        )

    def _extract_text(self, source: Union[str, bytes, Path]) -> list[str]:
        """Extract text from each page of the PDF using pdfplumber."""
        pages_text: list[str] = []
        try:
            if isinstance(source, bytes):
                import io
                pdf_file = io.BytesIO(source)
            else:
                pdf_file = str(source)

            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages_text.append(text)
        except Exception:
            logger.warning("Failed to extract text from PDF", exc_info=True)

        return pages_text

    @staticmethod
    def _is_summary_cover_page(text: str) -> bool:
        """Detect asset meeting summary/cover pages that reference multiple schedules.

        These pages are not a single document type — they summarise the entire
        packet and should not be classified.
        """
        if re.search(r"ASSET\s+MEETING", text, re.IGNORECASE):
            # Count distinct schedule-number references like (237), (240), (277)
            schedule_refs = set(re.findall(r"\(\s*(\d{3})\s*\)", text))
            if len(schedule_refs) >= 3:
                return True
        return False

    def _classify_page_with_score(self, text: str) -> tuple[int | None, int]:
        """Classify a single page's text to the best-matching document type.

        Returns (doc_id, score) of the best match, or (None, 0) if no match.
        """
        # Skip cover/summary pages that reference many schedules at once
        if self._is_summary_cover_page(text):
            return None, 0

        candidates: list[tuple[int, int]] = []  # (doc_id, match_score)

        for doc_id, _name, _wtf, primary_patterns, negative_patterns in _DOCUMENT_DEFS:
            # Check negative patterns first — if any match, skip this doc
            if any(p.search(text) for p in negative_patterns):
                continue

            # Count how many primary patterns match
            match_count = sum(1 for p in primary_patterns if p.search(text))
            if match_count > 0:
                priority = self._PRIORITY.get(doc_id, 50)
                # Score = match_count * 100 + priority (so more matches win,
                # ties broken by priority)
                score = match_count * 100 + priority
                candidates.append((doc_id, score))

        if not candidates:
            return None, 0

        # Return the doc_id with the highest score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    def _classify_page(self, text: str) -> int | None:
        """Classify a single page's text to the best-matching document type.

        Returns the doc_id of the best match, or None if no match.
        """
        doc_id, _ = self._classify_page_with_score(text)
        return doc_id
