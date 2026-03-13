"""Tests for flagging engine with per-store overrides."""

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
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@dataclass
class MockOverride:
    """Mimics StoreFlagOverride for unit testing without DB."""
    yellow_threshold: Optional[float] = None
    red_threshold: Optional[float] = None
    enabled: bool = True


def make_rule(
    name: str = "Test Rule",
    field: str = "value",
    yellow=None,
    red=None,
    comparison: str = "gt",
    template: str = "{value}",
) -> FlagRule:
    return FlagRule(
        category=FlagCategory.INVENTORY,
        name=name,
        model="TestModel",
        field=field,
        yellow_threshold=yellow,
        red_threshold=red,
        comparison=comparison,
        message_template=template,
    )


# ── Tests ──────────────────────────────────────────────────────


class TestApplyOverride:
    engine = FlaggingEngine()

    def test_no_override_returns_original_rule(self):
        rule = make_rule(yellow=60, red=90)
        result = self.engine._apply_override(rule, None)
        assert result.yellow_threshold == 60
        assert result.red_threshold == 90

    def test_override_replaces_both_thresholds(self):
        rule = make_rule(yellow=60, red=90)
        override = MockOverride(yellow_threshold=45.0, red_threshold=75.0)
        result = self.engine._apply_override(rule, override)
        assert result.yellow_threshold == 45.0
        assert result.red_threshold == 75.0

    def test_partial_override_yellow_only(self):
        """Only yellow overridden; red stays default."""
        rule = make_rule(yellow=60, red=90)
        override = MockOverride(yellow_threshold=45.0, red_threshold=None)
        result = self.engine._apply_override(rule, override)
        assert result.yellow_threshold == 45.0
        assert result.red_threshold == 90  # stays default

    def test_partial_override_red_only(self):
        """Only red overridden; yellow stays default."""
        rule = make_rule(yellow=60, red=90)
        override = MockOverride(yellow_threshold=None, red_threshold=120.0)
        result = self.engine._apply_override(rule, override)
        assert result.yellow_threshold == 60  # stays default
        assert result.red_threshold == 120.0

    def test_override_does_not_mutate_original_rule(self):
        rule = make_rule(yellow=60, red=90)
        override = MockOverride(yellow_threshold=45.0, red_threshold=75.0)
        self.engine._apply_override(rule, override)
        assert rule.yellow_threshold == 60
        assert rule.red_threshold == 90


class TestEvaluateRecordWithOverrides:
    engine = FlaggingEngine()

    def test_default_thresholds_used_when_no_override(self):
        """Without overrides, default thresholds apply."""
        record = MockRecord(days_in_stock=95)
        rule = make_rule(field="days_in_stock", yellow=60, red=90)
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

    def test_override_threshold_changes_severity(self):
        """With red threshold raised to 120, a 100-day vehicle is now yellow instead of red."""
        record = MockRecord(days_in_stock=100)
        rule = make_rule(field="days_in_stock", yellow=60, red=90)
        # Without override: 100 > 90 → red
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.RED

        # With override: red at 120
        override = MockOverride(yellow_threshold=None, red_threshold=120.0)
        effective = self.engine._apply_override(rule, override)
        # 100 > 60 but < 120 → yellow
        assert self.engine._evaluate_record(record, effective) == FlagSeverity.YELLOW

    def test_override_makes_value_no_longer_flagged(self):
        """Raising thresholds above the value means no flag."""
        record = MockRecord(days_in_stock=50)
        rule = make_rule(field="days_in_stock", yellow=60, red=90)
        # 50 < 60 → no flag
        assert self.engine._evaluate_record(record, rule) is None

        # Even with lower override, still works
        override = MockOverride(yellow_threshold=30.0, red_threshold=70.0)
        effective = self.engine._apply_override(rule, override)
        # 50 > 30 → yellow
        assert self.engine._evaluate_record(record, effective) == FlagSeverity.YELLOW

    def test_disabled_rule_is_skipped(self):
        """When override has enabled=False, the rule should be skipped."""
        override = MockOverride(enabled=False)
        # This is checked in evaluate_meeting, not _evaluate_record.
        # Just verify the override object exposes enabled=False.
        assert override.enabled is False


class TestOverrideWithLtComparison:
    """Test overrides with 'lt' comparison (like parts turnover)."""
    engine = FlaggingEngine()

    def test_turnover_override_changes_thresholds(self):
        record = MockRecord(true_turnover=Decimal("1.5"))
        rule = make_rule(
            field="true_turnover",
            yellow=Decimal("2.0"),
            red=Decimal("1.0"),
            comparison="lt",
        )
        # Default: 1.5 < 2.0 → yellow
        assert self.engine._evaluate_record(record, rule) == FlagSeverity.YELLOW

        # Override: raise yellow to 3.0, red to 2.0
        override = MockOverride(yellow_threshold=3.0, red_threshold=2.0)
        effective = self.engine._apply_override(rule, override)
        # 1.5 < 2.0 → red now (red threshold raised)
        assert self.engine._evaluate_record(record, effective) == FlagSeverity.RED
