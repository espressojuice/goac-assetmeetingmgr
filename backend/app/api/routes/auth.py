"""Authentication routes: Google OAuth callback and token management."""

from __future__ import annotations

import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole

router = APIRouter()


class GoogleCallbackRequest(BaseModel):
    """Request from NextAuth after Google sign-in."""
    email: str
    name: str
    google_id: str
    avatar_url: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: str
    role: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    avatar_url: Optional[str] = None
    is_active: bool


@router.post("/auth/callback", response_model=AuthTokenResponse)
async def google_auth_callback(
    body: GoogleCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """
    Called by NextAuth after Google sign-in.
    Creates or updates the user in our DB and returns a backend JWT.
    """
    # Look up existing user by google_id or email
    result = await db.execute(
        select(User).where(
            (User.google_id == body.google_id) | (User.email == body.email)
        )
    )
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.name = body.name
        user.google_id = body.google_id
        if body.avatar_url:
            user.avatar_url = body.avatar_url
        user.last_login_at = datetime.datetime.now(ZoneInfo(settings.TIMEZONE))
    else:
        # Create new user
        user = User(
            email=body.email,
            name=body.name,
            google_id=body.google_id,
            avatar_url=body.avatar_url,
            role=UserRole.VIEWER,
            last_login_at=datetime.datetime.now(ZoneInfo(settings.TIMEZONE)),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
    )

    return AuthTokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
    )


@router.get("/auth/me", response_model=UserProfileResponse)
async def get_profile(user: User = Depends(get_current_user)) -> UserProfileResponse:
    """Get the current user's profile."""
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
    )
