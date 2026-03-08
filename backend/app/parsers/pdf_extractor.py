"""PDF text and table extraction layer using pdfplumber."""

import io
import logging

import pdfplumber

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extracts text and tables from uploaded PDF files."""

    def extract(self, file_path: str) -> list[dict]:
        """
        Extract all pages from a PDF file on disk.

        Returns list of page dicts:
            - page_number (int, 1-indexed)
            - text (str) — full text of the page
            - lines (list[str]) — text split by newlines
            - tables (list[list[list[str]]]) — pdfplumber table extractions
        """
        with pdfplumber.open(file_path) as pdf:
            return self._extract_pages(pdf)

    def extract_from_bytes(self, file_bytes: bytes) -> list[dict]:
        """Extract from in-memory bytes (for uploaded files)."""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return self._extract_pages(pdf)

    def _extract_pages(self, pdf: pdfplumber.PDF) -> list[dict]:
        """Extract structured data from all pages in an open PDF."""
        pages = []
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                pages.append(
                    {
                        "page_number": i + 1,
                        "text": text,
                        "lines": text.split("\n") if text else [],
                        "tables": tables,
                    }
                )
            except Exception:
                logger.exception(f"Error extracting page {i + 1}")
                pages.append(
                    {
                        "page_number": i + 1,
                        "text": "",
                        "lines": [],
                        "tables": [],
                    }
                )
        return pages
