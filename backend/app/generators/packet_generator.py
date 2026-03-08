"""Generates a standardized meeting packet PDF from parsed data."""

import io
import logging
from datetime import datetime
from decimal import Decimal
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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.models.store import Store
from app.models.inventory import (
    NewVehicleInventory,
    UsedVehicleInventory,
    ServiceLoaner,
    FloorplanReconciliation,
)
from app.models.parts import PartsInventory, PartsAnalysis
from app.models.financial import Receivable, FIChargeback, ContractInTransit
from app.models.operations import OpenRepairOrder, MissingTitle, SlowToAccounting
from app.models.flag import Flag, FlagSeverity

logger = logging.getLogger(__name__)

# Color constants
RED_BG = colors.Color(1.0, 0.78, 0.78)        # (255, 200, 200)
YELLOW_BG = colors.Color(1.0, 1.0, 0.78)       # (255, 255, 200)
LIGHT_GRAY = colors.Color(0.95, 0.95, 0.95)
WHITE = colors.white
HEADER_BG = colors.Color(0.2, 0.2, 0.4)
HEADER_TEXT = colors.white


def _fmt_currency(val) -> str:
    """Format a value as currency: $1,234.56 or ($1,234.56) for negatives."""
    if val is None:
        return "—"
    try:
        d = Decimal(str(val))
    except Exception:
        return str(val)
    if d < 0:
        return f"(${abs(d):,.2f})"
    return f"${d:,.2f}"


def _fmt_date(val) -> str:
    """Format a date as MM/DD/YYYY."""
    if val is None:
        return "—"
    try:
        return val.strftime("%m/%d/%Y")
    except Exception:
        return str(val)


def _fmt_int(val) -> str:
    if val is None:
        return "—"
    return f"{int(val):,}"


