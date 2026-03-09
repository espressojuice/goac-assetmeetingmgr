"""PDF text and table extraction layer using pdfplumber with OCR fallback."""

import io
import logging
import os
import tempfile
from collections import defaultdict

import pdfplumber

logger = logging.getLogger(__name__)

# Lazy-loaded OCR dependencies
_ocr_reader = None

# Y-coordinate tolerance for grouping OCR elements into the same row
_ROW_TOLERANCE = 15


def _get_ocr_reader():
    """Lazy-load EasyOCR reader (heavy import, only when needed)."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized")
        except ImportError:
            logger.warning("easyocr not installed — OCR fallback unavailable")
            return None
    return _ocr_reader


def _ocr_page_detailed(pdf_path: str, page_index: int, rotation: int = 0):
    """Render a PDF page and run OCR, returning detailed results with bounding boxes.

    Returns list of (bbox, text, confidence) tuples, or empty list on failure.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.warning("pypdfium2 not installed — cannot render pages for OCR")
        return []

    reader = _get_ocr_reader()
    if reader is None:
        return []

    try:
        pdf = pdfium.PdfDocument(pdf_path)
        page = pdf[page_index]
        bitmap = page.render(scale=2, rotation=rotation)
        img = bitmap.to_pil()
        pdf.close()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            tmp_path = f.name

        try:
            return reader.readtext(tmp_path, detail=1, paragraph=False)
        finally:
            os.unlink(tmp_path)

    except Exception:
        logger.exception("OCR failed for page %d", page_index + 1)
        return []


def _build_text_and_tables(ocr_results):
    """Build text string and synthetic table from OCR bounding box results.

    Groups OCR elements by y-coordinate into rows, sorts by x-coordinate.
    Returns (text, tables) where tables is a list containing one synthetic table.
    """
    if not ocr_results:
        return "", []

    # Extract (y_center, x_left, text) for each element
    elements = []
    for bbox, text, conf in ocr_results:
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_left = bbox[0][0]
        elements.append((y_center, x_left, text))

    # Sort by y then x
    elements.sort(key=lambda e: (e[0], e[1]))

    # Group into rows by y-coordinate proximity
    rows = []
    current_row = [elements[0]]
    for elem in elements[1:]:
        if abs(elem[0] - current_row[-1][0]) <= _ROW_TOLERANCE:
            current_row.append(elem)
        else:
            rows.append(current_row)
            current_row = [elem]
    rows.append(current_row)

    # Sort each row by x-coordinate and build text/table
    text_lines = []
    table_rows = []
    for row in rows:
        row.sort(key=lambda e: e[1])
        cells = [e[2] for e in row]
        text_lines.append("  ".join(cells))
        table_rows.append(cells)

    text = "\n".join(text_lines)

    # Normalize table: pad rows to the max column count
    if table_rows:
        max_cols = max(len(r) for r in table_rows)
        for row in table_rows:
            while len(row) < max_cols:
                row.append("")
        tables = [table_rows]
    else:
        tables = []

    return text, tables


def _is_landscape_content(ocr_results):
    """Heuristic: if OCR produces mostly single-char garbage, content may be rotated."""
    if not ocr_results:
        return False
    texts = [r[1] for r in ocr_results]
    if len(texts) < 5:
        return False
    avg_len = sum(len(t) for t in texts) / len(texts)
    return avg_len < 3


class PDFExtractor:
    """Extracts text and tables from uploaded PDF files.

    Falls back to OCR (EasyOCR + pypdfium2) for scanned/image-based pages.
    Reconstructs table structure from OCR bounding box positions.
    """

    def __init__(self, enable_ocr: bool = True):
        self.enable_ocr = enable_ocr
        self._source_path = None

    def extract(self, file_path: str) -> list[dict]:
        """Extract all pages from a PDF file on disk."""
        self._source_path = file_path
        with pdfplumber.open(file_path) as pdf:
            return self._extract_pages(pdf)

    def extract_from_bytes(self, file_bytes: bytes) -> list[dict]:
        """Extract from in-memory bytes (for uploaded files)."""
        if self.enable_ocr:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(file_bytes)
                self._source_path = f.name
            try:
                with pdfplumber.open(self._source_path) as pdf:
                    return self._extract_pages(pdf)
            finally:
                os.unlink(self._source_path)
                self._source_path = None
        else:
            self._source_path = None
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return self._extract_pages(pdf)

    def _extract_pages(self, pdf: pdfplumber.PDF) -> list[dict]:
        """Extract structured data from all pages in an open PDF."""
        pages = []
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                has_chars = len(page.chars) > 0

                # If no text extracted and page has images, try OCR
                if not text.strip() and not has_chars and self.enable_ocr and self._source_path:
                    logger.info("Page %d: no text layer, attempting OCR", i + 1)
                    ocr_results = _ocr_page_detailed(self._source_path, i)

                    # Handle rotated pages
                    if _is_landscape_content(ocr_results):
                        logger.info("Page %d: detected rotated content, retrying with 90° rotation", i + 1)
                        ocr_rotated = _ocr_page_detailed(self._source_path, i, rotation=90)
                        if not _is_landscape_content(ocr_rotated) and len(ocr_rotated) > 0:
                            ocr_results = ocr_rotated

                    text, tables = _build_text_and_tables(ocr_results)

                pages.append(
                    {
                        "page_number": i + 1,
                        "text": text,
                        "lines": text.split("\n") if text else [],
                        "tables": tables,
                        "ocr_used": not has_chars and bool(text),
                    }
                )
            except Exception:
                logger.exception("Error extracting page %d", i + 1)
                pages.append(
                    {
                        "page_number": i + 1,
                        "text": "",
                        "lines": [],
                        "tables": [],
                        "ocr_used": False,
                    }
                )
        return pages
