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


# Helper: OCR-tolerant schedule number pattern.  Matches both pdfplumber
# "SCHEDULE 237" and OCR "Schedule#: 237" / "Schedule#  237" forms.
_SCH = r"(?:SCHEDULE|Schedule)\s*#?\s*:?\s*"

# 1. Reynolds Employee List
# Real packets show employee names with job titles (SALES, TECH, SERVICE MANAGER)
# without a formal "Employee List" header.
_register(1, "Reynolds Employee List",
          "Reynolds -> Dynamic Reporting -> Employee List",
          [r"EMPLOYEE\s*(LIST|ROSTER)", r"PERSONNEL\s*(LIST|REPORT)",
           r"(?:SALES|TECH|SERVICE\s+(?:ADVISOR|MANAGER)|WASH\s+BAY|LUBE\s+TECH|FI\s+MANAGER)\s*\n"])

# 2. Parts 2213
# OCR renders as "MONTHLY AMALISIS 2213" or "MONTHLY MALYSIS 2213"
_register(2, "Parts 2213",
          "Reynolds -> Reports -> 2213 Parts Inventory",
          [r"\b2213\b", r"PARTS\s+INVENTORY", r"MONTHLY\s+[A-Z]*LYSIS\s+2213"])

# 3. Parts 2222
_register(3, "Parts 2222",
          "Reynolds -> Reports -> 2222 Parts Analysis",
          [r"\b2222\b", r"PARTS\s+ANALYSIS", r"MONTHLY\s+[A-Z]*LYSIS",
           r"STORE\s+\d+\s+BRANCH"])

# 4. Service and Parts Receivables (Schedule 200)
# OCR: "Schedule#: 200 ACCOUNTS RECEIVABLE"
_register(4, "Service and Parts Receivables",
          "Reynolds -> Schedule Summary -> Service & Parts (Sch 200)",
          [r"SERVICE.*RECEIVABLE", r"PARTS?\s+RECEIVABLE",
           r"ACCOUNTS?\s+RECEIVABLE",
           r"P\s*&\s*S\s*\(\s*200\s*\)",
           _SCH + r"200\b"],
          negative=[r"CONTRACT.*IN\s+TRANSIT", r"\bCIT\b"])

# 5. Warranty Claims (Schedule 263)
# OCR: "263 WARR CLAIMS-GM 263"
_register(5, "Warranty Claims",
          "Reynolds -> Schedule Summary -> Warranty Claims",
          [r"WARR.*CLAIM", r"WARRANTY.*CLAIM", _SCH + r"263\b",
           r"\b263\b.*(?:WARR|WARRANTY)"])

# 6. Open RO List (3617)
# OCR: "Open ROs" with detail lines
_register(6, "Open RO List (3617)",
          "Reynolds -> Reports -> 3617 Open RO List",
          [r"\b3617\b", r"OPEN\s+R\.?O", r"REPAIR\s+ORDER"])

# 7. Loaner Inventory (Schedule 277)
# OCR: "Schedule#: 277 LOANERS"
_register(7, "Loaner Inventory",
          "Reynolds -> Schedule Summary -> Loaner Inventory",
          [r"SERVICE?\s+LOANER", r"SRV\s+LOANER", r"LOANER",
           _SCH + r"277\b", r"\(277\)", r"\b277\b.*LOANER"])

# 8. GL 0504 New & Used — must NOT contain chargeback keywords
# OCR: "CLASSIC CHEVROLET 0504" + "GL INQUIRY"
_register(8, "GL 0504 New & Used",
          "Reynolds -> GL -> 0504 -> New & Used",
          [r"(?:GL|GENERAL\s+LEDGER).*0504", r"\b0504\b.*(?:NEW|USED)",
           r"\b0504\b", r"GL\s+INQUIRY.*0504"],
          negative=[r"CHARGEBACK", r"F\s*&?\s*I\s+CHARGEBACK"])

# 9. New Inventory (Schedule 237)
# OCR: "Schedule#: 237 NEW VEH INVENTORY 231-237"
_register(9, "New Inventory",
          "Reynolds -> Schedule Summary -> New Inventory (Sch 237)",
          [r"NEW\s+VEH", r"NEW\s+VEHICLE", r"NEW\s+CAR",
           _SCH + r"237\b", r"NEW\s*\(\s*237\s*\)", r"\(237\)",
           r"\b237\b.*NEW\s+VEH"])

# 10. Used Inventory (Schedule 240)
# OCR: "Schedule#: 240 USED VEHICLE INVENTORY"
_register(10, "Used Inventory",
           "Reynolds -> Schedule Summary -> Used Inventory (Sch 240)",
           [r"USED\s+VEH", r"USED\s+VEHICLE", r"USED\s+CAR",
            _SCH + r"240\b", r"USED\s*\(\s*240\s*\)", r"\(240\)",
            r"\b240\b.*USED\s+VEH"])

# 11. Wholesale Deals in Range — requires "DEAL" or date-range context
# OCR: "WHOLESALE DEALS IN A DATE RANGE"
_register(11, "Wholesale Deals in Range",
           "Reynolds -> Dynamic Reporting -> Wholesale Deals",
           [r"WHOLESALE\s+DEAL", r"WHOLESALE.*(?:RANGE|FROM|THRU|THROUGH|DATE)"],
           negative=[r"Schedule\s*#?\s*:?\s*\d+\s+WHOLESALE"])

