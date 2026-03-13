"""Flagging engine — evaluates parsed meeting data against rules to generate Flag records."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import Flag, FlagCategory, FlagSeverity
from app.models.inventory import (
    FloorplanReconciliation,
    NewVehicleInventory,
    ServiceLoaner,
    UsedVehicleInventory,
)
from app.models.parts import PartsAnalysis
from app.models.financial import (
    ContractInTransit,
    FIChargeback,
    Receivable,
)
from app.models.operations import (
    MissingTitle,
    OpenRepairOrder,
    SlowToAccounting,
)
from app.flagging.rules import DEFAULT_RULES, FlagRule

logger = logging.getLogger(__name__)

# Maps rule model names to SQLAlchemy model classes
_MODEL_MAP = {
    "NewVehicleInventory": NewVehicleInventory,
    "UsedVehicleInventory": UsedVehicleInventory,
    "ServiceLoaner": ServiceLoaner,
    "FloorplanReconciliation": FloorplanReconciliation,
    "PartsAnalysis": PartsAnalysis,
    "Receivable": Receivable,
    "FIChargeback": FIChargeback,
    "ContractInTransit": ContractInTransit,
    "MissingTitle": MissingTitle,
    "OpenRepairOrder": OpenRepairOrder,
    "SlowToAccounting": SlowToAccounting,
}


class FlaggingEngine:
    """Evaluates parsed meeting data against flag rules."""

    def __init__(self, rules: Optional[list[FlagRule]] = None):
        self.rules = rules or DEFAULT_RULES

    async def evaluate_meeting(
        self,
        meeting_id: str,
        store_id: str,
        db: AsyncSession,
        store_overrides: Optional[dict] = None,
    ) -> list[Flag]:
        """
        Run all enabled rules against parsed data for a meeting.

        Args:
            store_overrides: dict keyed by rule_name → StoreFlagOverride.
                If an override exists and enabled=False, the rule is skipped.
                If an override has non-null threshold values, they replace defaults.
        Returns list of Flag model instances (not yet committed).
        """
        meeting_uuid = uuid.UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        store_uuid = uuid.UUID(store_id) if isinstance(store_id, str) else store_id
        overrides = store_overrides or {}

        flags: list[Flag] = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            override = overrides.get(rule.name)

            # If override exists and is disabled, skip the rule
            if override and not override.enabled:
                logger.info(f"Rule '{rule.name}' disabled by store override")
                continue

            # Build effective rule with override thresholds
            effective_rule = self._apply_override(rule, override)

            records = await self._get_records(rule.model, meeting_uuid, db)

            for record in records:
                severity = self._evaluate_record(record, effective_rule)
                if severity:
                    flag = self._create_flag(record, effective_rule, severity, store_uuid, meeting_uuid)
                    flags.append(flag)

        logger.info(
            f"Meeting {meeting_id}: generated {len(flags)} flags "
            f"({sum(1 for f in flags if f.severity == FlagSeverity.RED)} red, "
            f"{sum(1 for f in flags if f.severity == FlagSeverity.YELLOW)} yellow)"
        )
        return flags

    @staticmethod
    def _apply_override(rule: FlagRule, override) -> FlagRule:
        """Return a new FlagRule with override thresholds applied (if any)."""
        if not override:
            return rule
        from dataclasses import replace
        yellow = override.yellow_threshold if override.yellow_threshold is not None else rule.yellow_threshold
        red = override.red_threshold if override.red_threshold is not None else rule.red_threshold
        return replace(rule, yellow_threshold=yellow, red_threshold=red)

    def _evaluate_record(self, record: object, rule: FlagRule) -> Optional[FlagSeverity]:
        """
        Evaluate a single record against a rule.
        Check red first — if it meets red threshold, flag as red (don't double-flag).
        """
        value = getattr(record, rule.field, None)
        if value is None:
            return None

        # Check red threshold first (if defined)
        if rule.red_threshold is not None and self._compare(value, rule.red_threshold, rule.comparison):
            return FlagSeverity.RED

        # Then check yellow (if defined)
        if rule.yellow_threshold is not None and self._compare(value, rule.yellow_threshold, rule.comparison):
            return FlagSeverity.YELLOW

        return None

    @staticmethod
    def _compare(value, threshold, comparison: str) -> bool:
        """Perform the comparison based on the comparison type."""
        if comparison == "gt":
            return value > threshold
        elif comparison == "lt":
            return value < threshold
        elif comparison == "gte":
            return value >= threshold
        elif comparison == "lte":
            return value <= threshold
        elif comparison == "any_gt":
            return value > 0
        elif comparison == "abs_gt":
            return abs(value) > threshold
        else:
            logger.warning(f"Unknown comparison type: {comparison}")
            return False

    @staticmethod
    def _create_flag(
        record: object,
        rule: FlagRule,
        severity: FlagSeverity,
        store_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> Flag:
        """Create a Flag instance with formatted message."""
        value = getattr(record, rule.field, None)

        # Build template context from record attributes
        context = {}
        for attr in dir(record):
            if not attr.startswith("_") and attr not in ("metadata", "registry"):
                try:
                    v = getattr(record, attr)
                    if not callable(v):
                        context[attr] = v
                except Exception:
                    pass

        # Format message, falling back to a simple message on error
        try:
            message = rule.message_template.format(**context)
        except (KeyError, ValueError, TypeError):
            message = f"{rule.name}: {rule.field}={value}"

        # Determine threshold string for the flag record
        threshold = rule.red_threshold if severity == FlagSeverity.RED else rule.yellow_threshold

        return Flag(
            meeting_id=meeting_id,
            store_id=store_id,
            category=rule.category,
            severity=severity,
            field_name=rule.field,
            field_value=str(value) if value is not None else None,
            threshold=str(threshold) if threshold is not None else None,
            message=message,
        )

    async def _get_records(
        self, model_name: str, meeting_id: uuid.UUID, db: AsyncSession
    ) -> list:
        """Query records for the given model and meeting."""
        model_class = _MODEL_MAP.get(model_name)
        if not model_class:
            logger.warning(f"No model mapping for rule model: {model_name}")
            return []

        result = await db.execute(
            select(model_class).where(model_class.meeting_id == meeting_id)
        )
        return list(result.scalars().all())
