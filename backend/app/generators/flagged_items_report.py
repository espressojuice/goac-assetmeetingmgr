"""Generates a separate report of only flagged items requiring response."""

import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.models.store import Store
from app.models.flag import Flag, FlagSeverity, FlagCategory

logger = logging.getLogger(__name__)

RED_BG = colors.Color(1.0, 0.78, 0.78)
YELLOW_BG = colors.Color(1.0, 1.0, 0.78)
DARK_RED = colors.Color(0.7, 0.0, 0.0)
DARK_YELLOW = colors.Color(0.6, 0.5, 0.0)

CATEGORY_LABELS = {
    FlagCategory.INVENTORY: "Inventory",
    FlagCategory.PARTS: "Parts",
    FlagCategory.FINANCIAL: "Financial",
    FlagCategory.OPERATIONS: "Operations",
}


class FlaggedItemsReportGenerator:
    """Generates a separate report of only flagged items requiring response."""

    def __init__(self):
        self.page_width = letter[0]
        self.page_height = letter[1]
        self.margin = 0.75 * inch
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
        self._store_name = ""
        self._meeting_date_str = ""

    def _add_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Title"],
            fontSize=20,
            textColor=colors.red,
            alignment=1,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=self.styles["Normal"],
            fontSize=12,
            alignment=1,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="DueNotice",
            parent=self.styles["Normal"],
            fontSize=11,
            textColor=colors.red,
            alignment=1,
            spaceBefore=4,
            spaceAfter=12,
        ))
        self.styles.add(ParagraphStyle(
            name="RedSectionHeader",
            parent=self.styles["Heading2"],
            fontSize=14,
            textColor=DARK_RED,
            spaceBefore=12,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="YellowSectionHeader",
            parent=self.styles["Heading2"],
            fontSize=14,
            textColor=DARK_YELLOW,
            spaceBefore=12,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="FlagItem",
            parent=self.styles["Normal"],
            fontSize=10,
            leading=13,
            spaceBefore=2,
        ))
        self.styles.add(ParagraphStyle(
            name="FlagCategory",
            parent=self.styles["Normal"],
            fontSize=9,
            textColor=colors.gray,
        ))
        self.styles.add(ParagraphStyle(
            name="ResponseLine",
            parent=self.styles["Normal"],
            fontSize=10,
            spaceBefore=4,
            spaceAfter=8,
        ))
        self.styles.add(ParagraphStyle(
            name="NoFlags",
            parent=self.styles["Normal"],
            fontSize=14,
            alignment=1,
            spaceBefore=2 * inch,
        ))
        self.styles.add(ParagraphStyle(
            name="SummaryText",
            parent=self.styles["Normal"],
            fontSize=10,
            alignment=1,
            spaceBefore=6,
        ))

    async def generate(self, meeting_id: str, db: AsyncSession) -> bytes:
        """Generate flagged items PDF for a meeting. Returns PDF as bytes."""
        data = await self._fetch_data(meeting_id, db)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        self._store_name = data["store_name"]
        self._meeting_date_str = data["meeting_date_str"]

        elements = []

        # Header
        elements.extend(self._build_header(data))

        red_flags = data["red_flags"]
        yellow_flags = data["yellow_flags"]

        if not red_flags and not yellow_flags:
            elements.append(Paragraph(
                "No flagged items for this meeting.",
                self.styles["NoFlags"],
            ))
        else:
            # Red flags first
            if red_flags:
                elements.extend(self._build_red_section(red_flags))

            # Yellow flags second
            if yellow_flags:
                elements.extend(self._build_yellow_section(yellow_flags))

        # Summary footer
        elements.extend(self._build_summary_footer(data))

        doc.build(elements, onFirstPage=self._draw_header_footer, onLaterPages=self._draw_header_footer)
        return buf.getvalue()

    def _draw_header_footer(self, canvas, doc):
        """Draw header and footer on every page."""
        canvas.saveState()
        # Header
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(colors.red)
        canvas.drawString(self.margin, self.page_height - 0.5 * inch, "FLAGGED ITEMS — ACTION REQUIRED")
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            self.page_width - self.margin,
            self.page_height - 0.5 * inch,
            f"{self._store_name} — {self._meeting_date_str}",
        )
        canvas.drawCentredString(
            self.page_width / 2,
            self.page_height - 0.62 * inch,
            "Responses due within 24 hours of meeting",
        )
        # Footer
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(
            self.page_width / 2, 0.4 * inch,
            f"Page {canvas.getPageNumber()} — CONFIDENTIAL",
        )
        canvas.restoreState()

    async def _fetch_data(self, meeting_id: str, db: AsyncSession) -> dict:
        meeting_result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = meeting_result.scalar_one()

        store_result = await db.execute(
            select(Store).where(Store.id == meeting.store_id)
        )
        store = store_result.scalar_one()

        flags = (await db.execute(
            select(Flag).where(Flag.meeting_id == meeting_id)
        )).scalars().all()

        red_flags = sorted(
            [f for f in flags if f.severity == FlagSeverity.RED],
            key=lambda f: f.category.value,
        )
        yellow_flags = sorted(
            [f for f in flags if f.severity == FlagSeverity.YELLOW],
            key=lambda f: f.category.value,
        )

        return {
            "meeting": meeting,
            "store": store,
            "store_name": store.name,
            "meeting_date_str": meeting.meeting_date.strftime("%B %d, %Y"),
            "flags": flags,
            "red_flags": red_flags,
            "yellow_flags": yellow_flags,
        }

    def _build_header(self, data: dict) -> list:
        elements = []
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("FLAGGED ITEMS — ACTION REQUIRED", self.styles["ReportTitle"]))
        elements.append(Paragraph(
            f"{data['store_name']} — {data['meeting_date_str']}",
            self.styles["ReportSubtitle"],
        ))
        elements.append(Paragraph(
            "Responses due within 24 hours of meeting",
            self.styles["DueNotice"],
        ))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.red))
        elements.append(Spacer(1, 0.15 * inch))
        return elements

    def _build_red_section(self, red_flags: list) -> list:
        elements = []
        elements.append(Paragraph(
            "ESCALATED ITEMS — IMMEDIATE ATTENTION REQUIRED",
            self.styles["RedSectionHeader"],
        ))
        elements.append(HRFlowable(width="100%", thickness=1, color=DARK_RED))
        elements.append(Spacer(1, 0.1 * inch))

        for i, flag in enumerate(red_flags, start=1):
            elements.extend(self._build_flag_item(i, flag, RED_BG))

        return elements

    def _build_yellow_section(self, yellow_flags: list) -> list:
        elements = []
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph(
            "WARNING ITEMS — RESPONSE REQUIRED",
            self.styles["YellowSectionHeader"],
        ))
        elements.append(HRFlowable(width="100%", thickness=1, color=DARK_YELLOW))
        elements.append(Spacer(1, 0.1 * inch))

        for i, flag in enumerate(yellow_flags, start=1):
            elements.extend(self._build_flag_item(i, flag, YELLOW_BG))

        return elements

    def _build_flag_item(self, number: int, flag, bg_color) -> list:
        elements = []
        avail_width = self.page_width - 2 * self.margin
        category_label = CATEGORY_LABELS.get(flag.category, flag.category.value)

        # Build a table for each flag item
        item_data = [
            [f"#{number}", f"[{category_label}]", flag.message],
            ["", "Value:", f"{flag.field_value or '—'}  |  Threshold: {flag.threshold or '—'}"],
            ["", "RESPONSE:", "_______________________________________________"],
            ["", "Manager:", "________________________  Date: _______________"],
        ]
        col_widths = [avail_width * 0.06, avail_width * 0.14, avail_width * 0.80]
        item_table = Table(item_data, colWidths=col_widths)
        item_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), bg_color),
            ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTSIZE", (0, 0), (0, 0), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.gray),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 0.1 * inch))

        return elements

    def _build_summary_footer(self, data: dict) -> list:
        elements = []
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.black))
        elements.append(Spacer(1, 0.1 * inch))

        red_count = len(data["red_flags"])
        yellow_count = len(data["yellow_flags"])

        summary_data = [
            ["Summary"],
            [f"Red Flags: {red_count}  |  Yellow Flags: {yellow_count}  |  Total: {red_count + yellow_count}"],
        ]
        avail_width = self.page_width - 2 * self.margin
        summary_table = Table(summary_data, colWidths=[avail_width * 0.6])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.4)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.15 * inch))

        elements.append(Paragraph(
            "All responses must be submitted to corporate within 24 hours of meeting date.",
            self.styles["SummaryText"],
        ))
        elements.append(Paragraph(
            "Unresolved items from previous meetings will be auto-escalated.",
            self.styles["SummaryText"],
        ))

        return elements
