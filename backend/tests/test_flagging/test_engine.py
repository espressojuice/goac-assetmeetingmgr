"""Tests for the flagging engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import pytest

from app.flagging.engine import FlaggingEngine
from app.flagging.rules import FlagRule
from app.models.flag import FlagCategory, FlagSeverity


# ── Helpers ────────────────────────────────────────────────────


@dataclass
class MockRecord:
    """Minimal mock for testing — dynamically assigned fields."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_rule(
    field: str = "value",
    yellow: Optional[int | Decimal] = None,
    red: Optional[int | Decimal] = None,
    comparison: str = "gt",
    template: str = "{value}",
) -> FlagRule:
    return FlagRule(
        category=FlagCategory.INVENTORY,
        name="Test Rule",
        model="TestModel",
        field=field,
        yellow_threshold=yellow,
        red_threshold=red,
        comparison=comparison,
        message_template=template,
    )


# ── _compare tests ────────────────────────────────────────────


class TestCompare:
    _compare = staticmethod(FlaggingEngine._compare)

    def test_gt_above(self):
        assert self._compare(91, 90, "gt") is True

    def test_gt_equal(self):
        assert self._compare(90, 90, "gt") is False

    def test_gt_below(self):
        assert self._compare(89, 90, "gt") is False

    def test_lt_below(self):
        assert self._compare(1.5, 2.0, "lt") is True

    def test_lt_above(self):
        assert self._compare(2.5, 2.0, "lt") is False

    def test_lt_equal(self):
        assert self._compare(2.0, 2.0, "lt") is False

    def test_gte_equal(self):
        assert self._compare(0, 0, "gte") is True

    def test_gte_above(self):
        assert self._compare(1, 0, "gte") is True

    def test_gte_below(self):
        assert self._compare(-1, 0, "gte") is False

    def test_any_gt_positive(self):
        assert self._compare(0.01, 0, "any_gt") is True

    def test_any_gt_zero(self):
        assert self._compare(0, 0, "any_gt") is False

    def test_any_gt_negative(self):
        assert self._compare(-1, 0, "any_gt") is False

    def test_abs_gt_negative_exceeds(self):
        assert self._compare(-150, 100, "abs_gt") is True

    def test_abs_gt_positive_exceeds(self):
        assert self._compare(150, 100, "abs_gt") is True

    def test_abs_gt_within(self):
        assert self._compare(50, 100, "abs_gt") is False

    def test_abs_gt_equal(self):
        assert self._compare(100, 100, "abs_gt") is False

    def test_lte(self):
        assert self._compare(5, 5, "lte") is True
        assert self._compare(4, 5, "lte") is True
        assert self._compare(6, 5, "lte") is False

    def test_unknown_returns_false(self):
        assert self._compare(1, 1, "unknown") is False


# ── _evaluate_record tests ────────────────────────────────────