# 12. GL 0504 Chargebacks — requires chargeback context
# OCR: "0504" + "CHARGEBACK" on same page
_register(12, "GL 0504 Chargebacks",
           "Reynolds -> GL -> 0504 -> Chargebacks",
           [r"CHARGEBACK.*0504", r"0504.*CHARGEBACK",
            r"F\s*&?\s*I\s+CHARGEBACK", r"CHARGEBACK"])

# 13. Contracts in Transit (Schedule 205)
# OCR: "Schedule#: 205 CONTRACTS IN TRANSIT"
_register(13, "Contracts in Transit",
           "Reynolds -> Schedule Summary -> CIT (Sch 205)",
           [r"CONTRACT\S?\s+IN\s+TRANSIT", r"\bCIT\b",
            _SCH + r"205\b", r"\(\s*205\s*\)"])

# 14. Slow to Accounting
# OCR: "SLOW TO ACCOUNTING"
_register(14, "Slow to Accounting",
           "Reynolds -> Reports -> Slow to Accounting",
           [r"SLOW[\s-]+TO[\s-]+ACCOUNTING"])

# 15. Wholesales (schedule summary, Sch 220) — broader wholesale without "DEAL"
# OCR: "Schedule#: 220 WHOLESALES 220A"
_register(15, "Wholesales",
           "Reynolds -> Schedule Summary -> Wholesales (Sch 220)",
           [r"WHOL[EA]SALE", r"SCHEDULE\s+SUMMARY.*WHOLESALE",
            _SCH + r"220\b", r"\(\s*220\s*\)"],
           negative=[r"WHOLESALE\s+DEAL", r"WHOLESALE.*(?:RANGE|FROM|THRU|THROUGH|DATE)"])

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

    def validate_detailed_with_progress(
        self, source: Union[str, bytes, Path], meeting_id: str
    ) -> DetailedValidationResult:
        """Validate a PDF page-by-page, updating progress store after each page.

        Same result as validate_detailed() but streams progress to the in-memory store.
        Extracts and classifies one page at a time so progress updates during OCR.
        """
        import io
        import os
        import tempfile

        from app.services.validation_progress import ValidationProgress, set_progress

        progress = ValidationProgress(status="counting_pages")
        set_progress(meeting_id, progress)

        # Count pages cheaply first
        total_pages = self._count_pages(source)
        progress.total_pages = total_pages
        progress.status = "validating"
        set_progress(meeting_id, progress)

        # Prepare file handles for page-by-page extraction
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

        # Extract and classify page by page
        classified_pages: list[ClassifiedPage] = []
        unclassified_pages: list[UnclassifiedPage] = []
        doc_pages: dict[int, list[int]] = {}
        found_count = 0
        required_documents: list[RequiredDocumentCheck] = []

        try:
            with pdfplumber.open(pdf_file) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    progress.current_page = page_num
                    set_progress(meeting_id, progress)

                    # Extract text (with OCR fallback) for this single page
                    text = page.extract_text() or ""
                    if len(text.strip()) < self._OCR_THRESHOLD and tmp_path:
                        ocr_text = self._tesseract_ocr_page(tmp_path, page_idx)
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                            logger.info(
                                "Page %d: used tesseract OCR (%d chars)", page_num, len(text)
                            )

                    # Classify this page
                    if not text or not text.strip():
                        up = UnclassifiedPage(page_number=page_num, snippet="(blank page)")
                        unclassified_pages.append(up)
                        progress.unclassified_pages.append(up.model_dump())
                    else:
                        best_doc_id, best_score = self._classify_page_with_score(text)
                        if best_doc_id is not None:
                            doc_name = next(
                                name for did, name, _, _, _ in _DOCUMENT_DEFS if did == best_doc_id
                            )
                            cp = ClassifiedPage(
                                page_number=page_num,
                                document_type=doc_name,
                                confidence=best_score,
                            )
                            classified_pages.append(cp)
                            doc_pages.setdefault(best_doc_id, []).append(page_num)
                            progress.classified_pages.append(cp.model_dump())
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

                    # Update required documents checklist after each page
                    required_documents = []
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

        # Final result
        progress.status = "complete"
        progress.is_complete = found_count == len(_DOCUMENT_DEFS)
        set_progress(meeting_id, progress)

        return DetailedValidationResult(
            classified_pages=classified_pages,
            unclassified_pages=unclassified_pages,
            required_documents=required_documents,
            completeness_percentage=round(completeness, 1),
            is_complete=found_count == len(_DOCUMENT_DEFS),
            total_pages=total_pages,
        )

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

    # Minimum characters from pdfplumber before triggering OCR fallback
    _OCR_THRESHOLD = 50

    def _extract_text(self, source: Union[str, bytes, Path]) -> list[str]:
        """Extract text from each page of the PDF, with fast OCR fallback for scanned pages.

        Uses pytesseract (tesseract-ocr) for OCR instead of EasyOCR — much faster on CPU
        since we only need enough text to classify pages, not high-quality data extraction.
        """
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

                    # OCR fallback for blank/near-blank pages
                    if len(text.strip()) < self._OCR_THRESHOLD and tmp_path:
                        ocr_text = self._tesseract_ocr_page(tmp_path, i)
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                            logger.info(
                                "Page %d: used tesseract OCR (%d chars)", i + 1, len(text)
                            )

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
        """Render a single PDF page and run tesseract OCR on it.

        Returns extracted text string, or empty string on failure.
        """
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
