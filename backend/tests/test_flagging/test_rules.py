"""Tests for flagging rule definitions."""

from app.flagging.rules import DEFAULT_RULES, FlagRule
from app.models.flag import FlagCategory


# Models that the flagging engine knows about
VALID_MODELS = {
    "NewVehicleInventory",
    "UsedVehicleInventory",
    "ServiceLoaner",
    "FloorplanReconciliation",
    "PartsAnalysis",
    "Receivable",
    "FIChargeback",
    "ContractInTransit",
    "MissingTitle",
    "OpenRepairOrder",
    "SlowToAccounting",
}


def test_default_rules_count():
    """There should be exactly 15 rules."""
    assert len(DEFAULT_RULES) == 15


def test_all_rules_are_flag_rule_instances():
    for rule in DEFAULT_RULES:
        assert isinstance(rule, FlagRule)


def test_all_categories_represented():
    """Every FlagCategory value should appear in at least one rule."""
    categories_used = {rule.category for rule in DEFAULT_RULES}
    for cat in FlagCategory:
        assert cat in categories_used, f"Category {cat} has no rules"


def test_all_model_names_valid():
    """Every rule must reference a model in the engine's MODEL_MAP."""
    for rule in DEFAULT_RULES:
        assert rule.model in VALID_MODELS, (
            f"Rule '{rule.name}' references unknown model '{rule.model}'"
        )


def test_lt_comparison_thresholds():
    """For 'lt' comparisons, yellow_threshold must be > red_threshold.

    Lower values are worse, so yellow triggers at a higher value (e.g. <2.0)
    and red triggers at a lower value (e.g. <1.0).
    """
    lt_rules = [r for r in DEFAULT_RULES if r.comparison == "lt"]
    assert len(lt_rules) > 0, "Expected at least one 'lt' rule"
    for rule in lt_rules:
        assert rule.yellow_threshold is not None and rule.red_threshold is not None, (
            f"Rule '{rule.name}' with 'lt' comparison must have both thresholds"
        )
        assert rule.yellow_threshold > rule.red_threshold, (
            f"Rule '{rule.name}': yellow ({rule.yellow_threshold}) must be > red ({rule.red_threshold}) for 'lt'"
        )


def test_all_rules_have_at_least_one_threshold():
    """Every rule must define at least a yellow or red threshold."""
    for rule in DEFAULT_RULES:
        assert rule.yellow_threshold is not None or rule.red_threshold is not None, (
            f"Rule '{rule.name}' has no thresholds defined"
        )


def test_valid_comparison_types():
    valid = {"gt", "lt", "gte", "lte", "any_gt", "abs_gt"}
    for rule in DEFAULT_RULES:
        assert rule.comparison in valid, (
            f"Rule '{rule.name}' has invalid comparison '{rule.comparison}'"
        )


def test_all_rules_enabled_by_default():
    for rule in DEFAULT_RULES:
        assert rule.enabled is True


def test_unique_rule_names():
    names = [rule.name for rule in DEFAULT_RULES]
    assert len(names) == len(set(names)), "Duplicate rule names found"
