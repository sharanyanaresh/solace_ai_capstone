"""Authentication endpoints — researcher-only, JWT (access + refresh)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import RefreshToken, User
from ..schemas import AccessOut, LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    sha256,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> TokenOut:
    access, expires_in = create_access_token(user.id, user.email)
    refresh, refresh_hash, refresh_exp = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_exp))
    db.commit()
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if not settings.allow_open_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    exists = db.scalar(select(User).where(User.email == str(body.email)))
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=str(body.email),
        display_name=body.display_name or str(body.email).split("@")[0],
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email)))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=AccessOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    token_hash = sha256(body.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    if row is None or row.revoked_at is not None or _aware(row.expires_at) < now:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or unknown user")
    access, expires_in = create_access_token(user.id, user.email)
    return AccessOut(access_token=access, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    token_hash = sha256(body.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


def _aware(dt: datetime) -> datetime:
    """SQLite may return naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
