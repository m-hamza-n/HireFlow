from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
from database import get_db
from models import User, RefreshToken, Candidate
from schemas import UserRegister, UserLogin, TokenResponse, RefreshRequest, AccessTokenResponse, MessageResponse
from auth import hash_password, verify_password, create_access_token, create_refresh_token
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check existing user
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed,
        role=user_data.role,
        full_name=user_data.full_name,
    )
    db.add(new_user)
    await db.flush()

    if user_data.role == "candidate":
        candidate = Candidate(user_id=new_user.id)
        db.add(candidate)

    refresh_token_str = create_refresh_token()
    refresh_expires = datetime.utcnow() + timedelta(days=7)
    db_refresh = RefreshToken(
        user_id=new_user.id,
        token=refresh_token_str,
        expires_at=refresh_expires
    )
    db.add(db_refresh)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")

    access_token = create_access_token(new_user.id, new_user.role)
    return {"access_token": access_token, "refresh_token": refresh_token_str}

@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User inactive")

    refresh_token_str = create_refresh_token()
    refresh_expires = datetime.utcnow() + timedelta(days=7)
    db_refresh = RefreshToken(
        user_id=user.id,
        token=refresh_token_str,
        expires_at=refresh_expires
    )
    db.add(db_refresh)
    await db.commit()

    access_token = create_access_token(user.id, user.role)
    return {"access_token": access_token, "refresh_token": refresh_token_str}

@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(refresh_data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_data.refresh_token,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one()
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User inactive")
    new_access = create_access_token(user.id, user.role)
    return {"access_token": new_access}

@router.post("/logout", response_model=MessageResponse)
async def logout(refresh_data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == refresh_data.refresh_token))
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
        await db.commit()
    return {"message": "Logged out"}