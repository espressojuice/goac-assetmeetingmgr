"""Generates the Execute Report PDF — condensed action-focused meeting summary."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional
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
    PageBreak,
    HRFlowable,
)

logger = logging.getLogger(__name__)

# Color constants
GOAC_BLUE = colors.Color(0.0, 0.2, 0.4)       # #003366
GOAC_BLUE_LIGHT = colors.Color(0.9, 0.93, 0.97)  # light blue bg
RED_BG = colors.Color(1.0, 0.88, 0.88)          # #FFE0E0
YELLOW_BG = colors.Color(1.0, 0.99, 0.88)       # #FFFDE0
GREEN_BG = colors.Color(0.88, 1.0, 0.88)        # #E0FFE0
DARK_RED = colors.Color(0.6, 0.0, 0.0)
DARK_GREEN = colors.Color(0.0, 0.45, 0.0)
DARK_YELLOW = colors.Color(0.55, 0.45, 0.0)
WHITE = colors.white
LIGHT_GRAY = colors.Color(0.95, 0.95, 0.95)
HEADER_BG = GOAC_BLUE
HEADER_TEXT = colors.white


class ExecuteReportGenerator:
    """Generates the condensed Execute Report PDF for corporate/GM review."""

    def __init__(self):
        self.page_width = letter[0]
        self.page_height = letter[1]
        self.margin = 0.6 * inch
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
        self._store_name = ""
        self._meeting_date_str = ""
        self._generated_str = ""

    def _add_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="ERTitle",
            parent=self.styles["Title"],
            fontSize=22,
            textColor=GOAC_BLUE,
            alignment=1,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="ERSubtitle",
            parent=self.styles["Normal"],
            fontSize=12,
            alignment=1,
            spaceAfter=4,
            textColor=colors.Color(0.3, 0.3, 0.3),
        ))
        self.styles.add(ParagraphStyle(
            name="ERSectionHeader",
            parent=self.styles["Heading2"],
            fontSize=14,
            textColor=GOAC_BLUE,
            spaceBefore=12,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="ERStatusHeader",
            parent=self.styles["Heading3"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="ERBody",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=11,
        ))
        self.styles.add(ParagraphStyle(
            name="ERFlagDetail",
            parent=self.styles["Normal"],
            fontSize=8,
            leading=10,
            leftIndent=10,
        ))
        self.styles.add(ParagraphStyle(
            name="ERSmall",
            parent=self.styles["Normal"],
            fontSize=7,
            textColor=colors.gray,
        ))

    def generate(self, data: dict) -> bytes:
        """Generate the Execute Report PDF from pre-loaded data dict.

        Args:
            data: Dict containing all report data (flags, attendance, metrics, etc.)

        Returns:
            PDF bytes.
        """
        self._store_name = data["store_name"]
        self._meeting_date_str = data["meeting_date_str"]
        self._generated_str = datetime.now(ZoneInfo("US/Central")).strftime(
            "%m/%d/%Y %I:%M %p CT"
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        elements = []

        # Page 1 — Executive Summary
        elements.extend(self._build_executive_summary(data))

        # Page 2 — Top Priority Items
        elements.append(PageBreak())
        elements.extend(self._build_top_priorities(data))

        # Page 3+ — Flags by Status
        elements.append(PageBreak())
        elements.extend(self._build_flags_by_status(data))

        # Manager Accountability Snapshot
        elements.extend(self._build_manager_accountability(data))

        doc.build(elements, onFirstPage=self._draw_header_footer, onLaterPages=self._draw_header_footer)
        return buf.getvalue()

    def _draw_header_footer(self, canvas, doc):
        """Draw header and footer on every page."""
        canvas.saveState()
        # Header bar
        canvas.setFillColor(GOAC_BLUE)
        canvas.rect(0, self.page_height - 0.35 * inch, self.page_width, 0.35 * inch, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(self.margin, self.page_height - 0.25 * inch, "EXECUTE REPORT")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            self.page_width - self.margin,
            self.page_height - 0.25 * inch,
            f"{self._store_name} — {self._meeting_date_str}",
        )
        # Footer
        canvas.setFillColor(colors.gray)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            self.margin, 0.3 * inch,
            f"Generated {self._generated_str}",
        )
        canvas.drawCentredString(
            self.page_width / 2, 0.3 * inch,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.drawRightString(
            self.page_width - self.margin, 0.3 * inch,
            "CONFIDENTIAL",
        )
        canvas.restoreState()

    # ── Page 1: Executive Summary ────────────────────────────────

    def _build_executive_summary(self, data: dict) -> list:
        elements = []
        avail_width = self.page_width - 2 * self.margin

        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph("EXECUTE REPORT", self.styles["ERTitle"]))
        elements.append(Paragraph(
            f"{data['store_name']} — {data['meeting_date_str']}",
            self.styles["ERSubtitle"],
        ))
        elements.append(HRFlowable(width="100%", thickness=2, color=GOAC_BLUE))
        elements.append(Spacer(1, 0.15 * inch))

        # Meeting status box
        meeting_status = data.get("meeting_status", "N/A")
        closed_at = data.get("closed_at_str", "N/A")
        closed_by = data.get("closed_by_name", "N/A")

        status_data = [
            ["Meeting Status", meeting_status.upper()],
            ["Closed", closed_at],
            ["Closed By", closed_by],
        ]
        status_table = Table(status_data, colWidths=[avail_width * 0.35, avail_width * 0.35])
        status_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), GOAC_BLUE_LIGHT),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(status_table)
        elements.append(Spacer(1, 0.15 * inch))

        # Attendance box
        att = data.get("attendance", {})
        present_names = att.get("present_names", [])
        absent_names = att.get("absent_names", [])
        present_count = att.get("present", 0)
        absent_count = att.get("absent", 0)

        elements.append(Paragraph("Attendance", self.styles["ERSectionHeader"]))
        att_data = [
            ["Present", "Absent"],
            [
                ", ".join(present_names) if present_names else "None recorded",
                ", ".join(absent_names) if absent_names else "None",
            ],
            [f"Total: {present_count}", f"Total: {absent_count}"],
        ]
        att_table = Table(att_data, colWidths=[avail_width * 0.5, avail_width * 0.5])
        att_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GOAC_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BACKGROUND", (0, 2), (-1, 2), LIGHT_GRAY),
            ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ]))
        elements.append(att_table)
        elements.append(Spacer(1, 0.15 * inch))

        # Key metrics row
        total_flags = data.get("total_flags", 0)
        red_count = data.get("red_count", 0)
        yellow_count = data.get("yellow_count", 0)
        verified_count = data.get("verified_count", 0)
        unresolved_count = data.get("unresolved_count", 0)
        open_count = data.get("open_count", 0)
        resolution_rate = data.get("resolution_rate", 0.0)

        elements.append(Paragraph("Flag Metrics", self.styles["ERSectionHeader"]))
        metrics_data = [
            ["Total Flags", "Red", "Yellow", "Verified", "Unresolved", "Open"],
            [str(total_flags), str(red_count), str(yellow_count),
             str(verified_count), str(unresolved_count), str(open_count)],
        ]
        col_w = avail_width / 6
        metrics_table = Table(metrics_data, colWidths=[col_w] * 6)
        metrics_style = [
            ("BACKGROUND", (0, 0), (-1, 0), GOAC_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, 1), 14),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        # Color-code the count cells
        if red_count > 0:
            metrics_style.append(("BACKGROUND", (1, 1), (1, 1), RED_BG))
        if yellow_count > 0:
            metrics_style.append(("BACKGROUND", (2, 1), (2, 1), YELLOW_BG))
        if verified_count > 0:
            metrics_style.append(("BACKGROUND", (3, 1), (3, 1), GREEN_BG))
        if unresolved_count > 0:
            metrics_style.append(("BACKGROUND", (4, 1), (4, 1), RED_BG))
        metrics_table.setStyle(TableStyle(metrics_style))
        elements.append(metrics_table)
        elements.append(Spacer(1, 0.1 * inch))

        # Resolution rate
        elements.append(Paragraph(
            f"<b>Resolution Rate: {resolution_rate:.0f}%</b>",
            self.styles["ERBody"],
        ))

        return elements

    # ── Page 2: Top Priority Items ───────────────────────────────

    def _build_top_priorities(self, data: dict) -> list:
        elements = []
        avail_width = self.page_width - 2 * self.margin

        elements.append(Paragraph("TOP PRIORITY ITEMS", self.styles["ERSectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=GOAC_BLUE))
        elements.append(Spacer(1, 0.1 * inch))

        priorities = data.get("top_priorities", [])
        if not priorities:
            elements.append(Paragraph(
                "No unresolved priority items.",
                self.styles["ERBody"],
            ))
            return elements

        header = ["#", "Score", "Description", "Severity", "Status", "Assigned To", "Days Out", "Promise Date"]
        col_widths = [avail_width * w for w in [0.04, 0.06, 0.30, 0.08, 0.10, 0.16, 0.08, 0.18]]
        rows = [header]
        for i, item in enumerate(priorities, start=1):
            promise = item.get("expected_resolution_date") or "—"
            rows.append([
                str(i),
                str(item.get("priority_score", 0)),
                Paragraph(str(item.get("description", ""))[:100], self.styles["ERFlagDetail"]),
                item.get("severity", "").upper(),
                item.get("status", "").upper(),
                item.get("assigned_to_name") or "Unassigned",
                str(item.get("days_outstanding", 0)),
                str(promise),
            ])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), GOAC_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        # Color-code rows by priority score
        for i, item in enumerate(priorities, start=1):
            score = item.get("priority_score", 0)
            if score >= 10:
                style.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
            elif score >= 5:
                style.append(("BACKGROUND", (0, i), (-1, i), YELLOW_BG))

        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements

    # ── Page 3+: Flags by Status ─────────────────────────────────

    def _build_flags_by_status(self, data: dict) -> list:
        elements = []

        unresolved = data.get("flags_unresolved", [])
        responded = data.get("flags_responded", [])
        verified = data.get("flags_verified", [])
        auto_unresolved = data.get("flags_auto_unresolved", [])

        # Unresolved section
        elements.extend(self._build_status_section(
            f"UNRESOLVED ({len(unresolved)})",
            unresolved, DARK_RED, RED_BG, show_recurring=True,
        ))

        # Responded — Pending Verification
        elements.extend(self._build_status_section(
            f"RESPONDED — Pending Verification ({len(responded)})",
            responded, DARK_YELLOW, YELLOW_BG, show_response=True,
        ))

        # Verified
        elements.extend(self._build_status_section(
            f"VERIFIED ({len(verified)})",
            verified, DARK_GREEN, GREEN_BG, show_verification=True,
        ))

        # Auto-Unresolved
        if auto_unresolved:
            elements.extend(self._build_status_section(
                f"AUTO-UNRESOLVED — No Response ({len(auto_unresolved)})",
                auto_unresolved, DARK_RED, RED_BG,
            ))

        return elements

    def _build_status_section(
        self,
        title: str,
        flags: list,
        header_color,
        bg_color,
        show_recurring: bool = False,
        show_response: bool = False,
        show_verification: bool = False,
    ) -> list:
        elements = []
        avail_width = self.page_width - 2 * self.margin

        # Section header bar
        header_data = [[title]]
        header_table = Table(header_data, colWidths=[avail_width])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), header_color),
            ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(header_table)

        if not flags:
            elements.append(Paragraph(
                "<i>None</i>",
                self.styles["ERBody"],
            ))
            elements.append(Spacer(1, 0.05 * inch))
            return elements

        for flag in flags:
            detail_parts = []
            rule_name = flag.get("rule_name", "")
            description = flag.get("description", "")
            assigned_to = flag.get("assigned_to_name") or "Unassigned"
            days = flag.get("days_outstanding", 0)
            severity = flag.get("severity", "").upper()

            detail_parts.append(f"<b>{severity}</b> — {rule_name}: {description[:200]}")
            detail_parts.append(f"Assigned to: <b>{assigned_to}</b> | Days outstanding: <b>{days}</b>")

            if show_recurring and flag.get("escalation_level", 0) > 0:
                detail_parts.append(
                    f"<font color='red'><b>Recurring — escalation level {flag['escalation_level']}</b></font>"
                )

            if flag.get("expected_resolution_date"):
                detail_parts.append(f"Expected resolution: {flag['expected_resolution_date']}")

            if show_response and flag.get("response_text"):
                text = flag["response_text"][:200]
                detail_parts.append(f"Response: <i>{text}</i>")

            if show_verification:
                verified_by = flag.get("verified_by_name", "")
                notes = flag.get("verification_notes", "")
                if verified_by:
                    detail_parts.append(f"Verified by: {verified_by}")
                if notes:
                    detail_parts.append(f"Notes: <i>{notes[:200]}</i>")

            # Build a compact row
            detail_text = "<br/>".join(detail_parts)
            row_data = [[Paragraph(detail_text, self.styles["ERFlagDetail"])]]
            row_table = Table(row_data, colWidths=[avail_width])
            row_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.gray),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(row_table)
            elements.append(Spacer(1, 0.03 * inch))

        return elements

    # ── Manager Accountability Snapshot ──────────────────────────

    def _build_manager_accountability(self, data: dict) -> list:
        elements = []
        avail_width = self.page_width - 2 * self.margin

        manager_metrics = data.get("manager_metrics", [])
        if not manager_metrics:
            return elements

        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph("MANAGER ACCOUNTABILITY", self.styles["ERSectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=GOAC_BLUE))
        elements.append(Spacer(1, 0.1 * inch))

        header = ["Manager", "Assigned", "Resolved", "Unresolved", "Resolution Rate"]
        col_widths = [avail_width * w for w in [0.30, 0.15, 0.15, 0.18, 0.22]]
        rows = [header]
        for m in manager_metrics:
            rate = m.get("resolution_rate", 0.0)
            rows.append([
                m.get("name", ""),
                str(m.get("assigned", 0)),
                str(m.get("resolved", 0)),
                str(m.get("unresolved", 0)),
                f"{rate:.0f}%",
            ])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), GOAC_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ]
        # Color-code worst resolution rates
        for i, m in enumerate(manager_metrics, start=1):
            rate = m.get("resolution_rate", 0.0)
            if rate < 50:
                style.append(("BACKGROUND", (4, i), (4, i), RED_BG))
            elif rate < 80:
                style.append(("BACKGROUND", (4, i), (4, i), YELLOW_BG))

        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements
