"""Tests for authentication routes."""

import uuid

import pytest
import pytest_asyncio
from jose import jwt

from app.auth import create_access_token, decode_token
from app.config import settings
from app.models.user import User, UserRole


# --- Unit tests for JWT ---

class TestJWT:
    def test_create_and_decode_token(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "test@test.com", "viewer")
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["email"] == "test@test.com"
        assert payload["role"] == "viewer"

    def test_decode_invalid_token(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    def test_decode_wrong_secret(self):
        from fastapi import HTTPException
        token = jwt.encode({"sub": "123"}, "wrong-secret", algorithm="HS256")
        with pytest.raises(HTTPException):
            decode_token(token)


# --- API tests for auth callback ---

@pytest.mark.asyncio
class TestAuthCallback:
    async def test_callback_creates_new_user(self, client):
        resp = await client.post("/api/v1/auth/callback", json={
            "email": "newuser@test.com",
            "name": "New User",
            "google_id": "google-id-123",
            "avatar_url": "https://example.com/avatar.jpg",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@test.com"
        assert data["name"] == "New User"
        assert data["role"] == "viewer"
        assert "access_token" in data

    async def test_callback_updates_existing_user(self, client):
        # First call creates the user
        await client.post("/api/v1/auth/callback", json={
            "email": "existing@test.com",
            "name": "Original Name",
            "google_id": "google-id-456",
        })
        # Second call updates the user
        resp = await client.post("/api/v1/auth/callback", json={
            "email": "existing@test.com",
            "name": "Updated Name",
            "google_id": "google-id-456",
            "avatar_url": "https://example.com/new-avatar.jpg",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"

    async def test_callback_returns_valid_jwt(self, client):
        resp = await client.post("/api/v1/auth/callback", json={
            "email": "jwttest@test.com",
            "name": "JWT Test",
            "google_id": "google-id-jwt",
        })
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert payload["email"] == "jwttest@test.com"


@pytest.mark.asyncio
class TestAuthMe:
    async def test_me_with_valid_token(self, client, db_session):
        # Create user via callback
        resp = await client.post("/api/v1/auth/callback", json={
            "email": "me@test.com",
            "name": "Me User",
            "google_id": "google-me-123",
        })
        token = resp.json()["access_token"]

        # Call /auth/me
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["name"] == "Me User"
        assert data["role"] == "viewer"

    async def test_me_without_token(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, client):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401
