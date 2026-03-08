"""Routes PDF pages to the appropriate parser modules."""

import logging
from collections import defaultdict

from .base import BaseParser

logger = logging.getLogger(__name__)


class ParserRouter:
    """Routes PDF pages to the appropriate parser modules."""

    def __init__(self):
        self.parsers: list[BaseParser] = []
        self._register_parsers()

    def _register_parsers(self):
        """Register all available parser modules."""
        from .inventory_parser import InventoryParser
        from .parts_parser import PartsParser
        from .financial_parser import FinancialParser
        from .operations_parser import OperationsParser

        self.parsers.append(InventoryParser())
        self.parsers.append(PartsParser())
        self.parsers.append(FinancialParser())
        self.parsers.append(OperationsParser())

    def route_and_parse(self, pages: list[dict]) -> dict:
        """
        Route pages to appropriate parsers and collect results.

        Groups pages by parser, calls each parser, merges results.
        Returns combined dict of all parsed records plus metadata.
        """
        results = {}
        unhandled_pages = []

        # Group pages by which parser(s) can handle them
        parser_pages: dict[int, list[dict]] = defaultdict(list)

        for page in pages:
            handled = False
            for idx, parser in enumerate(self.parsers):
                if parser.can_handle(page["text"]):
                    parser_pages[idx].append(page)
                    handled = True
            if not handled:
                unhandled_pages.append(page["page_number"])

        # Call each parser with its pages
        for idx, parser in enumerate(self.parsers):
            if idx in parser_pages:
                parser_name = type(parser).__name__
                try:
                    parsed = parser.parse(parser_pages[idx])
                    for model_name, records in parsed.items():
                        if model_name in results:
                            results[model_name].extend(records)
                        else:
                            results[model_name] = records
                    logger.info(
                        f"{parser_name} parsed {sum(len(r) for r in parsed.values())} "
                        f"records from {len(parser_pages[idx])} pages"
                    )
                except Exception:
                    logger.exception(f"Error in {parser_name}")

        if unhandled_pages:
            logger.info(f"Unhandled pages: {unhandled_pages}")

        results["_unhandled_pages"] = unhandled_pages
        return results
