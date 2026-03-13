"""Per-store flag rule override management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import FlagRuleOverrideRequest, FlagRuleResponse
from app.auth import get_current_user, require_corporate_or_gm, verify_store_access
from app.database import get_db
from app.flagging.rules import DEFAULT_RULES
from app.models.store import Store
from app.models.store_flag_override import StoreFlagOverride
from app.models.user import User

router = APIRouter()


def _validate_store_uuid(store_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid store_id format")


async def _get_store_or_404(store_uuid: uuid.UUID, db: AsyncSession) -> Store:
    result = await db.execute(select(Store).where(Store.id == store_uuid))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


def _threshold_to_float(val) -> float | None:
    if val is None:
        return None
    return float(val)


@router.get(
    "/stores/{store_id}/flag-rules",
    response_model=list[FlagRuleResponse],
)
async def get_store_flag_rules(
    store_id: str,
    current_user: User = Depends(verify_store_access),
    db: AsyncSession = Depends(get_db),
) -> list[FlagRuleResponse]:
    """Get all flag rules with effective thresholds for a store."""
    store_uuid = _validate_store_uuid(store_id)
    await _get_store_or_404(store_uuid, db)

    # Load all overrides for this store
    result = await db.execute(
        select(StoreFlagOverride).where(StoreFlagOverride.store_id == store_uuid)
    )
    overrides = {o.rule_name: o for o in result.scalars().all()}

    rules_out = []
    for rule in DEFAULT_RULES:
        override = overrides.get(rule.name)
        has_override = override is not None

        default_yellow = _threshold_to_float(rule.yellow_threshold)
        default_red = _threshold_to_float(rule.red_threshold)

        if has_override:
            eff_yellow = _threshold_to_float(override.yellow_threshold) if override.yellow_threshold is not None else default_yellow
            eff_red = _threshold_to_float(override.red_threshold) if override.red_threshold is not None else default_red
            enabled = override.enabled
        else:
            eff_yellow = default_yellow
            eff_red = default_red
            enabled = rule.enabled

        rules_out.append(FlagRuleResponse(
            rule_name=rule.name,
            category=rule.category.value,
            default_yellow=default_yellow,
            default_red=default_red,
            effective_yellow=eff_yellow,
            effective_red=eff_red,
            has_override=has_override,
            enabled=enabled,
        ))

    return rules_out


@router.put("/stores/{store_id}/flag-rules/{rule_name}")
async def upsert_store_flag_rule(
    store_id: str,
    rule_name: str,
    body: FlagRuleOverrideRequest,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a flag rule override for a store. Corporate or GM only."""
    store_uuid = _validate_store_uuid(store_id)
    await _get_store_or_404(store_uuid, db)

    # Verify store access for GM
    from app.auth import _user_has_store_access
    from app.models.user import UserRole
    if current_user.role == UserRole.GM:
        if not await _user_has_store_access(current_user.id, store_uuid, db):
            raise HTTPException(status_code=403, detail="You do not have access to this store")

    # Validate rule_name exists in DEFAULT_RULES
    valid_names = {r.name for r in DEFAULT_RULES}
    if rule_name not in valid_names:
        raise HTTPException(status_code=404, detail=f"Unknown rule: {rule_name}")

    # Upsert
    result = await db.execute(
        select(StoreFlagOverride).where(
            StoreFlagOverride.store_id == store_uuid,
            StoreFlagOverride.rule_name == rule_name,
        )
    )
    override = result.scalar_one_or_none()

    if override:
        if body.yellow_threshold is not None:
            override.yellow_threshold = body.yellow_threshold
        if body.red_threshold is not None:
            override.red_threshold = body.red_threshold
        override.enabled = body.enabled
    else:
        override = StoreFlagOverride(
            store_id=store_uuid,
            rule_name=rule_name,
            yellow_threshold=body.yellow_threshold,
            red_threshold=body.red_threshold,
            enabled=body.enabled,
        )
        db.add(override)

    await db.commit()
    await db.refresh(override)

    return {
        "id": str(override.id),
        "store_id": str(override.store_id),
        "rule_name": override.rule_name,
        "yellow_threshold": _threshold_to_float(override.yellow_threshold),
        "red_threshold": _threshold_to_float(override.red_threshold),
        "enabled": override.enabled,
    }


@router.delete("/stores/{store_id}/flag-rules/{rule_name}")
async def delete_store_flag_rule(
    store_id: str,
    rule_name: str,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
):
    """Delete a flag rule override, reverting to defaults. Corporate or GM only."""
    store_uuid = _validate_store_uuid(store_id)
    await _get_store_or_404(store_uuid, db)

    # Verify store access for GM
    from app.auth import _user_has_store_access
    from app.models.user import UserRole
    if current_user.role == UserRole.GM:
        if not await _user_has_store_access(current_user.id, store_uuid, db):
            raise HTTPException(status_code=403, detail="You do not have access to this store")

    result = await db.execute(
        select(StoreFlagOverride).where(
            StoreFlagOverride.store_id == store_uuid,
            StoreFlagOverride.rule_name == rule_name,
        )
    )
    override = result.scalar_one_or_none()

    if not override:
        raise HTTPException(status_code=404, detail=f"No override found for rule '{rule_name}'")

    await db.delete(override)
    await db.commit()

    return {"detail": f"Override for '{rule_name}' deleted, reverted to defaults"}
