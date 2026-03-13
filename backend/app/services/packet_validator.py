"""Packet Completeness Validator — scans a PDF to identify which required documents are present.

Rebuilt with reference signatures from the Ashdown labeled reference PDF.
Uses context-aware classification: continuation page detection, GL 0504 account-based
subtyping, and schedule-number-first matching for Schedule Summaries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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
# Document type IDs and metadata
# ---------------------------------------------------------------------------

@dataclass
class DocumentType:
    doc_id: int
    name: str
    where_to_find: str


REQUIRED_DOCUMENTS: list[DocumentType] = [
    DocumentType(1,  "Reynolds Employee List",        "Reynolds -> Dynamic Reporting -> Employee List"),
    DocumentType(2,  "Parts 2213",                    "Reynolds -> Reports -> 2213 Parts Inventory"),
    DocumentType(3,  "Parts 2222",                    "Reynolds -> Reports -> 2222 Parts Analysis"),
    DocumentType(4,  "Service and Parts Receivables",  "Reynolds -> Schedule Summary -> Service & Parts (Sch 200)"),
    DocumentType(5,  "Warranty Claims",               "Reynolds -> Schedule Summary -> Warranty Claims (Sch 263)"),
    DocumentType(6,  "Open RO List (3617)",           "Reynolds -> Reports -> 3617 Open RO List"),
    DocumentType(7,  "Loaner Inventory",              "Reynolds -> Schedule Summary -> Loaner Inventory (Sch 277)"),
    DocumentType(8,  "GL 0504 New & Used",            "Reynolds -> GL -> 0504 -> New & Used"),
    DocumentType(9,  "New Inventory",                 "Reynolds -> Schedule Summary -> New Inventory (Sch 237)"),
    DocumentType(10, "Used Inventory",                "Reynolds -> Schedule Summary -> Used Inventory (Sch 240)"),
    DocumentType(11, "Wholesale Deals in Range",      "Reynolds -> Dynamic Reporting -> Wholesale Deals"),
    DocumentType(12, "GL 0504 Chargebacks",           "Reynolds -> GL -> 0504 -> Chargebacks"),
    DocumentType(13, "Contracts in Transit",          "Reynolds -> Schedule Summary -> CIT (Sch 205)"),
    DocumentType(14, "Slow to Accounting",            "Reynolds -> Reports -> Slow to Accounting"),
    DocumentType(15, "Wholesales",                    "Reynolds -> Schedule Summary -> Wholesales (Sch 220)"),
    DocumentType(16, "Missing Titles",                "Google Sheets -- maintained manually outside R&R"),
]

_DOC_BY_ID: dict[int, DocumentType] = {d.doc_id: d for d in REQUIRED_DOCUMENTS}

# Schedule number → document ID mapping
_SCHEDULE_MAP: dict[int, int] = {
    200: 4,   # Service & Parts Receivables (but check for CIT — see below)
    205: 13,  # Contracts in Transit
    220: 15,  # Wholesales
    237: 9,   # New Inventory
    240: 10,  # Used Inventory
    263: 5,   # Warranty Claims
    277: 7,   # Loaner Inventory
}

# GL 0504 account number → (doc_id, subtype_label)
_GL_ACCOUNT_MAP: dict[str, tuple[int, str]] = {
    "15A":  (8,  "GL 0504 New"),
    "15B":  (8,  "GL 0504 Used"),
    "850":  (12, "F&I Chargeback — New"),
    "850A": (12, "F&I Chargeback Over 90 — New"),
    "851":  (12, "F&I Chargeback — Used"),
    "851A": (12, "F&I Chargeback Over 90 — Used"),
}

# Document IDs that can span multiple pages (continuation-eligible)
_MULTI_PAGE_SCHEDULE_IDS = {4, 5, 7, 9, 10, 13, 15}
_MULTI_PAGE_IDS = _MULTI_PAGE_SCHEDULE_IDS | {6, 2}  # Open ROs and Parts 2213 too


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    doc_id: int | None = None
    score: int = 0
    subtype: str | None = None
    needs_user_input: bool = False


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------

class PageClassifier:
    """Context-aware page classifier using reference signatures."""

    def classify(self, text: str, previous_doc_id: int | None = None) -> ClassificationResult:
        """Classify a page with context from the previous page.

        Checks document types in priority order (most distinctive first).
        """
        if not text or not text.strip():
            return ClassificationResult()

        upper = text.upper()
        # Use more lines for first_lines — OCR can shift content down
        first_lines = "\n".join(text.split("\n")[:20]).upper()

        # 0. Skip cover/intro pages
        if self._is_intro_page(upper, first_lines):
            return ClassificationResult()

        # 1. Open ROs — very distinctive header
        r = self._check_open_ros(upper, first_lines, previous_doc_id)
        if r.doc_id is not None:
            return r

        # 2. Slow to Accounting
        if re.search(r"SLOW[\s\-]*TO[\s\-]*ACCOUNTING", upper):
            return ClassificationResult(doc_id=14, score=300, subtype="Slow to Accounting")

        # 3. Wholesale Deals in Range (NOT schedule summary)
        if re.search(r"WHOLESALE\s+DEALS?\s+IN\s+A?\s*DATE\s*RANGE", upper):
            return ClassificationResult(doc_id=11, score=300, subtype="Wholesale Deals in Range")

        # 4. Missing Titles — search full text, OCR may garble "TITLE" → "TTTLE", "T1TLE"
        if re.search(r"MISSING\s+T+[iI1tT]*LES?\b", upper):
            return ClassificationResult(doc_id=16, score=300, subtype="Missing Titles")

        # 5. Parts 2222 — "Core Inventory Value" or "2222"
        if re.search(r"CORE\s+INVENTORY\s+VALUE", upper) or re.search(r"\b2222\b", first_lines):
            return ClassificationResult(doc_id=3, score=300, subtype="Parts 2222")

        # 6. Parts 2213 — "MONTHLY ANALYSIS" or "2213"
        if re.search(r"\b2213\b", upper) or re.search(r"MONTHLY\s+\w*\s*LYSIS", upper):
            return ClassificationResult(doc_id=2, score=250, subtype="Parts 2213")

        # 7. GL 0504 family — "0504" + "GL INQUIRY" or "GL" nearby
        r = self._check_gl_0504(upper, first_lines)
        if r.doc_id is not None:
            return r

        # 8. Schedule Summary — extract schedule number from header
        r = self._check_schedule_summary(upper, first_lines, previous_doc_id)
        if r.doc_id is not None:
            return r

        # 9. Employee List — name roster pattern (fallback, least distinctive)
        r = self._check_employee_list(upper, first_lines, text)
        if r.doc_id is not None:
            return r

        # No match
        return ClassificationResult()

    # --- Individual checkers ---

    def _is_intro_page(self, upper: str, first_lines: str) -> bool:
        """Detect ASSET MEETING intro/cover pages."""
        if re.search(r"ASSET\s+MEETING", first_lines):
            # Count distinct schedule-number references like (237), (240), (277)
            schedule_refs = set(re.findall(r"\(\s*(\d{3})\s*\)", upper))
            if len(schedule_refs) >= 2:
                return True
            # Even without schedule refs, if it has "ASSET MEETING" + summary table keywords
            if re.search(r"UNITS", upper) and re.search(r"BALANCE", upper):
                return True
        return False

    def _check_open_ros(self, upper: str, first_lines: str, prev_id: int | None) -> ClassificationResult:
        """Check for Open RO List (3617)."""
        # OCR variants: "Open ROs" → "Dpen ROs", "Ppen ROs", "0pen ROs"
        has_open_ros = bool(re.search(r"[DO0]?PEN\s+R\.?O", first_lines))

        if has_open_ros:
            # First page has "Report Format: Detail"
            if re.search(r"REPORT\s+FORMAT", upper):
                return ClassificationResult(doc_id=6, score=300, subtype="Open RO List (3617)")
            # Continuation page — "Open ROs" header but no "Report Format"
            if prev_id == 6:
                return ClassificationResult(doc_id=6, score=250, subtype="Open RO List (3617) — continuation")
            # Still likely an Open ROs page even without previous context
            return ClassificationResult(doc_id=6, score=200, subtype="Open RO List (3617)")

        # Also check for "3617" directly
        if re.search(r"\b3617\b", first_lines) or re.search(r"REPAIR\s+ORDER", first_lines):
            return ClassificationResult(doc_id=6, score=200, subtype="Open RO List (3617)")

        return ClassificationResult()

    def _check_gl_0504(self, upper: str, first_lines: str) -> ClassificationResult:
        """Check for GL 0504 variants — account number determines subtype."""
        has_0504 = bool(re.search(r"\b0504\b", first_lines))
        # OCR variants: GL → CL, OL; may split across lines ("CL\nINQUIRY")
        has_gl_inquiry = bool(re.search(r"[GCO]L\s+INQUIRY", upper))

        if not (has_0504 or (has_gl_inquiry and re.search(r"\b0504\b", upper))):
            return ClassificationResult()

        # Extract account number — OCR garbles "ACCOUNT" → "ACCCUNT", "A00010;T", etc.
        # Try strict first, then broad
        acct = self._extract_gl_account(upper)

        if acct and acct in _GL_ACCOUNT_MAP:
            doc_id, subtype = _GL_ACCOUNT_MAP[acct]
            return ClassificationResult(doc_id=doc_id, score=300, subtype=subtype)

        # Account 15 without A/B suffix — check description for NEW/USED
        if acct and (acct == "15" or acct.startswith("15")):
            if re.search(r"POLICY\s+ADJ\s+NEW|NEW\s+VEH", upper):
                return ClassificationResult(doc_id=8, score=280, subtype="GL 0504 New")
            elif re.search(r"POLICY\s+ADJ\s+(?:USD|USED)|USED\s+VEH", upper):
                return ClassificationResult(doc_id=8, score=280, subtype="GL 0504 Used")
            else:
                return ClassificationResult(
                    doc_id=8, score=200, subtype="GL 0504 (New or Used — needs review)",
                    needs_user_input=True,
                )

        # Try keyword-based classification when account extraction fails
        # Check for chargeback patterns (accounts 850/851)
        if re.search(r"CHARGEBACK", upper) or re.search(r"F\s*&?\s*I\s+(?:CHARGEBACK|OV)", upper):
            # Try to find account number near "850" or "851" even if ACCOUNT prefix garbled
            acct_num = self._find_account_number_broad(upper)
            if acct_num and acct_num in _GL_ACCOUNT_MAP:
                doc_id, subtype = _GL_ACCOUNT_MAP[acct_num]
                return ClassificationResult(doc_id=doc_id, score=280, subtype=subtype)
            if re.search(r"OV\s*90|OVER\s*90", upper):
                return ClassificationResult(doc_id=12, score=250, subtype="F&I Chargeback Over 90")
            return ClassificationResult(doc_id=12, score=250, subtype="F&I Chargeback")

        # POLICY ADJ — distinguish New vs Used
        if re.search(r"POLICY\s+ADJ", upper):
            if re.search(r"POLICY\s+ADJ\s+NEW|ADJ\s+NEW", upper):
                return ClassificationResult(doc_id=8, score=250, subtype="GL 0504 New")
            elif re.search(r"POLICY\s+ADJ\s*\n?\s*USD|ADJ\s+USD|ADJ\s+USED", upper):
                return ClassificationResult(doc_id=8, score=250, subtype="GL 0504 Used")
            return ClassificationResult(doc_id=8, score=200, subtype="GL 0504 New & Used",
                                        needs_user_input=True)

        # Generic 0504 — classify as GL 0504, needs review
        return ClassificationResult(
            doc_id=8, score=150, subtype="GL 0504 (unspecified)",
            needs_user_input=True,
        )

    @staticmethod
    def _extract_gl_account(upper: str) -> str | None:
        """Extract GL account number, tolerating OCR garbling of 'ACCOUNT'."""
        # Strict: "ACCOUNT 15A", "ACCOUNT 850", etc.
        m = re.search(r"ACCOUNT\s+(\d+[A-Z]?)\b", upper)
        if m:
            return m.group(1)
        # OCR-tolerant: "ACCCUNT", "ACC0UNT", "A00010;T" etc. — look for
        # something that starts with A and ends near a known account number
        m = re.search(r"A\w{2,8}T\s+(\d+[A-Z]?)\b", upper)
        if m:
            return m.group(1)
        # Look for account numbers on their own line after garbled ACCOUNT prefix
        # e.g., "ACCCUNT\nlA" → find 1-digit + letter patterns near known numbers
        # Check for "15A", "15B", "850", "850A", "851", "851A" anywhere nearby
        for known_acct in ["851A", "850A", "851", "850", "15A", "15B"]:
            if known_acct in upper:
                return known_acct
        # OCR may render "15A" as "lA" or "1A" or "iSA" — check for POLICY ADJ context
        if re.search(r"[l1i]\s*A\b", upper) and re.search(r"POLICY\s+ADJ\s+NEW", upper):
            return "15A"
        if re.search(r"[l1i]\s*[SB5]\s*[PB]?\b", upper) and re.search(r"POLICY\s+ADJ", upper):
            return "15B"
        return None

    @staticmethod
    def _find_account_number_broad(upper: str) -> str | None:
        """Broadly search for known GL account numbers in text."""
        for known_acct in ["851A", "850A", "851", "850", "15A", "15B"]:
            if re.search(rf"\b{known_acct}\b", upper):
                return known_acct
        return None

    def _check_schedule_summary(self, upper: str, first_lines: str, prev_id: int | None) -> ClassificationResult:
        """Check for Schedule Summary documents — schedule number is the primary key."""
        # OCR variants: "Schedule Summary" → "hedule Summary" (truncated),
        # "5chedule Summary", "Schedu1e Summary"
        has_schedule_summary = bool(re.search(
            r"(?:S|5)?(?:C|c)?HEDULE?\s+SUMMARY", first_lines, re.IGNORECASE
        ))

        if not has_schedule_summary:
            return ClassificationResult()

        # Extract schedule number — OCR garbles "Schedule#:" → "5chedule#:", "edule#:", etc.
        # Be very permissive on the prefix, strict on the number
        sch_match = re.search(
            r"(?:S|5)?(?:C|c)?HEDU[L1I]?E?\s*#?\s*:?\s*(\d{2,3})\b", first_lines, re.IGNORECASE
        )

        if sch_match:
            sch_num = int(sch_match.group(1))

            # Special case: Schedule 200 can be either Service & Parts Receivables OR CIT
            if sch_num == 200:
                if re.search(r"CONTRACT", upper):
                    return ClassificationResult(doc_id=13, score=300, subtype="Contracts in Transit (Sch 200)")
                return ClassificationResult(doc_id=4, score=300, subtype="Service & Parts Receivables (Sch 200)")

            # Look up in schedule map
            if sch_num in _SCHEDULE_MAP:
                doc_id = _SCHEDULE_MAP[sch_num]
                doc = _DOC_BY_ID[doc_id]
                return ClassificationResult(doc_id=doc_id, score=300, subtype=f"{doc.name} (Sch {sch_num})")

            # Unknown schedule number — still a Schedule Summary but unrecognized
            return ClassificationResult()

        # No schedule number found — this is likely a continuation page
        if prev_id in _MULTI_PAGE_SCHEDULE_IDS:
            doc = _DOC_BY_ID[prev_id]
            return ClassificationResult(doc_id=prev_id, score=250, subtype=f"{doc.name} — continuation")

        # Schedule Summary with no number and no previous context
        # Try keyword fallback
        return self._schedule_keyword_fallback(upper)

    def _schedule_keyword_fallback(self, upper: str) -> ClassificationResult:
        """Last resort: match Schedule Summaries by body keywords when no schedule number found."""
        if re.search(r"ACCOUNTS?\s+RECEIVABLE", upper):
            return ClassificationResult(doc_id=4, score=150, subtype="Service & Parts Receivables")
        if re.search(r"WARR.*CLAIM|WARRANTY", upper):
            return ClassificationResult(doc_id=5, score=150, subtype="Warranty Claims")
        if re.search(r"LOANER", upper):
            return ClassificationResult(doc_id=7, score=150, subtype="Loaner Inventory")
        if re.search(r"NEW\s+VEH", upper):
            return ClassificationResult(doc_id=9, score=150, subtype="New Inventory")
        if re.search(r"USED\s+VEH", upper):
            return ClassificationResult(doc_id=10, score=150, subtype="Used Inventory")
        if re.search(r"CONTRACT\S?\s+IN\s+TRANSIT|\bCIT\b", upper):
            return ClassificationResult(doc_id=13, score=150, subtype="Contracts in Transit")
        if re.search(r"WHOLESALE", upper):
            return ClassificationResult(doc_id=15, score=150, subtype="Wholesales")
        return ClassificationResult()

    def _check_employee_list(self, upper: str, first_lines: str, raw_text: str) -> ClassificationResult:
        """Check for Employee List — least distinctive, checked last."""
        # Explicit headers
        if re.search(r"EMPLOYEE\s*(LIST|ROSTER)", upper):
            return ClassificationResult(doc_id=1, score=300, subtype="Employee List")
        if re.search(r"PERSONNEL\s*(LIST|REPORT)", upper):
            return ClassificationResult(doc_id=1, score=300, subtype="Employee List")

        # Pattern: dense list of names with job titles — no dollar amounts, no VINs
        # Look for 5+ lines that match "LASTNAME FIRSTNAME" pattern with role keywords
        role_keywords = (
            r"SALES|TECH|SERVICE\s*(?:ADVISOR|MANAGER|WRITER)|WASH|LUBE|"
            r"PORTER|MANAGER|BDC|F\s*&?\s*I|PARTS|DETAIL|RECON|OFFICE|CASHIER"
        )
        role_matches = len(re.findall(role_keywords, upper))
        has_dollar = bool(re.search(r"\$\s*[\d,]+\.?\d*", raw_text))
        has_vin = bool(re.search(r"[A-Z0-9]{17}", raw_text))
        has_schedule = bool(re.search(r"SCHEDULE", upper))

        if role_matches >= 4 and not has_dollar and not has_vin and not has_schedule:
            return ClassificationResult(doc_id=1, score=180, subtype="Employee List")

        return ClassificationResult()


# ---------------------------------------------------------------------------
# PacketValidator — public API unchanged
# ---------------------------------------------------------------------------

class PacketValidator:
    """Scans a PDF and checks which of the 16 required documents are present."""

    def __init__(self) -> None:
        self._classifier = PageClassifier()

    def validate(self, source: Union[str, bytes, Path]) -> PacketValidationResult:
        """Validate a PDF for packet completeness.

        Args:
            source: file path (str/Path) or raw PDF bytes.

        Returns:
            PacketValidationResult with found/missing documents.
        """
        pages_text = self._extract_text(source)
        total_pages = len(pages_text)

        doc_pages: dict[int, list[int]] = {}
        prev_doc_id: int | None = None

        for page_idx, text in enumerate(pages_text):
            if not text or not text.strip():
                prev_doc_id = None
                continue

            result = self._classifier.classify(text, prev_doc_id)
            if result.doc_id is not None:
                doc_pages.setdefault(result.doc_id, []).append(page_idx + 1)
                prev_doc_id = result.doc_id
            else:
                prev_doc_id = None

        found: list[FoundDocument] = []
        missing: list[MissingDocument] = []

        for doc in REQUIRED_DOCUMENTS:
            if doc.doc_id in doc_pages:
                found.append(FoundDocument(name=doc.name, page_numbers=sorted(doc_pages[doc.doc_id])))
            else:
                missing.append(MissingDocument(name=doc.name, where_to_find=doc.where_to_find))

        completeness = (len(found) / len(REQUIRED_DOCUMENTS)) * 100.0 if REQUIRED_DOCUMENTS else 0.0

        return PacketValidationResult(
            found_documents=found,
            missing_documents=missing,
            completeness_percentage=round(completeness, 1),
            is_complete=len(missing) == 0,
            total_pages=total_pages,
        )

    def validate_detailed(self, source: Union[str, bytes, Path]) -> DetailedValidationResult:
        """Validate a PDF and return page-level classification detail."""
        pages_text = self._extract_text(source)
        return self._classify_all_pages(pages_text)

    def validate_detailed_with_progress(
        self, source: Union[str, bytes, Path], meeting_id: str
    ) -> DetailedValidationResult:
        """Validate a PDF page-by-page, updating progress store after each page."""
        import io
        import os
        import tempfile

        from app.services.validation_progress import ValidationProgress, set_progress

        progress = ValidationProgress(status="counting_pages")
        set_progress(meeting_id, progress)

        total_pages = self._count_pages(source)
        progress.total_pages = total_pages
        progress.status = "validating"
        set_progress(meeting_id, progress)

        # Prepare file handles
        tmp_path: str | None = None
        created_tmp = False
        if isinstance(source, bytes):
            pdf_file: object = io.BytesIO(source)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(source)
                tmp_path = f.name
                created_tmp = True
        else:
            pdf_file = str(source)
            tmp_path = str(source)

        classified_pages: list[ClassifiedPage] = []
        unclassified_pages: list[UnclassifiedPage] = []
        doc_pages: dict[int, list[int]] = {}
        prev_doc_id: int | None = None

        try:
            with pdfplumber.open(pdf_file) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    progress.current_page = page_num
                    set_progress(meeting_id, progress)

                    # Extract text with OCR fallback
                    text = page.extract_text() or ""
                    if len(text.strip()) < self._OCR_THRESHOLD and tmp_path:
                        ocr_text = self._tesseract_ocr_page(tmp_path, page_idx)
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                            logger.info("Page %d: used tesseract OCR (%d chars)", page_num, len(text))

                    # Classify with context
                    if not text or not text.strip():
                        up = UnclassifiedPage(page_number=page_num, snippet="(blank page)")
                        unclassified_pages.append(up)
                        progress.unclassified_pages.append(up.model_dump())
                        prev_doc_id = None
                    else:
                        result = self._classifier.classify(text, prev_doc_id)
                        if result.doc_id is not None:
                            doc_name = _DOC_BY_ID[result.doc_id].name
                            cp = ClassifiedPage(
                                page_number=page_num,
                                document_type=doc_name,
                                confidence=result.score,
                                subtype=result.subtype,
                                needs_user_input=result.needs_user_input,
                            )
                            classified_pages.append(cp)
                            doc_pages.setdefault(result.doc_id, []).append(page_num)
                            progress.classified_pages.append(cp.model_dump())
                            prev_doc_id = result.doc_id
                        else:
                            snippet = ""
                            for line in text.split("\n"):
                                stripped = line.strip()
                                if stripped:
                                    snippet = stripped[:120]
                                    break
                            up = UnclassifiedPage(
                                page_number=page_num, snippet=snippet or "(no readable text)"
                            )
                            unclassified_pages.append(up)
                            progress.unclassified_pages.append(up.model_dump())
                            prev_doc_id = None

                    # Update checklist after each page
                    required_documents, found_count = self._build_checklist(doc_pages)
                    completeness = (found_count / len(REQUIRED_DOCUMENTS)) * 100.0
                    progress.required_documents = [rd.model_dump() for rd in required_documents]
                    progress.completeness_percentage = round(completeness, 1)
                    set_progress(meeting_id, progress)

        except Exception:
            logger.warning("Failed during page-by-page validation", exc_info=True)
        finally:
            if created_tmp and tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # Final
        required_documents, found_count = self._build_checklist(doc_pages)
        completeness = (found_count / len(REQUIRED_DOCUMENTS)) * 100.0 if REQUIRED_DOCUMENTS else 0.0

        progress.status = "complete"
        progress.is_complete = found_count == len(REQUIRED_DOCUMENTS)
        set_progress(meeting_id, progress)

        return DetailedValidationResult(
            classified_pages=classified_pages,
            unclassified_pages=unclassified_pages,
            required_documents=required_documents,
            completeness_percentage=round(completeness, 1),
            is_complete=found_count == len(REQUIRED_DOCUMENTS),
            total_pages=total_pages,
        )

    # --- Helpers ---

    def _classify_all_pages(self, pages_text: list[str]) -> DetailedValidationResult:
        """Classify all pages with context tracking."""
        classified_pages: list[ClassifiedPage] = []
        unclassified_pages: list[UnclassifiedPage] = []
        doc_pages: dict[int, list[int]] = {}
        prev_doc_id: int | None = None

        for page_idx, text in enumerate(pages_text):
            page_num = page_idx + 1
            if not text or not text.strip():
                unclassified_pages.append(UnclassifiedPage(page_number=page_num, snippet="(blank page)"))
                prev_doc_id = None
                continue

            result = self._classifier.classify(text, prev_doc_id)
            if result.doc_id is not None:
                doc_name = _DOC_BY_ID[result.doc_id].name
                classified_pages.append(ClassifiedPage(
                    page_number=page_num,
                    document_type=doc_name,
                    confidence=result.score,
                    subtype=result.subtype,
                    needs_user_input=result.needs_user_input,
                ))
                doc_pages.setdefault(result.doc_id, []).append(page_num)
                prev_doc_id = result.doc_id
            else:
                snippet = ""
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped:
                        snippet = stripped[:120]
                        break
                unclassified_pages.append(UnclassifiedPage(
                    page_number=page_num, snippet=snippet or "(no readable text)",
                ))
                prev_doc_id = None

        required_documents, found_count = self._build_checklist(doc_pages)
        completeness = (found_count / len(REQUIRED_DOCUMENTS)) * 100.0 if REQUIRED_DOCUMENTS else 0.0

        return DetailedValidationResult(
            classified_pages=classified_pages,
            unclassified_pages=unclassified_pages,
            required_documents=required_documents,
            completeness_percentage=round(completeness, 1),
            is_complete=found_count == len(REQUIRED_DOCUMENTS),
            total_pages=len(pages_text),
        )

    @staticmethod
    def _build_checklist(doc_pages: dict[int, list[int]]) -> tuple[list[RequiredDocumentCheck], int]:
        """Build the 16-document checklist from found pages."""
        required_documents: list[RequiredDocumentCheck] = []
        found_count = 0
        for doc in REQUIRED_DOCUMENTS:
            found = doc.doc_id in doc_pages
            if found:
                found_count += 1
            required_documents.append(RequiredDocumentCheck(
                name=doc.name,
                found=found,
                page_numbers=sorted(doc_pages.get(doc.doc_id, [])),
                where_to_find=doc.where_to_find,
            ))
        return required_documents, found_count

    @staticmethod
    def _count_pages(source: Union[str, bytes, Path]) -> int:
        """Count PDF pages cheaply without extracting text."""
        import io

        if isinstance(source, bytes):
            pdf_file = io.BytesIO(source)
        else:
            pdf_file = str(source)

        with pdfplumber.open(pdf_file) as pdf:
            return len(pdf.pages)

    _OCR_THRESHOLD = 50

    def _extract_text(self, source: Union[str, bytes, Path]) -> list[str]:
        """Extract text from each page of the PDF, with tesseract OCR fallback."""
        import io
        import os
        import tempfile

        pages_text: list[str] = []
        tmp_path: str | None = None
        created_tmp = False

        try:
            if isinstance(source, bytes):
                pdf_file: object = io.BytesIO(source)
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(source)
                    tmp_path = f.name
                    created_tmp = True
            else:
                pdf_file = str(source)
                tmp_path = str(source)

            with pdfplumber.open(pdf_file) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""

                    if len(text.strip()) < self._OCR_THRESHOLD and tmp_path:
                        ocr_text = self._tesseract_ocr_page(tmp_path, i)
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                            logger.info("Page %d: used tesseract OCR (%d chars)", i + 1, len(text))

                    pages_text.append(text)
        except Exception:
            logger.warning("Failed to extract text from PDF", exc_info=True)
        finally:
            if created_tmp and tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return pages_text

    @staticmethod
    def _tesseract_ocr_page(pdf_path: str, page_index: int) -> str:
        """Render a single PDF page and run tesseract OCR on it."""
        try:
            import pypdfium2 as pdfium
            import pytesseract
        except ImportError:
            logger.warning("pytesseract or pypdfium2 not installed — OCR unavailable")
            return ""

        try:
            pdf = pdfium.PdfDocument(pdf_path)
            page = pdf[page_index]
            bitmap = page.render(scale=2)
            img = bitmap.to_pil()
            pdf.close()

            return pytesseract.image_to_string(img)
        except Exception:
            logger.exception("Tesseract OCR failed for page %d", page_index + 1)
            return ""