class StandardizedPacketGenerator:
    """Generates a standardized meeting packet PDF from parsed data."""

    def __init__(self):
        self.page_width = letter[0]
        self.page_height = letter[1]
        self.margin = 0.75 * inch
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
        self._store_name = ""
        self._meeting_date_str = ""
        self._generated_str = ""

    def _add_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading1"],
            fontSize=16,
            spaceAfter=6,
            spaceBefore=12,
            textColor=colors.Color(0.15, 0.15, 0.35),
        ))
        self.styles.add(ParagraphStyle(
            name="SubHeader",
            parent=self.styles["Heading2"],
            fontSize=12,
            spaceAfter=4,
            spaceBefore=8,
        ))
        self.styles.add(ParagraphStyle(
            name="CoverTitle",
            parent=self.styles["Title"],
            fontSize=28,
            spaceAfter=12,
            alignment=1,
        ))
        self.styles.add(ParagraphStyle(
            name="CoverSubtitle",
            parent=self.styles["Heading2"],
            fontSize=18,
            alignment=1,
            spaceAfter=8,
        ))
        self.styles.add(ParagraphStyle(
            name="CoverBody",
            parent=self.styles["Normal"],
            fontSize=14,
            alignment=1,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="FlagAlert",
            parent=self.styles["Normal"],
            fontSize=12,
            textColor=colors.red,
            alignment=1,
            spaceBefore=12,
        ))
        self.styles.add(ParagraphStyle(
            name="BodyText2",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=11,
        ))

    async def generate(self, meeting_id: str, db: AsyncSession) -> bytes:
        """Generate the full packet PDF for a meeting. Returns PDF as bytes."""
        data = await self._fetch_all_data(meeting_id, db)

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
        self._generated_str = datetime.now(ZoneInfo("US/Central")).strftime(
            "%m/%d/%Y %I:%M %p CT"
        )

        elements = []
        elements.extend(self._build_cover_page(data))
        elements.append(PageBreak())
        elements.extend(self._build_executive_summary(data))
        elements.append(PageBreak())
        elements.extend(self._build_new_vehicle_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_used_vehicle_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_service_loaner_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_parts_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_receivables_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_fi_chargeback_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_contracts_in_transit_section(data))
        elements.append(PageBreak())
        elements.extend(self._build_operations_section(data))

        doc.build(elements, onFirstPage=self._draw_footer, onLaterPages=self._draw_footer)
        return buf.getvalue()

    def _draw_footer(self, canvas, doc):
        """Draw footer on every page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        page_num = canvas.getPageNumber()
        footer_left = (
            f"GOAC Asset Meeting Packet — {self._store_name} — {self._meeting_date_str}"
        )
        footer_right = f"Generated {self._generated_str} — CONFIDENTIAL"
        canvas.drawString(self.margin, 0.4 * inch, footer_left)
        canvas.drawRightString(
            self.page_width - self.margin, 0.4 * inch, footer_right
        )
        canvas.drawCentredString(
            self.page_width / 2, 0.4 * inch, f"Page {page_num}"
        )
        canvas.restoreState()

    async def _fetch_all_data(self, meeting_id: str, db: AsyncSession) -> dict:
        """Fetch all data needed to build the packet."""
        meeting_result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = meeting_result.scalar_one()

        store_result = await db.execute(
            select(Store).where(Store.id == meeting.store_id)
        )
        store = store_result.scalar_one()

        new_vehicles = (await db.execute(
            select(NewVehicleInventory)
            .where(NewVehicleInventory.meeting_id == meeting_id)
            .order_by(NewVehicleInventory.days_in_stock.desc())
        )).scalars().all()

        used_vehicles = (await db.execute(
            select(UsedVehicleInventory)
            .where(UsedVehicleInventory.meeting_id == meeting_id)
            .order_by(UsedVehicleInventory.days_in_stock.desc())
        )).scalars().all()

        service_loaners = (await db.execute(
            select(ServiceLoaner)
            .where(ServiceLoaner.meeting_id == meeting_id)
            .order_by(ServiceLoaner.days_in_service.desc())
        )).scalars().all()

        floorplan_recons = (await db.execute(
            select(FloorplanReconciliation)
            .where(FloorplanReconciliation.meeting_id == meeting_id)
        )).scalars().all()

        parts_inventory = (await db.execute(
            select(PartsInventory).where(PartsInventory.meeting_id == meeting_id)
        )).scalars().all()

        parts_analyses = (await db.execute(
            select(PartsAnalysis).where(PartsAnalysis.meeting_id == meeting_id)
        )).scalars().all()

        receivables = (await db.execute(
            select(Receivable).where(Receivable.meeting_id == meeting_id)
        )).scalars().all()

        fi_chargebacks = (await db.execute(
            select(FIChargeback).where(FIChargeback.meeting_id == meeting_id)
        )).scalars().all()

        contracts = (await db.execute(
            select(ContractInTransit)
            .where(ContractInTransit.meeting_id == meeting_id)
            .order_by(ContractInTransit.days_in_transit.desc())
        )).scalars().all()

        open_ros = (await db.execute(
            select(OpenRepairOrder)
            .where(OpenRepairOrder.meeting_id == meeting_id)
            .order_by(OpenRepairOrder.days_open.desc())
        )).scalars().all()

        missing_titles = (await db.execute(
            select(MissingTitle).where(MissingTitle.meeting_id == meeting_id)
        )).scalars().all()

        slow_deals = (await db.execute(
            select(SlowToAccounting)
            .where(SlowToAccounting.meeting_id == meeting_id)
            .order_by(SlowToAccounting.days_to_accounting.desc())
        )).scalars().all()

        flags = (await db.execute(
            select(Flag).where(Flag.meeting_id == meeting_id)
        )).scalars().all()

        red_flags = [f for f in flags if f.severity == FlagSeverity.RED]
        yellow_flags = [f for f in flags if f.severity == FlagSeverity.YELLOW]

        return {
            "meeting": meeting,
            "store": store,
            "store_name": store.name,
            "meeting_date": meeting.meeting_date,
            "meeting_date_str": meeting.meeting_date.strftime("%B %d, %Y"),
            "new_vehicles": new_vehicles,
            "used_vehicles": used_vehicles,
            "service_loaners": service_loaners,
            "floorplan_recons": floorplan_recons,
            "parts_inventory": parts_inventory,
            "parts_analyses": parts_analyses,
            "receivables": receivables,
            "fi_chargebacks": fi_chargebacks,
            "contracts": contracts,
            "open_ros": open_ros,
            "missing_titles": missing_titles,
            "slow_deals": slow_deals,
            "flags": flags,
            "red_flags": red_flags,
            "yellow_flags": yellow_flags,
        }

    # ── Section Builders ──────────────────────────────────────

    def _build_cover_page(self, data: dict) -> list:
        elements = []
        elements.append(Spacer(1, 1.5 * inch))
        elements.append(Paragraph("GREGG ORR AUTO COLLECTION", self.styles["CoverTitle"]))
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(data["store_name"], self.styles["CoverTitle"]))
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph("Asset & Receivable Meeting Packet", self.styles["CoverSubtitle"]))
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(data["meeting_date_str"], self.styles["CoverBody"]))
        elements.append(Paragraph(f"Generated {self._generated_str}", self.styles["CoverBody"]))
        elements.append(Spacer(1, 0.5 * inch))

        red_count = len(data["red_flags"])
        yellow_count = len(data["yellow_flags"])
        summary_data = [
            ["Flag Summary"],
            [f"Red Flags: {red_count}    |    Yellow Flags: {yellow_count}    |    Total: {red_count + yellow_count}"],
        ]
        summary_table = Table(summary_data, colWidths=[5 * inch])
        summary_style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_TEXT),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("FONTSIZE", (0, 1), (-1, -1), 11),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
        if red_count > 0:
            summary_style.append(("BACKGROUND", (0, 1), (-1, 1), RED_BG))
        summary_table.setStyle(TableStyle(summary_style))
        elements.append(summary_table)

        return elements

    def _build_executive_summary(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 1: Executive Summary", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        new_count = len(data["new_vehicles"])
        total_floorplan = sum(v.floorplan_balance or Decimal(0) for v in data["new_vehicles"])
        used_count = len(data["used_vehicles"])
        used_over_60 = sum(1 for v in data["used_vehicles"] if v.days_in_stock > 60)
        used_over_90 = sum(1 for v in data["used_vehicles"] if v.days_in_stock > 90)
        loaner_count = len(data["service_loaners"])
        total_neg_equity = sum(v.negative_equity or Decimal(0) for v in data["service_loaners"])
        parts_turnover = "—"
        if data["parts_analyses"]:
            latest = max(data["parts_analyses"], key=lambda p: (p.period_year, p.period_month))
            if latest.true_turnover is not None:
                parts_turnover = f"{latest.true_turnover:.1f}"
        ro_count = len(data["open_ros"])
        total_recv_over_30 = sum(
            (r.over_30 or Decimal(0)) + (r.over_60 or Decimal(0)) + (r.over_90 or Decimal(0))
            for r in data["receivables"]
        )
        missing_count = len(data["missing_titles"])
        cit_count = len(data["contracts"])

        stats_data = [
            ["Metric", "Value"],
            ["New Vehicle Count", _fmt_int(new_count)],
            ["Total Floorplan Exposure (New)", _fmt_currency(total_floorplan)],
            ["Used Vehicle Count", _fmt_int(used_count)],
            ["Used Units Over 60 Days", _fmt_int(used_over_60)],
            ["Used Units Over 90 Days", _fmt_int(used_over_90)],
            ["Service Loaner Count", _fmt_int(loaner_count)],
            ["Total Loaner Negative Equity", _fmt_currency(total_neg_equity)],
            ["Parts Turnover Rate", parts_turnover],
            ["Open Repair Orders", _fmt_int(ro_count)],
            ["Total Receivables Over 30 Days", _fmt_currency(total_recv_over_30)],
            ["Missing Titles", _fmt_int(missing_count)],
            ["Contracts in Transit", _fmt_int(cit_count)],
        ]

        avail_width = self.page_width - 2 * self.margin
        stats_table = Table(stats_data, colWidths=[avail_width * 0.6, avail_width * 0.4])
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 0.2 * inch))

        red_count = len(data["red_flags"])
        if red_count > 0:
            elements.append(Paragraph(
                f"⚠ {red_count} RED FLAG(S) — REQUIRES IMMEDIATE ATTENTION",
                self.styles["FlagAlert"],
            ))
            elements.append(Spacer(1, 0.15 * inch))

        # Floorplan reconciliation summary (always shown)
        elements.append(Paragraph("Floorplan Reconciliation", self.styles["SubHeader"]))
        recon_data = [["Type", "Book Balance", "Floorplan Balance", "Variance"]]
        if data["floorplan_recons"]:
            for r in data["floorplan_recons"]:
                label = "New (237)" if "237" in str(r.reconciliation_type.value) else "Used (240)"
                row = [label, _fmt_currency(r.book_balance), _fmt_currency(r.floorplan_balance), _fmt_currency(r.variance)]
                recon_data.append(row)
        else:
            recon_data.append(["No reconciliation data", "—", "—", "$0.00"])

        recon_table = Table(recon_data, colWidths=[avail_width * 0.25] * 4)
        recon_style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        # Highlight variance if non-zero
        for i, r in enumerate(data.get("floorplan_recons", []), start=1):
            if r.variance and abs(r.variance) > 0:
                recon_style.append(("BACKGROUND", (3, i), (3, i), YELLOW_BG))
            if r.variance and abs(r.variance) > 1000:
                recon_style.append(("BACKGROUND", (3, i), (3, i), RED_BG))
        recon_table.setStyle(TableStyle(recon_style))
        elements.append(recon_table)

        return elements

    def _build_new_vehicle_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 2: New Vehicle Inventory", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        vehicles = data["new_vehicles"]
        if not vehicles:
            elements.append(Paragraph("No new vehicle inventory data.", self.styles["BodyText2"]))
            return elements

        avail_width = self.page_width - 2 * self.margin
        col_widths = [avail_width * w for w in [0.12, 0.08, 0.15, 0.25, 0.12, 0.28]]
        header = ["Stock #", "Year", "Make", "Model", "Days", "Floorplan Bal"]
        rows = [header]
        total_fp = Decimal(0)
        for v in vehicles:
            rows.append([
                v.stock_number,
                str(v.year),
                v.make,
                v.model,
                str(v.days_in_stock),
                _fmt_currency(v.floorplan_balance),
            ])
            total_fp += v.floorplan_balance or Decimal(0)
        rows.append(["", "", "", "TOTAL", "", _fmt_currency(total_fp)])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = self._base_table_style(len(rows))
        # Color-code by days
        for i, v in enumerate(vehicles, start=1):
            if v.days_in_stock > 120:
                style.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
            elif v.days_in_stock > 90:
                style.append(("BACKGROUND", (0, i), (-1, i), YELLOW_BG))
        # Bold total row
        style.append(("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold"))
        style.append(("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 1.5, colors.black))
        table.setStyle(TableStyle(style))
        elements.append(table)

        # Floorplan reconciliation box for new
        elements.append(Spacer(1, 0.2 * inch))
        new_recons = [r for r in data["floorplan_recons"] if "237" in str(r.reconciliation_type.value)]
        if new_recons:
            r = new_recons[0]
            elements.append(Paragraph("Floorplan Reconciliation — New (Schedule 237)", self.styles["SubHeader"]))
            recon_data = [
                ["Book Balance", _fmt_currency(r.book_balance)],
                ["Floorplan Balance", _fmt_currency(r.floorplan_balance)],
                ["Variance", _fmt_currency(r.variance)],
            ]
            recon_table = Table(recon_data, colWidths=[avail_width * 0.4, avail_width * 0.3])
            recon_style = [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
            if r.variance and abs(r.variance) > 0:
                bg = RED_BG if abs(r.variance) > 1000 else YELLOW_BG
                recon_style.append(("BACKGROUND", (1, 2), (1, 2), bg))
            recon_table.setStyle(TableStyle(recon_style))
            elements.append(recon_table)

        return elements

    def _build_used_vehicle_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 3: Used Vehicle Inventory", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        vehicles = data["used_vehicles"]
        if not vehicles:
            elements.append(Paragraph("No used vehicle inventory data.", self.styles["BodyText2"]))
            return elements

        over_60 = sum(1 for v in vehicles if v.days_in_stock > 60)
        over_90 = sum(1 for v in vehicles if v.days_in_stock > 90)
        elements.append(Paragraph(
            f"Units over 60 days: <b>{over_60}</b>  |  Units over 90 days: <b>{over_90}</b>",
            self.styles["BodyText2"],
        ))
        elements.append(Spacer(1, 0.1 * inch))

        avail_width = self.page_width - 2 * self.margin
        col_widths = [avail_width * w for w in [0.10, 0.07, 0.13, 0.22, 0.08, 0.20, 0.20]]
        header = ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Market Value"]
        rows = [header]
        total_book = Decimal(0)
        for v in vehicles:
            rows.append([
                v.stock_number,
                str(v.year),
                v.make,
                v.model,
                str(v.days_in_stock),
                _fmt_currency(v.book_value),
                _fmt_currency(v.market_value),
            ])
            total_book += v.book_value or Decimal(0)
        rows.append(["", "", "", "TOTAL", "", _fmt_currency(total_book), ""])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = self._base_table_style(len(rows))
        for i, v in enumerate(vehicles, start=1):
            if v.days_in_stock > 90:
                style.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
            elif v.days_in_stock > 60:
                style.append(("BACKGROUND", (0, i), (-1, i), YELLOW_BG))
        style.append(("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold"))
        style.append(("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 1.5, colors.black))
        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements

    def _build_service_loaner_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 4: Service Loaners", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        loaners = data["service_loaners"]
        if not loaners:
            elements.append(Paragraph("No service loaner data.", self.styles["BodyText2"]))
            return elements

        total_neg = sum(v.negative_equity or Decimal(0) for v in loaners)
        elements.append(Paragraph(
            f"Total Negative Equity: <b>{_fmt_currency(total_neg)}</b>",
            self.styles["BodyText2"],
        ))
        elements.append(Spacer(1, 0.1 * inch))

        avail_width = self.page_width - 2 * self.margin
        col_widths = [avail_width * w for w in [0.10, 0.06, 0.12, 0.18, 0.10, 0.16, 0.14, 0.14]]
        header = ["Stock #", "Year", "Make", "Model", "Days", "Book Val", "Curr Val", "Neg Equity"]
        rows = [header]
        for v in loaners:
            rows.append([
                v.stock_number,
                str(v.year),
                v.make,
                v.model,
                str(v.days_in_service),
                _fmt_currency(v.book_value),
                _fmt_currency(v.current_value),
                _fmt_currency(v.negative_equity),
            ])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = self._base_table_style(len(rows))
        for i, v in enumerate(loaners, start=1):
            neg = v.negative_equity or Decimal(0)
            days = v.days_in_service
            if days > 90 or neg > 50000:
                style.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
            elif days > 60 or neg > 30000:
                style.append(("BACKGROUND", (0, i), (-1, i), YELLOW_BG))
        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements

    def _build_parts_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 5: Parts", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        avail_width = self.page_width - 2 * self.margin

        # Parts inventory summary
        if data["parts_inventory"]:
            elements.append(Paragraph("Parts Inventory Summary", self.styles["SubHeader"]))
            inv_rows = [["Category", "GL Account", "Total Value"]]
            for p in data["parts_inventory"]:
                inv_rows.append([p.category.value, p.gl_account, _fmt_currency(p.total_value)])
            inv_table = Table(inv_rows, colWidths=[avail_width * 0.4, avail_width * 0.2, avail_width * 0.4])
            inv_table.setStyle(TableStyle(self._base_table_style(len(inv_rows))))
            elements.append(inv_table)
            elements.append(Spacer(1, 0.15 * inch))

        # Monthly analysis
        if data["parts_analyses"]:
            elements.append(Paragraph("Monthly Analysis", self.styles["SubHeader"]))
            analysis_rows = [["Period", "Turnover", "Obsolete Value", "Stock Order %"]]
            for p in sorted(data["parts_analyses"], key=lambda x: (x.period_year, x.period_month)):
                turnover_str = f"{p.true_turnover:.1f}" if p.true_turnover is not None else "—"
                analysis_rows.append([
                    f"{p.period_month}/{p.period_year}",
                    turnover_str,
                    _fmt_currency(p.obsolete_value),
                    f"{p.stock_order_performance}%" if p.stock_order_performance is not None else "—",
                ])

            analysis_table = Table(analysis_rows, colWidths=[avail_width * 0.25] * 4)
            a_style = self._base_table_style(len(analysis_rows))
            # Color-code turnover
            for i, p in enumerate(sorted(data["parts_analyses"], key=lambda x: (x.period_year, x.period_month)), start=1):
                if p.true_turnover is not None:
                    if p.true_turnover < 1.0:
                        a_style.append(("BACKGROUND", (1, i), (1, i), RED_BG))
                    elif p.true_turnover < 2.0:
                        a_style.append(("BACKGROUND", (1, i), (1, i), YELLOW_BG))
            analysis_table.setStyle(TableStyle(a_style))
            elements.append(analysis_table)

        if not data["parts_inventory"] and not data["parts_analyses"]:
            elements.append(Paragraph("No parts data.", self.styles["BodyText2"]))

        return elements

    def _build_receivables_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 6: Receivables", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        receivables = data["receivables"]
        if not receivables:
            elements.append(Paragraph("No receivables data.", self.styles["BodyText2"]))
            return elements

        avail_width = self.page_width - 2 * self.margin
        col_widths = [avail_width * w for w in [0.25, 0.15, 0.15, 0.15, 0.15, 0.15]]
        header = ["Type", "Current", "30+", "60+", "90+", "Total"]
        rows = [header]
        for r in receivables:
            rows.append([
                r.receivable_type.value.replace("_", " ").title(),
                _fmt_currency(r.current_balance),
                _fmt_currency(r.over_30),
                _fmt_currency(r.over_60),
                _fmt_currency(r.over_90),
                _fmt_currency(r.total_balance),
            ])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = self._base_table_style(len(rows))
        # Color-code any non-zero aging over 30
        for i, r in enumerate(receivables, start=1):
            for col_idx, val in [(2, r.over_30), (3, r.over_60), (4, r.over_90)]:
                if val and val > 0:
                    style.append(("BACKGROUND", (col_idx, i), (col_idx, i), YELLOW_BG))
        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements

    def _build_fi_chargeback_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 7: F&I Chargebacks", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        chargebacks = data["fi_chargebacks"]
        if not chargebacks:
            elements.append(Paragraph("No F&I chargeback data.", self.styles["BodyText2"]))
            return elements

        avail_width = self.page_width - 2 * self.margin
        col_widths = [avail_width * w for w in [0.15, 0.35, 0.25, 0.25]]
        header = ["Account", "Description", "Current", "Over 90"]
        rows = [header]
        for c in chargebacks:
            rows.append([
                c.account_number,
                c.account_description or "",
                _fmt_currency(c.current_balance),
                _fmt_currency(c.over_90_balance),
            ])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = self._base_table_style(len(rows))
        for i, c in enumerate(chargebacks, start=1):
            if c.over_90_balance and c.over_90_balance > 0:
                style.append(("BACKGROUND", (3, i), (3, i), RED_BG))
        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements

    def _build_contracts_in_transit_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 8: Contracts in Transit", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        contracts = data["contracts"]
        if not contracts:
            elements.append(Paragraph("No contracts in transit.", self.styles["BodyText2"]))
            return elements

        avail_width = self.page_width - 2 * self.margin
        col_widths = [avail_width * w for w in [0.12, 0.22, 0.15, 0.08, 0.18, 0.25]]
        header = ["Deal #", "Customer", "Sale Date", "Days", "Amount", "Lender"]
        rows = [header]
        for c in contracts:
            rows.append([
                c.deal_number,
                c.customer_name or "",
                _fmt_date(c.sale_date),
                str(c.days_in_transit),
                _fmt_currency(c.amount),
                c.lender or "",
            ])

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = self._base_table_style(len(rows))
        for i, c in enumerate(contracts, start=1):
            if c.days_in_transit > 14:
                style.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
            elif c.days_in_transit > 7:
                style.append(("BACKGROUND", (0, i), (-1, i), YELLOW_BG))
        table.setStyle(TableStyle(style))
        elements.append(table)

        return elements

    def _build_operations_section(self, data: dict) -> list:
        elements = []
        elements.append(Paragraph("Section 9: Operations", self.styles["SectionHeader"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
        elements.append(Spacer(1, 0.15 * inch))

        avail_width = self.page_width - 2 * self.margin

        # Open ROs
        elements.append(Paragraph("Open Repair Orders", self.styles["SubHeader"]))
        ros = data["open_ros"]
        if ros:
            col_widths = [avail_width * w for w in [0.12, 0.14, 0.08, 0.26, 0.15, 0.25]]
            header = ["RO #", "Date", "Days", "Customer", "Type", "Amount"]
            rows = [header]
            for r in ros:
                rows.append([
                    r.ro_number,
                    _fmt_date(r.open_date),
                    str(r.days_open),
                    r.customer_name or "",
                    r.service_type or "",
                    _fmt_currency(r.amount),
                ])

            table = Table(rows, colWidths=col_widths, repeatRows=1)
            style = self._base_table_style(len(rows))
            for i, r in enumerate(ros, start=1):
                if r.days_open > 30:
                    style.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
                elif r.days_open > 14:
                    style.append(("BACKGROUND", (0, i), (-1, i), YELLOW_BG))
            table.setStyle(TableStyle(style))
            elements.append(table)
        else:
            elements.append(Paragraph("No open repair orders.", self.styles["BodyText2"]))

        elements.append(Spacer(1, 0.2 * inch))

        # Missing titles
        elements.append(Paragraph("Missing Titles", self.styles["SubHeader"]))
        titles = data["missing_titles"]
        if titles:
            col_widths = [avail_width * w for w in [0.2, 0.2, 0.4, 0.2]]
            header = ["Stock #", "Deal #", "Customer", "Days Missing"]
            rows = [header]
            for t in titles:
                rows.append([
                    t.stock_number,
                    t.deal_number or "",
                    t.customer_name or "",
                    str(t.days_missing),
                ])

            table = Table(rows, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle(self._base_table_style(len(rows))))
            elements.append(table)
        else:
            elements.append(Paragraph("No missing titles.", self.styles["BodyText2"]))

        elements.append(Spacer(1, 0.2 * inch))

        # Slow to accounting
        elements.append(Paragraph("Slow to Accounting", self.styles["SubHeader"]))
        slow = data["slow_deals"]
        if slow:
            col_widths = [avail_width * w for w in [0.15, 0.15, 0.10, 0.30, 0.30]]
            header = ["Deal #", "Sale Date", "Days", "Customer", "Salesperson"]
            rows = [header]
            for s in slow:
                rows.append([
                    s.deal_number,
                    _fmt_date(s.sale_date),
                    str(s.days_to_accounting),
                    s.customer_name or "",
                    s.salesperson or "",
                ])

            table = Table(rows, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle(self._base_table_style(len(rows))))
            elements.append(table)
        else:
            elements.append(Paragraph("No slow-to-accounting deals.", self.styles["BodyText2"]))

        return elements

    # ── Shared Helpers ────────────────────────────────────────

    @staticmethod
    def _base_table_style(row_count: int) -> list:
        """Return base table style commands as a list (not TableStyle yet)."""
        return [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ]