class TestEvaluateRecord:
    engine = FlaggingEngine()

    def test_used_vehicle_95_days_is_red(self):
        record = MockRecord(days_in_stock=95)
        rule = make_rule(field="days_in_stock", yellow=60, red=90, comparison="gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

    def test_used_vehicle_65_days_is_yellow(self):
        record = MockRecord(days_in_stock=65)
        rule = make_rule(field="days_in_stock", yellow=60, red=90, comparison="gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

    def test_used_vehicle_55_days_is_none(self):
        record = MockRecord(days_in_stock=55)
        rule = make_rule(field="days_in_stock", yellow=60, red=90, comparison="gt")
        assert self.engine._evaluate_record(record, rule) is None

    def test_red_takes_priority_over_yellow(self):
        """A 95-day vehicle should be red, not yellow (red checked first)."""
        record = MockRecord(days_in_stock=95)
        rule = make_rule(field="days_in_stock", yellow=60, red=90, comparison="gt")
        result = self.engine._evaluate_record(record, rule)
        assert result == FlagSeverity.RED

    def test_service_loaner_neg_equity_45k_is_yellow(self):
        record = MockRecord(negative_equity=45000)
        rule = make_rule(field="negative_equity", yellow=30000, red=50000, comparison="gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

    def test_service_loaner_neg_equity_55k_is_red(self):
        record = MockRecord(negative_equity=55000)
        rule = make_rule(field="negative_equity", yellow=30000, red=50000, comparison="gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

    def test_parts_turnover_01_is_red(self):
        """Turnover of 0.1 < 1.0 → red."""
        record = MockRecord(true_turnover=Decimal("0.1"))
        rule = make_rule(
            field="true_turnover",
            yellow=Decimal("2.0"),
            red=Decimal("1.0"),
            comparison="lt",
        )
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

    def test_parts_turnover_15_is_yellow(self):
        """Turnover of 1.5 < 2.0 but > 1.0 → yellow."""
        record = MockRecord(true_turnover=Decimal("1.5"))
        rule = make_rule(
            field="true_turnover",
            yellow=Decimal("2.0"),
            red=Decimal("1.0"),
            comparison="lt",
        )
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

    def test_parts_turnover_25_is_none(self):
        """Turnover of 2.5 ≥ 2.0 → no flag."""
        record = MockRecord(true_turnover=Decimal("2.5"))
        rule = make_rule(
            field="true_turnover",
            yellow=Decimal("2.0"),
            red=Decimal("1.0"),
            comparison="lt",
        )
        assert self.engine._evaluate_record(record, rule) is None

    def test_floorplan_variance_neg500_is_yellow(self):
        record = MockRecord(variance=Decimal("-500"))
        rule = make_rule(field="variance", yellow=100, red=1000, comparison="abs_gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

    def test_floorplan_variance_1500_is_red(self):
        record = MockRecord(variance=Decimal("1500"))
        rule = make_rule(field="variance", yellow=100, red=1000, comparison="abs_gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

    def test_floorplan_variance_50_is_none(self):
        record = MockRecord(variance=Decimal("50"))
        rule = make_rule(field="variance", yellow=100, red=1000, comparison="abs_gt")
        assert self.engine._evaluate_record(record, rule) is None

    def test_none_field_returns_none(self):
        record = MockRecord(days_in_stock=None)
        rule = make_rule(field="days_in_stock", yellow=60, red=90, comparison="gt")
        assert self.engine._evaluate_record(record, rule) is None

    def test_missing_field_returns_none(self):
        record = MockRecord()
        rule = make_rule(field="nonexistent", yellow=60, red=90, comparison="gt")
        assert self.engine._evaluate_record(record, rule) is None

    def test_yellow_only_rule(self):
        """Rule with only yellow threshold (no red)."""
        record = MockRecord(over_30=Decimal("500"))
        rule = make_rule(field="over_30", yellow=0, red=None, comparison="any_gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

    def test_red_only_rule(self):
        """Rule with only red threshold (no yellow)."""
        record = MockRecord(over_60=Decimal("500"))
        rule = make_rule(field="over_60", yellow=None, red=0, comparison="any_gt")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

    def test_gte_zero_flags_immediately(self):
        """Missing title with 0 days should still flag as yellow (gte 0)."""
        record = MockRecord(days_missing=0)
        rule = make_rule(field="days_missing", yellow=0, red=14, comparison="gte")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

    def test_gte_14_days_is_red(self):
        record = MockRecord(days_missing=14)
        rule = make_rule(field="days_missing", yellow=0, red=14, comparison="gte")
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED


# ── _create_flag tests ────────────────────────────────────────


class TestCreateFlag:
    engine = FlaggingEngine()

    def test_creates_flag_with_correct_fields(self):
        import uuid

        record = MockRecord(
            days_in_stock=95,
            year=2024,
            make="Chevrolet",
            model="Silverado",
            stock_number="U1234",
        )
        rule = FlagRule(
            category=FlagCategory.INVENTORY,
            name="Used Vehicle Age",
            model="UsedVehicleInventory",
            field="days_in_stock",
            yellow_threshold=60,
            red_threshold=90,
            comparison="gt",
            message_template="Used: {year} {make} {model} (Stk#{stock_number}) — {days_in_stock} days in stock",
        )
        store_id = uuid.uuid4()
        meeting_id = uuid.uuid4()

        flag = self.engine._create_flag(record, rule, FlagSeverity.RED, store_id, meeting_id)

        assert flag.category == FlagCategory.INVENTORY
        assert flag.severity == FlagSeverity.RED
        assert flag.field_name == "days_in_stock"
        assert flag.field_value == "95"
        assert flag.threshold == "90"
        assert flag.store_id == store_id
        assert flag.meeting_id == meeting_id
        assert "Chevrolet" in flag.message
        assert "Silverado" in flag.message
        assert "U1234" in flag.message
        assert "95 days" in flag.message

    def test_yellow_flag_uses_yellow_threshold(self):
        import uuid

        record = MockRecord(days_in_stock=65)
        rule = make_rule(field="days_in_stock", yellow=60, red=90, comparison="gt")

        flag = self.engine._create_flag(
            record, rule, FlagSeverity.YELLOW, uuid.uuid4(), uuid.uuid4()
        )
        assert flag.threshold == "60"

    def test_message_fallback_on_bad_template(self):
        import uuid

        record = MockRecord(days_in_stock=95)
        rule = FlagRule(
            category=FlagCategory.INVENTORY,
            name="Bad Template",
            model="Test",
            field="days_in_stock",
            yellow_threshold=60,
            red_threshold=90,
            comparison="gt",
            message_template="{nonexistent_field} broke",
        )

        flag = self.engine._create_flag(
            record, rule, FlagSeverity.RED, uuid.uuid4(), uuid.uuid4()
        )
        assert "Bad Template" in flag.message
        assert "95" in flag.message
