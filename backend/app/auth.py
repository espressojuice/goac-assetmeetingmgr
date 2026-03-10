"""Authentication utilities: JWT creation/validation and dependencies."""

import datetime
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole, UserStore

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, email: str, role: str) -> str:
    """Create a JWT access token."""
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=settings.JWT_EXPIRATION_HOURS
    )
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate the current user from JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency: optionally extract user (returns None if no token)."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_role(*roles: UserRole):
    """Dependency factory: require the current user to have one of the specified roles."""
    async def check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in roles]}",
            )
        return user
    return check_role


# ── Convenience role dependencies ─────────────────────────────────────


async def require_corporate(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require corporate role."""
    if current_user.role != UserRole.CORPORATE:
        raise HTTPException(status_code=403, detail="Corporate access required")
    return current_user


async def require_corporate_or_gm(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require corporate or GM role."""
    if current_user.role not in (UserRole.CORPORATE, UserRole.GM):
        raise HTTPException(status_code=403, detail="Corporate or GM access required")
    return current_user


# ── Store-scoped access helpers ───────────────────────────────────────


async def _user_has_store_access(
    user_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession
) -> bool:
    """Check if a user has an explicit UserStore association."""
    result = await db.execute(
        select(UserStore).where(
            UserStore.user_id == user_id,
            UserStore.store_id == store_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def verify_store_access(
    store_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify user has access to the specified store.

    Corporate: always pass.
    GM/Manager: must have UserStore association.
    """
    if current_user.role == UserRole.CORPORATE:
        return current_user

    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid store_id format")

    if not await _user_has_store_access(current_user.id, store_uuid, db):
        raise HTTPException(status_code=403, detail="You do not have access to this store")
    return current_user


async def get_user_store_ids(user: User, db: AsyncSession) -> list[uuid.UUID]:
    """Return list of store IDs the user can access. Corporate returns empty (meaning all)."""
    if user.role == UserRole.CORPORATE:
        return []  # empty = no filter needed
    result = await db.execute(
        select(UserStore.store_id).where(UserStore.user_id == user.id)
    )
    return list(result.scalars().all())
