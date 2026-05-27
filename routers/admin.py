from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import User, Job, Application, Company
from dependencies import require_role
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role("admin"))
):
    """Get total counts for main entities."""
    total_users = await db.scalar(select(func.count()).select_from(User))
    total_jobs = await db.scalar(select(func.count()).select_from(Job))
    total_applications = await db.scalar(select(func.count()).select_from(Application))
    total_companies = await db.scalar(select(func.count()).select_from(Company))
    return {
        "total_users": total_users,
        "total_jobs": total_jobs,
        "total_applications": total_applications,
        "total_companies": total_companies,
    }

@router.get("/users")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role("admin"))
):
    """List all users with pagination."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]

@router.get("/jobs")
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role("admin"))
):
    """List all jobs with pagination."""
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).offset(skip).limit(limit)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "title": j.title,
            "company_id": str(j.company_id),
            "status": j.status,
            "location": j.location,
            "created_at": j.created_at,
        }
        for j in jobs
    ]