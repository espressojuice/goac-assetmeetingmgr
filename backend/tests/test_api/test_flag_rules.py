"""Tests for per-store flag rule override API endpoints."""

import pytest

from tests.test_api.conftest import auth_header

STORE_ID = "11111111-1111-1111-1111-111111111111"
FAKE_STORE = "99999999-9999-9999-9999-999999999999"
RULE_NAME = "Used Vehicle Age"
RULES_URL = f"/api/v1/stores/{STORE_ID}/flag-rules"


@pytest.mark.asyncio
class TestGetStoreRules:

    async def test_returns_all_15_rules_with_defaults(self, client, sample_store, auth_headers):
        """GET returns all 15 rules with default thresholds when no overrides exist."""
        response = await client.get(RULES_URL, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 15
        # Every rule should show no override
        assert all(r["has_override"] is False for r in data)
        assert all(r["enabled"] is True for r in data)

    async def test_defaults_match_default_rules(self, client, sample_store, auth_headers):
        """Default and effective thresholds should be identical when no overrides."""
        response = await client.get(RULES_URL, headers=auth_headers)
        data = response.json()
        for r in data:
            assert r["effective_yellow"] == r["default_yellow"]
            assert r["effective_red"] == r["default_red"]

    async def test_reflects_override_thresholds(self, client, sample_store, auth_headers):
        """After creating an override, GET should reflect the new effective thresholds."""
        # Create override
        await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45, "red_threshold": 75},
            headers=auth_headers,
        )
        # Check
        response = await client.get(RULES_URL, headers=auth_headers)
        data = response.json()
        rule = next(r for r in data if r["rule_name"] == RULE_NAME)
        assert rule["has_override"] is True
        assert rule["effective_yellow"] == 45.0
        assert rule["effective_red"] == 75.0
        # Defaults unchanged
        assert rule["default_yellow"] == 60.0
        assert rule["default_red"] == 90.0

    async def test_nonexistent_store_returns_404(self, client, auth_headers):
        """GET for a nonexistent store returns 404."""
        response = await client.get(
            f"/api/v1/stores/{FAKE_STORE}/flag-rules", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_unauthenticated_blocked(self, client, sample_store):
        """GET without auth returns 401."""
        response = await client.get(RULES_URL)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestPutOverride:

    async def test_create_override(self, client, sample_store, auth_headers):
        """PUT creates a new override."""
        response = await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45, "red_threshold": 75},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rule_name"] == RULE_NAME
        assert data["yellow_threshold"] == 45.0
        assert data["red_threshold"] == 75.0
        assert data["enabled"] is True

    async def test_update_existing_override(self, client, sample_store, auth_headers):
        """PUT updates an existing override."""
        # Create
        await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45, "red_threshold": 75},
            headers=auth_headers,
        )
        # Update
        response = await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 50, "red_threshold": 100},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["yellow_threshold"] == 50.0
        assert data["red_threshold"] == 100.0

    async def test_disable_rule(self, client, sample_store, auth_headers):
        """PUT with enabled=False disables the rule."""
        response = await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"enabled": False},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    async def test_unknown_rule_returns_404(self, client, sample_store, auth_headers):
        """PUT with an unknown rule_name returns 404."""
        response = await client.put(
            f"{RULES_URL}/Nonexistent Rule",
            json={"yellow_threshold": 10},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_manager_cannot_put(self, client, sample_store, manager_user):
        """Manager role cannot create/update overrides."""
        headers = auth_header(manager_user)
        response = await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_unauthenticated_blocked(self, client, sample_store):
        """PUT without auth returns 401."""
        response = await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45},
        )
        assert response.status_code == 401

    async def test_gm_with_store_access_can_put(self, client, sample_store, gm_user):
        """GM with store access can create overrides."""
        headers = auth_header(gm_user)
        response = await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45, "red_threshold": 75},
            headers=headers,
        )
        assert response.status_code == 200


@pytest.mark.asyncio
class TestDeleteOverride:

    async def test_delete_override_reverts_to_defaults(self, client, sample_store, auth_headers):
        """DELETE removes override; GET shows defaults again."""
        # Create
        await client.put(
            f"{RULES_URL}/{RULE_NAME}",
            json={"yellow_threshold": 45, "red_threshold": 75},
            headers=auth_headers,
        )
        # Delete
        response = await client.delete(f"{RULES_URL}/{RULE_NAME}", headers=auth_headers)
        assert response.status_code == 200
        # Verify reverted
        get_response = await client.get(RULES_URL, headers=auth_headers)
        rule = next(r for r in get_response.json() if r["rule_name"] == RULE_NAME)
        assert rule["has_override"] is False
        assert rule["effective_yellow"] == rule["default_yellow"]
        assert rule["effective_red"] == rule["default_red"]

    async def test_delete_nonexistent_returns_404(self, client, sample_store, auth_headers):
        """DELETE when no override exists returns 404."""
        response = await client.delete(f"{RULES_URL}/{RULE_NAME}", headers=auth_headers)
        assert response.status_code == 404

    async def test_manager_cannot_delete(self, client, sample_store, manager_user):
        """Manager role cannot delete overrides."""
        headers = auth_header(manager_user)
        response = await client.delete(f"{RULES_URL}/{RULE_NAME}", headers=headers)
        assert response.status_code == 403

    async def test_unauthenticated_blocked(self, client, sample_store):
        """DELETE without auth returns 401."""
        response = await client.delete(f"{RULES_URL}/{RULE_NAME}")
        assert response.status_code == 401
