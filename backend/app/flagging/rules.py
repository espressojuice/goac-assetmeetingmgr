"""Data-driven flag rule definitions for the asset meeting flagging engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Union

from app.models.flag import FlagCategory


@dataclass
class FlagRule:
    category: FlagCategory
    name: str
    model: str
    field: str
    yellow_threshold: Optional[Union[Decimal, int]]
    red_threshold: Optional[Union[Decimal, int]]
    comparison: str  # "gt", "lt", "gte", "lte", "any_gt", "abs_gt"
    message_template: str
    enabled: bool = True


DEFAULT_RULES: list[FlagRule] = [
    # ── Inventory ──────────────────────────────────────────────
    FlagRule(
        category=FlagCategory.INVENTORY,
        name="Used Vehicle Age",
        model="UsedVehicleInventory",
        field="days_in_stock",
        yellow_threshold=60,
        red_threshold=90,
        comparison="gt",
        message_template="Used: {year} {make} {model} (Stk#{stock_number}) — {days_in_stock} days in stock",
    ),
    FlagRule(
        category=FlagCategory.INVENTORY,
        name="New Vehicle Age",
        model="NewVehicleInventory",
        field="days_in_stock",
        yellow_threshold=90,
        red_threshold=120,
        comparison="gt",
        message_template="New: {year} {make} {model} (Stk#{stock_number}) — {days_in_stock} days in stock",
    ),
    FlagRule(
        category=FlagCategory.INVENTORY,
        name="Service Loaner Days",
        model="ServiceLoaner",
        field="days_in_service",
        yellow_threshold=60,
        red_threshold=90,
        comparison="gt",
        message_template="Loaner: {year} {make} {model} (Stk#{stock_number}) — {days_in_service} days in service",
    ),
    FlagRule(
        category=FlagCategory.INVENTORY,
        name="Service Loaner Neg Equity",
        model="ServiceLoaner",
        field="negative_equity",
        yellow_threshold=30000,
        red_threshold=50000,
        comparison="gt",
        message_template="Loaner: {year} {make} {model} (Stk#{stock_number}) — ${negative_equity:,.0f} negative equity",
    ),
    FlagRule(
        category=FlagCategory.INVENTORY,
        name="Floorplan Variance",
        model="FloorplanReconciliation",
        field="variance",
        yellow_threshold=100,
        red_threshold=1000,
        comparison="abs_gt",
        message_template="Floorplan variance ({reconciliation_type}): ${variance:,.2f}",
    ),
    # ── Financial ──────────────────────────────────────────────
    FlagRule(
        category=FlagCategory.FINANCIAL,
        name="Receivable Over 30",
        model="Receivable",
        field="over_30",
        yellow_threshold=0,
        red_threshold=None,
        comparison="any_gt",
        message_template="Receivable ({receivable_type}): ${over_30:,.2f} over 30 days",
    ),
    FlagRule(
        category=FlagCategory.FINANCIAL,
        name="Receivable Over 60",
        model="Receivable",
        field="over_60",
        yellow_threshold=None,
        red_threshold=0,
        comparison="any_gt",
        message_template="Receivable ({receivable_type}): ${over_60:,.2f} over 60 days",
    ),
    FlagRule(
        category=FlagCategory.FINANCIAL,
        name="F&I Chargeback Current",
        model="FIChargeback",
        field="current_balance",
        yellow_threshold=0,
        red_threshold=None,
        comparison="any_gt",
        message_template="F&I chargeback: ${current_balance:,.2f} current activity",
    ),
    FlagRule(
        category=FlagCategory.FINANCIAL,
        name="F&I Chargeback Over 90",
        model="FIChargeback",
        field="over_90_balance",
        yellow_threshold=None,
        red_threshold=0,
        comparison="any_gt",
        message_template="F&I chargeback: ${over_90_balance:,.2f} over 90 days",
    ),
    FlagRule(
        category=FlagCategory.FINANCIAL,
        name="Contract In Transit Age",
        model="ContractInTransit",
        field="days_in_transit",
        yellow_threshold=7,
        red_threshold=14,
        comparison="gt",
        message_template="CIT: {customer_name} — {days_in_transit} days in transit (${amount:,.2f}, {lender})",
    ),
    # ── Operations ─────────────────────────────────────────────
    FlagRule(
        category=FlagCategory.OPERATIONS,
        name="Missing Title",
        model="MissingTitle",
        field="days_missing",
        yellow_threshold=0,
        red_threshold=14,
        comparison="gte",
        message_template="Missing title: Stk#{stock_number} ({customer_name}) — {days_missing} days missing",
    ),
    FlagRule(
        category=FlagCategory.OPERATIONS,
        name="Open RO Age",
        model="OpenRepairOrder",
        field="days_open",
        yellow_threshold=14,
        red_threshold=30,
        comparison="gt",
        message_template="Open RO#{ro_number}: {customer_name} — {days_open} days open (${amount:,.2f})",
    ),
    FlagRule(
        category=FlagCategory.OPERATIONS,
        name="Slow To Accounting",
        model="SlowToAccounting",
        field="days_to_accounting",
        yellow_threshold=5,
        red_threshold=10,
        comparison="gt",
        message_template="Slow to accounting: Deal#{deal_number} ({customer_name}) — {days_to_accounting} days",
    ),
    # ── Parts ──────────────────────────────────────────────────
    FlagRule(
        category=FlagCategory.PARTS,
        name="Parts True Turnover",
        model="PartsAnalysis",
        field="true_turnover",
        yellow_threshold=Decimal("2.0"),
        red_threshold=Decimal("1.0"),
        comparison="lt",
        message_template="Parts turnover: {true_turnover:.1f}x (target: ≥2.0x)",
    ),
    FlagRule(
        category=FlagCategory.PARTS,
        name="Parts Obsolete Value",
        model="PartsAnalysis",
        field="obsolete_value",
        yellow_threshold=500,
        red_threshold=2000,
        comparison="gt",
        message_template="Parts obsolete inventory: ${obsolete_value:,.2f}",
    ),
]
